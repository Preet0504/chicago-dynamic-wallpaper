#!/bin/zsh
# Installs the live wallpaper as a LaunchAgent (runs at login and every :00 and :30).
# Re-run after changing anything in this folder. ./install.sh uninstall removes it.
# launchd jobs can't read ~/Documents (macOS privacy), so the runtime lives in Application Support.
set -euo pipefail
setopt NULL_GLOB
SRC="$(cd "$(dirname "$0")" && pwd)"
DIR="$HOME/Library/Application Support/DynamicWallpaper"
LABEL="local.dynamic-wallpaper"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [[ "${1:-}" == "uninstall" ]]; then
  launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  rm -rf "$DIR"
  echo "Uninstalled (your files in $SRC are untouched)."
  exit 0
fi

mkdir -p "$DIR/bin" "$DIR/render" "$DIR/logs" "$HOME/Library/LaunchAgents"
swiftc -O "$SRC/setwallpaper.swift" -o "$DIR/bin/setwallpaper"
# build the one-time analysis caches in the source folder first
"$SRC/.venv/bin/python" -c "import sys; sys.path.insert(0, '$SRC/render'); import timeofday as T; [T.Assets(n) for n in T.TEMPLATES if T.template_for(n) == n]"
rm -rf "$DIR/render" "$DIR/templates" "$DIR/images" "$DIR/conditions.py" "$DIR/base.png"
mkdir -p "$DIR/render/effects" "$DIR/templates/4k"
cp "$SRC/dynamic_wallpaper.py" "$DIR/"
cp "$SRC"/render/timeofday.py "$SRC"/render/astro.py "$SRC"/render/masks.py "$SRC"/render/tod_*.py "$DIR/render/"
cp "$SRC"/render/masks.npz "$SRC"/render/depth.npy "$SRC"/render/depth_labels.npy "$SRC"/render/cache_*.npz "$DIR/render/"
cp "$SRC"/render/effects/*.py "$DIR/render/effects/"
cp "$SRC"/templates/*.png "$DIR/templates/"
cp "$SRC"/templates/4k/*.png "$DIR/templates/4k/"
echo "Copied $(ls "$DIR/templates/4k" | wc -l | tr -d ' ') 4K template masters."
if [[ ! -x "$DIR/.venv/bin/python" ]]; then
  echo "Creating runtime Python environment…"
  python3 -m venv "$DIR/.venv"
  "$DIR/.venv/bin/pip" install -q numpy opencv-python-headless
fi

cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$DIR/.venv/bin/python</string>
    <string>$DIR/dynamic_wallpaper.py</string>
  </array>
  <key>StartCalendarInterval</key>
  <array>
    <dict><key>Minute</key><integer>0</integer></dict>
    <dict><key>Minute</key><integer>30</integer></dict>
  </array>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$DIR/logs/wallpaper.log</string>
  <key>StandardErrorPath</key><string>$DIR/logs/wallpaper.log</string>
</dict>
</plist>
PL

launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Installed — renders a new wallpaper at login and every 30 minutes. Log: $DIR/logs/wallpaper.log"
