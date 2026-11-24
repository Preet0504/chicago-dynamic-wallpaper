"""Late-autumn template (Chicago, Nov 15-30): templates/autumnlate_clear_night.png (+ _sky.png).

  .venv/bin/python render/season_autumnlate.py                 # rebuild from saved AI outputs
  .venv/bin/python render/season_autumnlate.py --tiles DIR     # write the 2x guide tiles fed to the AI

Same pipeline as season_summer.py (deterministic from templates/ai/):
  1. Branch: FLUX.2-klein edit of the spring painting (templates/ai/autumnlate_edit_branch.png): almost
     bare twigs with a few last rust/brown leaves; used through a soft, de-haloed colour matte only.
  2. Shrubs -> browned, thinning bushes; walkway -> scattered leaf litter. Procedural guide, then klein
     img2img (strength 0.4, 2x tiles) -> templates/ai/autumnlate_tile_{BL,BR}.png, composited only in
     the shrub masks, the blossom box behind the pavilion railing, and the walkway.
       mflux-generate-flux2 --model flux2-klein-4b -q 8 --image tile_K.png 0.4 --width 1792 --height 1008
       --steps 10 --seed 21 --prompt-file templates/ai/autumnlate_tile_K.prompt.txt
  3. No snow; volcano keeps its painted snow cap; everything else pixel-identical to spring.
"""
import os, sys
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import season_winter as WS
import season_summer as SU
from season_winter import (W, H, poly, dil, soft, lum, blend, noise, Scene, clean_sky, branch_layer,
                           depink, PATH, ROOT, AI)

NAME = "autumnlate"
TILES = SU.TILES
TW, TH = WS.TW, WS.TH
BUSH_DARK = np.array([0.06, 0.09, 0.14], np.float32)     # BGR, night: dark umber
BUSH_LIT = np.array([0.13, 0.24, 0.40], np.float32)      # rust, moon/lantern-lit
LITTER = [np.array(c, np.float32) for c in ([0.10, 0.22, 0.42], [0.08, 0.15, 0.30], [0.12, 0.20, 0.30])]


def paths(name):
    return (os.path.join(ROOT, "templates", "%s_clear_night.png" % name),
            os.path.join(AI, "%s_edit_branch.png" % name), os.path.join(AI, "%s_tile_%%s.png" % name))


def litter(S, g, density=1.0, seed=40):
    """Fallen leaves on the walkway: small, flat-lying ovals (foreshortened), denser along the railing and
    edges, lit from above with a dark side; the AI pass turns them into painted leaves."""
    path = poly([PATH]) & ~dil(poly(WS.LANTERN_BODIES), 3)
    rng = np.random.default_rng(seed)
    lay = np.zeros((H, W), np.float32); col = np.zeros((H, W, 3), np.float32)
    ys, xs = np.where(path)
    n = int(420 * density)
    rb = np.array(WS.RAIL_BASE, np.float32)
    for _ in range(n):
        i = rng.integers(len(xs)); x, y = xs[i], ys[i]
        near_rail = y - np.interp(x, rb[:, 0], rb[:, 1])
        if near_rail > 20 and rng.random() < 0.55:      # thinner out in the open middle of the path
            continue
        sc = 0.6 + 0.5 * (y - 820) / 120
        a, b = max(2, int(rng.uniform(3, 6) * sc)), max(1, int(rng.uniform(1.2, 2.5) * sc))
        c = LITTER[rng.integers(3)] * rng.uniform(0.8, 1.2)
        m = np.zeros((H, W), np.uint8)
        cv2.ellipse(m, (int(x), int(y)), (a, b), rng.uniform(-35, 35), 0, 360, 1, -1)
        mm = m.astype(bool)
        lay[mm] = 1; col[mm] = c
    sh = np.clip(1.0 - 0.35 * (S.yy % 3 == 0), 0.6, 1)       # slight texture
    return blend(g, col * sh[..., None], soft(lay > 0, 0.5) * path), lay > 0


def build_guide(S, name=NAME, bush=(BUSH_DARK, BUSH_LIT), do_litter=True):
    out, edit, tile = paths(name)
    g, holes = clean_sky(S)
    g, _ = branch_layer(S, g, edit, 1.0, soft_edge=True)
    sh, bp = SU.shrub_mask(S, holes)
    L = S.L
    dt = cv2.distanceTransform(sh.astype(np.uint8), cv2.DIST_L2, 5)
    hgt = np.sqrt(np.minimum(dt, 30) / 30.0) * 22 + cv2.GaussianBlur(L, (0, 0), 3.0) * 60 * np.clip(dt / 8, 0, 1)
    hgt = cv2.GaussianBlur(hgt, (0, 0), 2)
    gy, gx = np.gradient(hgt)
    n = np.sqrt(gx ** 2 + gy ** 2 + 1.0)
    shade = np.clip((0.45 * gx + 0.75 * gy + 0.5) / n, 0, 1)
    leafy = np.clip(shade + noise(12, 1.2, 0.22), 0, 1)
    bsh = blend(bush[0], bush[1], leafy)
    g = blend(g, bsh, soft(sh, 0.8))
    Lb = cv2.GaussianBlur(L, (0, 0), 1)
    t = np.clip(Lb[bp] * 1.6, 0, 1)[:, None]
    g[bp] = bush[0] * (1 - t) + bush[1] * t
    p2 = (S.Hh > 195) & (S.Hh < 245) & (S.S > 40) & (S.V > 70)
    pet = dil((S.pink | p2) & poly([PATH]), 3) & ~S.warm
    g8 = (np.clip(g, 0, 1) * 255 + 0.5).astype(np.uint8)
    g = cv2.inpaint(g8, pet.astype(np.uint8), 4, cv2.INPAINT_TELEA).astype(np.float32) / 255
    lit = np.zeros((H, W), bool)
    if do_litter:
        g, lit = litter(S, g)
    return np.clip(g, 0, 1), dict(sh=sh, bp=bp, holes=holes, pet=pet, lit=lit)


def compose(S, guide, gm, name=NAME, path_from_ai=True, ai_tint=(1.0, 1.0, 1.0)):
    out, edit, tile = paths(name)
    SU.TILE = tile
    ai, wsum = SU.merge_tiles(guide)
    ai = ai * np.array(ai_tint, np.float32)
    ok = (wsum > 0.5).astype(np.float32)
    take = soft(dil(gm["sh"], 5), 1.5) * ok
    take = np.maximum(take, soft(poly([SU.BEHIND]), 3.0) * ok)
    path = poly([PATH]) & ~dil(poly(WS.LANTERN_BODIES), 3)
    if path_from_ai:
        take = np.maximum(take, soft(path, 1.5) * ok)
    else:
        take = np.maximum(take, soft(dil(gm["pet"], 3), 1.5) * ok)
    # late November: the AI's shrubs come out October-orange -> browner, duller
    gray = lum(ai)[..., None]
    ai = ai * 0.6 + gray * np.array([0.32, 0.38, 0.42], np.float32) / 0.37 * 0.4 * 0.95
    img = blend(guide, ai, take)
    keep = dil(S.warm, 3) | dil(S.sky & ~S.tz, 2) | S.water
    _, bm = branch_layer(S, img, edit, 1.0, soft_edge=True)
    img = depink(img, keep)
    band = poly([PATH, WS.RAIL_ENV]) & ~dil(S.warm, 3)
    img = blend(img, depink(img, ~band), band.astype(np.float32))
    near = dil(gm["sh"] | gm["bp"], 25) & ~dil(S.warm, 3)
    img = blend(img, depink(img, ~near), near.astype(np.float32))
    skym = (S.tod_sky | gm["holes"] | (S.tz & ~S.pav)) & (bm < 0.35)
    n, lab, st, _ = cv2.connectedComponentsWithStats((~skym).astype(np.uint8), connectivity=4)
    isl = np.zeros(n, bool); isl[1:] = (st[1:, cv2.CC_STAT_AREA] < 400) & (st[1:, cv2.CC_STAT_TOP] + st[1:, cv2.CC_STAT_HEIGHT] < 620)
    skym |= isl[lab] & (bm < 0.35)
    return np.clip(img, 0, 1), skym


def run(a, name=NAME, guide_fn=build_guide, compose_fn=compose):
    S = Scene()
    guide, gm = guide_fn(S)
    if "--tiles" in a:
        d = a[a.index("--tiles") + 1]; os.makedirs(d, exist_ok=True)
        g8 = (guide * 255 + 0.5).astype(np.uint8)
        cv2.imwrite(os.path.join(d, "guide.png"), g8)
        for k, (x, y) in TILES.items():
            cv2.imwrite(os.path.join(d, "tile_%s.png" % k),
                        cv2.resize(g8[y:y + TH, x:x + TW], (2 * TW, 2 * TH), interpolation=cv2.INTER_LANCZOS4))
        return
    img, skym = compose_fn(S, guide, gm)
    out = a[a.index("--out") + 1] if "--out" in a else paths(name)[0]
    cv2.imwrite(out, (img * 255 + 0.5).astype(np.uint8))
    cv2.imwrite(out.replace(".png", "_sky.png"), skym.astype(np.uint8) * 255)
    print("wrote", out)


if __name__ == "__main__":
    run(sys.argv[1:])
