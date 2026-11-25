"""Original hand-built pipeline vs the new generated one, on the benchmark matrix of render/benchmark.py.

    .venv-gen/bin/python -m wallgen.compare chicago

Both render the same 24 moments at 3840x2160. Judging is blind and identical for both:
  - absolute: the review panel scores each frame on the rubric (same prompt, same reference = the base painting);
  - pairwise: each panel model sees both frames side by side in random order and picks the better one;
  - deterministic: structure kept vs the base painting, brightness by time of day, render time.
Writes compare/<job>/ : originals/, generated/, results.json, summary.md and side-by-side sheets.
"""
import concurrent.futures as cf
import json
import os
import random
import subprocess
import sys
import time

import cv2
import numpy as np

from . import codegen, config, llm, review
from .common import Job, jpeg_b64, read_json, write_json

sys.path.insert(0, os.path.join(config.ROOT, "render"))
from benchmark import MATRIX  # noqa: E402  (the original benchmark's 24 moments)

ORIG_SCRIPT = """
import sys, json, time, cv2
sys.path.insert(0, %r)
import timeofday as T
for it in json.load(open(sys.argv[1])):
    t0 = time.time()
    img, st = T.render(T.parse_when(it["when"]), it["cover"], season=it["season"], weather=it["wx"], intensity=it["intensity"])
    cv2.imwrite(it["out"], T.to8(img))
    print(json.dumps(dict(id=it["id"], seconds=round(time.time() - t0, 2), sun_alt=round(st["sun_alt"], 1))), flush=True)
"""

PAIR_SCHEMA = {"type": "object", "properties": {
    "better": {"type": "string", "enum": ["left", "right", "tie"]},
    "margin": {"type": "integer", "minimum": 0, "maximum": 3},
    "reason": {"type": "string"}}, "required": ["better", "margin", "reason"]}
PAIR_PROMPT = """Two candidate desktop wallpapers of the same painted place are shown side by side (LEFT and RIGHT
halves of the image). Both should show: {cond}. The second image is the original painting they were made from.
Which one is the better wallpaper for that moment: more believable light, sky, season and weather, cleaner (no
halos, smudges, seams, floating bits), and true to the original's composition and style? margin 0 = tie,
3 = clearly better. Judge only what you see."""


def cases():
    out = []
    for i, (season, weather, when, extra) in enumerate(MATRIX, 1):
        inten = float(extra[extra.index("--intensity") + 1]) if "--intensity" in extra else 1.0
        cover = {"clear": 0.0, "partly_cloudy": 0.35}.get(weather, 1.0)
        wx = weather if weather in ("rain", "storm", "fog", "snow") else None
        cond = "%s, %s local time, %s" % ({"autumnlate": "late autumn", "winterbare": "winter without snow on the ground",
                                            "winter": "winter with snow lying on the ground"}.get(season, season),
                                           when, weather.replace("_", " "))
        out.append(dict(id="%02d_%s_%s" % (i, season, weather), season=season, weather=weather, when=when, cover=cover,
                        wx=wx, intensity=inten, cond=cond, snow_depth_m=0.05 if season == "winter" else 0.0))
    return out


def render_original(items, d):
    os.makedirs(os.path.join(d, "originals"), exist_ok=True)
    todo = [dict(it, out=os.path.join(d, "originals", it["id"] + ".png")) for it in items]
    todo = [t for t in todo if not os.path.exists(t["out"])]
    secs = read_json(os.path.join(d, "orig_seconds.json"), {}) or {}
    if todo:
        sp = os.path.join(d, "orig_items.json")
        write_json(sp, todo)
        script = os.path.join(d, "render_orig.py")
        open(script, "w").write(ORIG_SCRIPT % os.path.join(config.ROOT, "render"))
        p = subprocess.run([os.path.join(config.ROOT, ".venv", "bin", "python"), script, sp], capture_output=True,
                           text=True, cwd=os.path.join(config.ROOT, "render"))
        for line in p.stdout.splitlines():
            if line.startswith("{"):
                r = json.loads(line)
                secs[r["id"]] = r
        if p.returncode:
            raise RuntimeError(p.stderr[-1500:])
        write_json(os.path.join(d, "orig_seconds.json"), secs)
    return secs


def render_new(job, items, d):
    pkg = job.path("04_package")
    cs = [dict(id=it["id"], when=it["when"], cover=it["cover"], weather=it["wx"], intensity=it["intensity"],
               snow_depth_m=it["snow_depth_m"]) for it in items]
    have = all(os.path.exists(os.path.join(d, "generated", c["id"] + ".png")) for c in cs)
    if have and read_json(os.path.join(d, "new_seconds.json")):
        return read_json(os.path.join(d, "new_seconds.json"))
    res = codegen.run_cases(pkg, os.path.join(pkg, "scene_renderer.py"), cs, os.path.join(d, "generated"))
    bad = [r for r in res if not r["ok"]]
    if bad:
        raise RuntimeError("generated renderer failed: %s" % bad[0])
    secs = {r["id"]: r for r in res}
    write_json(os.path.join(d, "new_seconds.json"), secs)
    return secs


def pairwise(model, a, b, base, cond, log):
    h = 1080
    sa = cv2.resize(a, (int(a.shape[1] * h / a.shape[0]), h), interpolation=cv2.INTER_AREA)
    sb = cv2.resize(b, (int(b.shape[1] * h / b.shape[0]), h), interpolation=cv2.INTER_AREA)
    pair = np.hstack([sa, np.full((h, 16, 3), 255, np.uint8), sb])
    out, _ = llm.chat_json(model, PAIR_PROMPT.format(cond=cond), PAIR_SCHEMA,
                           images=[jpeg_b64(pair, 2400), jpeg_b64(base, 1024)], temperature=0.1, log=log)
    return out


def main(job_id, models=None):
    job = Job(job_id)
    d = os.path.join(config.ROOT, "compare", job_id)
    os.makedirs(d, exist_ok=True)
    log = lambda m: print(time.strftime("%H:%M:%S"), m, flush=True)
    items = cases()
    log("rendering %d moments with the ORIGINAL renderer…" % len(items))
    osec = render_original(items, d)
    log("rendering %d moments with the GENERATED renderer…" % len(items))
    nsec = render_new(job, items, d)
    base = cv2.imread(os.path.join(config.ROOT, "templates", "spring_clear_night.png"))
    z = np.load(job.path("04_package", "layers.npz"))
    masks = {k: cv2.resize(z[k].astype(np.float32), (base.shape[1], base.shape[0])) for k in ("sky", "water", "structure")}
    masks["light_source"] = cv2.resize(z["lights"].astype(np.float32), (base.shape[1], base.shape[0]))
    llm.unload_all()
    results = read_json(os.path.join(d, "results.json"), {}) or {}
    rng = random.Random(7)
    for it in items:
        if it["id"] in results and "pair" in results[it["id"]]:
            continue
        r = dict(cond=it["cond"])
        for name, folder, secs in (("original", "originals", osec), ("generated", "generated", nsec)):
            img = cv2.imread(os.path.join(d, folder, it["id"] + ".png"))
            small = cv2.resize(img, (base.shape[1], base.shape[0]), interpolation=cv2.INTER_AREA)
            sun = secs[it["id"]].get("sun_alt", 0)
            m, chk = review.deterministic(small, base, masks, dict(is_night=sun < -6, sun_alt=sun, weather=it["wx"]))
            pr = review.panel(img, base, it["cond"], notes="Japanese lakeside town with pagoda, volcano, lake, "
                              "pavilion with hanging lantern, stone lanterns, a tree branch top right.", log=log)
            clusters, agg = review.merge(pr, chk)
            r[name] = dict(scores=agg, metrics=m, issues=review.summarize(clusters, 5), seconds=secs[it["id"]]["seconds"],
                           per_model={p["model"]: p["scores"] for p in pr})
        a = cv2.imread(os.path.join(d, "originals", it["id"] + ".png"))
        b = cv2.imread(os.path.join(d, "generated", it["id"] + ".png"))
        votes = []
        for mdl in config.REVIEW_PANEL:
            flip = rng.random() < 0.5                     # random side, so position bias cancels
            left, right = (b, a) if flip else (a, b)
            v = pairwise(mdl, left, right, base, it["cond"], log)
            winner = {"left": "generated" if flip else "original", "right": "original" if flip else "generated",
                      "tie": "tie"}[v["better"]]
            votes.append(dict(model=mdl, winner=winner, margin=v["margin"], reason=v["reason"], generated_on="left" if flip else "right"))
        r["pair"] = votes
        results[it["id"]] = r
        write_json(os.path.join(d, "results.json"), results)
        log("%-28s orig %.2f  new %.2f  votes %s" % (it["id"], r["original"]["scores"]["mean"], r["generated"]["scores"]["mean"],
                                                    ",".join(v["winner"][0] for v in votes)))
    llm.unload_all()
    sheets(items, d)
    summary(items, results, d)


def sheets(items, d):
    for s in range(0, len(items), 6):
        rows = []
        for it in items[s:s + 6]:
            a = cv2.resize(cv2.imread(os.path.join(d, "originals", it["id"] + ".png")), (960, 540), interpolation=cv2.INTER_AREA)
            b = cv2.resize(cv2.imread(os.path.join(d, "generated", it["id"] + ".png")), (960, 540), interpolation=cv2.INTER_AREA)
            for im, lab in ((a, "ORIGINAL"), (b, "GENERATED")):
                cv2.rectangle(im, (0, 0), (520, 36), (0, 0, 0), -1)
                cv2.putText(im, "%s  %s" % (lab, it["id"][:26]), (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            rows.append(np.hstack([a, np.full((540, 10, 3), 255, np.uint8), b]))
        cv2.imwrite(os.path.join(d, "sheet_%d.jpg" % (s // 6 + 1)), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 88])


def summary(items, res, d):
    R = config.RUBRIC
    mean = lambda k, name: round(float(np.mean([res[i["id"]][name]["scores"]["per_metric"][k] for i in items])), 2)
    tot = {n: round(float(np.mean([res[i["id"]][n]["scores"]["mean"] for i in items])), 2) for n in ("original", "generated")}
    votes = [v for i in items for v in res[i["id"]]["pair"]]
    wins = {w: sum(1 for v in votes if v["winner"] == w) for w in ("original", "generated", "tie")}
    t = {n: round(float(np.mean([res[i["id"]][n]["seconds"] for i in items])), 2) for n in ("original", "generated")}
    er = {n: round(float(np.mean([res[i["id"]][n]["metrics"].get("edge_recall_static", 1) for i in items])), 3)
          for n in ("original", "generated")}
    lines = ["# Original vs generated pipeline (Chicago, %d benchmark moments)" % len(items), "",
             "| | original | generated |", "|---|---|---|",
             "| panel mean (1-5) | %.2f | %.2f |" % (tot["original"], tot["generated"])]
    lines += ["| %s | %.2f | %.2f |" % (k, mean(k, "original"), mean(k, "generated")) for k in R]
    lines += ["| structure kept (edge recall vs painting) | %.3f | %.3f |" % (er["original"], er["generated"]),
              "| render time per frame (s) | %.2f | %.2f |" % (t["original"], t["generated"]), "",
              "Blind pairwise votes (%d = %d moments x %d models): original %d, generated %d, tie %d" % (
                  len(votes), len(items), len(config.REVIEW_PANEL), wins["original"], wins["generated"], wins["tie"]), "",
              "| moment | orig | gen | votes |", "|---|---|---|---|"]
    for i in items:
        r = res[i["id"]]
        lines.append("| %s | %.2f | %.2f | %s |" % (i["id"], r["original"]["scores"]["mean"], r["generated"]["scores"]["mean"],
                                                   ", ".join("%s:%s" % (v["model"].split(":")[0], v["winner"]) for v in r["pair"])))
    open(os.path.join(d, "summary.md"), "w").write("\n".join(lines) + "\n")
    write_json(os.path.join(d, "summary.json"), dict(panel_mean=tot, wins=wins, seconds=t, edge_recall=er,
                                                     per_metric={k: dict(original=mean(k, "original"), generated=mean(k, "generated")) for k in R}))
    print("\n".join(lines))


if __name__ == "__main__":
    main(sys.argv[1])
