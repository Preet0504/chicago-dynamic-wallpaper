"""Review tool: renders one condition and saves (1) a downscaled full frame and (2) a sheet of
full-resolution detail crops, so problems can't hide in a thumbnail.

  .venv/bin/python render/preview.py SEASON WEATHER "YYYY-MM-DD HH:MM" OUT_PREFIX [--cover 0.35] [--intensity 1]
  WEATHER: clear | partly_cloudy | overcast | rain | storm | fog | snow

Writes OUT_PREFIX_full.png (1672x941) and OUT_PREFIX_crops.png (full-res crops, labelled).
Always Read BOTH files when reviewing.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cv2, numpy as np
import timeofday as T

# (label, x, y, w, h) in OUTPUT pixels (2560x1441)
CROPS = [("tree top", 1300, 0, 1260, 520), ("walkway + lanterns", 1150, 1080, 1250, 361),
         ("lake + town", 380, 1000, 1250, 300), ("mountain + horizon", 330, 700, 1300, 380),
         ("pagoda", 0, 420, 520, 900), ("pavilion + hanging lantern", 1850, 250, 710, 950)]


def main(a):
    season, weather, when, prefix = a[:4]
    cover = float(a[a.index("--cover") + 1]) if "--cover" in a else {"clear": 0.0, "partly_cloudy": 0.35}.get(weather, 1.0)
    inten = float(a[a.index("--intensity") + 1]) if "--intensity" in a else 1.0
    wx = weather if weather in T.WEATHER_EFFECTS else None
    img, st = T.render(T.parse_when(when), cover, season=season, weather=wx, intensity=inten)
    out = T.to8(img)
    cv2.imwrite(prefix + "_full.png", cv2.resize(out, (1672, 941), interpolation=cv2.INTER_AREA))
    tiles = []
    k = T.OUT_W / 2560.0                       # crop boxes are defined on a 2560-wide frame
    for label, x, y, w, h in CROPS:
        x, y, w, h = int(x * k), int(y * k), int(w * k), int(h * k)
        c = out[y:y + h, x:x + w]
        s = min(640 / w, 620 / h)              # fit inside the tile, keep aspect (no black cut-off)
        c = cv2.resize(c, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
        canvas = np.zeros((640, 640, 3), np.uint8); canvas[:c.shape[0], :c.shape[1]] = c
        cv2.putText(canvas, label, (8, 632), 0, 0.6, (0, 255, 255), 2)
        tiles.append(canvas)
    sheet = np.vstack([np.hstack(tiles[:3]), np.hstack(tiles[3:])])
    cv2.imwrite(prefix + "_crops.png", sheet)
    print("%s %s %s  sun %.1f  template=%s" % (season, weather, when, st["sun_alt"], T.template_for(season)))


if __name__ == "__main__":
    main(sys.argv[1:])
