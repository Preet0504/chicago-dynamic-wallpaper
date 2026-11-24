#!/usr/bin/env python3
"""Free local critic: scores renders with a vision model running in Ollama (no Claude usage).

  python3 tools/critic.py benchmark/run-4            # scores every item in manifest.json
  python3 tools/critic.py --image frame.png --cond "winter snow 22:00"
Options: --model qwen3.5:122b (default) | inkling-2-mini:26b-a5b, --items 1,5,9

Writes <run>/local_scores.json (same shape as the checker's scores.json + a defects list per item).
"""
import base64, json, os, sys, time, urllib.request
import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUBRIC = ["style_match", "composition_intact", "realism_rules", "structure_not_recolour",
          "light_consistency", "edges_artifacts", "depth_scale", "would_set_as_wallpaper"]
RULES = open(os.path.join(ROOT, "RULES.md")).read()
PROMPT = """You are a strict art director reviewing one frame of a painted anime-style desktop wallpaper.
The scene is always the same: Japanese lakeside town, five-tier pagoda left, snow-capped volcano centre, lake,
wooden pavilion with a hanging lantern right, stone walkway with two stone lanterns, a tree branch across the top right.
This frame should show: {cond}.

Realism rules the frame must satisfy:
{rules}

Score each criterion 1-5 (5 = would ship as-is, 3 = clearly flawed but readable, 1 = broken):
{rubric}
Then list the most important concrete defects (max 6, each under 25 words), each with where it is (e.g. "top-right branch",
"walkway", "left of the small pagoda") and why it looks wrong or fake. Look hard for: lights lit in daylight,
halos/fringes around silhouettes, smudges or smoke-like blobs, hard straight mask edges, recoloured-only
changes, AI-looking over-detailed texture, things floating, wrong season details.

Reply with ONLY a JSON object: {{"scores": {{criterion: int, ...}}, "defects": ["...", ...], "verdict": "accept"|"revise"|"reject"}}"""


def ask(model, img_path, cond, timeout=600):
    im = cv2.imread(img_path)
    h, w = im.shape[:2]
    s = 1600 / max(h, w)
    if s < 1:
        im = cv2.resize(im, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    b64 = base64.b64encode(cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, 92])[1]).decode()
    body = {"model": model, "stream": False, "format": "json", "think": False,
            "options": {"temperature": 0.1, "num_ctx": 16384},
            "messages": [{"role": "user", "images": [b64],
                          "content": PROMPT.format(cond=cond, rules=RULES, rubric=", ".join(RUBRIC))}]}
    req = urllib.request.Request("http://127.0.0.1:11434/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        txt = json.load(r)["message"]["content"]
    out = json.loads(txt[txt.index("{"):txt.rindex("}") + 1])
    sc = out.get("scores", {})
    out["scores"] = {k: int(max(1, min(5, round(float(sc.get(k, 3)))))) for k in RUBRIC}
    return out


def main(a):
    model = a[a.index("--model") + 1] if "--model" in a else "qwen3.5:122b"
    if "--image" in a:
        print(json.dumps(ask(model, a[a.index("--image") + 1], a[a.index("--cond") + 1]), indent=1))
        return
    run = a[0]
    man = json.load(open(os.path.join(run, "manifest.json")))
    only = set(int(x) for x in a[a.index("--items") + 1].split(",")) if "--items" in a else None
    items = []
    for it in man["items"]:
        if only and it["id"] not in only:
            continue
        scene = {"winter": "winter WITH snow lying on the ground (real snow cover)",
                 "winterbare": "winter with NO snow on the ground (bare, dormant)",
                 "autumnlate": "late November: mostly bare trees, few rust leaves",
                 }.get(it["season"], it["season"])
        cond = "%s; weather: %s; time: %s Chicago (judge sun/moon/lantern state by that time)" % (
            scene, it["weather"], it["when"])
        t0 = time.time()
        try:
            r = ask(model, it["full"], cond)
        except Exception as e:
            r = {"scores": {k: 0 for k in RUBRIC}, "defects": ["critic error: %s" % e], "verdict": "error"}
        r.update(id=it["id"], season=it["season"], weather=it["weather"], when=it["when"],
                 seconds=round(time.time() - t0, 1))
        items.append(r)
        avg = sum(r["scores"].values()) / len(RUBRIC)
        print("%2d %-10s %-13s %s  avg %.2f  %s" % (it["id"], it["season"], it["weather"], it["when"][11:], avg, r["verdict"]), flush=True)
    allv = [v for r in items for v in r["scores"].values() if v]
    res = dict(run=man.get("run"), model=model, overall=round(sum(allv) / max(1, len(allv)), 2), items=items)
    json.dump(res, open(os.path.join(run, "local_scores.json"), "w"), indent=1)
    print("overall %.2f (%s)" % (res["overall"], model))


if __name__ == "__main__":
    main(sys.argv[1:])
