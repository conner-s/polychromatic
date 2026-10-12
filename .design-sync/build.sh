#!/usr/bin/env bash
#
# Assembles the Claude Design brand-reference bundle into ./ds-bundle.
#
#   .design-sync/brand/   hand-authored CSS port, cards, guidelines, README
#   data/img, data/qt     icons, header art and Qt indicator assets (copied as-is)
#   .design-sync/qtshots.py   renders the real Qt theme offscreen -> assets/reference/
#
# Needs Nix (for PyQt6). Run from anywhere.
set -euo pipefail
cd "$(dirname "$0")/.."

OUT=ds-bundle
rm -rf "$OUT"
mkdir -p "$OUT"/{fonts,assets/img,assets/qt,assets/reference}

cp -r .design-sync/brand/. "$OUT"/
cp data/qt/fonts/Play_regular.ttf "$OUT"/fonts/Play-Regular.ttf
for d in general options params devices zones effects dialog header logo emblems empty tray; do
    cp -r "data/img/$d" "$OUT/assets/img/"
done
cp data/qt/assets/*.svg "$OUT"/assets/qt/

# Idle/disabled icon variants, recoloured the way common.get_icon_styles() does at runtime:
# #00FF00 -> colour, #008000 -> #808080. assets/img/ keeps the green originals (active/selected).
for variant in idle:DED9CB disabled:575757; do
    name=${variant%%:*}; colour=${variant#*:}
    for d in general effects; do
        mkdir -p "$OUT/assets/img-$name/$d"
        for f in data/img/$d/*.svg; do
            sed -e "s/#00[Ff][Ff]00/#$colour/g" -e "s/#008000/#808080/g" "$f" > "$OUT/assets/img-$name/$d/$(basename "$f")"
        done
    done
done

nix-shell -p 'python3.withPackages(p: [p.pyqt6])' --run \
    "python3 .design-sync/qtshots.py '$PWD' '$OUT/assets/reference'" 2>&1 \
    | grep -v 'propagateSizeHints\|^structuredAttrs'

echo "Built $(find "$OUT" -type f | wc -l) files in $OUT/"
