#!/usr/bin/env python3
"""Live runtime for a GENERATED scene package (the counterpart of dynamic_wallpaper.py for the original scene).
Needs only numpy + opencv (the runtime .venv). Renders this moment for the package's location with live weather and
real snow depth, then sets it on every display with bin/setwallpaper.

    .venv/bin/python wallgen/live.py <package dir> [--at "YYYY-MM-DD HH:MM"] [--out frame.png] [--no-set]

To make it the live wallpaper, point the LaunchAgent's ProgramArguments at this script and the package (not done
automatically - the original runtime keeps running until you decide).
"""
import datetime as dt
import importlib.util
import json
import os
import subprocess
import sys
import urllib.request

WMO = {51: ("rain", 0.25), 53: ("rain", 0.35), 55: ("rain", 0.45), 56: ("rain", 0.35), 57: ("rain", 0.5),
       61: ("rain", 0.5), 63: ("rain", 0.75), 65: ("rain", 1.0), 66: ("rain", 0.5), 67: ("rain", 0.8),
       80: ("rain", 0.5), 81: ("rain", 0.8), 82: ("rain", 1.0), 71: ("snow", 0.35), 73: ("snow", 0.65),
       75: ("snow", 1.0), 77: ("snow", 0.3), 85: ("snow", 0.6), 86: ("snow", 1.0), 45: ("fog", 0.75),
       48: ("fog", 0.9), 95: ("storm", 0.9), 96: ("storm", 1.0), 99: ("storm", 1.0)}


def main(argv):
    pkg = os.path.abspath(argv[0])
    arg = lambda k: argv[argv.index(k) + 1] if k in argv else None
    sys.path.insert(0, pkg)
    from scenekit import kit
    import cv2
    scene = kit.Scene(pkg)
    spec = importlib.util.spec_from_file_location("scene_renderer", os.path.join(pkg, "scene_renderer.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if getattr(mod, "CAMERA", None):
        scene.cam.update(mod.CAMERA)
    state_p = os.path.join(pkg, "live_state.json")
    try:
        state = json.load(open(state_p))
    except Exception:
        state = {}
    try:
        url = ("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s&current=weather_code,cloud_cover,"
               "snow_depth&timezone=auto" % (scene.lat, scene.lon))
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "dynamic-wallpaper/1.0"}), timeout=15) as r:
            state["weather"] = json.load(r)["current"]
    except Exception as e:
        print("weather fetch failed (%s), using last known" % e)
    w = state.get("weather", {})
    cover = w.get("cloud_cover", 30) / 100.0
    wx, inten = WMO.get(w.get("weather_code", 0), (None, 0.0))
    when = kit.parse_when(arg("--at"), scene.tz) if arg("--at") else dt.datetime.now(scene.tz)
    F = kit.Frame.at(scene, when, cover, wx, inten or 1.0, w.get("snow_depth"))
    img = mod.render(F)
    out = arg("--out") or os.path.join(pkg, "frames", "wallpaper-%s.png" % when.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cv2.imwrite(out, kit.to8(img))
    print("%s  phase=%s weather=%s cover=%.2f sun=%.1f -> %s" % (when.strftime("%Y-%m-%d %H:%M"), F.phase, wx, cover,
                                                                F.sun_alt, out))
    if "--no-set" not in argv:
        setter = os.path.expanduser("~/Library/Application Support/DynamicWallpaper/bin/setwallpaper")
        subprocess.run([setter, out], check=True)
    json.dump(state, open(state_p, "w"))


if __name__ == "__main__":
    main(sys.argv[1:])
