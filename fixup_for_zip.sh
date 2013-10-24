#!/bin/bash

# Apply some fix-ups to make the output directory as small as possible
# (10MB or less).

cd $(dirname $0)

# Convert the large node-edge PNGs to 1x-resolution JPGs.
echo "Node-edge resizing..."
png_filename_fixup_regex="s/(?<=nodeedge\\/)([^.]+)\.png/\$1.jpg/g"
for f in signaling/explore/cell_line/img/nodeedge/*.png; do
    echo " " $(basename "$f")
    base=$(basename "${f%.png}")
    path=$(dirname "$f")
    convert "$f" -resize 250x235 "$path/$base.jpg"
    rm "$f"
    html=signaling/explore/cell_line/$base.html
    if [[ -e "$html" ]]; then
        perl -pi -e "$png_filename_fixup_regex" "$html"
    fi
done
perl -pi -e "$png_filename_fixup_regex" signaling/start.html

# Optimize remaining PNGs.
for f in signaling/explore/*/img/*/*.png; do
    convert "$f" -type Optimize optimize.png
    pngcrush -brute optimize.png crush.png
    mv crush.png "$f"
done
rm optimize.png
