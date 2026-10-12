# Polychromatic: brand reference

Polychromatic is a Qt (PyQt6) desktop app for configuring Razer devices on Linux. It has **no web component library**. This project holds its look, ported to CSS: tokens, a `pc-*` class set translated from the shipping Qt stylesheet (`data/qt/style.qss`), the app's real icons, and screenshots of the real Qt theme. Designs here are mockups that a developer rebuilds in Qt widgets. Use only standard widget shapes (buttons, tool buttons, combo boxes, sliders, trees, tables, group boxes, tabs) so every screen maps onto a stock Qt widget plus `style.qss`.

## Setup
Link `styles.css` (it imports `tokens/colors.css`, `tokens/metrics.css` and the Play font) and put **`class="pc-app"` on the root**. That class sets the black background, the Play 13.33px font and `#D6D6D6` text. Without it, text falls back to the browser's black-on-white default.

## Look, in rules
- **Dark only.** Window, sidebar, menus and lists are `#000`. Controls are `#323232`. The content area is a vertical gradient from `#000` to `#323232` (`--pc-bg-content`). There is no light theme.
- **One accent.** `#00FF00` (`--pc-primary`) marks active text, the selected-tab border, slider fill and checked indicators. `#008000` (`--pc-secondary`) fills selected rows and checked buttons; their text turns `#fff`. Don't introduce other hues, except orange (`--pc-warning`) for warnings.
- **Square and flat.** Radius 0 everywhere (2px only on slider handles). 1–2px `#2D2D2D` borders. No shadows, no blur.
- **One typeface, one weight.** Play Regular. Hierarchy comes only from size (13.33 / 17 / 18.67px) and the green accent. No bold, no uppercase eyebrows.
- **Form layout.** Option rows have a fixed 120px label column, with controls to its right (`.pc-row`). Related rows sit under a group title rule (`.pc-group`). A mode choice uses large 105×70 tool buttons with a 40px icon above the label (`.pc-effect-btn`).

## Class vocabulary (`styles.css`)
| Area | Classes |
|---|---|
| Window | `pc-window`, `pc-menubar` / `__item`, `pc-menu` / `__item` / `__separator`, `pc-header` / `__title`, `pc-maintabs`, `pc-maintab` (+`is-active`), `pc-body`, `pc-footer`, `pc-status` |
| Navigation | `pc-sidebar`, `pc-sidebar__heading`, `pc-sidebar__item` (+`is-selected`) |
| Content | `pc-content`, `pc-summary` / `__image` / `__main` / `__title` / `__indicators` / `__actions`, `pc-indicator`, `pc-group` / `__title`, `pc-row` / `__label` / `__controls` (`--vertical`), `pc-empty` / `__title` / `__subtitle` |
| Controls | `pc-button` (`--flat`, `--small`, checked via `aria-pressed="true"`), `pc-effect-btn`, `pc-check`, `pc-radio` (wrap a native input in a label), `pc-select`, `pc-input`, `pc-spin`, `pc-slider` (set `style="--value:NN"` for the fill), `pc-swatch` (`--swatch`), `pc-tabs` / `pc-tab` / `pc-tabpanel`, `pc-toolbar` / `__separator` |
| Data | `pc-table` (`--grid`; rows `aria-selected="true"` or `is-disabled`), `pc-list` |
| Misc | `pc-icon`, `pc-separator`, `pc-tooltip`, `pc-dock-title`, `pc-warning-label`, `pc-muted`, `pc-accent`, `pc-mono` |

State classes: `is-active`, `is-selected`, `is-checked`, `is-disabled`, or the matching ARIA attributes. For values, use `var(--pc-*)` tokens; never write raw hex in layout glue.

## Icons
SVGs drawn in green and recoloured by role:
- `assets/img/<folder>/<name>.svg`: the green original. Use it for effect/option buttons, indicators, and active or selected states.
- `assets/img-idle/<folder>/<name>.svg` (`#DED9CB`): use it on idle buttons, tabs and menus.
- `assets/img-disabled/<folder>/<name>.svg` (`#575757`): use it on disabled controls.

`img-idle` and `img-disabled` exist only for `general/` and `effects/`. The folders are `general` (actions, battery, dpi, lock…), `options` (lighting effects, poll_rate, sleep), `params` (directions, speeds, poll rates), `devices` (form factors), `zones`, `effects` (editor tools), `dialog`, `emblems`, `logo`, `header`, `empty`. The Foundations → Icons card lists every name. Indicator-style images for check and radio states are in `assets/qt/`.

## Where the truth lives
- `styles.css` and `tokens/*.css`: read them before styling anything.
- `assets/reference/*.png`: real renders of the Qt theme (device page, buttons, form controls, tabs/tree, preferences, custom DPI, colour picker). When the CSS port and a screenshot disagree, the screenshot wins.
- `guidelines/naga-bind-mapping.md`: the brief for the current project, a button-binding UI for a Razer Naga V3. The 12-key thumb-grid schematic is `assets/naga/naga-side-grid.svg`; each key is `<g id="key-N">`.

## Example
```html
<div class="pc-app pc-window">
  <header class="pc-header"><h1 class="pc-header__title">Razer Naga V3</h1></header>
  <div class="pc-body">
    <aside class="pc-sidebar">
      <div class="pc-sidebar__heading">Profiles</div>
      <button class="pc-sidebar__item is-selected">MMO Rotation</button>
    </aside>
    <main class="pc-content">
      <section class="pc-group">
        <h3 class="pc-group__title">Thumb Grid</h3>
        <div class="pc-row">
          <div class="pc-row__label">Action type</div>
          <div class="pc-row__controls">
            <button class="pc-effect-btn" aria-pressed="true"><img src="assets/img/general/controller.svg" alt="">Key</button>
            <button class="pc-effect-btn"><img src="assets/img/general/macro-keys.svg" alt="">Macro</button>
          </div>
        </div>
        <div class="pc-row">
          <div class="pc-row__label">Key</div>
          <div class="pc-row__controls"><select class="pc-select"><option>Keyboard: 1</option></select>
            <button class="pc-button"><img class="pc-icon" src="assets/img-idle/general/save.svg" alt="">Save</button></div>
        </div>
      </section>
    </main>
  </div>
</div>
```
