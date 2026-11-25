"""Runs a job end to end. Every stage is resumable (done-markers), so a crash or restart continues where it left off.

    .venv-gen/bin/python -m wallgen.pipeline --image path.png --location "Chicago, US" [--id name] [--full]
    .venv-gen/bin/python -m wallgen.pipeline --resume <job id>

Fast mode (default) is progressive: right after perception and the season plan it builds only TODAY's phase (plus the
reference pair), packages it with the reference renderer and renders "now" -> status preview_ready, usually within a
few minutes. Then it continues in the background with the rest of the year, the generated renderer code and the 4K
masters; each finished piece replaces what the preview used. Reviews are tiered (one quick screen, full multi-model
panel only when the screen is not clearly happy). --full is the original exhaustive run (every review by the panel).
"""
import argparse
import datetime as dt
import os
import time
from zoneinfo import ZoneInfo

import cv2
import numpy as np

from . import codegen, config, geo, imagegen, llm, package, perception, planner, plates
from .common import Job, Timer, read_json, write_json
from .live import WMO

FINAL = "06_finalize"
PREVIEW = "03p_preview"


def run(job, upscale=True, mode=None):
    t0 = time.time()
    mode = mode or job.meta().get("mode") or "fast"
    config.REVIEW_TIER = "tiered" if mode == "fast" else "full"
    fast = mode == "fast"
    job.update(status="running", error=None, mode=mode)
    # keep the Mac awake while the job runs (idle sleep froze a background build for 26 min); released on exit
    awake = None
    if os.path.exists("/usr/bin/caffeinate"):
        import subprocess
        awake = subprocess.Popen(["/usr/bin/caffeinate", "-i", "-w", str(os.getpid())])
    try:
        scene = perception.run(job)
        if not scene["affectable"]:
            job.update(status="nothing_to_change", message=scene["message"])
            job.log("STOP: " + scene["message"])
            return job.meta()
        if not scene["agreement"]["agreed"]:
            job.log("perception paths disagree (Jaccard %.2f) even after tie-breaks; continuing with the union"
                    % scene["agreement"]["jaccard"])
        plan = planner.run(job, scene)
        if fast:
            preview(job, scene, plan, t0, upscale=upscale)
        pl = plates.run(job, scene, plan, rounds=config.FAST_PLATE_ROUNDS if fast else None)
        manifest = package.run(job, scene, plan, pl)
        redo = lambda key, fix: plates.redo(job, scene, plan, key, fix)
        codegen.run(job, manifest, scene, plan, redo_plate=redo, fast=fast)
        finalize(job, manifest, upscale=upscale)
        job.update(status="done", total_seconds=round(time.time() - t0))
    except Exception as e:
        job.update(status="failed", error="%s: %s" % (type(e).__name__, e))
        job.log("FAILED: %r" % e)
        raise
    finally:
        llm.unload_all()
        if awake:
            awake.terminate()
    return job.meta()


def preview(job, scene, plan, t0, upscale=True):
    """First wallpaper fast: plates for the reference pair + the phase that is in season today, packaged with the
    reference renderer, rendered for this moment with live weather. Its plates are accepted into the shared plate
    state, so the full run does not redo them."""
    if job.done(PREVIEW):
        return read_json(job.path(PREVIEW, "preview.json"))
    d = job.stage_dir(PREVIEW)
    loc = plan["location"]
    now = dt.datetime.now(ZoneInfo(loc["timezone"]))
    cur = planner.phase_for(plan, now)["id"]
    bp = plan["base_phase_id"]
    keys = sorted({bp + "_day", bp + "_night", cur + "_day", cur + "_night"})
    job.log("== preview: today is in phase '%s'; making %s first ==" % (cur, ", ".join(keys)))
    pl = plates.run(job, scene, plan, only=keys, rounds=config.FAST_PLATE_ROUNDS)
    package.run(job, scene, plan, pl, preview=True)
    try:
        w = geo.current_weather(loc["lat"], loc["lon"])
    except Exception as e:
        job.log("  live weather unavailable (%s); rendering a fair-weather frame" % e)
        w = {}
    wx, inten = WMO.get(w.get("weather_code", 0), (None, 0.0))
    case = dict(id="now", when=now.strftime("%Y-%m-%d %H:%M"), cover=w.get("cloud_cover", 30) / 100.0, weather=wx,
                intensity=inten or 1.0, snow_depth_m=w.get("snow_depth"))
    pkg = job.path("04_package")
    out = codegen.run_cases(pkg, os.path.join(pkg, "scene_renderer.py"), [case], d)[0]
    if not out["ok"]:
        raise RuntimeError("preview render failed: %s" % out.get("error"))
    import cv2
    cv2.imwrite(os.path.join(d, "now.jpg"), cv2.imread(out["file"]), [cv2.IMWRITE_JPEG_QUALITY, 92])
    secs = round(time.time() - t0)
    info = dict(file=PREVIEW + "/now.png", jpg=PREVIEW + "/now.jpg", when=case["when"], phase=out.get("phase"),
                weather=wx, cover=case["cover"], seconds=secs, plates=keys)
    write_json(os.path.join(d, "preview.json"), info)
    job.update(preview=info)
    job.log("== PREVIEW READY in %ds (phase %s, %s) - the rest of the year continues in the background ==" % (
        secs, out.get("phase"), wx or "dry"))
    if upscale:         # the plates the live wallpaper uses right now get their 4K masters first
        os.makedirs(os.path.join(pkg, "plates4k"), exist_ok=True)
        for k in (cur + "_day", cur + "_night"):
            _upscale(job, pkg, k)
        job.log("  4K masters ready for %s" % cur)
    job.mark_done(PREVIEW)
    return info


def _upscale(job, pkg, k):
    """(Re)make a plate's 4K master if it is missing or older than the plate (loop B can replace plates)."""
    src, dst = os.path.join(pkg, "plates", k + ".png"), os.path.join(pkg, "plates4k", k + ".png")
    if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
        return False
    imagegen.upscale(src, dst, log=job.log)
    return True


def finalize(job, manifest, upscale=True):
    d = job.stage_dir(FINAL)
    if job.done(FINAL):
        return
    with Timer(job, FINAL):
        pkg = job.path("04_package")
        if upscale:
            os.makedirs(os.path.join(pkg, "plates4k"), exist_ok=True)
            for k in manifest["plates"]:
                _upscale(job, pkg, k)
        # a 24-hour strip of the base phase, rendered by the final renderer, for the web page
        cases = []
        res = read_json(job.path("05_renderer", "cases.json"), [])
        day = res[0]["when"][:10] if res else "2026-06-01"
        for h in range(0, 24, 2):
            cases.append(dict(id="strip_%02d" % h, when="%s %02d:00" % (day, h), cover=0.25, phase=manifest["base_phase"]))
        out = codegen.run_cases(pkg, os.path.join(pkg, "scene_renderer.py"), cases, os.path.join(d, "strip"))
        ims = [cv2.resize(cv2.imread(r["file"]), (480, 270)) for r in out if r["ok"]]
        if ims:
            rows = [np.hstack(ims[i:i + 6]) for i in range(0, len(ims) - len(ims) % 6 or 6, 6) if len(ims[i:i + 6]) == 6]
            if rows:
                cv2.imwrite(os.path.join(d, "day_strip.jpg"), np.vstack(rows))
        meta = job.meta()
        report = dict(job=job.id, location=manifest["location"], phases=manifest["phases"],
                      stages={k: dict(seconds=v.get("seconds"), status=v.get("status")) for k, v in meta.get("stages", {}).items()},
                      plates=read_json(job.path("03_plates", "plates.json")),
                      renderer=read_json(job.path("05_renderer", "result.json")),
                      perception=read_json(job.path("01_perception", "scene.json"), {}).get("agreement"),
                      render_seconds=[r.get("seconds") for r in out if r.get("ok")])
        write_json(os.path.join(d, "report.json"), report)
        job.mark_done(FINAL)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image")
    ap.add_argument("--location")
    ap.add_argument("--id")
    ap.add_argument("--resume")
    ap.add_argument("--no-upscale", action="store_true")
    ap.add_argument("--full", action="store_true", help="exhaustive mode: no preview, every review by the full panel")
    a = ap.parse_args()
    job = Job(a.resume) if a.resume else Job.create(a.image, a.location, a.id)
    run(job, upscale=not a.no_upscale, mode="full" if a.full else None)
    print(job.dir)


if __name__ == "__main__":
    main()
