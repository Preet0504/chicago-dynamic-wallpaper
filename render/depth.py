"""Depth map for the shared composition (template coords, 1672x941).
0 = nearest to the viewer, 1 = sky / infinitely far. Saved as render/depth.npy (float16).

How it is built:
  1. Hand-traced outline polygons (traced at 3-5x zoom on templates/spring_clear_night.png)
     give a coarse label per object: pagodas, lanterns, railing, walkway, pavilion, hills...
     Some labels are refined from the painting itself: the railing is its brown wood pixels,
     blossoms come from the pink mask, the mountain / far-hill ridge is traced per column.
  2. Labels are snapped to the painted edges with a colour-guided filter (He et al.) run on
     each label's one-hot mask, using the painting as guide; then argmax.
  3. Every label has a depth *field* (constant, or a gradient: the town gets per-superpixel
     depth from the bottom of each roof/house segment, so rows further up are further away;
     lake and walkway follow perspective).
  4. Soft composite with the guided weights (anti-aliased, edges follow the paint), sky = 1.

Also writes render/depth_labels.npy (uint8 label ids, LABELS below) for effects that need
to know "this is walkway / railing / roof" (snow accumulation).

  .venv/bin/python render/depth.py [vis.png]
"""
import os, sys
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
BW, BH = 1672, 941
GUIDE = os.path.join(ROOT, "templates", "spring_clear_night.png")
OUT = os.path.join(HERE, "depth.npy")
OUT_LABELS = os.path.join(HERE, "depth_labels.npy")

# label ids (stored in depth_labels.npy)
LABELS = dict(sky=0, mountain=1, farhill=2, farshore=3, lake=4, hill=5, peninsula=6, town=7,
              small_pagoda=8, pagoda=9, fg_roof=10, railing=11, walkway=12, lantern1=13,
              lantern2=14, shrub=15, tree_left=16, blossom_near=17, pavilion=18,
              hanging_lantern=19, branch=20, petal=21, near_houses=22)
L = LABELS

# ---------------------------------------------------------------- traced outlines (template px)
SMALL_PAGODA = [(351, 657), (355, 657), (357, 699), (373, 703), (396, 715), (399, 722), (379, 726),
                (379, 745), (401, 749), (415, 755), (411, 760), (396, 763), (396, 818), (324, 818),
                (322, 763), (302, 759), (299, 752), (322, 745), (326, 726), (307, 722), (311, 715),
                (334, 703), (349, 699)]
# generous above the roofs (the sky mask cuts the real silhouette there)
PAGODA = [(140, 268), (166, 268), (166, 462), (256, 466), (256, 506), (214, 514), (212, 534),
          (257, 538), (259, 569), (215, 576), (215, 603), (262, 606), (265, 636), (226, 641),
          (226, 670), (270, 673), (271, 702), (232, 706), (230, 790), (66, 790),
          (64, 745), (40, 700), (32, 600), (30, 466), (140, 462)]
LANTERN1 = [(921, 778), (928, 778), (930, 795), (936, 800), (951, 808), (967, 818), (966, 827),
            (951, 831), (950, 893), (953, 926), (897, 926), (900, 893), (900, 831), (885, 829),
            (883, 820), (899, 808), (914, 800), (919, 795)]
LANTERN2 = [(1266, 745), (1271, 745), (1273, 757), (1281, 763), (1295, 770), (1295, 779),
            (1288, 781), (1288, 817), (1291, 821), (1291, 849), (1249, 849), (1250, 821),
            (1253, 817), (1253, 781), (1242, 779), (1241, 771), (1255, 763), (1263, 757)]
# big tiled roof bottom-left (its top-right edge is the white-highlighted eave line)
FG_ROOF = [(0, 736), (40, 740), (68, 751), (100, 783), (136, 797), (150, 818), (200, 852),
           (240, 876), (280, 896), (320, 908), (360, 917), (400, 931), (420, 941), (0, 941)]
# walkway: below the kerb stones at the foot of the railing, left of the pavilion base
KERB = [(905, 941), (930, 930), (946, 915), (1000, 886), (1063, 868), (1170, 841), (1250, 828),
        (1300, 822), (1390, 817)]
WALKWAY = KERB + [(1395, 860), (1490, 941)]
# railing band (wood pixels inside it are the railing; the rest is slope vegetation)
# top edge of the top rail (traced at 4-5x) and the posts standing above it (x0, x1, top y)
RAIL_TOP = [(560, 918), (600, 912), (675, 903), (695, 904), (785, 886), (802, 881), (840, 874),
            (852, 870), (885, 862), (960, 846), (992, 841), (1026, 832), (1038, 832), (1071, 826),
            (1082, 826), (1113, 821), (1123, 820), (1145, 816), (1155, 816), (1185, 810), (1218, 806),
            (1227, 807), (1251, 806), (1300, 796), (1322, 792), (1328, 793), (1374, 787), (1392, 788)]
RAIL_POSTS = [(675, 695, 894), (785, 802, 871), (837, 852, 861), (884, 892, 857), (980, 992, 837),
              (1026, 1038, 828), (1071, 1082, 822), (1112, 1123, 815), (1145, 1155, 812),
              (1176, 1185, 807), (1218, 1227, 802), (1294, 1300, 792), (1321, 1328, 789),
              (1373, 1379, 783)]
# pavilion: roof, pillars, railing, stone base; the openings between the pillars see the hill
PAVILION = [(1228, 330), (1400, 290), (1530, 235), (1560, 180), (1672, 140), (1672, 941),
            (1490, 941), (1395, 860), (1386, 818), (1386, 796), (1396, 796), (1396, 716),
            (1481, 716), (1481, 470), (1240, 470)]
PAV_OPENINGS = [[(1501, 547), (1511, 547), (1511, 714), (1501, 714)],
                [(1526, 547), (1569, 547), (1569, 714), (1526, 714)],
                [(1580, 547), (1626, 547), (1626, 714), (1580, 714)]]
HANG_BOX = [(1250, 405), (1355, 405), (1355, 585), (1250, 585)]   # only its non-sky pixels count
HILL = [(1150, 702), (1185, 680), (1300, 618), (1420, 552), (1520, 535), (1672, 530), (1672, 730),
        (1300, 740), (1150, 740)]
PENINSULA = [(895, 701), (990, 700), (1150, 700), (1200, 690), (1290, 700), (1300, 760), (1265, 754),
             (1200, 746), (1150, 738), (1100, 729), (1000, 721)]
LAKE = [[(390, 700), (600, 699), (900, 702), (940, 712), (1000, 719), (1100, 727), (1150, 736),
         (1200, 744), (1265, 752), (1268, 790), (1100, 792), (900, 790), (700, 787), (560, 784),
         (500, 768), (430, 760), (392, 756)],
        [(262, 700), (392, 700), (392, 705), (305, 710), (300, 745), (262, 748)]]
# the roof + lit house right below the big pagoda (stands in front of the pagoda's base)
NEAR_HOUSES = [(118, 752), (150, 745), (270, 752), (281, 790), (246, 796), (243, 847), (150, 847),
               (140, 800)]
SHRUB_ZONE = [(1285, 640), (1500, 600), (1672, 600), (1672, 800), (1395, 800), (1300, 830)]
TREE_LEFT_ZONE = [(0, 470), (70, 470), (70, 745), (0, 745)]


def poly_mask(polys):
    m = np.zeros((BH, BW), np.uint8)
    if polys and isinstance(polys[0], tuple):
        polys = [polys]
    cv2.fillPoly(m, [np.array(p, np.int32) for p in polys], 1)
    return m.astype(bool)


def interp_line(pts, xs):
    p = np.array(sorted(pts), np.float32)
    return np.interp(xs, p[:, 0], p[:, 1])


# ---------------------------------------------------------------- colour-guided filter
def _box(a, r):
    return cv2.boxFilter(a, -1, (2 * r + 1, 2 * r + 1), normalize=True, borderType=cv2.BORDER_REFLECT)


class GuidedFilter:
    """Colour-guided filter (He, Sun, Tang 2010). I: HxWx3 float32 guide."""

    def __init__(self, I, r, eps):
        self.I, self.r = I, r
        self.mI = _box(I, r)
        cov = np.empty(I.shape[:2] + (3, 3), np.float32)
        for i in range(3):
            for j in range(i, 3):
                c = _box(I[..., i] * I[..., j], r) - self.mI[..., i] * self.mI[..., j]
                cov[..., i, j] = cov[..., j, i] = c
        cov += np.eye(3, dtype=np.float32) * eps
        self.inv = np.linalg.inv(cov)

    def __call__(self, p):
        r, I = self.r, self.I
        mp = _box(p, r)
        cIp = _box(I * p[..., None], r) - self.mI * mp[..., None]
        a = np.einsum("...ij,...j->...i", self.inv, cIp)
        b = mp - (a * self.mI).sum(-1)
        return (_box(a, r) * I).sum(-1) + _box(b, r)


# ---------------------------------------------------------------- pieces traced from the paint
def trace_ridge(im, x0, x1, y0, y1):
    """Per column: the strongest 'lighter above / darker below' edge in [y0, y1] -> ridge y."""
    g = cv2.GaussianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (0, 0), 1.2)
    dy = g[:-2] - g[2:]   # positive where it gets darker going down
    ys = np.full(BW, np.nan, np.float32)
    for x in range(x0, x1):
        col = dy[y0 - 1:y1 - 1, x]
        ys[x] = y0 + int(np.argmax(col))
    ok = ~np.isnan(ys)
    ys[ok] = cv2.medianBlur(ys[ok].astype(np.float32).reshape(1, -1), 5).ravel()
    return ys


def superpixels(im, region, step=13):
    """Watershed over-segmentation (edge-following superpixels) inside `region`."""
    g = cv2.cvtColor((im * 255).astype(np.uint8), cv2.COLOR_BGR2GRAY)
    markers = np.zeros((BH, BW), np.int32)
    k = 1
    for y in range(step // 2, BH, step):
        for x in range(step // 2, BW, step):
            if region[y, x]:
                markers[y, x] = k
                k += 1
    markers[~cv2.dilate(region.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)] = k
    ws = cv2.watershed(cv2.cvtColor(g, cv2.COLOR_GRAY2BGR), markers.copy())
    ws = cv2.medianBlur(np.where(ws < 0, 0, ws).astype(np.float32), 3).astype(np.int32)
    return ws, k


def town_field(im, region):
    """Depth of the town: each superpixel gets the depth of its own lower edge, so a roof takes
    the depth of the house it belongs to and rows further up the slope are further away."""
    ws, n = superpixels(im, region)
    yy = np.repeat(np.arange(BH, dtype=np.float32)[:, None], BW, 1)
    from scipy import ndimage as ndi
    idx = np.arange(n + 1)
    ymax = ndi.maximum(yy, ws, idx)
    ymean = ndi.mean(yy, ws, idx)
    ybot = np.nan_to_num(0.55 * np.asarray(ymax) + 0.45 * np.asarray(ymean))
    yb = ybot[np.clip(ws, 0, n)]
    yb = np.where(region & (ws > 0) & (ws < n), np.clip(yb, yy, yy + 40), yy)
    keys_y = [700, 760, 790, 830, 860, 900, 941]
    keys_d = [0.52, 0.48, 0.44, 0.36, 0.30, 0.245, 0.19]
    return np.interp(yb, keys_y, keys_d).astype(np.float32)


def sky_fixups(sky):
    """The GrabCut sky mask misses painted sky around the big pagoda (a forced-foreground box
    above the top roof and around the spire, between the eaves) and between the left blossoms.
    Find it on the colour-recovered day plate, where sky is bright and clouds are white."""
    cache = os.path.join(HERE, "cache_tod.npz")
    if not os.path.exists(cache):
        return sky
    d = np.clip(np.load(cache)["day"].astype(np.float32), 0, 1)
    pink = np.load(os.path.join(HERE, "masks.npz"))["pink"]
    B, G, R = d[..., 0], d[..., 1], d[..., 2]
    Lm = 0.114 * B + 0.587 * G + 0.299 * R
    rule = (Lm > 0.58) & (B >= R - 0.03)
    spire = np.zeros((BH, BW), bool); spire[285:468, 140:168] = True
    rule |= spire & (Lm > 0.36) & (B > R + 0.02)
    rule &= ~(cv2.dilate(pink, np.ones((5, 5), np.uint8)) > 0)
    zone = np.zeros((BH, BW), bool); zone[270:700, 0:285] = True; zone[625:, 195:] = False
    r = (rule & zone & ~sky).astype(np.uint8)
    r = cv2.morphologyEx(r, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    n, lab = cv2.connectedComponents(r)
    touch = np.unique(lab[(cv2.dilate(sky.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0) & (r > 0)])
    r = np.isin(lab, touch[touch > 0]).astype(np.uint8)
    r = cv2.morphologyEx(r, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    return sky | (r > 0)


def build(vis_path=None, out=OUT, out_labels=OUT_LABELS):
    im8 = cv2.imread(GUIDE)
    im = im8.astype(np.float32) / 255
    cache = os.path.join(HERE, "cache_tod.npz")
    if os.path.exists(cache):
        sky = np.load(cache)["sky"].astype(bool)
    else:
        sky = np.load(os.path.join(HERE, "masks.npz"))["sky"].astype(bool)
    sky = sky_fixups(sky)
    pink = np.load(os.path.join(HERE, "masks.npz"))["pink"].astype(np.uint8)
    hsv = cv2.cvtColor(im8, cv2.COLOR_BGR2HSV_FULL).astype(np.int32)
    H, S, V = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    yy = np.repeat(np.arange(BH, dtype=np.float32)[:, None], BW, 1)
    xx = np.repeat(np.arange(BW, dtype=np.float32)[None, :], BH, 0)

    lab = np.full((BH, BW), L["town"], np.uint8)
    # ---- far: one continuous field (far-shore town -> hills -> mountain), no bands
    farzone = yy < 701
    lab[farzone] = L["farshore"]
    lab[farzone & (yy < 655)] = L["mountain"]
    lab[poly_mask(LAKE)] = L["lake"]
    # right hill: traced per column where the dark forest starts below the paler ranges
    g = cv2.GaussianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (0, 0), 1.5)
    dark = (g < 0.145).astype(np.float32)
    run = cv2.erode(dark, np.ones((7, 1), np.uint8), anchor=(0, 0))  # dark for 7 px downward
    hill = np.zeros((BH, BW), bool)
    for x in range(1150, BW):
        ys = np.nonzero(run[560:720, x] > 0)[0]
        if ys.size:
            hill[560 + ys[0]:740, x] = True
    hill &= poly_mask([(1150, 560), (1672, 520), (1672, 740), (1150, 740)])
    lab[hill] = L["hill"]
    lab[poly_mask(PENINSULA) & ~poly_mask(LAKE)] = L["peninsula"]
    # ---- near-side town is the default; nearer things on top, far to near
    lab[poly_mask(SMALL_PAGODA)] = L["small_pagoda"]
    lab[poly_mask(PAGODA)] = L["pagoda"]
    lab[poly_mask(TREE_LEFT_ZONE) & ~poly_mask(PAGODA)] = L["tree_left"]
    tree_l = poly_mask(TREE_LEFT_ZONE) & (cv2.morphologyEx(pink, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8)) > 0)
    lab[tree_l] = L["tree_left"]
    lab[poly_mask(NEAR_HOUSES)] = L["near_houses"]
    lab[poly_mask(FG_ROOF)] = L["fg_roof"]
    # railing: from the traced top rail down to the kerb (the vegetation seen between the rails
    # sits right behind it), plus the posts standing above the top rail
    xs = np.arange(BW, dtype=np.float32)
    top_line = interp_line(RAIL_TOP, xs)
    kerb_line = interp_line(KERB + [(560, 990), (700, 975)], xs)
    rail = (yy >= top_line[None, :]) & (yy <= kerb_line[None, :] + 1) & (xx >= 590) & (xx <= 1392)
    for x0, x1, yt in RAIL_POSTS:
        rail[yt:int(top_line[x0]) + 2, x0:x1 + 1] = True
    lab[rail] = L["railing"]
    lab[poly_mask(WALKWAY)] = L["walkway"]
    canopy = cv2.morphologyEx(pink, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    canopy = cv2.morphologyEx(canopy, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    shrub = poly_mask(SHRUB_ZONE) & (canopy > 0)
    lab[shrub & ~poly_mask(WALKWAY)] = L["shrub"]
    pav = poly_mask(PAVILION)
    lab[pav] = L["pavilion"]
    op = poly_mask(PAV_OPENINGS)
    lab[op] = L["hill"]
    pinkc = cv2.morphologyEx(pink, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8)) > 0
    lab[op & (pinkc | (yy > 690))] = L["shrub"]
    lab[poly_mask(LANTERN1)] = L["lantern1"]
    lab[poly_mask(LANTERN2)] = L["lantern2"]
    near_bl = (pinkc & (yy > 880) & ((xx < 330) | (xx > 1540))) | (pinkc & (xx > 1560) & (yy > 820))
    lab[near_bl] = L["blossom_near"]
    lab[poly_mask(HANG_BOX)] = L["hanging_lantern"]
    branch = (yy < 352) & (xx > 735) & ~pav
    lab[branch] = L["branch"]
    # floating petals and anything else left in the upper sky area
    upper = (yy < 600) & (xx > 700) & ~pav & ~poly_mask(HANG_BOX) & ~hill & ~branch
    lab[upper & (lab == L["farshore"]) | upper & (lab == L["town"])] = L["petal"]
    lab[sky] = L["sky"]

    # ---- snap labels to the painted edges: guided filter of every one-hot mask, then argmax
    gf = GuidedFilter(im, 4, 2e-3)
    ids = sorted(set(np.unique(lab).tolist()))
    soft = np.zeros((len(ids), BH, BW), np.float32)
    for k, i in enumerate(ids):
        m = (lab == i).astype(np.float32)
        soft[k] = gf(m)
        # the snap may move a traced outline by at most 3 px
        soft[k][cv2.dilate(m, np.ones((7, 7), np.uint8)) == 0] = -1
    snapped = np.array(ids, np.uint8)[np.argmax(soft, 0)]
    snapped[sky] = L["sky"]
    snapped[~sky & (snapped == L["sky"])] = lab[~sky & (snapped == L["sky"])]
    # thin hand-traced parts must not be eaten by the snap
    for name in ("lantern1", "lantern2"):
        core = cv2.erode((lab == L[name]).astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
        snapped[core & ~sky] = L[name]

    # ---- depth field per label
    town = town_field(im, (snapped == L["town"]) | (snapped == L["small_pagoda"]))
    walk_d = lambda y: np.interp(y, [815, 860, 900, 941], [0.205, 0.15, 0.105, 0.065]).astype(np.float32)
    kerb_y = interp_line(KERB + [(600, 960), (700, 958)], xx)
    lake_t = (1.0 / np.clip(yy - 640, 40, None) - 1 / 150.0) / (1 / 60.0 - 1 / 150.0)
    fields = {
        L["sky"]: np.float32(1.0),
        L["mountain"]: np.interp(yy, [560, 640, 668, 701], [0.95, 0.93, 0.87, 0.81]).astype(np.float32),
        L["farhill"]: np.interp(yy, [560, 640, 668, 701], [0.95, 0.93, 0.87, 0.81]).astype(np.float32),
        L["farshore"]: np.interp(yy, [560, 640, 668, 701], [0.95, 0.93, 0.87, 0.81]).astype(np.float32),
        L["lake"]: np.clip(0.50 + 0.30 * lake_t, 0.48, 0.81).astype(np.float32),
        L["hill"]: (np.interp(xx, [1150, 1672], [0.66, 0.58])
                    + 0.05 * np.clip((yy - 650) / 50, 0, 1) * np.clip((1350 - xx) / 150, 0, 1)).astype(np.float32),
        L["peninsula"]: np.clip(np.interp(xx, [900, 1000, 1120, 1290], [0.81, 0.79, 0.75, 0.70])
                                + np.interp(yy, [690, 760], [0.01, -0.03]), 0.66, 0.81).astype(np.float32),
        L["town"]: town,
        L["small_pagoda"]: np.float32(0.405),
        L["pagoda"]: np.float32(0.29),
        L["fg_roof"]: np.interp(yy, [736, 941], [0.16, 0.10]).astype(np.float32),
        L["railing"]: np.clip(walk_d(kerb_y) - 0.012, 0.05, 0.3),
        L["walkway"]: walk_d(yy),
        L["lantern1"]: np.float32(0.085),
        L["lantern2"]: np.float32(0.185),
        L["shrub"]: np.float32(0.215),
        L["tree_left"]: np.float32(0.10),
        L["blossom_near"]: np.float32(0.045),
        L["pavilion"]: np.interp(xx, [1228, 1480, 1672], [0.15, 0.10, 0.05]).astype(np.float32),
        L["hanging_lantern"]: np.float32(0.11),
        L["branch"]: np.float32(0.03),
        L["petal"]: np.float32(0.12),
        L["near_houses"]: np.float32(0.27),
    }
    dhard = np.zeros((BH, BW), np.float32)
    for i, f in fields.items():
        m = snapped == i
        dhard[m] = (f[m] if np.ndim(f) else f)

    # ---- anti-alias along the painted edges: small guided filter on the depth itself,
    # clamped to the local min/max so it never overshoots
    gf2 = GuidedFilter(im, 1, 1e-3)
    d = gf2(dhard)
    lo = cv2.erode(dhard, np.ones((3, 3), np.uint8))
    hi = cv2.dilate(dhard, np.ones((3, 3), np.uint8))
    d = np.clip(d, lo, hi)
    skyf = cv2.GaussianBlur(sky.astype(np.float32), (0, 0), 0.6)
    d = d * (1 - skyf) + skyf
    d = np.clip(d, 0, 1)

    # atomic writes: other renderers read these files concurrently
    tmp = out + ".%d.tmp.npy" % os.getpid()
    np.save(tmp, d.astype(np.float16))
    os.replace(tmp, out)
    tmp = out_labels + ".%d.tmp.npy" % os.getpid()
    np.save(tmp, snapped.astype(np.uint8))
    os.replace(tmp, out_labels)
    if vis_path:
        vis = cv2.applyColorMap((d * 255).astype(np.uint8), cv2.COLORMAP_TURBO)
        cv2.imwrite(vis_path, vis)
        edges = cv2.Canny((d * 255).astype(np.uint8), 8, 20)
        ov = im8.copy()
        ov[edges > 0] = (0, 255, 255)
        cv2.imwrite(vis_path.replace(".png", "_edges.png"), ov)
    return d, snapped


if __name__ == "__main__":
    # depth.py [vis.png] [--dry DIR]  (--dry: write depth/labels into DIR instead of render/)
    a = sys.argv[1:]
    kw = {}
    if "--dry" in a:
        dd = a[a.index("--dry") + 1]
        kw = dict(out=os.path.join(dd, "depth.npy"), out_labels=os.path.join(dd, "depth_labels.npy"))
        a = [x for x in a if x not in ("--dry", dd)]
    build(a[0] if a else None, **kw)
