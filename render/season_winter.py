"""Winter season template: templates/winter_clear_night.png, derived from the spring painting.

  .venv/bin/python render/season_winter.py                 # rebuild the template from saved AI outputs
  .venv/bin/python render/season_winter.py --tiles DIR     # write the 2x guide tiles that were fed to the AI

How it was made (deterministic from the files in templates/ai/):
  1. A FLUX.2-klein edit of the spring painting (templates/ai/winter_edit_branch.png) supplies the bare,
     snow-lined tree branch. Only the branch is used (soft colour matte inside the tree zone); the AI
     edit drifts the layout, so nothing else from it is used.
  2. A procedural *guide* is built from the original painting: blossoms removed, shrubs turned into
     evergreen bushes with snow caps, roofs / walkway / shore ice whitened.  The guide is cut into four
     tiles, upscaled 2x and run through FLUX.2-klein img2img at strength 0.4 (keeps layout, repaints
     the snow in the painting's style) -> templates/ai/winter_tile_{BL,BR,UR,UL}.png.
     mflux-generate-flux2 --model flux2-klein-4b -q 8 --image tile_K.png 0.4 --width 1792 --height 1008
     --steps 10 --seed 21 (BR: seed 22) --prompt-file templates/ai/winter_tile_K.prompt.txt
  3. The tiles are merged back to base px and composited onto the ORIGINAL painting only where the
     season changes (ground, roofs, buildings, shrubs, near hills, shore ice).  Sky, moon, stars, lake
     water, the volcano and the far shore stay pixel-identical to the original.
"""
import os, sys
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import masks as M

SRC = os.path.join(ROOT, "templates", "spring_clear_night.png")
OUT = os.path.join(ROOT, "templates", "winter_clear_night.png")
AI = os.path.join(ROOT, "templates", "ai")
EDIT = os.path.join(AI, "winter_edit_branch.png")
TILE = os.path.join(AI, "winter_tile_%s.png")
W, H = 1672, 941

# tiles (x0, y0) of TW x TH base px; each is fed to the AI upscaled 2x (1664x944)
TILES = {"BL": (0, 437), "BR": (776, 437), "UR": (776, 60), "UL": (0, 140)}   # overlapping
TW, TH = 896, 504

# ---------------------------------------------------------------- hand-placed geometry (base px)
PAGODA_TIERS = [[(128, 466), (170, 466), (205, 480), (250, 492), (247, 501), (150, 503), (52, 501), (48, 492), (95, 478)],
                [(90, 545), (200, 545), (256, 555), (252, 564), (150, 567), (44, 563), (41, 555)],
                [(85, 603), (205, 603), (263, 614), (259, 625), (150, 631), (40, 626), (36, 617)],
                [(100, 671), (205, 671), (269, 685), (266, 696), (150, 701), (60, 698), (52, 688)],
                [(120, 748), (235, 748), (275, 768), (292, 786), (280, 795), (150, 795), (100, 790)]]
SPAG_TIERS = [[(338, 702), (367, 702), (399, 719), (396, 728), (352, 731), (311, 728), (307, 720)],
              [(323, 744), (382, 744), (413, 753), (409, 763), (355, 767), (299, 763), (296, 756)]]
FG_ROOF = [[(0, 815), (140, 806), (160, 815), (200, 840), (260, 872), (320, 900), (380, 925), (398, 941), (0, 941)],
           [(0, 736), (55, 744), (75, 752), (105, 772), (135, 790), (140, 806), (0, 812)]]
LANTERN_ROOFS = [[(912, 797), (938, 797), (966, 818), (962, 827), (925, 831), (888, 827), (884, 820)],
                 [(1258, 762), (1278, 762), (1295, 780), (1292, 787), (1268, 789), (1245, 787), (1242, 780)],
                 [(1300, 478), (1316, 478), (1346, 495), (1342, 502), (1310, 505), (1278, 502), (1275, 495)]]
PAV_ROOF_TOP = [(1222, 356), (1440, 302), (1538, 258), (1556, 212), (1566, 176), (1588, 176), (1600, 194), (1672, 158)]
TOWN_ENV = [(170, 790), (560, 789), (700, 793), (900, 796), (1010, 800), (1010, 941), (170, 941)]
PATH = [(684, 941), (700, 934), (800, 913), (900, 888), (1000, 868), (1100, 857), (1200, 848), (1300, 838),
        (1390, 828), (1400, 860), (1440, 900), (1480, 941)]
RAIL_BASE = [(700, 935), (800, 912), (1000, 866), (1200, 847), (1387, 825)]
TRACK = [(1120, 941), (1150, 905), (1200, 875), (1260, 852), (1320, 838)]
LANTERN_BODIES = [[(893, 790), (958, 790), (958, 896), (893, 896)], [(1246, 752), (1291, 752), (1291, 836), (1246, 836)]]
LANTERN_BASES = [(925, 905), (1268, 838)]
RAIL_ENV = [(560, 900), (672, 862), (850, 838), (1000, 822), (1100, 806), (1200, 793), (1300, 780), (1392, 772),
            (1392, 852), (1250, 864), (1100, 888), (1000, 902), (900, 938), (900, 941), (560, 941)]
HANG_LANTERN = (1255, 440, 1365, 600)            # x0, y0, x1, y1
TREE_ZONE = (740, 0, W, 362)
# near hill right of the lake (evergreens get snow from the AI); everything else far stays original
SPAG_BOX = [(292, 640), (420, 640), (420, 792), (292, 792)]
RHILL = [(1180, 640), (1300, 600), (1400, 560), (W, 540), (W, 800), (1180, 800)]

SH = np.array([0.50, 0.38, 0.30], np.float32)    # moonlit snow in shadow (BGR)
LIT = np.array([0.95, 0.91, 0.87], np.float32)   # moonlit snow, lit
FOLIAGE = np.array([0.17, 0.19, 0.12], np.float32)


# ---------------------------------------------------------------- helpers
def poly(ps):
    m = np.zeros((H, W), np.uint8)
    cv2.fillPoly(m, [np.array(p, np.int32) for p in ps], 1)
    return m.astype(bool)


def dil(m, k):
    return cv2.dilate(m.astype(np.uint8), np.ones((k, k), np.uint8)).astype(bool)


def soft(m, s):
    return np.clip(cv2.GaussianBlur(m.astype(np.float32), (0, 0), s), 0, 1)


def lum(img):
    return img[..., 0] * .114 + img[..., 1] * .587 + img[..., 2] * .299


def snow(Ls, lo=0.08, hi=0.55):
    t = np.clip((Ls - lo) / (hi - lo), 0, 1)[..., None]
    return SH * (1 - t) + LIT * t


def noise(seed, sigma, amp):
    r = np.random.default_rng(seed).standard_normal((H, W)).astype(np.float32)
    r = cv2.GaussianBlur(r, (0, 0), sigma)
    return r / (r.std() + 1e-6) * amp


def load_ai(p):
    return cv2.resize(cv2.imread(p), (W, H), interpolation=cv2.INTER_AREA).astype(np.float32) / 255


def blend(dst, src, a):
    a = a[..., None] if np.ndim(a) == 2 else a
    return dst * (1 - a) + src * a


class Scene:
    def __init__(self):
        self.o8 = cv2.imread(SRC)
        self.o = self.o8.astype(np.float32) / 255
        mk = np.load(os.path.join(HERE, "masks.npz"))
        self.pink = mk["pink"].astype(bool)
        self.warm = mk["warm"].astype(bool)
        self.sky = mk["sky"].astype(bool)
        self.water = mk["water"].astype(bool)
        hsv = cv2.cvtColor(self.o8, cv2.COLOR_BGR2HSV_FULL).astype(np.int32)
        self.Hh, self.S, self.V = hsv[..., 0], hsv[..., 1], hsv[..., 2]
        self.L = lum(self.o)
        self.pav = poly([M.PAVILION])
        x0, y0, x1, y1 = TREE_ZONE
        self.tz = np.zeros((H, W), bool); self.tz[y0:y1, x0:x1] = True
        x0, y0, x1, y1 = HANG_LANTERN
        self.lant = np.zeros((H, W), bool); self.lant[y0:y1, x0:x1] = True
        self.yy, self.xx = np.mgrid[0:H, 0:W].astype(np.float32)
        tod = os.path.join(HERE, "cache_tod.npz")   # the engine's refined spring sky (for the sky sidecar)
        self.tod_sky = (np.load(tod)["sky"] > 0) if os.path.exists(tod) else self.sky


# ---------------------------------------------------------------- 1. sky: blossoms, old branch, petals out
def clean_sky(S):
    """Original sky with every blossom / petal / old-branch pixel replaced by sky (smooth fill + real
    star texture borrowed from clear sky further left)."""
    o, sky = S.o, S.sky
    purple = (S.Hh > 185) & (S.Hh < 250) & (S.S > 30) & (S.V > 50)
    zone = S.tz & ~dil(S.pav, 3)
    holes = zone & dil(~sky | S.pink | purple, 5)
    above = ~poly([M.HORIZON + [(W, H), (0, H)]])
    pet = (S.pink | purple) & above & ~S.tz & ~S.pav & ~dil(poly(PAGODA_TIERS) | poly([M.PAGODA]), 9)
    # petals are small isolated specks; lavender clouds are large -> drop big components
    n, lab, st, _ = cv2.connectedComponentsWithStats(dil(pet, 3).astype(np.uint8))
    small = np.zeros(n, bool); small[1:] = st[1:, cv2.CC_STAT_AREA] < 500
    pet = dil(small[lab] & (S.pink | ((S.Hh > 200) & (S.S > 45))), 7)
    x0, y0, x1, y1 = HANG_LANTERN                      # the lantern's pink glow is not a petal
    pet[y0 - 10:y1 + 10, x0 - 10:x1 + 10] = False
    holes |= pet
    # blossom sprigs poking into the sky beside the pagoda (left edge)
    left = (S.xx < 110) & (S.yy > 470) & (S.yy < 800)
    holes |= dil(left & sky & (S.pink | purple), 5) & ~dil(poly(PAGODA_TIERS) | poly([M.PAGODA]), 3)
    good = (sky & ~holes).astype(np.float32)
    fill = np.zeros_like(o)
    for c in range(3):
        fill[..., c] = cv2.GaussianBlur(o[..., c] * good, (0, 0), 22) / np.maximum(cv2.GaussianBlur(good, (0, 0), 22), 1e-4)
    # stars: high-pass of clear sky shifted from the left half (avoid moon and clouds)
    hp = o - cv2.GaussianBlur(o, (0, 0), 2.0)
    star = np.zeros_like(o)
    shift = 700
    src_ok = good.copy()
    cv2.circle(src_ok, M.MOON[0], M.MOON[1] + 40, 0, -1)
    hp = np.clip(hp, 0, None) * src_ok[..., None]
    star[:, shift:] = hp[:, :W - shift]
    star[:, :shift] = hp[:, W - shift:]
    fill = fill + np.where(lum(star)[..., None] > 0.025, star, 0)
    a = soft(holes, 1.2)
    return blend(o, fill, a), holes


def branch_layer(S, base, edit=EDIT, gain=1.0, soft_edge=False):
    """Branch from an AI edit (bare+snowy for winter, leafy for summer) as a soft matte over `base`
    inside the tree zone; the AI's own sky is discarded."""
    ai = load_ai(edit)
    aL = lum(ai)
    zone = (S.tz | ((S.yy < 410) & (S.xx > 760) & (S.xx < 1200))) & ~S.pav
    # sky estimate of the AI image -> matte = distance from it
    est = cv2.medianBlur((ai * 255).astype(np.uint8), 61 if soft_edge else 31).astype(np.float32) / 255
    for _ in range(2):
        d = np.linalg.norm(ai - est, axis=2)
        clear = (d < 0.035).astype(np.float32)
        est = np.dstack([cv2.GaussianBlur(ai[..., c] * clear, (0, 0), 15) / np.maximum(cv2.GaussianBlur(clear, (0, 0), 15), 1e-4)
                         for c in range(3)])
    if soft_edge:   # big dark trunks pollute the median: estimate the sky from clearly sky-blue pixels only
        clear = ((ai[..., 0] > ai[..., 2] + 0.10) & (aL < 0.35) & (np.linalg.norm(ai - est, axis=2) < 0.06)).astype(np.float32)
        est = np.dstack([cv2.GaussianBlur(ai[..., c] * clear, (0, 0), 25) / np.maximum(cv2.GaussianBlur(clear, (0, 0), 25), 1e-4)
                         for c in range(3)])
    d = np.linalg.norm(ai - est, axis=2)
    m = np.clip((d - 0.03) / 0.06, 0, 1)
    # branch = brown wood or white snow; bluish wisps of the AI's own clouds are not branch
    if soft_edge:   # clouds: bluish-grey and lighter; leaves are green (G > B) or rust (R > B); twigs are dark
        woody = ~((ai[..., 0] >= ai[..., 2] + 0.02) & (ai[..., 0] >= ai[..., 1]) & (aL > 0.2))
    else:
        woody = ~((ai[..., 0] > ai[..., 2] + 0.06) & (aL > 0.16) & (aL < 0.45))
    m *= soft(woody, 0.7)
    # drop small isolated specks (keep everything connected to the real limbs)
    n, lab, st, _ = cv2.connectedComponentsWithStats((m > 0.2).astype(np.uint8))
    x0s, y0s = st[:, cv2.CC_STAT_LEFT], st[:, cv2.CC_STAT_TOP]
    edge = (y0s <= 1) | (x0s + st[:, cv2.CC_STAT_WIDTH] >= W - 1)
    big = np.zeros(n, bool); big[1:] = (st[1:, cv2.CC_STAT_AREA] >= 800) | edge[1:]   # falling leaves etc. dropped
    m *= soft(dil(big[lab], 3), 1.0)
    zf = np.zeros((H, W), np.float32); zf[:345, 760:] = 1; zf[:400, 770:1190] = 1   # leaves hang lower
    zf = cv2.GaussianBlur(zf, (0, 0), 10) * (1 - soft(S.pav, 1.2))
    m = m * zf * zone
    # the AI edit drew its own (shifted) snowy roof: nothing from it within 50 px above the real roofline
    pr = np.array(PAV_ROOF_TOP, np.float32)
    prior = np.interp(np.arange(W), pr[:, 0], pr[:, 1])
    guard = (S.yy > prior[None] - 50) & (S.xx > 1180)
    m = m * (1 - soft(guard, 4))
    # colour-match the AI to the original sky so the anti-aliased edges sit in the painting
    osky = S.sky & S.tz & ~dil(S.pink, 9)
    asky = zone & (m < 0.05)
    aim = ai.copy()
    for c in range(3):
        aim[..., c] = (ai[..., c] - ai[..., c][asky].mean()) * (S.o[..., c][osky].std() / ai[..., c][asky].std()) + S.o[..., c][osky].mean()
    m2 = np.clip((m - 0.3) / 0.4, 0, 1)[..., None]
    aim = aim * (1 - m2) + ai * gain * m2                   # branch body keeps its own colour
    if soft_edge:
        # leaves: un-mix the AI's own sky out of the edge pixels (no halo) and pull the matte in by ~1 px
        # so the painted dark outline ring goes; the leaf keeps its interior light/shadow shading
        F = np.clip((ai - (1 - m)[..., None] * est) / np.maximum(m, 0.25)[..., None], 0, 1)
        m = cv2.GaussianBlur(cv2.erode(m, np.ones((3, 3), np.uint8)), (0, 0), 0.7)
        aim = F * gain
    return blend(base, aim, m), m


# ---------------------------------------------------------------- 2. guide for the AI img2img pass
def build_guide(S):
    o, L = S.o, S.L
    g, holes = clean_sky(S)
    g, _ = branch_layer(S, g)
    p2 = (S.Hh > 195) & (S.Hh < 245) & (S.S > 40) & (S.V > 70)
    # shrubs -> evergreen bushes under snow caps (height field: rounded body + blossom-cluster lumps)
    sh = (S.pink | (p2 & dil(S.pink, 7))) & ~S.tz & ~S.lant & ~S.water & ~holes
    sh = cv2.morphologyEx(sh.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    sh = (cv2.GaussianBlur(sh.astype(np.float32), (0, 0), 4) > 0.45) & ~S.warm
    sh &= (S.xx < 1385) | dil(S.pink, 3)
    dt = cv2.distanceTransform(sh.astype(np.uint8), cv2.DIST_L2, 5)
    hgt = np.sqrt(np.minimum(dt, 30) / 30.0) * 22 + cv2.GaussianBlur(L, (0, 0), 3.5) * 60 * np.clip(dt / 8, 0, 1)
    hgt = cv2.GaussianBlur(hgt, (0, 0), 2)
    gy, gx = np.gradient(hgt)
    n = np.sqrt(gx ** 2 + gy ** 2 + 1.0)
    shade = np.clip((0.45 * gx + 0.75 * gy + 0.5) / (n * 0.995), 0, 1)     # light from upper left
    up = np.clip((gy / n) * 2.2, 0, 1)                                       # surface facing up
    cov = np.clip((up - 0.15) / 0.35, 0, 1) * np.clip(dt / 3, 0, 1)
    bush = blend(FOLIAGE * (0.7 + 0.6 * shade[..., None]), snow(0.2 + 0.5 * shade), cov)
    g = blend(g, bush, soft(sh, 0.8))
    # blossoms behind the pavilion railing: recolour per pixel
    bp = (S.pink | p2 | ((S.Hh > 185) & (S.Hh < 245) & (S.S > 25) & (S.V > 40))) & (S.xx >= 1385) & (S.yy > 560) & ~S.tz & ~sh & ~S.lant & ~S.warm
    g[bp] = snow(cv2.GaussianBlur(L, (0, 0), 1) * 1.5)[bp]
    d = S.lant & p2
    g[d] = g[d] * np.array([0.7, 1.0, 1.1], np.float32)
    # roofs: pagoda tiers, small pagoda, foreground roofs, lantern caps
    roofs = poly(PAGODA_TIERS + SPAG_TIERS + FG_ROOF + LANTERN_ROOFS) & ~S.warm
    g = blend(g, snow(cv2.GaussianBlur(L, (0, 0), 2) * 1.6 + 0.12), soft(roofs, 0.8))
    town = poly([TOWN_ENV])
    slate = town & (S.V < 110) & (o[..., 0] >= o[..., 2]) & ~S.warm & ~roofs
    slate = cv2.morphologyEx(slate.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8)).astype(bool)
    g = blend(g, snow(L * 2 + 0.15), soft(slate, 0.7) * 0.6)
    band = poly([PAV_ROOF_TOP + [(x, y + 50) for x, y in PAV_ROOF_TOP[::-1]]]) & (S.xx >= 1250)
    pr = band & (S.V < 120) & (o[..., 0] >= o[..., 2] - 5) & ~S.warm
    g = blend(g, snow(L * 2 + 0.2), soft(pr, 0.8) * 0.75)
    # walkway: blanket with low undulation, drift along the railing base, lantern mounds, footprints
    pathm = poly([PATH]) & ~poly(LANTERN_BODIES)
    base = 0.20 + 0.08 * np.clip((S.yy - 830) / 110, 0, 1) + noise(5, 28, 0.05) + noise(6, 8, 0.012)
    drift = np.zeros((H, W), np.float32); shadow = np.zeros((H, W), np.float32)
    rb = np.array(RAIL_BASE, np.int32)
    cv2.polylines(drift, [rb + [0, 7]], False, 1.0, 9)
    cv2.polylines(shadow, [rb + [0, 17]], False, 1.0, 8)
    for (x, y) in LANTERN_BASES:
        cv2.ellipse(drift, (x, y + 4), (34, 9), 0, 180, 360, 1.0, -1)
        cv2.ellipse(shadow, (x + 6, y + 14), (36, 7), 0, 0, 360, 1.0, -1)
    base = base + 0.16 * cv2.GaussianBlur(drift, (0, 0), 3) - 0.12 * cv2.GaussianBlur(shadow, (0, 0), 4)
    wl = snow(base)
    for (lx, ly), rad in [((925, 880), 110), ((1268, 830), 80)]:
        dd = np.exp(-((S.xx - lx) ** 2 + ((S.yy - ly) * 1.6) ** 2) / (2 * rad ** 2))[..., None]
        wl = wl * (1 - 0.45 * dd) + np.array([0.55, 0.75, 1.0], np.float32) * dd * 0.45
    tr = np.zeros((H, W), np.float32)
    cv2.polylines(tr, [np.array(TRACK, np.int32)], False, 1.0, 24)
    tr = cv2.GaussianBlur(tr, (0, 0), 6) * np.clip(0.7 + noise(9, 4, 0.5), 0, 1)
    wl = wl * (1 - 0.22 * tr[..., None])
    g = blend(g, wl, soft(pathm, 1.2))
    # near-shore ice: thin irregular band along the bottom edge of the lake
    ice = np.zeros((H, W), bool)
    wid = np.clip(5 + 3 * noise(7, 9, 1.0)[0], 2, 12)
    wtr = S.water
    for x in range(262, 1268):
        ys = np.where(wtr[:, x])[0]
        if len(ys):
            b = ys.max(); ice[int(b - wid[x]):b + 1, x] = True
    ice &= ~S.warm
    icec = np.array([0.50, 0.43, 0.37], np.float32) + noise(8, 2, 0.02)[..., None]
    g = blend(g, icec, soft(ice, 1.0) * 0.55)
    return np.clip(g, 0, 1), dict(sh=sh, ice=ice, pathm=pathm, roofs=roofs, holes=holes)


# ---------------------------------------------------------------- 3. merge AI tiles, composite
def merge_tiles(guide):
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
        if k == "BR":  # the hanging lantern drifted 2.6 px in this tile -> take it from UR only
            x0, y0, x1, y1 = HANG_LANTERN
            ex = np.zeros((H, W), np.float32); ex[y0 - 10:y1, x0 - 10:x1 + 10] = 1
            w = w * (1 - cv2.GaussianBlur(ex, (0, 0), 6)[y:y + TH, x:x + TW])
        acc[y:y + TH, x:x + TW] += t * w[..., None]; wsum[y:y + TH, x:x + TW] += w
    out = guide.copy(); m = wsum > 1e-3
    out[m] = acc[m] / wsum[m][:, None]
    return out


def depink(img, keep):
    """Any pink/magenta hue left outside the warm lights -> neutral."""
    hsv = cv2.cvtColor((np.clip(img, 0, 1) * 255).astype(np.uint8), cv2.COLOR_BGR2HSV_FULL).astype(np.int32)
    pk = (hsv[..., 0] > 185) & (hsv[..., 0] < 250) & (hsv[..., 1] > 22) & (hsv[..., 2] > 40) & ~keep
    a = soft(pk, 1.0)[..., None] * 0.85
    L = lum(img)[..., None]
    neutral = L * np.array([1.12, 1.0, 0.93], np.float32)          # cool neutral
    return img * (1 - a) + neutral * a


def shade_walkway(S, img):
    """Procedural fix on the AI walkway: moonlit (not glowing) snow level, soft undulation, a blue lee
    shadow under the railing drift, warm lantern pools, and the AI's hard dark 'holes' softened into
    shallow dents."""
    path = poly([PATH]) & ~dil(poly(LANTERN_BODIES), 3)
    m = soft(cv2.erode(path.astype(np.uint8), np.ones((3, 3), np.uint8)), 1.5)
    w = img.copy()
    bl = cv2.GaussianBlur(w, (0, 0), 5)
    dark = np.clip((lum(bl) - lum(w) - 0.05) / 0.12, 0, 1)[..., None]
    w = w + (bl - w) * 0.7 * dark
    lee = np.zeros((H, W), np.float32)
    cv2.polylines(lee, [np.array(RAIL_BASE, np.int32) + [0, 24]], False, 1.0, 16)
    lee = cv2.GaussianBlur(lee, (0, 0), 8)
    F = 0.80 * (1 + noise(15, 30, 0.07)) * (1 - 0.28 * lee)
    w = w * F[..., None] * (1 - lee[..., None] * np.array([0.0, 0.06, 0.12], np.float32))
    for (lx, ly), rad in [((925, 885), 95), ((1268, 838), 70)]:
        d = np.exp(-((S.xx - lx) ** 2 + ((S.yy - ly) * 1.7) ** 2) / (2 * rad ** 2))[..., None]
        w = w + np.array([0.10, 0.30, 0.55], np.float32) * d * 0.35
    return blend(img, w, m)


PAV_BASE = [(1388, 770), (W, 735), (W, H), (1480, H), (1440, 900), (1400, 860), (1390, 828)]


def top_caps(solid, thick=3):
    """Snow ridge sitting on every upward-facing edge of `solid` (pixels just above its top edges)."""
    s8 = solid.astype(np.uint8)
    above = np.zeros_like(s8); above[2:] = s8[:-2]          # value of the pixel 2 rows up, shifted down
    top = solid & (above == 0)
    top = cv2.morphologyEx(top.astype(np.uint8), cv2.MORPH_OPEN, np.ones((1, 4), np.uint8)).astype(bool)
    cap = np.zeros_like(top)
    for d in range(0, thick + 1):
        cap[:H - d] |= top[d:]
    return cap, top


def wood_mask(S):
    o = S.o8.astype(np.int32)
    B, G, R = o[..., 0], o[..., 1], o[..., 2]
    return (R > G + 14) & (R > B + 8) & (S.V > 45) & (S.V < 235) & ~S.warm


def ground(S, img, gm):
    """Walkway, railing, pavilion base and foreground roof rebuilt on the ORIGINAL painting with thin old
    snow: snow settles in joints and drifts against the rail, stone tops show through on the trodden line,
    rails / ledges carry snow ridges, and the near-shore water gets an irregular ice shelf."""
    o, L = S.o, S.L
    Lb = cv2.GaussianBlur(L, (0, 0), 4)
    und = noise(21, 22, 0.10) + noise(22, 6, 0.03)
    # --- walkway
    path = poly([PATH]) & ~dil(poly(LANTERN_BODIES), 4)
    joint = np.clip((Lb - L) / 0.05, 0, 1)                                  # dark gaps between stones
    trk = np.zeros((H, W), np.float32)
    cv2.polylines(trk, [np.array(TRACK, np.int32)], False, 1.0, 26)
    trk = cv2.GaussianBlur(trk, (0, 0), 7) * np.clip(0.8 + noise(23, 5, 0.6), 0, 1)
    drift = np.zeros((H, W), np.float32)
    cv2.polylines(drift, [np.array(RAIL_BASE, np.int32) + [0, 8]], False, 1.0, 22)
    for (x, y) in LANTERN_BASES:
        cv2.ellipse(drift, (x, y + 6), (42, 13), 0, 0, 360, 1.0, -1)
    drift = cv2.GaussianBlur(drift, (0, 0), 7)
    field = 0.62 + 2.2 * und + 0.8 * drift - 1.0 * trk
    am = np.clip((field - 0.36) / 0.10, 0, 1)                 # opaque snow vs cleared stone, soft edge
    a = am + (1 - am) * 0.85 * joint                          # cleared stones keep snow in their joints
    edge_sh = np.clip(cv2.GaussianBlur(am, (0, 0), 1.5) - np.vstack([am[:3], am[:-3]]), 0, 1)
    shade = 0.34 + 1.3 * und
    lee = np.zeros((H, W), np.float32)
    cv2.polylines(lee, [np.array(RAIL_BASE, np.int32) + [0, 27]], False, 1.0, 10)
    lee = cv2.GaussianBlur(lee, (0, 0), 5)
    snowc = snow(shade + 0.10 * drift - 0.16 * lee - 0.25 * edge_sh)
    stone = o * np.array([1.0, 0.95, 0.90], np.float32) * 0.92                # cold, slightly darker stone
    walk = stone * (1 - a[..., None]) + snowc * a[..., None]
    for (lx, ly), rad in [((925, 885), 95), ((1268, 838), 70)]:          # warm pools of lantern light
        d = np.exp(-((S.xx - lx) ** 2 + ((S.yy - ly) * 1.7) ** 2) / (2 * rad ** 2))[..., None]
        walk = walk + np.array([0.05, 0.20, 0.42], np.float32) * d * 0.22 * a[..., None]
    img = blend(img, walk, soft(path, 1.2))
    # --- railing + pavilion base: the ORIGINAL rails/posts/ledges (the AI buried them) with snow ridges on top
    ob = S.o8.astype(np.int32)
    p2 = (S.Hh > 195) & (S.Hh < 245) & (S.S > 40) & (S.V > 70)
    wood = (ob[..., 2] >= ob[..., 0] + 3) & (ob[..., 2] > ob[..., 1] + 6) & (S.V > 25) & ~S.pink & ~p2 & ~S.warm
    rail = poly([RAIL_ENV]) & ~path & ~dil(poly(LANTERN_BODIES), 4)
    pb = poly([PAV_BASE]) & ~path & ~dil(gm["sh"], 6)
    wood_r = cv2.morphologyEx((wood & rail).astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8)).astype(bool)
    base = img.copy()
    base = blend(base, o, soft(wood_r, 0.7))                               # rails and posts back
    base = blend(base, o, soft(pb, 1.5))                                   # pavilion base back
    solid = wood_r | (wood & pb & (ob[..., 2] > ob[..., 1] + 18) & (S.V > 60))
    cap, top = top_caps(solid, 3)
    cap &= rail | pb
    base = blend(base, snow(0.58 + 0.5 * und), soft(cap, 0.6) * 0.92)
    img = base
    # --- foreground roof: original tiles under smooth snow, tile rows as soft relief
    roof = poly(FG_ROOF)
    rel = cv2.GaussianBlur(L, (0, 0), 1.2) - cv2.GaussianBlur(L, (0, 0), 6)
    grad = np.clip((S.yy - 730) / 211, 0, 1)
    rs = snow(0.62 - 0.12 * grad + 1.6 * rel + noise(25, 12, 0.06))
    img = blend(img, blend(o, rs, 0.9), soft(roof & ~S.warm, 1.0))
    # --- near-shore ice: ragged shelf along the near edge of the real water outline + a few floes
    import tod_plates as P
    lake = np.zeros((H, W), np.uint8)
    import timeofday as TD
    cv2.fillPoly(lake, [np.array(p_, np.int32) for p_ in TD.LAKE], 1)
    wat = P.refine_water(S.o8, lake).astype(bool)
    ybot = np.where(wat.any(0), H - 1 - np.argmax(wat[::-1], 0), -1)
    rng = np.random.default_rng(34)
    wid = np.clip(6 + noise(26, 18, 1.0)[0] * 3.5, 2, 12)
    dist = (ybot[None, :] - S.yy)
    ice = wat & (dist >= 0) & (dist < wid[None, :] + noise(28, 1.0, 0.6)) & (S.xx > 270) & (S.xx < 1262)
    fl = np.zeros((H, W), np.uint8)                                   # a few broken floes off the edge
    for _ in range(26):
        x = int(rng.uniform(300, 1240))
        if ybot[x] < 0: continue
        y = int(ybot[x] - wid[x] - rng.uniform(3, 12))
        cv2.ellipse(fl, (x, y), (int(rng.uniform(5, 16)), int(rng.uniform(1, 3))), rng.uniform(-4, 4), 0, 360, 1, -1)
    ice |= fl.astype(bool) & wat
    ice &= ~dil(S.warm, 2)
    up = np.vstack([np.zeros((1, W), bool), ice[:-1]])
    rim = ice & ~up                                                    # lit upper edge of each slab
    icec = np.array([0.70, 0.63, 0.57], np.float32) * (0.92 + noise(30, 3, 0.05))[..., None]
    icec = np.where(rim[..., None], np.minimum(icec * 1.2, 1), icec)
    img = blend(img, icec, soft(ice, 0.5) * 0.85)
    return img


def roof_snow(S, img):
    """Smooth snow layer lying on the pavilion roof: follows the real roofline, 6-12 px thick above it,
    rounded overhang at the eave end, moonlit top and a blue shadow on its underside."""
    sky = S.tod_sky
    x0, x1 = 1226, 1548
    ytop = np.full(W, -1)
    pr = np.array(PAV_ROOF_TOP, np.float32)
    prior = np.interp(np.arange(W), pr[:, 0], pr[:, 1])
    for x in range(x0, x1):
        a0 = int(max(0, prior[x] - 22)); a1 = int(prior[x] + 30)
        ys = np.where(~sky[a0:a1, x])[0]
        if len(ys): ytop[x] = ys[0] + a0
    ok = ytop > 0
    xs = np.arange(W)
    yt = np.interp(xs, xs[ok], ytop[ok]).astype(np.float32)
    yt = cv2.GaussianBlur(yt[None], (0, 0), 3)[0]
    thick = 9 + 3 * noise(32, 25, 1.0)[0]
    thick = np.clip(thick, 6, 13) * np.clip((xs - x0) / 14.0, 0, 1) ** 0.5     # rounded at the eave end
    top = yt - thick
    m = np.zeros((H, W), np.float32)
    yy = S.yy
    inside = (yy >= top[None]) & (yy <= yt[None] + 4) & (xs[None] >= x0 - 2) & (xs[None] < x1)
    m[inside] = 1
    m = soft(m > 0, 0.8) * (1 - soft(dil(S.warm, 2), 1)) * np.clip((x1 + 6 - S.xx) / 12, 0, 1)
    depth = np.clip((yy - top[None]) / (thick[None] + 4), 0, 1)
    sc = snow(0.78 - 0.28 * depth ** 1.5 + noise(33, 6, 0.03))
    return blend(img, sc, m)


def compose(S, guide, gm):
    ai = merge_tiles(guide)
    depth = np.load(os.path.join(HERE, "depth.npy")).astype(np.float32)
    far = (depth > 0.78) & ~poly([RHILL])
    sky_ext = S.sky | (S.tz & ~S.pav) | gm["holes"]
    water = S.water & ~poly([SPAG_BOX])
    keep = sky_ext | ((water | far) & ~gm["ice"])
    take = soft(~keep, 1.2)
    # pavilion roof: above the real roofline the sky stays original (the AI's snow strip floated off the roof)
    roofzone = poly([[(1200, 120), (W, 100), (W, 260), (1560, 300), (1440, 340), (1200, 400)]])
    take = take * (1 - (roofzone & S.tod_sky))
    # hanging lantern: keep the original lantern + glow, take only its snow cap from the AI
    x0, y0, x1, y1 = HANG_LANTERN
    hl = np.zeros((H, W), bool); hl[y0:y1, x0:x1] = True
    cap = dil(poly([LANTERN_ROOFS[2]]), 5)
    take = take * (1 - soft(hl & ~cap, 2.0)) + soft(cap, 1.0) * soft(hl, 2.0)
    # bottom-left corner sprigs: the AI repaints them as white flowers -> keep the guide's snow bushes
    corner = soft(dil(gm["sh"] & (S.xx < 220) & (S.yy > 850), 9), 2.0)
    ai = blend(ai, guide, corner)
    sky_img, _ = clean_sky(S)
    img = blend(sky_img, ai, take)
    img, bm = branch_layer(S, img)
    img = ground(S, img, gm)
    img = roof_snow(S, img)
    # exact sky mask of this template (the engine's spring-seeded GrabCut would erase the dark branch)
    skym = (S.tod_sky | gm["holes"] | (S.tz & ~S.pav)) & (take < 0.5) & (bm < 0.35)
    # small non-sky islands inside the sky (petal remnants, stray specks) count as sky
    n, lab, st, _ = cv2.connectedComponentsWithStats((~skym).astype(np.uint8), connectivity=4)
    isl = np.zeros(n, bool); isl[1:] = (st[1:, cv2.CC_STAT_AREA] < 400) & (st[1:, cv2.CC_STAT_TOP] + st[1:, cv2.CC_STAT_HEIGHT] < 620)
    skym |= isl[lab] & (bm < 0.35)
    lights = dil(S.warm, 3)
    img = depink(img, lights | dil(sky_ext, 2) | far | water)
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
    out = os.path.join(a[a.index("--out") + 1]) if "--out" in a else OUT
    cv2.imwrite(out, (img * 255 + 0.5).astype(np.uint8))
    cv2.imwrite(out.replace(".png", "_sky.png"), skym.astype(np.uint8) * 255)
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1:])
