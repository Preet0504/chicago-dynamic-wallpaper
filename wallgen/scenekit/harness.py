"""Runs a scene_renderer.py against a scene package for a list of test moments, in its own process.

    python harness.py <package dir> <scene_renderer.py> <cases.json> <out dir>

cases.json: [{"id": "c01", "when": "2026-04-20 06:10", "cover": 0.2, "weather": null, "intensity": 1.0,
              "phase": "spring_full", "snow_depth_m": 0}, ...]
Prints one JSON line per case: {"id", "ok", "seconds", "file" | "error"}.
"""
import importlib.util
import json
import os
import sys
import time
import traceback


def main(pkg, renderer, cases_path, out):
    sys.path.insert(0, pkg)
    from scenekit import kit
    os.makedirs(out, exist_ok=True)
    spec = importlib.util.spec_from_file_location("scene_renderer", renderer)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    scene = kit.Scene(pkg)
    if getattr(mod, "CAMERA", None):
        scene.cam.update({k: float(v) for k, v in mod.CAMERA.items() if k in ("view_az", "hfov", "horizon")})
    import cv2
    import numpy as np
    for c in json.load(open(cases_path)):
        t0 = time.time()
        try:
            F = kit.Frame.at(scene, kit.parse_when(c["when"], scene.tz), c.get("cover", 0.3), c.get("weather"),
                             c.get("intensity", 1.0), c.get("snow_depth_m"), c.get("phase"))
            img = mod.render(F)
            img = np.asarray(img, np.float32)
            if img.shape != (kit.OUT_H, kit.OUT_W, 3):
                raise ValueError("render() returned shape %s, expected (%d, %d, 3)" % (img.shape, kit.OUT_H, kit.OUT_W))
            if not np.isfinite(img).all():
                raise ValueError("render() returned NaN/inf values")
            f = os.path.join(out, c["id"] + ".png")
            cv2.imwrite(f, kit.to8(img))
            print(json.dumps(dict(id=c["id"], ok=True, seconds=round(time.time() - t0, 2), file=f,
                                  sun_alt=round(F.sun_alt, 1), phase=F.phase)), flush=True)
        except Exception as e:
            tb = traceback.format_exc(limit=4)
            print(json.dumps(dict(id=c["id"], ok=False, seconds=round(time.time() - t0, 2),
                                  error="%s: %s" % (type(e).__name__, e), traceback=tb[-1500:])), flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:5])
