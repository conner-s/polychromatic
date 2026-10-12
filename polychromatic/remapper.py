# Polychromatic is licensed under the GPLv3.
"""
Applies button binding profiles by remapping input events.

The kernel driver does not store button mappings on the device, so this works
at the Linux input-event level, like input-remapper. BindingService grabs the
evdev nodes of a supported mouse so the desktop stops reading them, passes
ordinary events (motion, clicks, scrolling) through a virtual clone of each
node, and hands every press of a bound button to Remapper. Remapper looks up
the active profile and sends the result through virtual uinput devices.

Remapper only talks to an output object, so it can be tested without evdev.
Ending the process releases the grabs, which returns the mouse to normal.
"""

import os
import select
import threading
import time

from . import bindings

try:
    import evdev
    from evdev import ecodes
except ImportError:
    evdev = None

PRESS = 1
RELEASE = 0
REPEAT = 2

MEDIA_KEYS = {
    "play": "KEY_PLAYPAUSE",
    "next": "KEY_NEXTSONG",
    "prev": "KEY_PREVIOUSSONG",
    "vol_up": "KEY_VOLUMEUP",
    "vol_down": "KEY_VOLUMEDOWN",
    "mute": "KEY_MUTE",
}

# Mouse actions that scroll instead of pressing a button: (axis, direction)
SCROLL = {
    "WHEEL_UP": ("REL_WHEEL", 1),
    "WHEEL_DOWN": ("REL_WHEEL", -1),
    "HWHEEL_LEFT": ("REL_HWHEEL", -1),
    "HWHEEL_RIGHT": ("REL_HWHEEL", 1),
}

# Seconds between the events of a macro or text, so applications keep up.
STEP_GAP = 0.002

# Typing text assumes a US keyboard layout.
_PLAIN_CHARS = {
    " ": "SPACE", "\n": "ENTER", "\t": "TAB", "-": "MINUS", "=": "EQUAL",
    "[": "LEFTBRACE", "]": "RIGHTBRACE", "\\": "BACKSLASH", ";": "SEMICOLON",
    "'": "APOSTROPHE", "`": "GRAVE", ",": "COMMA", ".": "DOT", "/": "SLASH",
}
_SHIFTED_CHARS = {
    "!": "1", "@": "2", "#": "3", "$": "4", "%": "5", "^": "6", "&": "7",
    "*": "8", "(": "9", ")": "0", "_": "MINUS", "+": "EQUAL", "{": "LEFTBRACE",
    "}": "RIGHTBRACE", "|": "BACKSLASH", ":": "SEMICOLON", "\"": "APOSTROPHE",
    "~": "GRAVE", "<": "COMMA", ">": "DOT", "?": "SLASH",
}


def char_key(char):
    """
    Returns (key, shifted) to type a character, or None if it cannot be typed.
    """
    if char.isascii() and char.isalpha():
        return "KEY_" + char.upper(), char.isupper()
    if char.isascii() and char.isdigit():
        return "KEY_" + char, False
    if char in _PLAIN_CHARS:
        return "KEY_" + _PLAIN_CHARS[char], False
    if char in _SHIFTED_CHARS:
        return "KEY_" + _SHIFTED_CHARS[char], True
    return None


def text_steps(text):
    """
    Converts text to macro steps. Characters that cannot be typed are skipped.
    """
    steps = []
    for char in text:
        typed = char_key(char)
        if not typed:
            continue
        key, shifted = typed
        if shifted:
            steps.append({"event": "press", "key": "KEY_LEFTSHIFT"})
        steps.append({"event": "press", "key": key})
        steps.append({"event": "release", "key": key})
        if shifted:
            steps.append({"event": "release", "key": "KEY_LEFTSHIFT"})
    return steps


class MacroRunner(threading.Thread):
    """
    Plays macro steps once, or repeatedly until stopped. Keys the macro still
    holds down when it stops are released.
    """
    def __init__(self, output, steps, loop):
        super().__init__(daemon=True)
        self.output = output
        self.steps = steps
        self.loop = loop
        self.stopping = threading.Event()
        self.pressed = []

    def run(self):
        while not self.stopping.is_set():
            for step in self.steps:
                if self.stopping.is_set():
                    break
                if step["event"] == "delay":
                    self.stopping.wait(step["ms"] / 1000)
                    continue
                pressed = step["event"] == "press"
                self.output.key(step["key"], PRESS if pressed else RELEASE)
                self.output.sync()
                if pressed:
                    self.pressed.append(step["key"])
                elif step["key"] in self.pressed:
                    self.pressed.remove(step["key"])
                self.stopping.wait(STEP_GAP)
            if not self.loop:
                break
            # A loop without delays would flood the desktop with events.
            self.stopping.wait(0.01)

        for key in reversed(self.pressed):
            self.output.key(key, RELEASE)
        self.output.sync()

    def stop(self):
        self.stopping.set()


class Remapper(object):
    """
    Turns presses of a layout's buttons into the actions bound to them.

    output needs key(name, value), scroll(axis, steps) and sync().
    device_action(function) is called for media functions that act on the
    device or the profiles, such as DPI stages.
    """
    def __init__(self, layout, profile, output, device_action=None):
        self.layout = layout
        self.profile = profile
        self.output = output
        self.device_action = device_action or (lambda function: None)
        self.sources = {button.source: button for button in layout.buttons}
        self.shift_held = False
        # Each held button keeps the binding it was pressed with, so changing
        # layer or profile mid-press still releases what it pressed.
        self.held = {}
        self.macros = {}

    def set_profile(self, profile):
        self.profile = profile

    def handles(self, source):
        return source in self.sources

    def button_event(self, source, value):
        uid = self.sources[source].uid
        if value == PRESS:
            binding = self._binding_for(uid)
            self.held[uid] = binding
            self._press(uid, binding)
        elif value == REPEAT:
            binding = self.held.get(uid)
            if binding and binding["type"] == "mouse" and binding["button"] in SCROLL:
                self._scroll(binding["button"])
        elif value == RELEASE:
            self._release(uid, self.held.pop(uid, None))

    def stop(self):
        """
        Release everything held, for when the device goes away.
        """
        for uid in list(self.held):
            self._release(uid, self.held.pop(uid))
        for runner in self.macros.values():
            runner.stop()

    def _binding_for(self, uid):
        standard = self.profile[bindings.STANDARD].get(uid)
        if self.shift_held and not bindings.is_hypershift(standard):
            return self.profile[bindings.HYPERSHIFT].get(uid)
        return standard

    def _press(self, uid, binding):
        if not binding:
            return
        kind = binding["type"]

        if kind == "key":
            for key in binding["keys"]:
                self.output.key(key, PRESS)
            self.output.sync()

        elif kind == "mouse":
            if binding["button"] in SCROLL:
                self._scroll(binding["button"])
            else:
                self.output.key(binding["button"], PRESS)
                self.output.sync()

        elif kind == "media":
            function = binding["function"]
            if function == "hypershift":
                self.shift_held = True
            elif function in MEDIA_KEYS:
                self.output.key(MEDIA_KEYS[function], PRESS)
                self.output.sync()
            else:
                self.device_action(function)

        elif kind == "text":
            self._start_macro(uid, text_steps(binding["text"]), loop=False)

        elif kind == "macro":
            repeat = binding.get("repeat", "once")
            running = self.macros.get(uid)
            if repeat == "toggle" and running and running.is_alive():
                running.stop()
                return
            self._start_macro(uid, binding["steps"], loop=repeat != "once")

    def _release(self, uid, binding):
        if not binding:
            return
        kind = binding["type"]

        if kind == "key":
            for key in reversed(binding["keys"]):
                self.output.key(key, RELEASE)
            self.output.sync()

        elif kind == "mouse":
            if binding["button"] not in SCROLL:
                self.output.key(binding["button"], RELEASE)
                self.output.sync()

        elif kind == "media":
            function = binding["function"]
            if function == "hypershift":
                self.shift_held = False
            elif function in MEDIA_KEYS:
                self.output.key(MEDIA_KEYS[function], RELEASE)
                self.output.sync()

        elif kind == "macro" and binding.get("repeat") == "held":
            runner = self.macros.get(uid)
            if runner:
                runner.stop()

    def _scroll(self, name):
        axis, steps = SCROLL[name]
        self.output.scroll(axis, steps)
        self.output.sync()

    def _start_macro(self, uid, steps, loop):
        running = self.macros.get(uid)
        if running and running.is_alive():
            return
        runner = MacroRunner(self.output, steps, loop)
        self.macros[uid] = runner
        runner.start()


if evdev:
    class _UInput(evdev.UInput):
        """
        A uinput device that does not open its own event node afterwards. The
        service writes to its devices but needs no read access to /dev/input,
        and without it python-evdev waits two seconds and then fails.
        """
        def _find_device(self, fd):
            return None


class UinputOutput(object):
    """
    Two virtual devices for remapped actions: a keyboard, and a mouse for
    buttons and scrolling. Safe to use from macro threads.
    """
    def __init__(self):
        key_codes = list(range(ecodes.KEY_ESC, ecodes.KEY_MICMUTE + 1))
        self.keyboard = _UInput({ecodes.EV_KEY: key_codes}, name="Polychromatic Bindings Keyboard")
        self.mouse = _UInput({
            ecodes.EV_KEY: list(range(ecodes.BTN_LEFT, ecodes.BTN_TASK + 1)),
            ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y, ecodes.REL_WHEEL, ecodes.REL_HWHEEL,
                            ecodes.REL_WHEEL_HI_RES, ecodes.REL_HWHEEL_HI_RES],
        }, name="Polychromatic Bindings Mouse")
        self.lock = threading.Lock()
        self.pending = set()

    def key(self, name, value):
        code = ecodes.ecodes.get(name)
        if code is None:
            return
        device = self.mouse if name.startswith("BTN_") else self.keyboard
        with self.lock:
            device.write(ecodes.EV_KEY, code, value)
            self.pending.add(device)

    def scroll(self, axis, steps):
        with self.lock:
            self.mouse.write(ecodes.EV_REL, ecodes.ecodes[axis], steps)
            self.mouse.write(ecodes.EV_REL, ecodes.ecodes[axis + "_HI_RES"], steps * 120)
            self.pending.add(self.mouse)

    def sync(self):
        with self.lock:
            for device in self.pending:
                device.syn()
            self.pending.clear()

    def close(self):
        self.keyboard.close()
        self.mouse.close()


class _Source(object):
    """
    A grabbed evdev node and the clone that passes its other events through.
    """
    def __init__(self, device, clone, group):
        self.device = device
        self.clone = clone
        self.group = group


class _Group(object):
    """
    The profiles and remapper shared by every node of one device layout.
    """
    def __init__(self, folder, layout, output, dbg):
        self.layout = layout
        self.dbg = dbg
        self.store = bindings.ProfileStore(folder, layout)
        self.mtime = self._mtime()
        self.codes = {ecodes.ecodes[b.source]: b.source for b in layout.buttons}
        self.remapper = Remapper(layout, self.store.active, output, self.device_action)

    def _mtime(self):
        try:
            return os.stat(self.store.path).st_mtime_ns
        except OSError:
            return None

    def reload_if_changed(self, force=False):
        mtime = self._mtime()
        if mtime == self.mtime and not force:
            return
        self.mtime = mtime
        self.store.load()
        self.remapper.set_profile(self.store.active)
        self.dbg.stdout("{0}: Using profile '{1}'".format(self.layout.name, self.store.active["name"]), self.dbg.action, 1)

    def device_action(self, function):
        if function == "profile_next":
            ids = [profile["id"] for profile in self.store.profiles]
            self.store.active_id = ids[(ids.index(self.store.active_id) + 1) % len(ids)]
            self.store.save()
            self.reload_if_changed(force=True)
        elif function in ("dpi_up", "dpi_down", "dpi_cycle"):
            # D-Bus calls are slow enough to delay the next input events.
            threading.Thread(target=step_dpi, args=(self.layout, function, self.dbg), daemon=True).start()


def step_dpi(layout, function, dbg):
    """
    Move the device's active DPI stage through OpenRazer.
    """
    try:
        from openrazer.client import DeviceManager
        devices = DeviceManager().devices
    except Exception as e:
        dbg.stdout("Cannot change DPI, OpenRazer is unavailable: " + str(e), dbg.error)
        return

    for device in devices:
        device_layout = bindings.get_layout(device.name)
        if not device_layout or device_layout.uid != layout.uid or not device.has("dpi_stages"):
            continue
        active, stages = device.dpi_stages
        if function == "dpi_up":
            active = min(active + 1, len(stages))
        elif function == "dpi_down":
            active = max(active - 1, 1)
        else:
            active = active % len(stages) + 1
        device.dpi_stages = (active, stages)
        dbg.stdout("{0}: DPI stage {1} of {2}".format(device.name, active, len(stages)), dbg.action, 1)


def _is_virtual(path):
    """
    Whether an evdev node was created through uinput, including the clones
    made here, which share the real device's name.
    """
    name = os.path.basename(path)
    return "/virtual/" in os.path.realpath("/sys/class/input/{0}/device".format(name))


def _device_name(path):
    try:
        with open("/sys/class/input/{0}/device/name".format(os.path.basename(path))) as f:
            return f.read().strip()
    except OSError:
        return ""


class BindingService(object):
    """
    Finds supported devices as they are connected, grabs them and applies the
    active profile of their layout until the process ends.
    """
    SCAN_INTERVAL = 2
    POLL_INTERVAL = 0.5

    def __init__(self, folder, dbg):
        self.folder = folder
        self.dbg = dbg
        self.output = None
        self.sources = {}
        self.groups = {}
        self.reload_requested = False

    def run(self):
        last_scan = 0
        while True:
            if time.monotonic() - last_scan > self.SCAN_INTERVAL:
                self._scan()
                last_scan = time.monotonic()

            for group in self.groups.values():
                group.reload_if_changed(force=self.reload_requested)
            self.reload_requested = False

            ready = select.select(list(self.sources), [], [], self.POLL_INTERVAL)[0]
            for fd in ready:
                self._read(fd)

    def _scan(self):
        attached = {source.device.path for source in self.sources.values()}
        for path in evdev.list_devices():
            if path in attached or _is_virtual(path):
                continue
            layout = bindings.get_layout(_device_name(path))
            if layout:
                self._attach(path, layout)

    def _attach(self, path, layout):
        try:
            device = evdev.InputDevice(path)
            clone = _UInput.from_device(device, name=device.name, vendor=device.info.vendor,
                                       product=device.info.product, version=device.info.version)
            device.grab()
        except OSError as e:
            self.dbg.stdout("{0}: Cannot grab {1}: {2}".format(layout.name, path, e), self.dbg.error)
            return

        if self.output is None:
            self.output = UinputOutput()
        if layout.uid not in self.groups:
            self.groups[layout.uid] = _Group(self.folder, layout, self.output, self.dbg)

        self.sources[device.fd] = _Source(device, clone, self.groups[layout.uid])
        self.dbg.stdout("{0}: Remapping {1}".format(device.name, path), self.dbg.success, 1)

    def _detach(self, fd):
        source = self.sources.pop(fd)
        self.dbg.stdout("{0}: Disconnected {1}".format(source.device.name, source.device.path), self.dbg.action, 1)
        if not any(other.group is source.group for other in self.sources.values()):
            source.group.remapper.stop()
        for closing in (source.clone, source.device):
            try:
                closing.close()
            except OSError:
                pass

    def _read(self, fd):
        source = self.sources[fd]
        try:
            events = source.device.read()
        except OSError:
            self._detach(fd)
            return

        group = source.group
        for event in events:
            try:
                if event.type == ecodes.EV_KEY and event.code in group.codes:
                    group.remapper.button_event(group.codes[event.code], event.value)
                elif event.type == ecodes.EV_MSC and event.code == ecodes.MSC_SCAN:
                    # Scan codes describe the physical key, so they would
                    # contradict a remapped one.
                    continue
                else:
                    source.clone.write_event(event)
            except Exception as e:
                self.dbg.stdout("Failed to handle {0}: {1}".format(event, e), self.dbg.error)
