#!/usr/bin/env python3
"""Repaint ONE region of a season template with local AI (Qwen-Image-Edit 2.1 via mflux), at 4K detail,
try several seeds, keep the best one according to the local critic, and write it back into BOTH the
base template (templates/<name>.png, 1672x941) and its 4K master (templates/4k/<name>.png).
Everything outside the region stays pixel-identical. Free and offline.

  python3 tools/ai_region_edit.py --template winter_clear_night \
      --box 780,820,700,121 --prompt "..." --seeds 1,2,3 [--mask regionmask.png] [--dry]

--box     x,y,w,h in BASE px (1672x941 coords, see .claude/skills/wallpaper-painter/SKILL.md)
--mask    optional black/white PNG (base px, full frame) limiting the change inside the box
--feather blend softness in base px (default 6)
--steps   diffusion steps (default 20)
--dry     write candidates to logs/ai_edit/ only; don't touch the template
Every run appends a line to templates/ai/edits.jsonl (prompt, seed, box, chosen) so results are reproducible.
"""
import argparse, json, os, shutil, subprocess, sys, time
import cv2, numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BW, BH, HW, HH = 1672, 941, 3840, 2160
K = HW / BW
MFLUX = os.path.expanduser("~/.local/bin/mflux-generate-qwen-2.1-edit")
sys.path.insert(0, os.path.join(ROOT, "tools"))


def run_edit(src, out, prompt, seed, w, h, steps):
    cmd = [MFLUX, "-q", "8", "--image-paths", src, "--width", str(w), "--height", str(h),
           "--steps", str(steps), "--seed", str(seed), "--prompt", prompt, "--output", out]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def shift(a, b):
    ga = cv2.Canny(cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), 50, 150).astype(np.float32)
    gb = cv2.Canny(cv2.cvtColor(b, cv2.COLOR_BGR2GRAY), 50, 150).astype(np.float32)
    (dx, dy), _ = cv2.phaseCorrelate(cv2.GaussianBlur(ga, (0, 0), 3), cv2.GaussianBlur(gb, (0, 0), 3))
    return float(np.hypot(dx, dy))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True)
    ap.add_argument("--box", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--mask")
    ap.add_argument("--feather", type=float, default=6)
    ap.add_argument("--steps", type=int, default=20)
    ap.add_argument("--cond", default="")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    name = a.template.replace(".png", "")
    base_p = os.path.join(ROOT, "templates", name + ".png")
    hi_p = os.path.join(ROOT, "templates", "4k", name + ".png")
    base = cv2.imread(base_p)
    hi = cv2.imread(hi_p) if os.path.exists(hi_p) else cv2.resize(base, (HW, HH), interpolation=cv2.INTER_LANCZOS4)
    x, y, w, h = [int(v) for v in a.box.split(",")]
    x, y = max(0, x), max(0, y)
    w, h = min(w, BW - x), min(h, BH - y)
    X, Y = int(round(x * K)), int(round(y * K))
    W = (HW if x + w >= BW else int(round((x + w) * K))) - X      # boxes touching an edge reach it in 4K too
    H = (HH if y + h >= BH else int(round((y + h) * K))) - Y
    crop = hi[Y:Y + H, X:X + W].copy()
    # model size: long side ~1536, multiples of 32
    s = 1536 / max(W, H)
    mw, mh = max(256, int(W * s) // 32 * 32), max(256, int(H * s) // 32 * 32)
    work = os.path.join(ROOT, "logs", "ai_edit", "%s_%d" % (name, int(time.time())))
    os.makedirs(work, exist_ok=True)
    src = os.path.join(work, "crop.png")
    cv2.imwrite(src, cv2.resize(crop, (mw, mh), interpolation=cv2.INTER_AREA))

    # blend mask (4K box coords)
    m = np.zeros((BH, BW), np.float32)
    m[y:y + h, x:x + w] = 1
    if a.mask:
        m *= (cv2.imread(a.mask, 0) > 127).astype(np.float32)
    m = cv2.erode(m, np.ones((3, 3), np.uint8))
    m = cv2.GaussianBlur(m, (0, 0), a.feather)
    mh4 = cv2.resize(m, (HW, HH), interpolation=cv2.INTER_LINEAR)[Y:Y + H, X:X + W][..., None]

    import critic
    best = None
    for seed in [int(v) for v in a.seeds.split(",")]:
        out = os.path.join(work, "seed%d.png" % seed)
        t0 = time.time()
        run_edit(src, out, a.prompt, seed, mw, mh, a.steps)
        ed = cv2.resize(cv2.imread(out), (W, H), interpolation=cv2.INTER_LANCZOS4)
        drift = shift(crop, ed)
        cand = (crop * (1 - mh4) + ed * mh4).astype(np.uint8)
        prev = os.path.join(work, "cand%d.png" % seed)
        cv2.imwrite(prev, np.hstack([crop, cand]))
        score = -1.0
        if drift <= 6:
            r = critic.ask("qwen3.5:122b", prev, "LEFT is the original region, RIGHT the edited one. Judge ONLY the "
                           "RIGHT half for: %s. Edit goal: %s" % (a.cond or name, a.prompt))
            score = sum(r["scores"].values()) / len(r["scores"])
        print("seed %d: drift %.1fpx  critic %.2f  (%.0fs)" % (seed, drift, score, time.time() - t0), flush=True)
        if best is None or score > best[0]:
            best = (score, seed, cand, drift)

    score, seed, cand, drift = best
    rec = dict(time=time.strftime("%Y-%m-%dT%H:%M:%S"), template=name, box=[x, y, w, h], prompt=a.prompt,
               seed=seed, steps=a.steps, model="qwen-image-edit-2.1 q8", critic=round(score, 2),
               drift_px=round(drift, 1), mask=a.mask, applied=not a.dry and score > 0)
    if a.dry or score <= 0:
        print("not applied (dry run or all candidates drifted). candidates in", work)
    else:
        for p in (base_p, hi_p):
            if os.path.exists(p):
                bak = os.path.join(ROOT, "templates", "ai", "backup")
                os.makedirs(bak, exist_ok=True)
                shutil.copy(p, os.path.join(bak, "%s_%s%s" % (name, rec["time"].replace(":", ""),
                                                              "_4k.png" if "4k" in p else ".png")))
        hi[Y:Y + H, X:X + W] = cand
        cv2.imwrite(hi_p, hi)
        small = cv2.resize(cand, (w, h), interpolation=cv2.INTER_AREA).astype(np.float32)
        mb = m[y:y + h, x:x + w][..., None]
        base[y:y + h, x:x + w] = (base[y:y + h, x:x + w] * (1 - mb) + small * mb).astype(np.uint8)
        cv2.imwrite(base_p, base)
        shutil.copy(os.path.join(work, "seed%d.png" % seed), os.path.join(ROOT, "templates", "ai",
                    "%s_edit_%s.png" % (name, rec["time"].replace(":", ""))))
        print("applied seed %d (critic %.2f) to %s + 4K master" % (seed, score, name))
    with open(os.path.join(ROOT, "templates", "ai", "edits.jsonl"), "a") as f:
        f.write(json.dumps(rec) + "\n")


if __name__ == "__main__":
    main()
