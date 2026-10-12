# Brief: button binding for the Razer Naga V3

A personal fork of Polychromatic adds a UI for mapping the Naga V3's buttons. These notes give designs the context the app's code would.

## What exists today
- Upstream Polychromatic has **no button remapping**. A device with programmable keys gets a single row on its device page with an **"Open Input Remapper"** button (`controller/devices.py: create_programmable_keys_control`), which hands off to the separate Input Remapper app. See `assets/reference/device-page.png`, last row of the "Device" group.
- OpenRazer's on-the-fly macro recording is deprecated, and the app shows it only as an info dialog.
- So the binding UI is new surface. It should look as if it always belonged: same window chrome, sidebar, group/row form layout and controls.

## Where it lives
Pick whichever fits the flow being explored. Each one uses existing patterns:
1. **Inline on the device page.** Replace the "Open Input Remapper" row with a `pc-group` titled "Buttons": the thumb-grid diagram on the left and the selected key's binding rows on the right.
2. **A dedicated window**, the way the effect editor and DPI-stage editor open separately: a `pc-sidebar` of profiles, a content area with the grid, and a `pc-table` listing every binding.
3. **A new main tab**, next to Devices / Effects / Presets / Triggers (`pc-maintab`). Upstream hides Presets and Triggers as unfinished, so there's room.

## Building blocks to reuse
- **Grid diagram:** `assets/naga/naga-side-grid.svg`, with keys 1–12 as `<g id="key-N">`. Show the key being edited with a `#00FF00` stroke or text, and bound keys with a `#008000` fill. This is a schematic, so confirm the real layout and any extra buttons (wheel, DPI, side) on the device.
- **Action type** (key, mouse button, macro, text, disabled): `pc-effect-btn` row with exclusive choice, like Effect on the device page.
- **Target:** `pc-select` for keys and mouse buttons, a `pc-input` field showing a captured key combo (`pc-mono` for evdev names like `KEY_LEFTCTRL`), and `pc-table` for macro steps.
- **Profiles:** `pc-sidebar` items under a "Profiles" heading. Use toolbar or push buttons with `img-idle/general/` icons: new, clone, delete, import, save.
- **Status and feedback:** `pc-status` in the footer, `pc-warning-label` for conflicts (e.g. two keys bound to the same action).

## Avoid
- Rounded cards, drop shadows, gradients other than the content-area one, or any hue besides the greens and the warning orange.
- Custom widgets that have no stock Qt counterpart. If it can't be a QPushButton/QToolButton/QComboBox/QTableWidget/QGroupBox plus `style.qss`, it costs real implementation work, so call that out in the design.
