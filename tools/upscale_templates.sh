#!/bin/zsh
# AI-upscales every season template to a 4K master (templates/4k/<name>.png, 3840x2160) with SeedVR2 (local, free).
export PATH="$HOME/.local/bin:$PATH"
cd "$(dirname "$0")/.."
mkdir -p templates/4k
for f in templates/*_clear_*.png; do
  case "$f" in *_sky.png) continue;; esac
  out="templates/4k/$(basename "$f")"
  [[ -f "$out" && "$out" -nt "$f" ]] && { echo "up to date: $out"; continue; }
  mflux-upscale-seedvr2 --image-path "$f" --resolution 2160 --seed 1 --output "$out" && \
    sips -z 2160 3840 "$out" >/dev/null && echo "upscaled: $out"
done
