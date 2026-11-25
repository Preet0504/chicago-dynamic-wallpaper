"""Calibrates the tier-1 review screen against verdicts the full panel already gave on a finished job.

    .venv-gen/bin/python -m wallgen.calibrate_screen chicago [--models qwen3.5:122b,inkling-2-mini:26b-a5b] [--limit N]

Ground truth = the full panel's pass/fail per plate attempt (03_plates/state.json) and per renderer frame
(05_renderer/history.json). Attempts the panel judged with a single model are marked "weak". The number that matters
is FALSE ACCEPTS: items the screen would wave through although the panel failed them (the screen can only accept;
everything else escalates to the panel, so a false reject only costs time).
"""
import argparse
import os
import time

import cv2
import numpy as np

from . import config, llm, review
from .common import Job, read_json, write_json
from .plates import load_masks, plate_conditions


def items(job):
    scene = read_json(job.path("01_perception", "scene.json"))
    plan = read_json(job.path("02_plan", "plan.json"))
    st = read_json(job.path("03_plates", "state.json"), {})
    out = []
    for k, p in st.get("plates", {}).items():
        for a in p.get("attempts", []):
            if "scores" not in a or not os.path.exists(job.path("03_plates", a["file"])):
                continue
            out.append(dict(kind="plate", id="%s/%s" % (k, os.path.basename(a["file"])), file=job.path("03_plates", a["file"]),
                            cond=plate_conditions(plan, k, scene), panel_pass=bool(a.get("passed")),
                            panel_mean=a["scores"]["mean"], weak=len(a["scores"].get("verdicts", [])) < 2,
                            ccond=dict(is_night=k.endswith("_night"), sun_alt=30 if k.endswith("_day") else -20)))
    for h in read_json(job.path("05_renderer", "history.json"), []) or []:
        for f in h["frames"]:
            fp = job.path("05_renderer", "v%d" % h["version"], f["id"] + ".png")
            if os.path.exists(fp):
                out.append(dict(kind="frame", id="v%d/%s" % (h["version"], f["id"]), file=fp, cond=f["cond"],
                                panel_pass=bool(f["passed"]), panel_mean=f["mean"], weak=False, ccond=None))
    return scene, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job")
    ap.add_argument("--models", default=",".join(dict.fromkeys([config.SCREEN_MODEL] + config.REVIEW_PANEL)))
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    job = Job(a.job)
    base = job.base()
    masks = load_masks(job)
    scene, its = items(job)
    if a.limit:
        its = its[:a.limit]
    rows = []
    for model in a.models.split(","):
        llm.unload_all()
        llm.chat_json(model, "Say {\"ok\": true}", {"type": "object", "properties": {"ok": {"type": "boolean"}},
                                                    "required": ["ok"]}, retries=0)      # load outside the timing
        for it in its:
            img = cv2.imread(it["file"])
            img = cv2.resize(img, (base.shape[1], base.shape[0]), interpolation=cv2.INTER_AREA)
            if it["ccond"]:
                _, chk = review.deterministic(img, base, masks, it["ccond"])
            else:
                chk = []
            t0 = time.time()
            s = review.screen(img, base, it["cond"], notes=scene["summary"][:300], model=model, log=print)
            secs = time.time() - t0
            acc = review.screen_accepts(s, chk)
            r = dict(model=model, id=it["id"], kind=it["kind"], panel_pass=it["panel_pass"], panel_mean=it["panel_mean"],
                     weak=it["weak"], screen_mean=review._mean(s) if s else None, verdict=s["verdict"] if s else None,
                     sev2=sum(i["severity"] >= 2 for i in s["issues"]) if s else None, checks=len(chk),
                     accept=acc, seconds=round(secs, 1))
            rows.append(r)
            print("%-28s %-40s panel %s %.2f | screen %s %s -> %s  %.0fs" % (
                model[:28], it["id"][:40], "PASS" if it["panel_pass"] else "fail", it["panel_mean"],
                r["screen_mean"], r["verdict"], "ACCEPT" if acc else "escalate", secs), flush=True)
    summary = {}
    for model in a.models.split(","):
        rs = [r for r in rows if r["model"] == model]
        fa = [r["id"] for r in rs if r["accept"] and not r["panel_pass"]]
        summary[model] = dict(
            n=len(rs), seconds_mean=round(float(np.mean([r["seconds"] for r in rs])), 1),
            accepted=sum(r["accept"] for r in rs), panel_passed=sum(r["panel_pass"] for r in rs),
            accepted_and_panel_passed=sum(r["accept"] and r["panel_pass"] for r in rs),
            false_accepts=fa, false_accepts_strong=[r["id"] for r in rs if r["accept"] and not r["panel_pass"] and not r["weak"]],
            failed_calls=sum(r["screen_mean"] is None for r in rs))
        print(model, summary[model])
    write_json(job.path("calibration.json"), dict(rows=rows, summary=summary,
                                                  thresholds=dict(mean=config.SCREEN_ACCEPT_MEAN, floor=config.SCREEN_ACCEPT_FLOOR)))
    llm.unload_all()


if __name__ == "__main__":
    main()
