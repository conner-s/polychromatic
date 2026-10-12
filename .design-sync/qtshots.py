"""Render Polychromatic's real Qt theme offscreen for design reference.

Mirrors polychromatic-controller's theme load (Fusion + Play 10 + palette + style.qss)
and rebuilds a device page the way controller/devices.py + shared.py do.
Usage: python3 qtshots.py <repo> <outdir>
"""
import os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6 import uic
from PyQt6.QtCore import Qt, QSize, QMargins
from PyQt6.QtGui import QFont, QFontDatabase, QIcon, QPalette, QColor, QPixmap, QPainter, QImage
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QToolButton, QPushButton, QLabel,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout, QGroupBox,
    QRadioButton, QCheckBox, QSlider, QComboBox, QSpinBox, QLineEdit, QTabWidget, QButtonGroup,
    QScrollArea, QDialog, QTableWidget, QSizePolicy)

REPO, OUT = sys.argv[1], sys.argv[2]
DATA = os.path.join(REPO, "data")
os.makedirs(OUT, exist_ok=True)
TMP = tempfile.mkdtemp()

app = QApplication(sys.argv)
app.setStyle("Fusion")
QFontDatabase.addApplicationFont(os.path.join(DATA, "qt", "fonts", "Play_regular.ttf"))
app.setFont(QFont("Play", 10))
QSS = open(os.path.join(DATA, "qt", "style.qss")).read().replace("[data]", DATA)


def palette():
    p = QPalette()
    white, primary, secondary = QColor(255, 255, 255), QColor(0, 255, 0), QColor(0, 128, 0)
    for role, c in [("Window", QColor(0, 0, 0)), ("WindowText", white), ("Base", QColor(25, 25, 25)),
                    ("AlternateBase", QColor(53, 53, 53)), ("ToolTipBase", white), ("ToolTipText", white),
                    ("Text", white), ("Button", QColor(50, 50, 50)), ("ButtonText", white),
                    ("Link", primary), ("Highlight", secondary), ("HighlightedText", white)]:
        p.setColor(getattr(QPalette.ColorRole, role), c)
    return p


def theme(w):
    w.setFont(QFont("Play", 10))
    w.setPalette(palette())
    w.setStyleSheet(QSS)


def icon(folder, name, colour="#DED9CB"):
    """common.get_icon_styles(): recolour #00FF00 -> colour, #008000 -> #808080."""
    src = open(os.path.join(DATA, "img", folder, name + ".svg")).read()
    out = os.path.join(TMP, f"{folder}-{name}-{colour[1:]}.svg")
    open(out, "w").write(src.replace("#00FF00", colour).replace("#00ff00", colour).replace("#008000", "#808080"))
    return QIcon(out)


def raw(folder, name):
    return QIcon(os.path.join(DATA, "img", folder, name + ".svg"))


def row(label_text, widgets, vertical=False, wrap=False):
    """shared.PolychromaticWidgets.create_row_widget (QFlowLayout swapped for HBox)."""
    w = QWidget()
    w.setLayout(QHBoxLayout() if wrap else QFormLayout())
    w.layout().setContentsMargins(QMargins(30, 5, 30, 5))
    label = QLabel(label_text)
    label.setAlignment(Qt.AlignmentFlag.AlignTop)
    label.setWordWrap(True)
    label.setMinimumWidth(120)
    label.setMaximumWidth(120)
    inner = QWidget()
    inner.setLayout(QHBoxLayout() if (wrap or not vertical) else QVBoxLayout())
    inner.layout().setContentsMargins(0, 0, 0, 0)
    for c in widgets:
        inner.layout().addWidget(c)
    if wrap:
        inner.layout().addStretch()
        w.layout().addWidget(label)
        w.layout().addWidget(inner)
    else:
        w.layout().addRow(label, inner)
    return w


def group(title):
    g = QGroupBox()
    g.setTitle(title)
    g.setLayout(QGridLayout())
    g.layout().setAlignment(Qt.AlignmentFlag.AlignTop)
    g.layout().setContentsMargins(QMargins(0, 6, 0, 6))
    return g


def effect_buttons(effects, active):
    grp = QButtonGroup(app)
    out = []
    for name, label in effects:
        b = QToolButton()
        b.setText(label)
        b.setCheckable(True)
        b.setIconSize(QSize(40, 40))
        b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        b.setIcon(raw("options", name))
        b.setMinimumHeight(70)
        b.setMinimumWidth(105)
        b.setChecked(name == active)
        grp.addButton(b)
        out.append(b)
    app._keep = getattr(app, "_keep", []) + [grp]
    return out


def slider(value):
    s = QSlider(Qt.Orientation.Horizontal)
    s.setRange(0, 100)
    s.setValue(value)
    s.setMinimumWidth(240)
    return s


def summary(title, indicators, buttons):
    """create_summary_widget()."""
    s = uic.loadUi(os.path.join(DATA, "qt", "widget-summary.ui"), QWidget())
    s.findChild(QLabel, "SummaryTitle").setText(title)
    s.findChild(QLabel, "SummaryTitle").setStyleSheet("QLabel { font-size: 17px; color: lime; }")
    container = s.findChild(QWidget, "SummaryContainer")
    bw = s.findChild(QWidget, "SummaryButtons")
    s.findChild(QLabel, "SummaryImage").deleteLater()
    r = QSvgRenderer(os.path.join(DATA, "img", "devices", "mouse.svg"))
    img = QImage(QSize(90, 90), QImage.Format.Format_ARGB32)
    img.fill(QColor(255, 255, 255, 0))
    p = QPainter(img); r.render(p); p.end()
    lbl = QLabel(); lbl.setPixmap(QPixmap.fromImage(img))
    s.setContentsMargins(14, 8, 8, 8)
    s.layout().addWidget(lbl); s.layout().addWidget(container); s.layout().addWidget(bw)
    iw = s.findChild(QWidget, "SummaryIcons")
    for folder, name, text in indicators:
        w = QWidget(); w.setLayout(QHBoxLayout()); w.layout().setContentsMargins(0, 0, 10, 0)
        il = QLabel(); il.setPixmap(raw(folder, name).pixmap(22, 22)); w.layout().addWidget(il)
        w.layout().addWidget(QLabel(text))
        iw.layout().addWidget(w)
    iw.layout().addStretch()
    for folder, name, text in buttons:
        b = QPushButton(text); b.setIcon(icon(folder, name)); bw.layout().addWidget(b)
    bw.layout().addStretch()
    return s


def shot(w, name, size=None):
    if size:
        w.resize(*size)
    w.show()
    app.processEvents()
    w.grab().save(os.path.join(OUT, name + ".png"))
    print("wrote", name, w.size().width(), "x", w.size().height())


# ---- 1. Main window, Devices tab, mouse device page -----------------------------------
win = uic.loadUi(os.path.join(DATA, "qt", "main.ui"), QMainWindow())
theme(win)
win.findChild(QLabel, "HeaderText").setText("Razer Naga V3")
tabs = win.findChild(QTabWidget, "MainTabWidget")
tabs.tabBar().hide()
for btn, ic in [("DevicesTabButton", "devices"), ("EffectsTabButton", "effects"),
                ("PresetsTabButton", "presets"), ("TriggersTabButton", "triggers")]:
    win.findChild(QToolButton, btn).setIcon(icon("general", ic))
win.findChild(QToolButton, "DevicesTabButton").setChecked(True)

tree = win.findChild(QTreeWidget, "DeviceSidebarTree")
tree.setIconSize(QSize(24, 24))
tree.clear()
tasks = QTreeWidgetItem(["Tasks"]); tree.addTopLevelItem(tasks)
t = QTreeWidgetItem(["Apply to All"]); t.setIcon(0, icon("general", "devices")); tasks.addChild(t)
devs = QTreeWidgetItem(["Devices"]); tree.addTopLevelItem(devs)
sel = None
for name, ff in [("Razer BlackWidow V3", "keyboard"), ("Razer Firefly", "mousemat"), ("Razer Naga V3", "mouse")]:
    it = QTreeWidgetItem([name]); it.setIcon(0, raw("devices", ff)); devs.addChild(it)
    if ff == "mouse":
        sel = it
tree.expandAll()
tree.setCurrentItem(sel)

contents = win.findChild(QWidget, "DeviceContents")
lay = contents.layout()
lay.addWidget(summary("Razer Naga V3",
    [("options", "spectrum", "Spectrum"), ("params", "75", "75%"), ("general", "dpi", "1800 DPI"), ("general", "battery-75", "75%")],
    [("general", "properties", "Details")]))
logo = group("Logo")
logo.layout().addWidget(row("Effect", effect_buttons([("spectrum", "Spectrum"), ("static", "Static"), ("breath", "Breath"), ("reactive", "Reactive"), ("none", "None")], "spectrum"), wrap=True))
logo.layout().addWidget(row("Brightness", [slider(75)]))
lay.addWidget(logo)
wheel = group("Scroll Wheel")
wheel.layout().addWidget(row("Effect", effect_buttons([("spectrum", "Spectrum"), ("static", "Static"), ("breath", "Breath"), ("none", "None")], "static"), wrap=True))
pw = QWidget(); pw.setLayout(QHBoxLayout()); pw.layout().setContentsMargins(0, 0, 0, 0)
prev = QWidget(objectName="PickerPreview"); prev.setFixedSize(80, 28); prev.setStyleSheet("QWidget { background-color: #00FF00 }")
pw.layout().addWidget(prev); pw.layout().addWidget(QPushButton("Change...", objectName="PickerCustom")); pw.layout().addStretch()
wheel.layout().addWidget(row("Colour", [pw]))
lay.addWidget(wheel)
dev = group("Device")
stages = QWidget(); stages.setLayout(QHBoxLayout()); stages.layout().setContentsMargins(0, 0, 0, 0)
for v in [400, 800, 1800, 3200, 6400]:
    b = QPushButton(str(v)); b.setCheckable(True); b.setChecked(v == 1800); stages.layout().addWidget(b)
eb = QPushButton("Edit"); eb.setIcon(icon("general", "edit")); stages.layout().addWidget(eb); stages.layout().addStretch()
dev.layout().addWidget(row("DPI", [stages], vertical=True))
pr = QComboBox()
for txt, ic in [("1000 Hz", "poll_high"), ("500 Hz", "poll_mid"), ("125 Hz", "poll_low")]:
    pr.addItem(raw("params", ic), txt)
pr.setIconSize(QSize(16, 16))
dev.layout().addWidget(row("Polling Rate", [pr, QWidget()]))
spacer = QWidget(); spacer.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Preferred)
dev.layout().addWidget(row("", [QPushButton("Open Input Remapper"), spacer]))
lay.addWidget(dev)
lay.addStretch()
win.findChild(QLabel, "GlobalStatus").setText("")
shot(win, "device-page", (1100, 1020))

# ---- 2. Control gallery ---------------------------------------------------------------
def gallery(title, rows, size):
    d = QDialog(); theme(d)
    d.setLayout(QVBoxLayout())
    g = group(title)
    for label, ws in rows:
        g.layout().addWidget(row(label, ws, wrap=True))
    d.layout().addWidget(g)
    d.layout().addStretch()
    shot(d, title.lower().replace(" ", "-"), size)

def pb(text, checked=None, disabled=False, flat=False, ic=None):
    b = QPushButton(text)
    if checked is not None:
        b.setCheckable(True); b.setChecked(checked)
    b.setDisabled(disabled); b.setFlat(flat)
    if ic:
        b.setIcon(icon("general", ic, "#575757" if disabled else "#DED9CB"))
    return b

gallery("Buttons", [
    ("Push button", [pb("Apply"), pb("Save", ic="save"), pb("Delete", ic="delete"), pb("Disabled", disabled=True)]),
    ("Toggle", [pb("400", checked=False), pb("1800", checked=True), pb("3200", checked=False)]),
    ("Flat", [pb("Flat action", flat=True, ic="external")]),
    ("Effect", effect_buttons([("wave", "Wave"), ("spectrum", "Spectrum"), ("static", "Static")], "wave")),
], (720, 330))

cb1 = QCheckBox("Enabled"); cb1.setChecked(True)
cb2 = QCheckBox("Disabled-off"); cb3 = QCheckBox("Unavailable"); cb3.setDisabled(True)
r1 = QRadioButton("Left"); r1.setIcon(raw("params", "left")); r1.setIconSize(QSize(22, 22)); r1.setChecked(True)
r2 = QRadioButton("Right"); r2.setIcon(raw("params", "right")); r2.setIconSize(QSize(22, 22))
r3 = QRadioButton("Unavailable"); r3.setDisabled(True)
rg = QButtonGroup(app); rg.addButton(r1); rg.addButton(r2); app._keep.append(rg)
combo = QComboBox(); combo.addItems(["Mouse Button 4", "Keyboard: Ctrl+C", "Macro: Reload"])
combo_d = QComboBox(); combo_d.addItem("Disabled"); combo_d.setDisabled(True)
sp = QSpinBox(); sp.setRange(100, 30000); sp.setValue(1800); sp.setSuffix(" DPI")
le = QLineEdit(); le.setPlaceholderText("Profile name"); le.setText("MMO Rotation")
s_d = slider(40); s_d.setDisabled(True)
gallery("Form Controls", [
    ("Checkbox", [cb1, cb2, cb3]),
    ("Radio", [r1, r2, r3]),
    ("Combo box", [combo, combo_d]),
    ("Slider", [slider(60), s_d]),
    ("Spin / text", [sp, le]),
], (760, 380))

# Tabs + tree/table
d = QDialog(); theme(d); d.setLayout(QVBoxLayout())
tw = QTabWidget()
for name in ["Buttons", "Lighting", "Performance", "Disabled"]:
    tw.addTab(QWidget(), name)
tw.setTabEnabled(3, False)
inner = QTreeWidget(); inner.setHeaderLabels(["Button", "Action"]); inner.setAlternatingRowColors(True)
for i, (k, v) in enumerate([("Thumb 1", "Keyboard: 1"), ("Thumb 2", "Keyboard: 2"), ("Thumb 3", "Macro: Burst"), ("Side Back", "Mouse Button 4")]):
    it = QTreeWidgetItem([k, v]); inner.addTopLevelItem(it)
    if i == 2:
        inner.setCurrentItem(it)
inner.setColumnWidth(0, 160)
tw.widget(0).setLayout(QVBoxLayout()); tw.widget(0).layout().addWidget(inner)
d.layout().addWidget(tw)
shot(d, "tabs-and-lists", (560, 260))

# Real dialogs from .ui files
for ui, size in [("preferences", (760, 560)), ("custom-dpi", None), ("colour-picker", None)]:
    try:
        dlg = uic.loadUi(os.path.join(DATA, "qt", ui + ".ui"), QDialog())
        theme(dlg)
        shot(dlg, "dialog-" + ui, size)
    except Exception as e:
        print("skip", ui, e)
