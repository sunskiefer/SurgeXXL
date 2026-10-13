#!/usr/bin/env bash
# Put Surge's data folder together for the plugin: <dest>/data = the vendored resources/data (patches, wavetables,
# FX and modulator presets, tunings; not Surge's GUI skins) plus the two files headless Surge reads from it,
# configuration.xml and windows.wt (the Window oscillator's windows).
#   tools/stage_data.sh <dest> [--link]     (--link: symlinks, for the offline tests; default: a copy, for the package)
set -euo pipefail
cd "$(dirname "$0")/.."
DEST="$1"
SRC="$PWD/third_party/surge/resources"
mkdir -p "$DEST/data"
for d in "$SRC/data"/*; do
  name="$(basename "$d")"
  [ "$name" = skins ] && continue
  if [ "${2:-}" = --link ]; then ln -sfn "$d" "$DEST/data/$name"; else cp -R "$d" "$DEST/data/"; fi
done
cp "$SRC/surge-shared/configuration.xml" "$SRC/surge-shared/windows.wt" "$DEST/data/"
