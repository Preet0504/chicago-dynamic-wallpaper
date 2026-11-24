"""Summer season template: templates/summer_clear_night.png, derived from the spring painting.

  .venv/bin/python render/season_summer.py                 # rebuild the template from saved AI outputs
  .venv/bin/python render/season_summer.py --tiles DIR     # write the 2x guide tiles that were fed to the AI

How it was made (deterministic from the files in templates/ai/):
  1. A FLUX.2-klein edit of the spring painting (templates/ai/summer_edit_branch.png) supplies the
     leafy branch (dense green leaves growing on visible twigs). Only the branch is used, via a soft
     colour matte inside the tree zone; blossoms, old branch and every falling petal are removed and
     the sky is rebuilt from the original sky (with its own star texture).
  2. Shrubs: a procedural guide (rounded leafy bushes, lit from the moon side) is run through
     FLUX.2-klein img2img at strength 0.4 on 2x tiles -> templates/ai/summer_tile_{BL,BR}.png, then
     mflux-generate-flux2 --model flux2-klein-4b -q 8 --image tile_K.png 0.4 --width 1792 --height 1008
     --steps 10 --seed 21 (BL: seed 24) --prompt-file templates/ai/summer_tile_K.prompt.txt
     composited only inside the shrub masks.
  3. Volcano: snow kept only as streaks near the summit; the rest of the slope is re-shaded as bare
     rock using the painting's own ridge texture (shape untouched).
  4. Petals lying on the walkway are inpainted away. Everything else is pixel-identical to spring.
"""
import os, sys
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import season_winter as WS
from season_winter import (W, H, poly, dil, soft, lum, blend, noise, Scene, clean_sky, branch_layer,
                           depink, PATH, ROOT, AI)

OUT = os.path.join(ROOT, "templates", "summer_clear_night.png")
EDIT = os.path.join(AI, "summer_edit_branch.png")
TILE = os.path.join(AI, "summer_tile_%s.png")
TILES = {"BL": (0, 437), "BR": (776, 437)}
TW, TH = WS.TW, WS.TH
# volcano (base px): summit and the slope polygon that may be re-shaded
PEAK = (505, 510)
MOUNTAIN = [(236, 642), (300, 610), (380, 568), (440, 535), (480, 514), (530, 510), (580, 530), (650, 560),
            (720, 588), (800, 606), (880, 618), (960, 626), (1010, 632), (1010, 668), (236, 668)]

# blossom tree seen through the pavilion railing (AI repaints this whole box, railing included)
BEHIND = [(1385, 600), (1672, 560), (1672, 745), (1385, 745)]
# leaves of the AI branch are lime at night -> deeper, bluer green so the day plate stays natural
LEAF_GAIN = np.array([0.80, 0.66, 0.48], np.float32)
LEAF_DARK = np.array([0.10, 0.17, 0.07], np.float32)   # BGR, night
LEAF_LIT = np.array([0.22, 0.42, 0.20], np.float32)


def shrub_mask(S, holes):
    p2 = (S.Hh > 195) & (S.Hh < 245) & (S.S > 40) & (S.V > 70)
    purp0 = dil(S.pink, 15) & (S.Hh > 188) & (S.Hh < 250) & (S.S > 40) & (S.V > 60) & (S.xx < 120)
    sh = (S.pink | purp0 | (p2 & dil(S.pink, 7))) & ~S.tz & ~S.lant & ~S.water & ~holes
    sh = cv2.morphologyEx(sh.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    sh = (cv2.GaussianBlur(sh.astype(np.float32), (0, 0), 3) > 0.45) & ~S.warm & ~poly([PATH])
    sh &= (S.xx < 1385) | dil(S.pink, 3)
    # the blossom tree at the far left (behind the pagoda eaves): everything that is not sky/pagoda
    tiers = dil(poly(WS.PAGODA_TIERS) | poly([WS.M.PAGODA]) | poly(WS.FG_ROOF), 2)
    box = (S.xx < 95) & (S.yy > 480) & (S.yy < 790)
    blos = box & (S.Hh > 178) & (S.Hh < 252) & (S.S > 25) & (S.V > 35) & ~tiers
    blos = cv2.morphologyEx(blos.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((17, 17), np.uint8))
    blos = cv2.morphologyEx(blos, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)).astype(bool)
    sh |= blos & box & ~tiers & ~holes & ~S.warm
    behind = poly([BEHIND])
    bp = behind & (S.Hh > 180) & (S.Hh < 240) & (S.S > 30) & ~S.warm & ~sh & ~S.lant
    return sh, bp


def mountain(S, g):
    """Snow only as streaks near the summit; lower slopes become bare dark rock (same ridges)."""
    o, L = S.o, S.L
    mt = (dil(poly([MOUNTAIN]), 31) & ~S.tod_sky & (S.yy > PEAK[1] - 6) & (S.xx > 230) & (S.xx < 1010)) | poly([MOUNTAIN])
    snowpx = mt & (L > 0.19)
    rock_ref = mt & (S.yy > 600) & (L < 0.25)
    rock = np.array([np.median(o[..., c][rock_ref]) for c in range(3)], np.float32)
    # snow line: ~28 px below the summit, ragged; streaks (gullies) reach a bit further down
    line = PEAK[1] + 26 + noise(11, 8, 6.0)
    hp = L - cv2.GaussianBlur(L, (0, 0), 3)
    streak = (S.yy < line + 40 + noise(13, 3, 12.0)) & (hp > 0.05)
    streak = cv2.morphologyEx(streak.astype(np.uint8), cv2.MORPH_OPEN, np.ones((7, 1), np.uint8)).astype(bool)
    streak &= ~dil(~mt, 9) | (S.yy < PEAK[1] + 12)
    keep = (S.yy < line) | streak
    keep = soft(keep, 1.5)
    # rock shading carries the painting's ridge texture
    shade = np.clip((cv2.GaussianBlur(L, (0, 0), 1.2) / (cv2.GaussianBlur(L, (0, 0), 10) + 1e-3)) ** 0.45, 0.65, 1.35)
    rockimg = rock[None, None, :] * shade[..., None] * 1.05
    a = soft(snowpx, 0.8) * (1 - keep)
    return blend(g, rockimg, a), a


def build_guide(S):
    g, holes = clean_sky(S)
    g, _ = branch_layer(S, g, EDIT, LEAF_GAIN, soft_edge=True)
    sh, bp = shrub_mask(S, holes)
    L = S.L
    dt = cv2.distanceTransform(sh.astype(np.uint8), cv2.DIST_L2, 5)
    hgt = np.sqrt(np.minimum(dt, 30) / 30.0) * 22 + cv2.GaussianBlur(L, (0, 0), 3.0) * 60 * np.clip(dt / 8, 0, 1)
    hgt = cv2.GaussianBlur(hgt, (0, 0), 2)
    gy, gx = np.gradient(hgt)
    n = np.sqrt(gx ** 2 + gy ** 2 + 1.0)
    shade = np.clip((0.45 * gx + 0.75 * gy + 0.5) / n, 0, 1)
    leafy = np.clip(shade + noise(12, 1.2, 0.18), 0, 1)
    bush = blend(LEAF_DARK, LEAF_LIT, leafy)
    g = blend(g, bush, soft(sh, 0.8))
    Lb = cv2.GaussianBlur(L, (0, 0), 1)
    t = np.clip(Lb[bp] * 1.6, 0, 1)[:, None]
    g[bp] = LEAF_DARK * (1 - t) + LEAF_LIT * t
    p2 = (S.Hh > 195) & (S.Hh < 245) & (S.S > 40) & (S.V > 70)
    d = S.lant & p2
    g[d] = g[d] * np.array([0.7, 1.0, 1.1], np.float32)
    # petals on the walkway -> inpaint stone
    pet = dil((S.pink | p2) & poly([PATH]), 3) & ~S.warm
    g8 = (np.clip(g, 0, 1) * 255 + 0.5).astype(np.uint8)
    g = cv2.inpaint(g8, pet.astype(np.uint8), 4, cv2.INPAINT_TELEA).astype(np.float32) / 255
    g, mta = mountain(S, g)
    return np.clip(g, 0, 1), dict(sh=sh, bp=bp, holes=holes, pet=pet, mt=mta)


def merge_tiles(base):
    acc = np.zeros((H, W, 3), np.float32); wsum = np.zeros((H, W), np.float32)
    for k, (x, y) in TILES.items():
        t = cv2.resize(cv2.imread(TILE % k), (TW, TH), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
        R = 40.0
        ax = np.ones(TW, np.float32); ay = np.ones(TH, np.float32)
        if x > 0: ax = np.minimum(ax, (np.arange(TW) + 1) / R)
        if x + TW < W: ax = np.minimum(ax, (TW - np.arange(TW)) / R)
        if y > 0: ay = np.minimum(ay, (np.arange(TH) + 1) / R)
        if y + TH < H: ay = np.minimum(ay, (TH - np.arange(TH)) / R)
        w = np.outer(np.clip(ay, 0, 1), np.clip(ax, 0, 1))
        acc[y:y + TH, x:x + TW] += t * w[..., None]; wsum[y:y + TH, x:x + TW] += w
    out = base.copy(); m = wsum > 1e-3
    out[m] = acc[m] / wsum[m][:, None]
    return out, wsum


def compose(S, guide, gm):
    ai, wsum = merge_tiles(guide)
    take = soft(dil(gm["sh"], 5), 1.5) * (wsum > 0.5)
    take = np.maximum(take, soft(poly([BEHIND]), 3.0) * (wsum > 0.5))
    # petals on the walkway: the AI's crisp stones instead of a smeared inpaint
    take = np.maximum(take, soft(dil(gm["pet"], 3), 1.5) * (wsum > 0.5))
    # AI greens are lime; deepen them like the branch so the day plate stays a natural green
    ai = ai * np.array([0.95, 0.85, 0.70], np.float32)
    img = blend(guide, ai, take)
    keep = dil(S.warm, 3) | dil(S.sky & ~S.tz, 2) | S.water
    _, bm = branch_layer(S, img, EDIT, LEAF_GAIN, soft_edge=True)
    skym = (S.tod_sky | gm["holes"] | (S.tz & ~S.pav)) & (bm < 0.35)
    n, lab, st, _ = cv2.connectedComponentsWithStats((~skym).astype(np.uint8), connectivity=4)
    isl = np.zeros(n, bool); isl[1:] = (st[1:, cv2.CC_STAT_AREA] < 400) & (st[1:, cv2.CC_STAT_TOP] + st[1:, cv2.CC_STAT_HEIGHT] < 620)
    skym |= isl[lab] & (bm < 0.35)
    img = depink(img, keep)
    # walkway + railing band: the stones' lilac tint gets boosted to pink by the day plate -> neutral
    band = poly([PATH, WS.RAIL_ENV]) & ~dil(S.warm, 3)
    img = blend(img, depink(img, ~band), band.astype(np.float32))
    # path stones: calmer saturation (the day plate pushes the lantern-warmed stones to pink-red)
    pth = poly([PATH]) & ~dil(S.warm, 6)
    gray = lum(img)[..., None] * np.ones(3, np.float32)
    img = blend(img, img * 0.55 + gray * 0.45, soft(pth, 1.5))
    # the one green-lit pagoda window -> warm like its neighbours
    pag = dil(poly([WS.M.PAGODA]) | poly(WS.PAGODA_TIERS), 6)
    gw = pag & (S.Hh > 35) & (S.Hh < 120) & (S.S > 50) & (S.V > 110)
    gw = dil(gw, 2) & pag & (S.V > 60)
    warmwin = lum(img)[..., None] * np.array([0.55, 0.85, 1.25], np.float32)
    img = blend(img, np.clip(warmwin, 0, 1), soft(gw, 0.8))
    # shrub edges sit partly inside the coarse spring sky mask: de-pink them regardless
    near = dil(gm["sh"] | gm["bp"], 25) & ~dil(S.warm, 3)
    img = blend(img, depink(img, ~near), near.astype(np.float32))
    return np.clip(img, 0, 1), skym


def main(a):
    S = Scene()
    guide, gm = build_guide(S)
    if "--tiles" in a:
        d = a[a.index("--tiles") + 1]; os.makedirs(d, exist_ok=True)
        g8 = (guide * 255 + 0.5).astype(np.uint8)
        cv2.imwrite(os.path.join(d, "guide.png"), g8)
        for k, (x, y) in TILES.items():
            cv2.imwrite(os.path.join(d, "tile_%s.png" % k),
                        cv2.resize(g8[y:y + TH, x:x + TW], (2 * TW, 2 * TH), interpolation=cv2.INTER_LANCZOS4))
        return
    img, skym = compose(S, guide, gm)
    out = a[a.index("--out") + 1] if "--out" in a else OUT
    cv2.imwrite(out, (img * 255 + 0.5).astype(np.uint8))
    cv2.imwrite(out.replace(".png", "_sky.png"), skym.astype(np.uint8) * 255)
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1:])
