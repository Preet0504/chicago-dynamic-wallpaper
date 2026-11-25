#!/usr/bin/env python3
"""Renders the wallpaper for this exact moment in Chicago and sets it on every display.
No AI at runtime: sun/moon come from astronomy, weather + snow depth from the free Open-Meteo API.

  dynamic_wallpaper.py                                     # render now and set
  dynamic_wallpaper.py --at "2026-11-14 16:30" --cover 0.3 # a specific moment
  dynamic_wallpaper.py --scene winter --weather snow       # force a scene / weather
"""
import datetime as dt
import glob
import json
import os
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "render"))
import timeofday as T  # noqa: E402

STATE = os.path.join(HERE, "state.json")
FRAMES = os.path.join(HERE, "frames")
SETTER = os.path.join(HERE, "bin", "setwallpaper")
KEEP_FRAMES = 12


def log(msg):
    print("%s  %s" % (dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg), flush=True)


def load_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except Exception:
        return {}


def fetch_weather():
    url = ("https://api.open-meteo.com/v1/forecast?latitude=41.8781&longitude=-87.6298"
           "&current=weather_code,cloud_cover,temperature_2m,snow_depth&timezone=America%2FChicago")
    req = urllib.request.Request(url, headers={"User-Agent": "dynamic-wallpaper/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)["current"]


def weather_effect(code):
    """Open-Meteo WMO code -> (renderer weather, intensity); (None, 0) for dry weather."""
    table = {51: ("rain", 0.25), 53: ("rain", 0.35), 55: ("rain", 0.45), 56: ("rain", 0.35),
             57: ("rain", 0.5), 61: ("rain", 0.5), 63: ("rain", 0.75), 65: ("rain", 1.0),
             66: ("rain", 0.5), 67: ("rain", 0.8), 80: ("rain", 0.5), 81: ("rain", 0.8),
             82: ("rain", 1.0), 71: ("snow", 0.35), 73: ("snow", 0.65), 75: ("snow", 1.0),
             77: ("snow", 0.3), 85: ("snow", 0.6), 86: ("snow", 1.0), 45: ("fog", 0.75),
             48: ("fog", 0.9), 95: ("storm", 0.9), 96: ("storm", 1.0), 99: ("storm", 1.0)}
    return table.get(code, (None, 0.0))


def scene_for(when, snow_depth_m):
    """Which painted template to use. Lying snow follows REAL snow depth, not the calendar."""
    def have(key):
        t = T.TEMPLATES.get(key)
        return t and os.path.exists(os.path.join(HERE, t["file"]))
    if snow_depth_m is not None and snow_depth_m >= 0.02:
        return "winter"                                   # actual snow on the ground, any month
    m, d = when.month, when.day
    if m in (12, 1, 2):
        wanted = ["winterbare", "autumnlate", "autumn"]   # cold but no snow on the ground
    elif m == 11 and d >= 15:
        wanted = ["autumnlate", "autumn"]
    else:
        wanted = [{3: "spring", 4: "spring", 5: "spring", 6: "summer", 7: "summer", 8: "summer"}.get(m, "autumn")]
    for k in wanted:
        if have(k):
            return k
    return wanted[-1]


def save_state(state):
    """Atomic write: the wallpaper agent may read state.json at any moment (on a Space switch)."""
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE)


def weather_info(cur):
    return "clouds=%s%% code=%s temp=%sC snow=%scm" % (
        cur.get("cloud_cover"), cur.get("weather_code"), cur.get("temperature_2m"),
        round(100 * (cur.get("snow_depth") or 0)))


# After boot/wake the network is often not up yet. Render right away with the last-known weather
# (the time of day is what matters most), then keep retrying and re-render once fresh weather arrives.
RETRY_EVERY = 30      # seconds between weather retries
RETRY_FOR = 600       # give up after this long; the :00/:30 schedule takes over


def main(argv):
    arg = lambda k: argv[argv.index(k) + 1] if k in argv else None
    state = load_state()
    fixed_time = bool(arg("--at"))
    when = T.parse_when(arg("--at")) if fixed_time else dt.datetime.now(T.TZ)
    if arg("--cover"):
        render_and_set(state, argv, when, float(arg("--cover")), "manual cover")
        return
    try:
        state["weather"] = fetch_weather()
        fresh, info = True, weather_info(state["weather"])
    except Exception as e:
        fresh, info = False, "weather fetch failed (%s), using last known" % e
    render_and_set(state, argv, when, None, info)
    if fresh or fixed_time:
        return
    deadline = time.time() + RETRY_FOR
    while time.time() < deadline:
        time.sleep(RETRY_EVERY)
        try:
            state["weather"] = fetch_weather()
        except Exception:
            continue
        render_and_set(state, argv, dt.datetime.now(T.TZ), None,
                       weather_info(state["weather"]) + " (after retry)")
        return
    log("weather still unreachable after %ds; next scheduled run will retry" % RETRY_FOR)


def render_and_set(state, argv, when, cover, info):
    arg = lambda k: argv[argv.index(k) + 1] if k in argv else None
    if cover is None:
        cover = state.get("weather", {}).get("cloud_cover", 30) / 100.0
    # raw cloud % -> renderer scale (clear < 20%, overcast > 85%)
    cover_r = 0.0 if cover < 0.2 else min(1.0, 0.15 + (cover - 0.2) * 1.1) if cover < 0.85 else 1.0

    code = state.get("weather", {}).get("weather_code", 0) if not arg("--cover") else 0
    wx, inten = (arg("--weather"), 1.0) if arg("--weather") else weather_effect(code)
    scene = arg("--scene") or scene_for(when, state.get("weather", {}).get("snow_depth"))

    t0 = time.time()
    img, st = T.render(when, cover_r, season=scene, weather=wx, intensity=inten)
    import cv2
    os.makedirs(FRAMES, exist_ok=True)
    out = os.path.join(FRAMES, "wallpaper-%s.png" % when.strftime("%Y%m%d-%H%M%S"))
    cv2.imwrite(out, T.to8(img), [cv2.IMWRITE_PNG_COMPRESSION, 1])
    log("[%s|%s %.2f] rendered %s %dx%d in %.1fs  sun %.1f° moon %.1f° (%.0f%% lit)  cover %.2f  [%s]" % (
        scene, wx or "dry", inten, when.strftime("%H:%M"), T.OUT_W, T.OUT_H, time.time() - t0,
        st["sun_alt"], st["moon_alt"], st["moon_illum"] * 100, cover_r, info))
    subprocess.run([SETTER, out], check=True)   # visible Space on every display; the agent does the rest
    state.update(current=out, updated=dt.datetime.now().isoformat(timespec="seconds"))
    save_state(state)
    # macOS caches by file name, so every frame gets a new one. Keep several: Spaces that are not
    # visible still point at an older frame until the agent updates them on switch.
    for old in sorted(glob.glob(os.path.join(FRAMES, "wallpaper-*.png")))[:-KEEP_FRAMES]:
        os.remove(old)


if __name__ == "__main__":
    main(sys.argv[1:])
