# Polychromatic is licensed under the GPLv3.
"""
The "Buttons" group on the device page, for editing button binding profiles.

Split layout: the button schematics on the left, the selected button's
binding on the right. Profiles are listed in the device sidebar
(see DevicesTab in devices.py).
"""

import copy
import time

from PyQt6.QtCore import QEvent, QObject, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (QAbstractItemView, QApplication, QButtonGroup,
                             QComboBox, QFrame, QGridLayout, QHBoxLayout,
                             QHeaderView, QLabel, QLineEdit, QPushButton,
                             QSizePolicy, QTableWidget, QTableWidgetItem,
                             QToolButton, QVBoxLayout, QWidget)

from .. import bindings, procpid
from ..qt.flowlayout import FlowLayout as QFlowLayout
from . import shared

STYLE = """
QToolButton#BindingKey { padding: 0; }
QToolButton#BindingKey[binding="remapped"] { background-color: #008000; color: #fff; }
QToolButton#BindingKey[binding="unbound"] { background-color: #000; color: #828282; }
QToolButton#BindingKey[conflict="true"] { border-color: #ffa500; }
QToolButton#BindingKey[editing="true"] { border-color: #00FF00; }
QFrame#BindingSideGrid { background-color: #0d0d0d; border: 2px solid #2D2D2D; border-radius: 28px; }
QLabel#BindingWarning { color: #ffa500; }
QLabel#BindingMuted { color: #828282; }
QLineEdit#BindingCombo { font-family: monospace; }
"""

# evdev key codes (linux/input-event-codes.h). Qt's native scan code on
# Linux is the evdev code + 8.
EVDEV_KEYS = {
    1: "KEY_ESC", 2: "KEY_1", 3: "KEY_2", 4: "KEY_3", 5: "KEY_4", 6: "KEY_5",
    7: "KEY_6", 8: "KEY_7", 9: "KEY_8", 10: "KEY_9", 11: "KEY_0", 12: "KEY_MINUS",
    13: "KEY_EQUAL", 14: "KEY_BACKSPACE", 15: "KEY_TAB", 16: "KEY_Q", 17: "KEY_W",
    18: "KEY_E", 19: "KEY_R", 20: "KEY_T", 21: "KEY_Y", 22: "KEY_U", 23: "KEY_I",
    24: "KEY_O", 25: "KEY_P", 26: "KEY_LEFTBRACE", 27: "KEY_RIGHTBRACE",
    28: "KEY_ENTER", 29: "KEY_LEFTCTRL", 30: "KEY_A", 31: "KEY_S", 32: "KEY_D",
    33: "KEY_F", 34: "KEY_G", 35: "KEY_H", 36: "KEY_J", 37: "KEY_K", 38: "KEY_L",
    39: "KEY_SEMICOLON", 40: "KEY_APOSTROPHE", 41: "KEY_GRAVE", 42: "KEY_LEFTSHIFT",
    43: "KEY_BACKSLASH", 44: "KEY_Z", 45: "KEY_X", 46: "KEY_C", 47: "KEY_V",
    48: "KEY_B", 49: "KEY_N", 50: "KEY_M", 51: "KEY_COMMA", 52: "KEY_DOT",
    53: "KEY_SLASH", 54: "KEY_RIGHTSHIFT", 55: "KEY_KPASTERISK", 56: "KEY_LEFTALT",
    57: "KEY_SPACE", 58: "KEY_CAPSLOCK", 59: "KEY_F1", 60: "KEY_F2", 61: "KEY_F3",
    62: "KEY_F4", 63: "KEY_F5", 64: "KEY_F6", 65: "KEY_F7", 66: "KEY_F8",
    67: "KEY_F9", 68: "KEY_F10", 69: "KEY_NUMLOCK", 70: "KEY_SCROLLLOCK",
    71: "KEY_KP7", 72: "KEY_KP8", 73: "KEY_KP9", 74: "KEY_KPMINUS", 75: "KEY_KP4",
    76: "KEY_KP5", 77: "KEY_KP6", 78: "KEY_KPPLUS", 79: "KEY_KP1", 80: "KEY_KP2",
    81: "KEY_KP3", 82: "KEY_KP0", 83: "KEY_KPDOT", 86: "KEY_102ND", 87: "KEY_F11",
    88: "KEY_F12", 96: "KEY_KPENTER", 97: "KEY_RIGHTCTRL", 98: "KEY_KPSLASH",
    99: "KEY_SYSRQ", 100: "KEY_RIGHTALT", 102: "KEY_HOME", 103: "KEY_UP",
    104: "KEY_PAGEUP", 105: "KEY_LEFT", 106: "KEY_RIGHT", 107: "KEY_END",
    108: "KEY_DOWN", 109: "KEY_PAGEDOWN", 110: "KEY_INSERT", 111: "KEY_DELETE",
    113: "KEY_MUTE", 114: "KEY_VOLUMEDOWN", 115: "KEY_VOLUMEUP", 119: "KEY_PAUSE",
    125: "KEY_LEFTMETA", 126: "KEY_RIGHTMETA", 127: "KEY_COMPOSE",
    163: "KEY_NEXTSONG", 164: "KEY_PLAYPAUSE", 165: "KEY_PREVIOUSSONG",
}
EVDEV_KEYS.update({183 + i: "KEY_F" + str(13 + i) for i in range(12)})

QT_MODIFIERS = [
    (Qt.KeyboardModifier.ControlModifier, "KEY_LEFTCTRL"),
    (Qt.KeyboardModifier.ShiftModifier, "KEY_LEFTSHIFT"),
    (Qt.KeyboardModifier.AltModifier, "KEY_LEFTALT"),
    (Qt.KeyboardModifier.MetaModifier, "KEY_LEFTMETA"),
]


def clear_now(layout):
    """
    Like shared.clear_layout(), but hides the old widgets straight away so
    they don't linger on screen until the deferred delete.
    """
    while layout.count():
        child = layout.takeAt(0)
        if child.widget():
            child.widget().hide()
            child.widget().deleteLater()


def evdev_name(event):
    """
    Returns the evdev name (e.g. KEY_A) for a QKeyEvent, or None.
    """
    name = EVDEV_KEYS.get(event.nativeScanCode() - 8)
    if name:
        return name

    # Not running on Linux, or an unlisted key: fall back to the Qt key.
    key = event.key()
    if Qt.Key.Key_0.value <= key <= Qt.Key.Key_9.value or Qt.Key.Key_A.value <= key <= Qt.Key.Key_Z.value:
        return "KEY_" + chr(key)
    return None


class KeyGrabber(QObject):
    """
    Intercepts every key press and release in the application while active,
    so the keys can be captured as a binding instead of acting on the UI.
    """
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.active = False

    def start(self):
        if not self.active:
            QApplication.instance().installEventFilter(self)
            self.active = True

    def stop(self):
        if self.active:
            QApplication.instance().removeEventFilter(self)
            self.active = False

    def eventFilter(self, obj, event):
        if event.type() not in [QEvent.Type.KeyPress, QEvent.Type.KeyRelease]:
            return False
        if not event.isAutoRepeat():
            self.callback(event, event.type() == QEvent.Type.KeyPress)
        return True


class TopView(QWidget):
    """
    Outline of the mouse seen from above, with the top buttons placed on it.
    """
    def __init__(self):
        super().__init__()
        self.setFixedSize(200, 300)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#2D2D2D"), 2)
        painter.setPen(pen)

        body = QPainterPath()
        body.addRoundedRect(QRectF(1, 1, 198, 298), 90, 110)
        painter.fillPath(body, QColor("#0d0d0d"))
        painter.drawPath(body)

        painter.setPen(QColor("#575757"))
        painter.drawText(QRectF(14, 130, 58, 20), Qt.AlignmentFlag.AlignCenter, "L")
        painter.drawText(QRectF(128, 130, 58, 20), Qt.AlignmentFlag.AlignCenter, "R")

        painter.setPen(pen)
        painter.drawLine(100, 14, 100, 30)
        painter.drawLine(100, 140, 100, 156)
        painter.drawLine(14, 156, 186, 156)


# Placement of the top buttons on TopView: (x, y, width, height)
TOP_GEOMETRY = {
    "t1": (20, 58, 22, 30),
    "t2": (20, 94, 22, 30),
    "tl": (70, 38, 18, 34),
    "mid": (90, 30, 20, 50),
    "tr": (112, 38, 18, 34),
    "b1": (86, 90, 28, 22),
    "b2": (86, 116, 28, 22),
    "rf": (166, 168, 24, 36),
}


class ButtonBindings(shared.TabData):
    """
    Builds and manages the "Buttons" group for one device.
    """
    def __init__(self, appdata, layout: bindings.DeviceLayout, store: bindings.ProfileStore):
        super().__init__(appdata)
        self.layout = layout
        self.store = store

        self.layer = bindings.STANDARD
        self.selected = layout.buttons[0].uid
        self.capturing = False
        self.capture_preview = ""
        self.recording = False
        self.last_step_time = None
        self.step_selected = 0
        self.grabber = KeyGrabber(self._key_event)
        self.key_buttons = {}

        self.widget = self.widgets.create_group_widget(self._("Buttons"))
        self.widget.setStyleSheet(STYLE)
        self.widget.destroyed.connect(self.grabber.stop)

        # Layer and Hypershift key rows span the full width
        self.layer_row = QWidget()
        self.layer_row.setLayout(QVBoxLayout())
        self.layer_row.layout().setContentsMargins(0, 0, 0, 0)
        self.widget.layout().addWidget(self.layer_row)

        # Split: schematics on the left, editor on the right
        split = QWidget()
        split.setLayout(QHBoxLayout())
        split.layout().setContentsMargins(30, 10, 30, 6)
        split.layout().setSpacing(28)
        split.layout().addWidget(self._create_diagrams(), 0, Qt.AlignmentFlag.AlignTop)

        self.editor = QWidget()
        self.editor.setLayout(QVBoxLayout())
        self.editor.layout().setContentsMargins(0, 0, 0, 0)
        self.editor.layout().setSpacing(0)
        self.editor.layout().setAlignment(Qt.AlignmentFlag.AlignTop)
        self.editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        split.layout().addWidget(self.editor, 1)
        self.widget.layout().addWidget(split)

        self.status = QLabel()
        self.status.setObjectName("BindingMuted")
        self.status.setContentsMargins(30, 4, 30, 0)
        self.status.setWordWrap(True)
        self.widget.layout().addWidget(self.status)

        self.refresh()

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------
    @property
    def profile(self):
        return self.store.active

    def _current_layer(self):
        if self.layer == bindings.HYPERSHIFT and bindings.get_hypershift_key(self.profile):
            return bindings.HYPERSHIFT
        return bindings.STANDARD

    def _current_binding(self):
        return self.profile[self._current_layer()].get(self.selected)

    def _stop_input(self):
        self.capturing = False
        self.capture_preview = ""
        self.recording = False
        self.grabber.stop()

    def _commit(self, binding, rebuild=True):
        """
        Store a binding for the selected button, save and redraw. Without
        rebuild, the editor is left alone so a text field keeps its focus.
        """
        bindings.set_binding(self.layout, self.profile, self._current_layer(), self.selected, binding)
        self.store.save()
        if rebuild:
            self.refresh()
        else:
            self._refresh_summary()

    def _patch(self, rebuild=True, **changes):
        binding = copy.deepcopy(self._current_binding())
        binding.update(changes)
        self._commit(binding, rebuild)

    def set_profile(self, profile_id):
        self._stop_input()
        self.store.active_id = profile_id
        self.store.save()
        self.layer = bindings.STANDARD
        self.refresh()

    def select(self, uid):
        self._stop_input()
        self.selected = uid
        self.step_selected = 0
        self.refresh()

    # ------------------------------------------------------------------
    # Schematics
    # ------------------------------------------------------------------
    def _make_key_button(self, button: bindings.Button):
        key = QToolButton()
        key.setObjectName("BindingKey")
        key.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        key.clicked.connect(lambda: self.select(button.uid))
        self.key_buttons[button.uid] = key
        return key

    def _create_diagrams(self):
        column = QWidget()
        column.setLayout(QVBoxLayout())
        column.layout().setContentsMargins(0, 0, 0, 0)
        column.layout().setSpacing(6)

        def _caption(text):
            label = QLabel(text)
            label.setObjectName("BindingMuted")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            return label

        top = TopView()
        for uid, (x, y, w, h) in TOP_GEOMETRY.items():
            key = self._make_key_button(self.layout.get_button(uid))
            key.setParent(top)
            key.setGeometry(x, y, w, h)
        column.layout().addWidget(top, 0, Qt.AlignmentFlag.AlignHCenter)
        column.layout().addWidget(_caption(self._("Top")))

        side = QFrame()
        side.setObjectName("BindingSideGrid")
        side.setFixedSize(240, 300)
        grid = QGridLayout()
        grid.setContentsMargins(28, 28, 28, 28)
        grid.setSpacing(6)
        side.setLayout(grid)
        side_buttons = [b for b in self.layout.buttons if b.uid.startswith("s")]
        for index, button in enumerate(side_buttons):
            key = self._make_key_button(button)
            key.setFixedSize(56, 56)
            grid.addWidget(key, index // 3, index % 3)
        column.layout().addSpacing(10)
        column.layout().addWidget(side, 0, Qt.AlignmentFlag.AlignHCenter)
        column.layout().addWidget(_caption(self._("Side")))

        legend = QWidget()
        legend.setLayout(QFlowLayout())
        legend.layout().setContentsMargins(0, 8, 0, 0)
        for colour, border, text in [("#008000", "#008000", self._("Remapped")),
                                     ("#323232", "#323232", self._("Default")),
                                     ("#000", "#2D2D2D", self._("Not bound")),
                                     ("transparent", "#00FF00", self._("Editing")),
                                     ("transparent", "#ffa500", self._("Conflict"))]:
            label = QLabel(text)
            swatch = QLabel()
            swatch.setFixedSize(14, 14)
            swatch.setStyleSheet(f"background-color: {colour}; border: 2px solid {border};")
            item = QWidget()
            item.setLayout(QHBoxLayout())
            item.layout().setContentsMargins(0, 0, 8, 0)
            item.layout().setSpacing(6)
            item.layout().addWidget(swatch)
            item.layout().addWidget(label)
            legend.layout().addWidget(item)
        legend.setFixedWidth(240)
        column.layout().addWidget(legend)
        return column

    def _refresh_keys(self, conflicts):
        layer = self._current_layer()
        trigger = bindings.get_hypershift_key(self.profile) if layer == bindings.HYPERSHIFT else None

        for button in self.layout.buttons:
            key = self.key_buttons[button.uid]
            binding = self.profile[layer].get(button.uid)

            if button.uid == trigger:
                state, sub, description = "unbound", "Shift", self._("Hypershift (hold)")
            elif not binding:
                state, sub, description = "unbound", "—", bindings.describe(None)
            else:
                remapped = bindings.is_remapped(self.layout, self.profile, layer, button.uid)
                state = "remapped" if remapped else "default"
                sub, description = bindings.short_text(binding), bindings.describe(binding)

            if button.uid.startswith("s"):
                key.setText(button.short + "\n" + sub)
            else:
                key.setText(button.short if len(button.short) == 1 else "")
            key.setToolTip(f"{button.name} — {description}")
            key.setProperty("binding", state)
            key.setProperty("editing", button.uid == self.selected)
            key.setProperty("conflict", button.uid in conflicts and button.uid != trigger)
            key.style().unpolish(key)
            key.style().polish(key)

    # ------------------------------------------------------------------
    # Editor
    # ------------------------------------------------------------------
    def _row(self, label_text, widgets, wrap=False):
        row = self.widgets.create_row_widget(label_text, widgets, wrap=wrap)
        margins = row.layout().contentsMargins()
        margins.setLeft(0)
        margins.setRight(0)
        row.layout().setContentsMargins(margins)
        return row

    def _note(self, text, warning=False):
        label = QLabel(text)
        label.setObjectName("BindingWarning" if warning else "BindingMuted")
        label.setWordWrap(True)
        return label

    def _combo(self, items, current, callback, width=240):
        """
        items is a list of (data, label).
        """
        combo = QComboBox()
        combo.setMinimumWidth(width)
        for data, label in items:
            combo.addItem(label, data)
        index = combo.findData(current)
        combo.setCurrentIndex(max(index, 0))
        combo.activated.connect(lambda i: callback(combo.itemData(i)))
        return combo

    def _push_button(self, label, callback, icon=None, checked=None, enabled=True, tooltip=None):
        button = QPushButton()
        if label:
            button.setText(label)
        if icon:
            button.setIcon(self.widgets.get_icon_qt("general", icon))
        if checked is not None:
            button.setCheckable(True)
            button.setChecked(checked)
        if tooltip:
            button.setToolTip(tooltip)
        button.setEnabled(enabled)
        button.clicked.connect(callback)
        return button

    def _spacer(self):
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Preferred)
        return spacer

    def _build_layer_rows(self):
        clear_now(self.layer_row.layout())
        trigger = bindings.get_hypershift_key(self.profile)
        layer = self._current_layer()

        standard = self._push_button(self._("Standard"), lambda: self._set_layer(bindings.STANDARD), checked=layer == bindings.STANDARD)
        hypershift = self._push_button(self._("Hypershift"), lambda: self._set_layer(bindings.HYPERSHIFT), checked=layer == bindings.HYPERSHIFT, enabled=trigger is not None)
        group = QButtonGroup(standard)
        group.addButton(standard)
        group.addButton(hypershift)
        self.layer_row.layout().addWidget(self.widgets.create_row_widget(self._("Layer"), [standard, hypershift, self._spacer()]))

        options = [("", self._("None"))] + [(b.uid, b.name) for b in self.layout.buttons]
        combo = self._combo(options, trigger or "", self._set_hypershift_key, 200)
        note = self._note(self._("Hold it to switch every other button to the Hypershift layer."))
        self.layer_row.layout().addWidget(self.widgets.create_row_widget(self._("Hypershift key"), [combo, note, self._spacer()]))

    def _set_layer(self, layer):
        self._stop_input()
        self.layer = layer
        self.refresh()

    def _set_hypershift_key(self, uid):
        bindings.set_hypershift_key(self.layout, self.profile, uid or None)
        if not uid:
            self.layer = bindings.STANDARD
        self.store.save()
        self.refresh()

    def _build_editor(self, conflicts):
        layout = self.editor.layout()
        clear_now(layout)

        layer = self._current_layer()
        button = self.layout.get_button(self.selected)
        binding = self._current_binding()
        trigger = bindings.get_hypershift_key(self.profile)
        is_trigger = layer == bindings.HYPERSHIFT and self.selected == trigger
        kind = binding["type"] if binding and not is_trigger else None

        # Button
        if layer == bindings.HYPERSHIFT:
            default_text = self._("Standard layer:") + " " + bindings.describe(self.profile[bindings.STANDARD].get(self.selected))
        else:
            default_text = self._("Default:") + " " + bindings.describe(button.default)
        default_text += "  ·  " + self._("sends") + " " + button.source
        combo = self._combo([(b.uid, b.name) for b in self.layout.buttons], self.selected, self.select, 200)
        layout.addWidget(self._row(self._("Button"), [combo, self._note(default_text)], wrap=True))

        if is_trigger:
            layout.addWidget(self._row("", [self._note(self._("This button switches layers, so it has no Hypershift binding. Change it under Hypershift key."))]))
            return

        # Action type
        type_buttons = []
        for type_id, label, folder, icon in [("key", self._("Key"), "devices", "keyboard"),
                                              ("mouse", self._("Mouse"), "devices", "mouse"),
                                              ("macro", self._("Macro"), "general", "macro-keys"),
                                              ("text", self._("Text"), "general", "edit"),
                                              ("media", self._("Media"), "general", "preferences")]:
            tool = QToolButton()
            tool.setText(label)
            tool.setCheckable(True)
            tool.setChecked(kind == type_id)
            tool.setIconSize(QSize(32, 32))
            tool.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            tool.setIcon(QIcon(self.common.get_icon(folder, icon)))
            tool.setMinimumSize(80, 64)
            tool.clicked.connect(lambda checked, t=type_id: self._set_type(t))
            type_buttons.append(tool)
        layout.addWidget(self._row(self._("Action"), type_buttons, wrap=True))

        if not binding:
            layout.addWidget(self._row("", [self._note(self._("Not bound on the Hypershift layer. Pick an action type to bind it."))]))

        if kind == "key":
            self._build_key_rows(layout, binding)
        elif kind == "mouse":
            items = [(code, label) for code, label in bindings.MOUSE_BUTTONS]
            combo = self._combo(items, binding["button"], lambda v: self._patch(button=v))
            code = self._note(binding["button"])
            layout.addWidget(self._row(self._("Mouse button"), [combo, code, self._spacer()]))
        elif kind == "text":
            text = QLineEdit(binding["text"])
            text.setPlaceholderText(self._("Text to type"))
            text.setMinimumWidth(300)
            text.textEdited.connect(lambda value: self._patch(rebuild=False, text=value))
            layout.addWidget(self._row(self._("Text"), [text, self._spacer()]))
        elif kind == "media":
            items = [(uid, label) for uid, label, short in bindings.MEDIA_FUNCTIONS
                     if layer == bindings.STANDARD or uid != "hypershift"]
            combo = self._combo(items, binding["function"], lambda v: self._commit(dict(binding, function=v)))
            layout.addWidget(self._row(self._("Function"), [combo, self._spacer()]))
        elif kind == "macro":
            self._build_macro_rows(layout, binding)

        others = conflicts.get(self.selected, [])
        if others:
            names = ", ".join(self.layout.get_button(uid).name for uid in others)
            text = self._("[1] is also bound to [2].").replace("[1]", bindings.describe(binding)).replace("[2]", names)
            layout.addWidget(self._row("", [self._note(text, warning=True)]))

        if layer == bindings.HYPERSHIFT:
            reset = self._push_button(self._("Clear Binding"), lambda: self._reset(None), icon="reset", enabled=binding is not None)
        else:
            reset = self._push_button(self._("Reset to Default"), lambda: self._reset(copy.deepcopy(button.default)), icon="reset",
                                      enabled=binding != button.default)
        layout.addWidget(self._row("", [reset, self._spacer()]))

    def _build_key_rows(self, layout, binding):
        field = QLineEdit()
        field.setObjectName("BindingCombo")
        field.setReadOnly(True)
        field.setMinimumWidth(300)
        if self.capturing:
            field.setText(self.capture_preview or self._("Press a key combination…  (Esc cancels)"))
        elif binding["keys"]:
            field.setText(" + ".join(binding["keys"]))
        else:
            field.setText(self._("Not set"))

        label = self._("Cancel") if self.capturing else self._("Capture…")
        capture = self._push_button(label, self._toggle_capture, checked=self.capturing)
        layout.addWidget(self._row(self._("Key combo"), [field, capture, self._spacer()]))

    def _build_macro_rows(self, layout, binding):
        name = QLineEdit(binding["name"])
        name.setMinimumWidth(240)
        name.textEdited.connect(lambda value: self._patch(rebuild=False, name=value))
        layout.addWidget(self._row(self._("Macro name"), [name, self._spacer()]))

        steps = binding["steps"]
        toolbar = QWidget()
        toolbar.setLayout(QHBoxLayout())
        toolbar.layout().setContentsMargins(0, 0, 0, 0)
        record_label = self._("Stop Recording") if self.recording else self._("Record")
        for widget in [self._push_button(record_label, self._toggle_record, checked=self.recording),
                       self._push_button(self._("Delay"), self._add_delay, icon="new"),
                       self._push_button(self._("Remove"), self._remove_step, icon="delete", enabled=bool(steps)),
                       self._push_button("", lambda: self._move_step(-1), icon="move-up", tooltip=self._("Move Up")),
                       self._push_button("", lambda: self._move_step(1), icon="move-down", tooltip=self._("Move Down")),
                       self._spacer()]:
            toolbar.layout().addWidget(widget)

        table = QTableWidget(len(steps), 3)
        table.setHorizontalHeaderLabels([self._("Event"), self._("Key"), self._("Delay")])
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setDefaultSectionSize(30)
        table.setFixedHeight(table.horizontalHeader().sizeHint().height() + 4 + 30 * min(max(len(steps), 4), 10))
        events = {"press": self._("Press"), "release": self._("Release"), "delay": self._("Delay")}
        for row, step in enumerate(steps):
            delay = str(step["ms"]) + " ms" if step["event"] == "delay" else ""
            for column, text in enumerate([events[step["event"]], step.get("key", ""), delay]):
                table.setItem(row, column, QTableWidgetItem(text))
        if steps:
            table.selectRow(min(self.step_selected, len(steps) - 1))
        table.itemSelectionChanged.connect(lambda: self._select_step(table.currentRow()))

        steps_widget = QWidget()
        steps_widget.setLayout(QVBoxLayout())
        steps_widget.layout().setContentsMargins(0, 0, 0, 0)
        steps_widget.layout().addWidget(toolbar)
        steps_widget.layout().addWidget(table)
        if not steps:
            steps_widget.layout().addWidget(self._note(self._("No steps yet. Press Record, then type the sequence.")))
        layout.addWidget(self._row(self._("Steps"), [steps_widget]))

        items = [(uid, self._(label)) for uid, label in bindings.REPEAT_MODES]
        combo = self._combo(items, binding["repeat"], lambda v: self._patch(repeat=v))
        layout.addWidget(self._row(self._("Repeat"), [combo, self._spacer()]))

    # ------------------------------------------------------------------
    # Editor actions
    # ------------------------------------------------------------------
    def _set_type(self, kind):
        binding = self._current_binding()
        if binding and binding["type"] == kind:
            self.refresh()
            return
        self._stop_input()
        self._commit(bindings.new_binding(kind))
        if kind == "key":
            self._toggle_capture()

    def _reset(self, binding):
        self._stop_input()
        self._commit(binding)

    def _toggle_capture(self):
        self.recording = False
        self.capturing = not self.capturing
        self.capture_preview = ""
        if self.capturing:
            self.grabber.start()
        else:
            self.grabber.stop()
        self.refresh()

    def _toggle_record(self):
        self.capturing = False
        if self.recording:
            self._stop_input()
            self.refresh()
            return
        self.recording = True
        self.last_step_time = None
        self.step_selected = 0
        self.grabber.start()
        self._patch(steps=[])

    def _select_step(self, row):
        self.step_selected = max(row, 0)

    def _add_delay(self):
        steps = copy.deepcopy(self._current_binding()["steps"])
        index = min(self.step_selected + 1, len(steps))
        steps.insert(index, {"event": "delay", "ms": 50})
        self.step_selected = index
        self._patch(steps=steps)

    def _remove_step(self):
        steps = copy.deepcopy(self._current_binding()["steps"])
        if not steps:
            return
        del steps[min(self.step_selected, len(steps) - 1)]
        self.step_selected = max(0, min(self.step_selected, len(steps) - 1))
        self._patch(steps=steps)

    def _move_step(self, offset):
        steps = copy.deepcopy(self._current_binding()["steps"])
        i, j = self.step_selected, self.step_selected + offset
        if not 0 <= i < len(steps) or not 0 <= j < len(steps):
            return
        steps[i], steps[j] = steps[j], steps[i]
        self.step_selected = j
        self._patch(steps=steps)

    def _key_event(self, event, pressed):
        """
        Called by KeyGrabber while capturing a combo or recording a macro.
        """
        name = evdev_name(event)

        if self.capturing:
            if not pressed:
                return
            if name == "KEY_ESC":
                self._toggle_capture()
                return
            modifiers = [code for flag, code in QT_MODIFIERS if event.modifiers() & flag]
            if name in bindings.MODIFIER_KEYS or not name:
                self.capture_preview = " + ".join(modifiers + ["…"])
                self.refresh()
                return
            self.capturing = False
            self.grabber.stop()
            self._patch(keys=[m for m in modifiers if m != name] + [name])
            return

        if self.recording:
            if pressed and name == "KEY_ESC":
                self._toggle_record()
                return
            if not name:
                return
            now = time.monotonic()
            steps = copy.deepcopy(self._current_binding()["steps"])
            if steps and self.last_step_time is not None:
                delay = int(round((now - self.last_step_time) * 100)) * 10
                if delay >= 10:
                    steps.append({"event": "delay", "ms": delay})
            self.last_step_time = now
            steps.append({"event": "press" if pressed else "release", "key": name})
            self.step_selected = len(steps) - 1
            self._patch(steps=steps)

    # ------------------------------------------------------------------
    def refresh(self):
        self._build_layer_rows()
        conflicts = self._refresh_summary()
        self._build_editor(conflicts)
        self.editor.layout().addStretch(1)

    def _refresh_summary(self):
        """
        Update the schematics and status line. Returns the layer's conflicts.
        """
        layer = self._current_layer()
        conflicts = bindings.find_conflicts(self.layout, self.profile, layer)
        self._refresh_keys(conflicts)

        trigger = bindings.get_hypershift_key(self.profile) if layer == bindings.HYPERSHIFT else None
        remapped = len([b for b in self.layout.buttons
                        if b.uid != trigger and bindings.is_remapped(self.layout, self.profile, layer, b.uid)])
        layer_name = self._("Hypershift layer") if layer == bindings.HYPERSHIFT else self._("Standard layer")
        parts = [self.profile["name"], layer_name, self._("[1] remapped").replace("[1]", str(remapped))]
        conflict_groups = len({tuple(sorted([uid] + others)) for uid, others in conflicts.items()})
        if conflict_groups:
            parts.append(self._("[1] conflicts").replace("[1]", str(conflict_groups)))
        running = procpid.ProcessManager("bindings").is_another_instance_is_running()
        if running:
            applied = self._("Applied by the bindings service.")
        else:
            applied = self._("Saved, but not applied: the bindings service is not running.")
        self.status.setObjectName("BindingMuted" if running else "BindingWarning")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.status.setText("  ·  ".join(parts) + "\n" + applied)
        return conflicts
