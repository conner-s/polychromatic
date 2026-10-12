# Polychromatic is licensed under the GPLv3.
"""
Button binding profiles for mice with programmable buttons.

A profile maps each physical button to an action on two layers: "standard",
and "hypershift" which applies while the Hypershift button is held. Profiles
are stored per device layout as JSON in the config directory.

Remapping happens at the Linux input-event level, not in device firmware:
each button is identified by the evdev code it sends ("source"), which a
remapping service would grab and re-emit. This module only stores and
describes the bindings; nothing here applies them to the device.
"""

import copy
import json
import os
import time

STANDARD = "standard"
HYPERSHIFT = "hypershift"

ACTION_TYPES = ["key", "mouse", "macro", "text", "media"]

MOUSE_BUTTONS = [
    ("BTN_LEFT", "Left click"),
    ("BTN_RIGHT", "Right click"),
    ("BTN_MIDDLE", "Middle click"),
    ("BTN_SIDE", "Back"),
    ("BTN_EXTRA", "Forward"),
    ("WHEEL_UP", "Scroll up"),
    ("WHEEL_DOWN", "Scroll down"),
    ("HWHEEL_LEFT", "Scroll left"),
    ("HWHEEL_RIGHT", "Scroll right"),
]

# (id, label, short label)
MEDIA_FUNCTIONS = [
    ("play", "Play / pause", "Play"),
    ("next", "Next track", "Next"),
    ("prev", "Previous track", "Prev"),
    ("vol_up", "Volume up", "Vol+"),
    ("vol_down", "Volume down", "Vol−"),
    ("mute", "Mute", "Mute"),
    ("dpi_up", "DPI stage up", "DPI+"),
    ("dpi_down", "DPI stage down", "DPI−"),
    ("dpi_cycle", "DPI stage cycle", "DPI"),
    ("profile_next", "Next profile", "Profile"),
    ("hypershift", "Hypershift (hold)", "Shift"),
]

REPEAT_MODES = [
    ("once", "Once"),
    ("held", "While held"),
    ("toggle", "Toggle on / off"),
]

KEY_LABELS = {
    "KEY_LEFTCTRL": "Ctrl", "KEY_RIGHTCTRL": "Ctrl",
    "KEY_LEFTSHIFT": "Shift", "KEY_RIGHTSHIFT": "Shift",
    "KEY_LEFTALT": "Alt", "KEY_RIGHTALT": "AltGr",
    "KEY_LEFTMETA": "Super", "KEY_RIGHTMETA": "Super",
    "KEY_MINUS": "-", "KEY_EQUAL": "=", "KEY_LEFTBRACE": "[", "KEY_RIGHTBRACE": "]",
    "KEY_SEMICOLON": ";", "KEY_APOSTROPHE": "'", "KEY_GRAVE": "`", "KEY_BACKSLASH": "\\",
    "KEY_COMMA": ",", "KEY_DOT": ".", "KEY_SLASH": "/",
    "KEY_SPACE": "Space", "KEY_ESC": "Esc", "KEY_ENTER": "Enter",
}

MODIFIER_KEYS = ["KEY_LEFTCTRL", "KEY_RIGHTCTRL", "KEY_LEFTSHIFT", "KEY_RIGHTSHIFT",
                 "KEY_LEFTALT", "KEY_RIGHTALT", "KEY_LEFTMETA", "KEY_RIGHTMETA"]


class Button(object):
    """
    A physical button on the device.

    source is the evdev code the button sends once the kernel driver has
    handled it, which is what an input-event remapper would intercept.
    """
    def __init__(self, uid, name, short, source, default):
        self.uid = uid
        self.name = name
        self.short = short
        self.source = source
        self.default = default


class DeviceLayout(object):
    """
    The programmable buttons of one device model.
    """
    def __init__(self, uid, name, buttons):
        self.uid = uid
        self.name = name
        self.buttons = buttons

    def get_button(self, uid):
        for button in self.buttons:
            if button.uid == uid:
                return button
        return None

    def factory(self):
        """
        Returns the standard layer as the device ships.
        """
        return {button.uid: copy.deepcopy(button.default) for button in self.buttons}


def _key(*keys):
    return {"type": "key", "keys": list(keys)}


def _mouse(button):
    return {"type": "mouse", "button": button}


def _media(function):
    return {"type": "media", "function": function}


def _naga_v3_layout():
    side_keys = ["KEY_1", "KEY_2", "KEY_3", "KEY_4", "KEY_5", "KEY_6",
                 "KEY_7", "KEY_8", "KEY_9", "KEY_0", "KEY_MINUS", "KEY_EQUAL"]
    buttons = []
    for index, code in enumerate(side_keys):
        number = str(index + 1)
        buttons.append(Button("s" + number, "Side " + number, number, code, _key(code)))

    # The driver turns wheel tilt and the DPI buttons into F13-F16 key events.
    # TODO: Confirm which codes the two top-left buttons send on the device.
    buttons += [
        Button("t1", "Top-left 1", "T1", "BTN_EXTRA", _mouse("BTN_EXTRA")),
        Button("t2", "Top-left 2", "T2", "BTN_SIDE", _mouse("BTN_SIDE")),
        Button("mid", "Middle click", "M", "BTN_MIDDLE", _mouse("BTN_MIDDLE")),
        Button("tl", "Tilt left", "‹", "KEY_F15", _mouse("HWHEEL_LEFT")),
        Button("tr", "Tilt right", "›", "KEY_F16", _mouse("HWHEEL_RIGHT")),
        Button("b1", "Below wheel 1", "W1", "KEY_F13", _media("dpi_up")),
        Button("b2", "Below wheel 2", "W2", "KEY_F14", _media("dpi_down")),
    ]
    return DeviceLayout("naga-v3", "Razer Naga V3", buttons)


def get_layout(device_name):
    """
    Returns the DeviceLayout for a device, or None if button bindings are
    not supported for it.
    """
    if "Naga V3" in device_name:
        return _naga_v3_layout()
    return None


def key_label(code):
    return KEY_LABELS.get(code, code.replace("KEY_", "", 1))


def _lookup(table, uid, column):
    for row in table:
        if row[0] == uid:
            return row[column]
    return uid


def short_text(binding):
    """
    A few characters for the button face in the schematic.
    """
    if not binding:
        return "—"
    kind = binding["type"]
    if kind == "key":
        return "+".join(key_label(k) for k in binding["keys"]) if binding["keys"] else "—"
    if kind == "mouse":
        return _lookup(MOUSE_BUTTONS, binding["button"], 1)
    if kind == "media":
        return _lookup(MEDIA_FUNCTIONS, binding["function"], 2)
    if kind == "macro":
        return "Macro"
    return "Text"


def describe(binding):
    """
    A sentence-length description of a binding.
    """
    if not binding:
        return "Not bound"
    kind = binding["type"]
    if kind == "key":
        if not binding["keys"]:
            return "Key: not set"
        return "Key: " + " + ".join(key_label(k) for k in binding["keys"])
    if kind == "mouse":
        return "Mouse: " + short_text(binding)
    if kind == "media":
        return _lookup(MEDIA_FUNCTIONS, binding["function"], 1)
    if kind == "macro":
        return "Macro: {0} ({1} steps)".format(binding["name"], len(binding["steps"]))
    return "Text: \"{0}\"".format(binding["text"])


def signature(binding):
    """
    Returns a value that is equal for two bindings producing the same output,
    or None when the binding produces nothing yet.
    """
    if not binding:
        return None
    kind = binding["type"]
    if kind == "key":
        return "key:" + "+".join(binding["keys"]) if binding["keys"] else None
    if kind == "mouse":
        return "mouse:" + binding["button"]
    if kind == "media":
        return "media:" + binding["function"]
    if kind == "macro":
        return "macro:" + binding["name"]
    return "text:" + binding["text"] if binding["text"] else None


def new_binding(kind):
    """
    Returns an empty binding for an action type.
    """
    return {
        "key": {"type": "key", "keys": []},
        "mouse": _mouse("BTN_SIDE"),
        "macro": {"type": "macro", "name": "New macro", "repeat": "once", "steps": []},
        "text": {"type": "text", "text": ""},
        "media": _media("play"),
    }[kind]


def is_hypershift(binding):
    return bool(binding) and binding["type"] == "media" and binding["function"] == "hypershift"


def new_profile(layout, name):
    return {
        "id": "p" + str(int(time.time() * 1000)),
        "name": name,
        STANDARD: layout.factory(),
        HYPERSHIFT: {},
    }


def clone_profile(profile, name):
    clone = copy.deepcopy(profile)
    clone["id"] = "p" + str(int(time.time() * 1000))
    clone["name"] = name
    return clone


def get_hypershift_key(profile):
    """
    Returns the ID of the button that holds the Hypershift layer, or None.
    """
    for uid, binding in profile[STANDARD].items():
        if is_hypershift(binding):
            return uid
    return None


def set_hypershift_key(layout, profile, uid):
    """
    Make a button the Hypershift key, or pass None to remove the layer key.
    The previous key goes back to its factory binding.
    """
    previous = get_hypershift_key(profile)
    if previous:
        profile[STANDARD][previous] = copy.deepcopy(layout.get_button(previous).default)
    if uid:
        profile[STANDARD][uid] = _media("hypershift")
        profile[HYPERSHIFT].pop(uid, None)


def set_binding(layout, profile, layer, uid, binding):
    """
    Bind (or with None, unbind) a button on a layer. Only one button can be the
    Hypershift key, and that button cannot have a Hypershift binding itself.
    """
    if layer == STANDARD and is_hypershift(binding):
        set_hypershift_key(layout, profile, uid)
        return

    if binding is None:
        profile[layer].pop(uid, None)
    else:
        profile[layer][uid] = binding


def is_remapped(layout, profile, layer, uid):
    binding = profile[layer].get(uid)
    if layer == HYPERSHIFT:
        return binding is not None
    return binding != layout.get_button(uid).default


def find_conflicts(layout, profile, layer):
    """
    Returns {button ID: [other button IDs with the same output]} for every
    button on the layer that shares its output with another.
    """
    trigger = get_hypershift_key(profile) if layer == HYPERSHIFT else None
    groups = {}
    for button in layout.buttons:
        if button.uid == trigger:
            continue
        sig = signature(profile[layer].get(button.uid))
        if sig:
            groups.setdefault(sig, []).append(button.uid)

    conflicts = {}
    for uids in groups.values():
        if len(uids) < 2:
            continue
        for uid in uids:
            conflicts[uid] = [other for other in uids if other != uid]
    return conflicts


class ProfileStore(object):
    """
    Loads and saves the binding profiles for one device layout.
    """
    def __init__(self, folder, layout):
        self.layout = layout
        self.path = os.path.join(folder, layout.uid + ".json")
        self.profiles = []
        self.active_id = None
        self.load()

    def load(self):
        data = {}
        if os.path.exists(self.path):
            try:
                with open(self.path, "r") as f:
                    data = json.load(f)
            except (OSError, ValueError):
                data = {}

        self.profiles = data.get("profiles", [])
        if not self.profiles:
            self.profiles = [new_profile(self.layout, "Default")]
            self.profiles[0]["id"] = "default"

        self.active_id = data.get("active")
        if not self.get(self.active_id):
            self.active_id = self.profiles[0]["id"]

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as f:
            json.dump({"active": self.active_id, "profiles": self.profiles}, f, indent=4)

    def get(self, profile_id):
        for profile in self.profiles:
            if profile["id"] == profile_id:
                return profile
        return None

    @property
    def active(self):
        return self.get(self.active_id)

    def add(self, profile):
        self.profiles.append(profile)
        self.active_id = profile["id"]
        self.save()

    def delete(self, profile_id):
        """
        Remove a profile. Returns False if it is the last one.
        """
        if len(self.profiles) < 2:
            return False
        self.profiles = [p for p in self.profiles if p["id"] != profile_id]
        if self.active_id == profile_id:
            self.active_id = self.profiles[0]["id"]
        self.save()
        return True

    def import_file(self, path):
        """
        Add a profile from a JSON file exported from another store.
        Raises ValueError if the file is not a profile.
        """
        with open(path, "r") as f:
            data = json.load(f)
        if not isinstance(data, dict) or STANDARD not in data or "name" not in data:
            raise ValueError("Not a button profile")
        data.setdefault(HYPERSHIFT, {})
        profile = clone_profile(data, data["name"])
        self.add(profile)
        return profile
