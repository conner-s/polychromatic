# design-sync notes

- **Shape: `brand-reference`** (off-script). Polychromatic is PyQt6 with no JS/React components, so the converter (`package-build.mjs` / storybook) doesn't apply. The project holds a CSS port of `data/qt/style.qss`, tokens, icons, real Qt screenshots, cards and guidelines. It ships no `_ds_bundle.js`, `.d.ts`/`.jsx`, or `_ds_sync.json` anchor, so every re-sync re-uploads everything (cheap, about 380 small files).
- **Build:** `.design-sync/build.sh` assembles `ds-bundle/` (gitignored) from `.design-sync/brand/` plus `data/img`, `data/qt/assets` and the Play font. It also runs `.design-sync/qtshots.py` under `nix-shell` (PyQt6, offscreen) to re-render `assets/reference/*.png`. The host is NixOS with no system python3.
- **Verification:** each card was screenshotted in headless Firefox and compared with the Qt renders (`firefox --headless --screenshot`). Known small gaps: the native number-input spinner in `.pc-spin`, and the summary's leading-spacer offset is approximate.
- **CSS `mask-image` icons don't work from `file://`** (CORS), so idle and disabled icon colourings are pre-generated as files (`assets/img-idle/`, `assets/img-disabled/`), mirroring `common.get_icon_styles()`.
- **Re-sync:** after editing `style.qss`, update `brand/styles.css` and the tokens to match, run `build.sh`, re-check the cards against `assets/reference/`, then upload the whole `ds-bundle/`.
- **Naga V3:** the repo has no Naga V3 device map. `brand/assets/naga/naga-side-grid.svg` is a hand-drawn 12-key schematic, still to be checked against the real device.
