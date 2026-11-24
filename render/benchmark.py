"""Benchmark harness: renders a fixed matrix of conditions into benchmark/run-N/ so every
iteration is scored on the same set. The checker agent scores them into scores.json.

  .venv/bin/python render/benchmark.py            # new run
  .venv/bin/python render/benchmark.py --summary  # print score table of all runs
"""
import os, sys, json, time, glob, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = os.path.join(ROOT, ".venv", "bin", "python")

# (season, weather, "YYYY-MM-DD HH:MM", extra args) — covers every season, weather and light state
MATRIX = [
    ("spring", "clear", "2026-04-15 06:05", []), ("spring", "partly_cloudy", "2026-04-15 13:00", []),
    ("spring", "clear", "2026-04-15 19:10", []), ("spring", "clear", "2026-04-15 22:00", []),
    ("spring", "rain", "2026-04-15 13:00", []), ("spring", "storm", "2026-04-15 21:00", []),
    ("spring", "fog", "2026-04-15 07:00", []),
    ("summer", "clear", "2026-07-15 13:00", []), ("summer", "partly_cloudy", "2026-07-15 19:50", []),
    ("summer", "clear", "2026-07-15 22:30", []), ("summer", "storm", "2026-07-15 16:00", []),
    ("summer", "rain", "2026-07-15 22:00", ["--intensity", "0.4"]),
    ("autumn", "clear", "2026-10-14 09:00", []), ("autumn", "partly_cloudy", "2026-10-14 17:45", []),
    ("autumn", "clear", "2026-10-14 22:00", []), ("autumn", "rain", "2026-10-14 18:20", []),
    ("autumn", "fog", "2026-10-14 13:00", []), ("autumnlate", "snow", "2026-11-20 13:00", ["--intensity", "0.4"]),
    ("winter", "clear", "2026-01-15 13:00", []), ("winter", "clear", "2026-01-15 16:45", []),
    ("winter", "clear", "2026-01-15 22:00", []), ("winter", "snow", "2026-01-15 22:00", []),
    ("winterbare", "overcast", "2026-01-15 11:00", []), ("winter", "fog", "2026-01-15 08:00", []),
]
RUBRIC = ["style_match", "composition_intact", "realism_rules", "structure_not_recolour",
          "light_consistency", "edges_artifacts", "depth_scale", "would_set_as_wallpaper"]


def new_run():
    os.makedirs(os.path.join(ROOT, "benchmark"), exist_ok=True)
    n = 1 + max([int(p.rsplit("-", 1)[1]) for p in glob.glob(os.path.join(ROOT, "benchmark", "run-*"))] or [0])
    out = os.path.join(ROOT, "benchmark", "run-%d" % n)
    os.makedirs(out)
    items = []
    for i, (season, weather, when, extra) in enumerate(MATRIX, 1):
        prefix = os.path.join(out, "%02d_%s_%s_%s" % (i, season, weather, when[11:].replace(":", "")))
        t0 = time.time()
        r = subprocess.run([PY, os.path.join(HERE, "preview.py"), season, weather, when, prefix] + extra,
                           capture_output=True, text=True)
        items.append(dict(id=i, season=season, weather=weather, when=when, args=extra,
                          full=prefix + "_full.png", crops=prefix + "_crops.png",
                          seconds=round(time.time() - t0, 1), ok=r.returncode == 0,
                          log=(r.stdout + r.stderr)[-400:]))
        print(items[-1]["id"], season, weather, when, "ok" if r.returncode == 0 else "FAILED", items[-1]["seconds"], "s")
    json.dump(dict(run=n, rubric=RUBRIC, items=items), open(os.path.join(out, "manifest.json"), "w"), indent=2)
    print(out)


def summary():
    for p in sorted(glob.glob(os.path.join(ROOT, "benchmark", "run-*", "scores.json")),
                    key=lambda s: int(s.split("run-")[1].split("/")[0])):
        s = json.load(open(p))
        allv = [v for it in s["items"] for k, v in it["scores"].items()]
        per = {k: round(sum(it["scores"][k] for it in s["items"]) / len(s["items"]), 2) for k in RUBRIC}
        print(os.path.basename(os.path.dirname(p)), "overall %.2f" % (sum(allv) / len(allv)), per)


if __name__ == "__main__":
    summary() if "--summary" in sys.argv else new_run()
