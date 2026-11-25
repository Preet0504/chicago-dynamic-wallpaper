"""Stage 4 - assemble the scene package the runtime (and the code model) work against:

  05_package/manifest.json   location, timezone, phases + start dates, snow rule, lamp threshold, camera
  05_package/plates/*.png    accepted plates (work resolution);  plates4k/ added by the finalize stage
  05_package/layers.npz      sky (soft matte), water, ground, roof, vegetation, terrain, structure, lights, depth

The `lights` layer is measured, not guessed: pixels inside lamp/window/structure areas that are bright and warm on
the night plate but not on the day plate of the same phase.
"""
import os
import shutil

import cv2
import numpy as np

from .common import Timer, read_json, write_json

STAGE = "04_package"


def light_mask(day, night, allowed):
    hsv_n = cv2.cvtColor(night, cv2.COLOR_BGR2HSV).astype(np.float32)
    ln = cv2.cvtColor(night, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    ld = cv2.cvtColor(day, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    warm = ((hsv_n[..., 0] < 40) | (hsv_n[..., 0] > 165)) & (hsv_n[..., 1] > 60)
    rel = np.clip((ln - np.percentile(ln, 60)) / 0.35, 0, 1)                # bright for a night picture
    lift = np.clip((ln - ld * 0.6) / 0.3, 0, 1)                            # brighter at night than in the day
    m = rel * lift * warm.astype(np.float32) * allowed
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    return np.clip(cv2.GaussianBlur(m, (0, 0), 1.2) * 1.3, 0, 1).astype(np.float32)


def extend_sky(plate, sky, thr=16.0, reach=9):
    """Per-plate sky matte: the shared matte plus fringe pixels whose colour matches this plate's own sky (estimated
    by normalised convolution of the sky pixels), so the old sky never shows as a halo around silhouettes."""
    if sky.max() < 0.5:
        return sky
    lab = cv2.cvtColor(plate, cv2.COLOR_BGR2LAB).astype(np.float32)
    core = (sky > 0.9).astype(np.float32)
    num = cv2.GaussianBlur(lab * core[..., None], (0, 0), 20)
    den = cv2.GaussianBlur(core, (0, 0), 20)[..., None] + 1e-4
    skycol = num / den
    dist = np.sqrt(((lab - skycol) ** 2).sum(2))
    band = cv2.dilate((sky > 0.5).astype(np.uint8), np.ones((2 * reach + 1, 2 * reach + 1), np.uint8)).astype(np.float32)
    a = np.clip(1 - dist / thr, 0, 1) * band * (cv2.GaussianBlur(core, (0, 0), 20) > 0.02)
    return np.clip(cv2.GaussianBlur(np.maximum(sky, a), (0, 0), 0.7), 0, 1).astype(np.float32)


DEFAULT_RENDERER = ("from scenekit import kit\nCAMERA = None\nCONFIG = {}\n\n\ndef render(F):\n"
                    "    return kit.default_render(F, CONFIG)\n")


def run(job, scene, plan, plates, log=None, preview=False):
    """preview=True packages only the plates made so far (the fast first wallpaper) and leaves the stage open; the
    full run re-packages every plate. Until the code model has written one, the renderer is kit.default_render."""
    log = log or job.log
    d = job.stage_dir(STAGE)
    if job.done(STAGE):
        return read_json(os.path.join(d, "manifest.json"))
    with Timer(job, STAGE + ("_preview" if preview else "")):
        pdir = os.path.join(d, "plates")
        os.makedirs(pdir, exist_ok=True)
        for k in plates["keys"]:
            shutil.copy2(job.path("03_plates", k + ".png"), os.path.join(pdir, k + ".png"))  # keeps mtime: 4K stays valid
        z = np.load(job.path("01_perception", "masks.npz"))
        L = {k: z[k].astype(np.float32) for k in z.files}
        dep = np.load(job.path("01_perception", "depth.npy")).astype(np.float32)
        bp = plates["base_phase"]
        day = cv2.imread(os.path.join(pdir, bp + "_day.png"))
        night = cv2.imread(os.path.join(pdir, bp + "_night.png"))
        allowed = np.clip(L.get("light_source", 0) + L.get("window", 0) + L.get("structure", 0) * 0.8
                          + L.get("roof", 0) * 0.3, 0, 1)
        allowed = allowed * (1 - np.clip(L["sky"], 0, 1)) * (1 - np.clip(L.get("water", 0), 0, 1))
        lights = light_mask(day, night, cv2.dilate(allowed, np.ones((5, 5), np.uint8)))
        log("  lights layer: %.2f%% of the frame" % (100 * float((lights > 0.3).mean())))
        layers = dict(sky=L["sky"], water=L.get("water", 0 * dep), ground=L.get("ground", 0 * dep),
                      roof=L.get("roof", 0 * dep), vegetation=L.get("vegetation", 0 * dep),
                      terrain=L.get("terrain", 0 * dep), structure=L.get("structure", 0 * dep), lights=lights, depth=dep)
        for k in plates["keys"]:
            layers["sky_" + k] = extend_sky(cv2.imread(os.path.join(pdir, k + ".png")), L["sky"])
        tmp = os.path.join(d, "layers.tmp.npz")         # atomic: the web preview may be reading the old one
        np.savez_compressed(tmp, **{k: np.asarray(v, np.float32).astype(np.float16) for k, v in layers.items()})
        os.replace(tmp, os.path.join(d, "layers.npz"))
        loc = plan["location"]
        cam = dict(view_az=180.0 if loc["lat"] >= 0 else 0.0, hfov=140.0,
                   horizon=float(scene["horizon"]) if scene["has_sky"] else 0.45)
        manifest = dict(
            location=dict(name=loc["name"], lat=loc["lat"], lon=loc["lon"], timezone=loc["timezone"]),
            phases=[dict(id=p["id"], name=p["name"], start_mmdd=p["start_mmdd"]) for p in plan["phases"]],
            base_phase=bp, snow_template=bool(plan["snow_cover_template"]), snow_min_depth_cm=plan["snow_min_depth_cm"],
            lights_on_below_sun_alt=plan["lights_on_below_sun_alt"], camera=cam, has_sky=scene["has_sky"],
            has_water=bool(np.asarray(layers["water"]).mean() > 0.005), has_lights=bool((lights > 0.3).mean() > 0.0002),
            plates=plates["keys"], style=scene["style"], summary=scene["summary"], preview=preview)
        write_json(os.path.join(d, "manifest.json"), manifest)
        kit_dst = os.path.join(d, "scenekit")
        if os.path.exists(kit_dst):
            shutil.rmtree(kit_dst)
        shutil.copytree(os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenekit"), kit_dst,
                        ignore=shutil.ignore_patterns("__pycache__"))
        cv2.imwrite(os.path.join(d, "lights_preview.jpg"),
                    (night.astype(np.float32) * (0.25 + 0.75 * lights[..., None])).astype(np.uint8))
        rp = os.path.join(d, "scene_renderer.py")
        if not os.path.exists(rp):
            open(rp, "w").write(DEFAULT_RENDERER)
        if not preview:
            job.mark_done(STAGE)
    return manifest


def refresh_sky(job, key):
    """Recompute one plate's sky matte inside layers.npz after the plate was replaced."""
    p = job.path(STAGE, "layers.npz")
    z = dict(np.load(p))
    z["sky_" + key] = extend_sky(cv2.imread(job.path(STAGE, "plates", key + ".png")),
                                 z["sky"].astype(np.float32)).astype(np.float16)
    tmp = job.path(STAGE, "layers.tmp.npz")
    np.savez_compressed(tmp, **z)
    os.replace(tmp, p)
