"""Rain and thunderstorm weather effects (no AI, numpy / OpenCV only).

apply(img, ctx)        rain; ctx['intensity'] 0..1 = drizzle .. downpour
apply_storm(img, ctx)  thunderstorm: heavier rain, lightning, choppy lake, blown leaves/petals

Input is the finished overcast frame (2560x1441 float32 BGR 0..1). Every layer is built from the
frame itself and the scene masks (A.sky, A.water, A.warm, A.depth), so it works for any template.
Coordinates below are OUTPUT pixels (2560x1441).
"""
import math
import numpy as np
import cv2

W, H = 2560, 1441
SX = W / 1672.0
HORIZON_Y = 600.0 * SX          # eye level (timeofday.HORIZON_Y in output px)
LAKE_WY = int(692 * SX)          # far-shore mirror line used by timeofday's lake reflection

# stone walkway (paving only): far edge runs along the curb in front of the railing
WALK = [(1250, 1441), (1300, 1428), (1372, 1412), (1462, 1392), (1560, 1369), (1660, 1349),
        (1760, 1331), (1850, 1314), (1925, 1301), (1990, 1291), (2060, 1282), (2108, 1277),
        (2124, 1300), (2150, 1338), (2196, 1382), (2262, 1418), (2330, 1441)]
# lantern bodies standing on the walkway edge (excluded from the wet paving)
LANTERN_BODIES = [[(1368, 1230), (1466, 1230), (1466, 1416), (1368, 1416)],
                  [(1896, 1150), (1962, 1150), (1962, 1300), (1896, 1300)]]
# wooden railing along the walkway (zone; refined by colour)
RAIL_ZONE = [(1060, 1441), (1060, 1395), (1225, 1340), (1530, 1262), (1840, 1225), (2130, 1195),
             (2130, 1290), (1840, 1320), (1530, 1360), (1300, 1430), (1250, 1441)]
# lantern roofs (centre, half-width, half-height) for splashes
LANTERN_CAPS = [((1416, 1236), 60, 10), ((1930, 1182), 38, 7), ((2005, 742), 42, 8)]
HANG_LANTERN = (2005, 805)       # hanging lantern body centre
# drip line of the pavilion eave (lower edge of the tile row), measured on the painting
EAVE = [(1902, 560), (1925, 574), (1960, 577), (2000, 578), (2040, 577), (2080, 575), (2120, 571),
        (2160, 566), (2200, 560), (2240, 553), (2280, 545), (2300, 540)]
# region of the lake / horizon / mountain
MOUNTAIN_PEAK = (766, 784)


# ---------------------------------------------------------------- small helpers
def C(r, g, b):
    return np.array([b, g, r], np.float32)


def lum(img):
    return img[..., 0] * 0.114 + img[..., 1] * 0.587 + img[..., 2] * 0.299


def mix(a, b, t):
    if np.ndim(t) == 2:
        t = t[..., None]
    return a + (b - a) * t


def screen(a, b):
    return 1 - (1 - a) * (1 - b)


def smooth(x, e0, e1):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def blur(a, s, sy=None):
    return cv2.GaussianBlur(a, (0, 0), s, sigmaY=sy if sy is not None else s)


def fbm(rng, h, w, base=4, octaves=5, aspect=1.0):
    """Fractal value noise in 0..1, built at low res and upsampled (fast)."""
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        n = base * 2 ** o
        gh = max(2, int(n * h / w * aspect)) + 1
        g = rng.random((gh, n + 1), dtype=np.float32)
        out += amp * cv2.resize(g, (w, h), interpolation=cv2.INTER_CUBIC)
        tot += amp
        amp *= 0.5
    out /= tot
    lo, hi = np.percentile(out[::7, ::7], [1, 99])
    return np.clip((out - lo) / (hi - lo + 1e-6), 0, 1)


def poly_mask(pts, sigma=0.0):
    m = np.zeros((H, W), np.float32)
    cv2.fillPoly(m, [np.array(pts, np.int32)], 1.0)
    return blur(m, sigma) if sigma else m


def seed_of(when, salt=0):
    return (when.year * 1000003 + when.timetuple().tm_yday * 7919 + when.hour * 131
            + (when.minute // 15) * 17 + salt * 9973) & 0x7FFFFFFF


# ---------------------------------------------------------------- scene analysis (per frame, cheap)
class Scene:
    def __init__(self, img, ctx):
        A = ctx["A"]
        self.A = A
        self.sky = A.sky
        self.water = A.water
        self.warm = A.warm
        yy = np.arange(H, dtype=np.float32)[:, None] / SX * np.ones((1, W), np.float32)
        if A.depth is not None:
            d = A.depth.astype(np.float32)
        else:  # y-based fallback: far band at the horizon, nearer toward the bottom
            d = np.where(yy < 700, 0.85, np.where(yy < 790, 0.75 - (yy - 700) / 90 * 0.15,
                                                   0.55 - (yy - 790) / 151 * 0.25)).astype(np.float32)
            d = d * (1 - self.sky) + self.sky
        self.depth = d
        # soft depth: polygon depth maps have hard steps; particles / haze use a softened copy
        small = cv2.resize(d, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
        self.depth_s = cv2.resize(blur(small, 6), (W, H), interpolation=cv2.INTER_LINEAR)
        self.depth_s = np.maximum(self.depth_s * (1 - self.sky), self.sky * 1.0)
        st = ctx["st"]
        self.sa = st["sun_alt"]
        self.day = float(smooth(self.sa, -6.0, 6.0))
        self.lights = float(ctx.get("lights_on", 0.0))
        self.when = ctx["when"]
        self.season = ctx.get("season", "spring")
        # environment light: what a raindrop at this spot refracts toward the viewer
        q = cv2.resize(img, (W // 8, H // 8), interpolation=cv2.INTER_AREA)
        env = cv2.resize(blur(q, 6), (W, H), interpolation=cv2.INTER_LINEAR)
        self.env = env
        # warm light field around lit lanterns / windows (for glints)
        if self.lights > 0.01:
            wl = cv2.resize(img * (self.warm * (1 - self.water))[..., None], (W // 4, H // 4), interpolation=cv2.INTER_AREA)
            g = blur(wl, 10) * 3.0 + blur(wl, 3) * 2.0
            self.glow = np.clip(cv2.resize(g, (W, H), interpolation=cv2.INTER_LINEAR) * self.lights, 0, 1.5)
        else:
            self.glow = np.zeros_like(img)


# ---------------------------------------------------------------- sky, haze, low cloud
def rain_sky(img, S, sky_layer, I, storm, rng):
    """Low, textured rain cloud over the sky (hides the moon disk and fair-weather clouds)."""
    row = sky_layer.mean(axis=1)                                  # (H, 3)
    base = np.broadcast_to(row[:, None, :], (H, W, 3))
    tex = fbm(rng, H // 4, W // 4, base=3, octaves=6, aspect=1.6)
    tex2 = fbm(rng, H // 4, W // 4, base=7, octaves=4, aspect=2.6)
    t = cv2.resize(tex * 0.6 + tex2 * 0.4, (W, H), interpolation=cv2.INTER_CUBIC)
    # cloud billows: brighter rounded masses with darker rain-heavy undersides
    billow = smooth(t, 0.35, 0.75)
    yy = np.arange(H, dtype=np.float32)[:, None] / HORIZON_Y
    contrast = (0.30 + 0.20 * storm) * (1.0 + 0.8 * (1 - S.day))
    shade = 1.0 - (0.10 + 0.12 * storm) * I + (billow - 0.5) * contrast
    rs = base * shade[..., None]
    # ragged low scud drifting across the lower sky, slightly lighter
    scud = fbm(rng, H // 4, W // 4, base=10, octaves=4, aspect=4.0)
    scud = cv2.resize(scud, (W, H), interpolation=cv2.INTER_CUBIC)
    sband = np.exp(-((yy - 0.78) / 0.22) ** 2)
    sa = smooth(scud, 0.55, 0.85) * sband * 0.5
    rs = mix(rs, base * (1.15 + 0.25 * (1 - S.day)), sa)
    # town light reflecting off the cloud base at night (warm, low in the sky)
    if S.lights > 0.01:
        glow = np.clip(yy - 0.35, 0, 1) ** 2 * (0.6 + 0.4 * t) * 0.10 * S.lights * (1 - S.day)
        rs = screen(rs, glow[..., None] * C(0.95, 0.62, 0.38))
    g = lum(rs)[..., None]
    rs = g + (rs - g) * 0.6
    k = 0.6 + 0.35 * I
    full = mix(sky_layer, rs, np.full((H, W), k, np.float32))     # the rain sky everywhere (for reflections)
    return mix(img, full, S.sky), t, full


def haze_and_cloudbank(img, S, haze_col, I, storm, rng, glow=None):
    d = S.depth_s
    # distance haze: far shore + mountain strongly, mid town lightly, near nothing
    w = smooth(d, 0.45, 0.95) ** 1.3 * (0.26 + 0.34 * I + 0.1 * storm)
    w = w * (1 - S.sky)
    out = mix(img, np.broadcast_to(haze_col, img.shape), w)
    # low cloud hanging on the mountain's lower slopes: density grows down the slope, its
    # edge is the threshold of 2D noise (ragged tendrils, no straight cut), it dissolves
    # past the silhouette and fades with distance behind the near town
    px, py = MOUNTAIN_PEAK
    r0, r1 = py - 40, int(HORIZON_Y) + 190
    land = smooth(d, 0.60, 0.80) * (1 - S.sky)
    lm = blur(land, 3.0)[r0:r1]
    n = fbm(rng, H // 4, W // 4, base=5, octaves=5, aspect=3.0)
    n = cv2.resize(n, (W, H), interpolation=cv2.INTER_CUBIC)[r0:r1]
    n2 = fbm(rng, H // 4, W // 4, base=12, octaves=3, aspect=5.0)
    n2 = cv2.resize(n2, (W, H), interpolation=cv2.INTER_CUBIC)[r0:r1]
    yy = np.arange(r0, r1, dtype=np.float32)[:, None]
    xx = np.arange(W, dtype=np.float32)[None, :]
    u = np.clip((yy - (py + 40)) / 260.0, 0, 1.2)
    dens = u * 1.5 - 0.22 + (n - 0.5) * 1.0
    a = smooth(dens, 0.0, 0.55) * (0.45 + 0.35 * I) * (0.7 + 0.3 * n2)
    a = a * np.clip(0.4 + 0.6 * np.exp(-((xx - px) / 1000.0) ** 2), 0, 1)
    a = np.clip(a * lm, 0, 0.88)
    lit = 1.04 + 0.10 * S.day + 0.16 * (n2 - 0.5) + 0.20 * (1 - S.day) * (0.5 + u * 0.5)
    ccol = lum(haze_col[None, None])[0, 0] * C(0.94, 0.96, 1.0) * 0.6 + haze_col * 0.4
    cloud = ccol[None, None] * lit[..., None]
    if S.lights > 0.01:   # warm underside from the town below
        cloud = cloud + (u * 0.06 * S.lights * (1 - S.day))[..., None] * C(0.9, 0.6, 0.35)
    if glow is not None:   # lit from behind / inside by the lightning
        cloud = screen(cloud, np.clip(glow[r0:r1] * (0.4 + 0.6 * n2), 0, 1)[..., None] * C(0.62, 0.66, 0.85))
    # the same mist climbs a little above the ridge (ragged top), so the far skyline is not a
    # ruler line between dark cloud and pale land
    hy = HORIZON_Y + 25
    ds = (yy - (hy - 170)) / 170.0 * 1.25 + (n - 0.5) * 1.0
    a_sky = smooth(ds, 0.1, 0.75) * (0.50 + 0.30 * I) * (0.75 + 0.25 * n2) * S.sky[r0:r1]
    a_sky = a_sky * (1 - smooth(yy - hy, 20, 80))
    a = np.maximum(a, np.clip(a_sky, 0, 0.8))
    a = a * smooth(yy - r0, 0, 70)    # the slice has no hard top edge (a straight line used to show on clear sky)
    out[r0:r1] = mix(out[r0:r1], cloud, a)
    # mist rising off the far ridge: the land is hazed lighter than the storm sky, which left a ruler-straight
    # skyline (and lightning ending on it). Where far land meets sky, the sky fades into the land's own haze
    # colour over a ragged band whose height follows the cloud noise (alpha is 1 right at the ridge).
    sk = S.sky[r0:r1] > 0.5
    hh = r1 - r0
    has = sk[0] & ~sk[-1]
    ridge = hh - 1 - np.argmax(sk[::-1], axis=0)            # last sky row of each column
    ridge = np.clip(ridge, 0, hh - 14)
    cols = np.arange(W)
    land = np.stack([out[r0:r1][np.clip(ridge + k, 0, hh - 1), cols] for k in range(5, 14, 2)]).mean(0)
    far = S.depth_s[r0:r1][np.clip(ridge + 8, 0, hh - 1), cols] > 0.55
    far = blur((far & has).astype(np.float32)[None], 12)[0]
    land = cv2.GaussianBlur(land[None], (0, 0), 25)[0]
    hmist = 58.0 * SX
    dist = (ridge[None, :] - np.arange(hh, dtype=np.float32)[:, None]).astype(np.float32)
    t = np.clip(dist, 0, None) / hmist * (0.8 + 1.4 * n)   # fully gone within 1.25 bands: never reaches the slice top
    am = (1 - smooth(t, 0.0, 1.0)) * sk * far[None, :] * (0.85 + 0.15 * I)
    am = am * smooth(yy - r0, 0, 70)
    out[r0:r1] = mix(out[r0:r1], np.broadcast_to(land[None], (hh, W, 3)), np.clip(am, 0, 1))
    # and the first rows of land under the ridge (the rim of the mist), so no pale ruler line is left
    for k in range(1, 6):
        rr = np.clip(ridge + k, 0, hh - 1)
        al = (far * has * (0.9 - 0.16 * k) * smooth(rr.astype(np.float32), 0, 70))[:, None]
        cur = out[r0:r1][rr, cols]
        out[r0 + rr, cols] = cur + (land - cur) * al
    return out


def lake(img, S, I, storm, rng, sky_col, bolt=None):
    Wm = S.water
    ys, xs = np.nonzero(Wm > 0.05)
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    sub = img[y0:y1, x0:x1]
    h, w = sub.shape[:2]
    wm2 = Wm[y0:y1, x0:x1]
    t = (np.arange(h, dtype=np.float32) / max(1, h - 1))[:, None]  # 0 far .. 1 near
    deep = blur(cv2.erode((wm2 > 0.5).astype(np.uint8), np.ones((15, 15), np.uint8)).astype(np.float32), 4.0)
    # rain dimples break the reflections into short horizontal dashes
    nx = blur(rng.standard_normal((h, w)).astype(np.float32), 4.0, 0.7)
    nx /= nx.std() + 1e-6
    ny = blur(rng.standard_normal((h, w)).astype(np.float32), 2.0, 0.8)
    ny /= ny.std() + 1e-6
    amp = (1.0 + 3.0 * t) * (0.6 + 0.6 * I + 0.8 * storm) * (0.15 + 0.85 * deep)
    mx = np.broadcast_to(np.arange(w, dtype=np.float32)[None, :] + x0, (h, w)) + nx * amp * 1.6
    my = np.broadcast_to(np.arange(h, dtype=np.float32)[:, None] + y0, (h, w)) + ny * amp * 0.7
    mx = mx.astype(np.float32); my = my.astype(np.float32)
    broken = cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    # the mirror is gone: low-frequency reflection detail flattens toward the row average
    rs = (broken * wm2[..., None]).sum(axis=1) / (wm2.sum(axis=1)[:, None] + 1e-3)
    flat = np.broadcast_to(rs[:, None, :], broken.shape)
    lo = blur(broken, 12.0)
    broken = broken - lo + mix(lo, flat, np.full((h, w), 0.35, np.float32))
    # reflections chopped into dashes
    bands = blur(rng.standard_normal((h, w)).astype(np.float32), 6.0, 0.6)
    bands = np.clip(0.8 + bands / (bands.std() + 1e-6) * 0.25, 0.4, 1.3)
    hl = np.clip(lum(broken) - lum(lo), 0, 1)[..., None]
    broken = broken - hl * (1 - bands[..., None]) * 1.2
    g = lum(broken)[..., None]
    broken = g + (broken - g) * 0.85
    haze = sky_col[None, None] * (0.95 + 0.1 * S.day)
    broken = mix(broken, np.broadcast_to(haze, broken.shape), np.full((h, w), 0.18 + 0.14 * I, np.float32))

    # ripple rings + stipple: each dimple catches the sky / nearby light
    rings = np.zeros((h, w), np.uint8)       # drawn with shift=2 (quarter-pixel centres)
    n = int((350 + 900 * I) * (1.4 if storm else 1.0))
    ry = rng.random(n) ** 0.7
    rx = rng.random(n) * w
    rad = (1.5 + 9.0 * ry ** 1.4) * (0.6 + 0.8 * rng.random(n))
    val = (60 + 150 * rng.random(n) ** 2).astype(int)
    for i in range(n):
        r = rad[i]
        cx, cy = int(rx[i] * 4), int(ry[i] * (h - 1) * 4)
        ax, ay = max(2, int(r * 4)), max(2, int(r * 0.3 * 4))
        if r > 2.5 and rng.random() < 0.5:     # second, older ring
            cv2.ellipse(rings, (cx, cy), (int(ax * 1.7), int(ay * 1.7)), 0, 0, 360, int(val[i] * 0.55), 1, cv2.LINE_AA, 2)
        cv2.ellipse(rings, (cx, cy), (ax, ay), 0, 0, 360, int(val[i]), 1, cv2.LINE_AA, 2)
    ndot = int((300 + 700 * I) * (1.4 if storm else 1.0))
    dy = (rng.random(ndot) * h).astype(int)
    dx = (rng.random(ndot) * w).astype(int)
    stip = np.zeros((h, w), np.float32)
    stip[dy, dx] = rng.random(ndot)
    stip = np.clip(blur(stip, 0.55) * 2.2, 0, 1)
    rr = rings.astype(np.float32) / 255 * (0.12 + 0.88 * smooth(t, 0.05, 0.6))
    ripple = np.clip(rr + stip * 0.25, 0, 1) * (0.3 + 0.7 * deep)
    # the dimple highlight colour: sky plus any light reflected nearby
    near_l = blur(cv2.resize(broken, (w // 4, h // 4), interpolation=cv2.INTER_AREA), 3)
    near_l = cv2.resize(near_l, (w, h), interpolation=cv2.INTER_LINEAR)
    hi = np.maximum(np.broadcast_to(sky_col * 1.18 + 0.04, broken.shape), near_l * 1.4)
    out = mix(broken, np.clip(hi, 0, 1), np.clip(ripple * 1.3, 0, 1) * (0.75 - 0.15 * S.day))
    if storm:
        out = whitecaps(out, h, w, y0, x0, rng, sky_col, deep)
    if bolt is not None:
        # the lightning mirrored in the lake, broken by the chop
        rows = np.arange(y0, y1, dtype=np.float32)
        src = np.clip(LAKE_WY - (rows - LAKE_WY) * 2.2 - 8 * SX, 0, H - 1)
        bm = np.ascontiguousarray(bolt[src.astype(int)][:, x0:x1])
        bm = cv2.remap(bm, mx - x0 + nx * 4, my - y0, cv2.INTER_LINEAR)
        out = screen(np.clip(out, 0, 1), np.clip(blur(bm, 2.0, 5.0) * 0.6 * bands[..., None], 0, 1))
    wm = wm2[..., None]
    img[y0:y1, x0:x1] = sub * (1 - wm) + np.clip(out, 0, 1) * wm
    return img


def whitecaps(out, h, w, y0, x0, rng, sky_col, deep):
    """Wind chop that follows the lake plane: a noise field defined in ground coordinates
    (X = x/dy, Z = 1/dy below the eye line) is projected to the screen, so wave size and spacing
    shrink toward the far shore and crests run along the wind. Troughs darken, slopes facing the
    viewer catch the sky, and the highest crests break into streaky foam."""
    yy = np.arange(y0, y0 + h, dtype=np.float32)[:, None]
    dy = np.maximum(yy - HORIZON_Y, 30.0)
    xs = (np.arange(w, dtype=np.float32)[None, :] + x0 - W / 2)
    X = xs / dy
    Z = np.broadcast_to(1.0 / dy, (h, w))
    X = np.broadcast_to(X, (h, w))
    xmin, xmax, zmin, zmax = X.min(), X.max(), Z.min(), Z.max()
    Gh, Gw = 480, 1400
    mx = ((X - xmin) / (xmax - xmin) * (Gw - 1)).astype(np.float32)
    mz = ((Z - zmin) / (zmax - zmin) * (Gh - 1)).astype(np.float32)
    big = fbm(rng, Gh, Gw, base=9, octaves=4, aspect=5.0)
    fine = fbm(rng, Gh, Gw, base=30, octaves=3, aspect=7.0)
    hg = cv2.remap(big, mx, mz, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    fn = cv2.remap(fine, mx, mz, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    height = hg * 0.75 + fn * 0.25
    near = np.clip((yy - y0) / max(1, h - 1), 0, 1)                   # 0 far .. 1 near
    slope = np.gradient(blur(height, 1.2), axis=0)                      # + = tilted away from viewer
    slope = slope / (np.abs(slope).max() + 1e-6)
    out = out * (0.66 + 0.60 * height[..., None])                       # troughs dark, crests lighter
    skylit = np.clip(-slope, 0, 1) * (0.25 + 0.75 * near)
    col = np.clip(sky_col * 1.25 + 0.06, 0, 1)
    out = out + (skylit * 0.55 * deep)[..., None] * col
    foam = smooth(height, 0.60, 0.82) * smooth(fn, 0.35, 0.65) * (0.25 + 0.75 * near) * deep
    return mix(out, np.broadcast_to(np.clip(sky_col * 1.5 + 0.20, 0, 1), out.shape), np.clip(foam * 0.8, 0, 0.85))


# ---------------------------------------------------------------- wet world
_GEOM = {}


def geometry(S):
    key = S.A.name if hasattr(S.A, "name") else "x"
    if key in _GEOM:
        return _GEOM[key]
    day = S.A.day
    hsv = cv2.cvtColor((np.clip(day, 0, 1) * 255).astype(np.uint8), cv2.COLOR_BGR2HSV_FULL)
    sat = hsv[..., 1].astype(np.float32) / 255
    hue = hsv[..., 0].astype(np.float32)
    walk = poly_mask(WALK)
    for b in LANTERN_BODIES:
        cv2.fillPoly(walk, [np.array(b, np.int32)], 0.0)
    walk *= (sat < 0.38).astype(np.float32)          # no grass / flowers
    walk = cv2.morphologyEx(walk, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    walk = blur(walk, 1.2)
    # mirror line: the far (top) edge of the paving in each column
    cols = np.where(poly_mask(WALK).any(axis=0))[0]
    pm = poly_mask(WALK)
    top = np.full(W, H, np.float32)
    top[cols] = np.argmax(pm[:, cols] > 0.5, axis=0)
    # wooden railing: warm-brown wood inside the rail zone
    rz = poly_mask(RAIL_ZONE)
    wood = ((hue < 40) | (hue > 240)) & (sat > 0.25) & (sat < 0.85)
    rail = blur(rz * wood.astype(np.float32), 0.8)
    railtop = np.clip(rail - np.roll(rail, 3, axis=0), 0, 1) * rz
    # roofs: blue-grey tiles that face the sky (pagodas, town, foreground roof, pavilion)
    B, G, R = day[..., 0], day[..., 1], day[..., 2]
    tile = (B > R + 0.03) & (B >= G - 0.02) & (S.sky < 0.5) & (S.water < 0.5)
    tile = tile & (S.depth < 0.62)
    roof = blur(tile.astype(np.float32), 1.0)
    # sky the template's sky mask missed (e.g. a smooth painted band above the pavilion roof):
    # the depth map says sky there and the paint is smooth and unsaturated
    extra = np.zeros((H, W), np.float32)
    if S.A.depth is not None:
        zone = np.zeros((H, W), np.float32); zone[240:720, 1840:] = 1
        Ld = lum(day)
        grad = cv2.morphologyEx(Ld, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
        cand = (S.A.depth > 0.97) & (S.sky < 0.5) & (sat < 0.3) & (blur(grad, 2) < 0.05) & (zone > 0)
        cand = cv2.morphologyEx(cand.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        extra = np.clip(blur(cand.astype(np.float32), 1.5) * (S.A.depth > 0.95), 0, 1)
    _GEOM[key] = dict(walk=walk, top=top, cols=cols, rail=rail, railtop=railtop, roof=roof, extra_sky=extra)
    return _GEOM[key]


def wet_world(img, S, G, I, storm, rng, rsky):
    out = img.copy()
    # ---- roofs: wet tiles darker with a sky sheen on every tile ridge
    roof = G["roof"] * (0.6 + 0.4 * I)
    L = lum(img)
    hp = L - blur(L, 2.5)
    skyl = float(np.mean(lum(rsky[200:int(HORIZON_Y)])))
    sheen = np.clip(hp * 6, 0, 1) * (0.25 + 0.6 * skyl)
    sheen_col = rsky[200:400].reshape(-1, 3).mean(axis=0)
    out = mix(out, out * 0.82, roof)
    out = out + (sheen * roof)[..., None] * np.clip(sheen_col * 1.4 + S.glow * 0.6, 0, 1)
    # ---- railing: darker, top edges catch the light
    rail = G["rail"] * (0.5 + 0.5 * I)
    out = mix(out, out * 0.72, rail)
    out = out + (G["railtop"] * (0.10 + 0.25 * skyl))[..., None] * (sheen_col + S.glow * 1.5)

    # ---- walkway: dark wet stone, glossy reflections, puddles in the low spots
    walk = G["walk"]
    cols = G["cols"]
    xa, xb = int(cols.min()), int(cols.max()) + 1
    ya = int(G["top"][cols].min()) - 4
    sub = out[ya:, xa:xb]
    h, w = sub.shape[:2]
    top = G["top"][xa:xb][None, :]
    yy = np.arange(ya, H, dtype=np.float32)[:, None] * np.ones((1, w), np.float32)
    xx = np.arange(xa, xb, dtype=np.float32)[None, :] * np.ones((h, 1), np.float32)
    tdown = np.clip((yy - top) / np.maximum(H - top, 1), 0, 1)       # 0 far edge .. 1 bottom
    # rippled reflection: displacement grows toward the viewer, in horizontal bands
    rip = blur(rng.standard_normal((h, w)).astype(np.float32), 3.0, 1.0)
    dx = rip * (2.0 + 9.0 * tdown) + np.sin(yy * 0.9 + rip * 2) * (0.8 + 2.5 * tdown)
    # shallow puddles in the low spots (flattened by perspective): smooth water, a near mirror
    puddles = fbm(rng, h, w, base=7, octaves=4, aspect=3.2)
    low = np.exp(-((tdown - 0.55) / 0.35) ** 2)
    pud = smooth(puddles * (0.7 + 0.5 * low), 0.70 - 0.08 * I, 0.74 - 0.08 * I)
    dx = dx * (1 - 0.8 * pud)
    src_near = (2 * top - yy).astype(np.float32)
    near_img = cv2.remap(img, (xx + dx).astype(np.float32), np.clip(src_near, 0, H - 1), cv2.INTER_LINEAR)
    nearness = (1 - smooth(S.depth, 0.24, 0.40)) * (1 - S.sky)
    near_ok = cv2.remap(nearness, (xx + dx).astype(np.float32), np.clip(src_near, 0, H - 1), cv2.INTER_LINEAR)
    near_ok = near_ok * (src_near > 0)
    src_far = (2 * HORIZON_Y - yy).astype(np.float32)
    skyb = blur(rsky, 6, 3)
    far_img = cv2.remap(skyb, (xx + dx * 2).astype(np.float32), np.clip(src_far, 0, H - 1), cv2.INTER_LINEAR)
    R = mix(far_img, near_img, near_ok)
    # wet light streaks: bright reflections smear into long vertical columns
    lamp = cv2.dilate(S.warm, np.ones((5, 5), np.uint8)) * S.lights
    lamp = cv2.remap(lamp, (xx + dx).astype(np.float32), np.clip(src_near, 0, H - 1), cv2.INTER_LINEAR) * near_ok
    bright = np.clip(R - 0.22, 0, 1) * lamp[..., None]
    kl = 140
    kern = np.exp(-np.arange(kl, dtype=np.float32) / 45.0)[:, None]
    kern = np.vstack([np.zeros((kl - 1, 1), np.float32), kern])     # only smears downward
    kern /= kern.sum()
    sm = cv2.filter2D(blur(bright, 2.0, 1.0), -1, kern, borderType=cv2.BORDER_CONSTANT)
    wave = 0.55 + 0.45 * np.sin(yy * 0.42 + rip * 2.5) ** 2
    streak = (blur(bright, 1.5, 6.0) * 1.2 + sm * 9.0 * wave[..., None]) * 1.0
    Ls = lum(sub)
    stone = np.clip(0.55 + (Ls - blur(Ls, 3.0)) * 6.0, 0.15, 1.2)      # stone tops gloss, joints less
    fres = (0.62 - 0.40 * tdown) * (0.5 + 0.5 * I)
    wetd = sub * (0.58 - 0.08 * I)
    g = lum(wetd)[..., None]
    wetd = g + (wetd - g) * 1.15
    gloss = 0.5 + 0.3 * (1 - S.day)
    wet = wetd + R * (fres * stone)[..., None] * gloss + streak * (fres * stone)[..., None] * 1.3
    rim = np.clip(blur(pud, 3.0) * 1.6 - pud, 0, 1)                  # damp dark margin
    wet = wet * (1 - 0.3 * rim[..., None])
    pool = mix(wetd * 0.4, R * 0.92 + streak * 0.9, np.full((h, w), 0.88, np.float32))
    wet = mix(wet, pool, pud)
    # hanging lantern: long warm streak on the far wet paving below it
    if S.lights > 0.01:
        hx = HANG_LANTERN[0]
        col = np.exp(-((xx - hx - dx * 1.5) / 16.0) ** 2) * np.clip(1 - tdown * 0.9, 0, 1)
        col = col * (0.55 + 0.45 * np.sin(yy * 0.55 + rip * 3) ** 2)
        wet = wet + (col * stone * (0.5 + pud))[..., None] * C(1.0, 0.70, 0.36) * 0.45 * S.lights
    # rain rings spreading on the puddles (perspective-flattened, bigger near the viewer)
    rl = np.zeros((h, w), np.uint8)
    py_, px_ = np.nonzero(pud[::3, ::3] > 0.6)
    if len(py_):
        for i in rng.integers(0, len(py_), int(40 + 140 * I)):
            cy, cx = py_[i] * 3, px_[i] * 3
            r = (2.5 + 7.0 * tdown[cy, cx]) * rng.uniform(0.6, 1.4)
            v = int(120 + 135 * rng.random())
            cv2.ellipse(rl, (int(cx * 4), int(cy * 4)), (int(r * 4), max(2, int(r * 0.3 * 4))), 0, 0, 360, v, 1, cv2.LINE_AA, 2)
            if r > 5 and rng.random() < 0.6:
                cv2.ellipse(rl, (int(cx * 4), int(cy * 4)), (int(r * 2.3), max(2, int(r * 0.7))), 0, 0, 360, int(v * 0.8), 1, cv2.LINE_AA, 2)
    ra = blur(rl.astype(np.float32) / 255, 0.5) * pud
    ring_col = np.clip(blur(R, 3.0) * 1.6 + S.amb * 0.3 + 0.03, 0, 1)
    wet = mix(wet, ring_col, ra * 0.7)
    m = walk[ya:, xa:xb, None]
    out[ya:, xa:xb] = sub * (1 - m) + np.clip(wet, 0, 1.2) * m
    return out


# ---------------------------------------------------------------- rain streaks
def streak_layer(rng, n, length, thick, angle, accept=None, blur_s=0.0, taper=True):
    canvas = np.zeros((H, W), np.uint8)
    if n <= 0:
        return canvas.astype(np.float32)
    x = rng.random(n) * (W + 200) - 100
    y = rng.random(n) * (H + 100) - 50
    if accept is not None:
        ix = np.clip(x, 0, W - 1).astype(int); iy = np.clip(y, 0, H - 1).astype(int)
        keep = rng.random(n) < accept[iy, ix]
        x, y = x[keep], y[keep]
    m = len(x)
    L = length[0] + (length[1] - length[0]) * rng.random(m)
    a = np.radians(angle + rng.normal(0, 1.2, m))
    ddx, ddy = np.sin(a) * L, np.cos(a) * L
    v = rng.random(m)
    buckets = [(0.0, 0.35, 90), (0.35, 0.7, 160), (0.7, 1.01, 255)]
    for lo, hi, val in buckets:
        s = (v >= lo) & (v < hi)
        if not s.any():
            continue
        p0 = np.stack([x[s] - ddx[s] / 2, y[s] - ddy[s] / 2], 1)
        p1 = np.stack([x[s] + ddx[s] / 2, y[s] + ddy[s] / 2], 1)
        if taper:   # dim long tail, brighter core
            pts = np.stack([p0, p1], 1).round().astype(np.int32)
            cv2.polylines(canvas, list(pts), False, int(val * 0.45), thick, cv2.LINE_AA)
            q0, q1 = p0 * 0.75 + p1 * 0.25, p0 * 0.2 + p1 * 0.8
            pts = np.stack([q0, q1], 1).round().astype(np.int32)
            cv2.polylines(canvas, list(pts), False, val, thick, cv2.LINE_AA)
        else:
            pts = np.stack([p0, p1], 1).round().astype(np.int32)
            cv2.polylines(canvas, list(pts), False, val, thick, cv2.LINE_AA)
    out = canvas.astype(np.float32) / 255
    if blur_s:
        out = blur(out, blur_s)
    return out


def rain_streaks(img, S, I, storm, rng):
    angle = 18.0 if storm else 7.0
    k = 0.25 + 0.75 * I
    if storm:
        k *= 1.35
    # gusty sheets of rain: density varies smoothly, never a uniform screen-door
    sheets = cv2.resize(fbm(rng, H // 8, W // 8, base=4, octaves=4, aspect=0.6), (W, H))
    sh = 0.35 + 0.65 * sheets
    layers = [
        # (count, length, thickness, blur, alpha, depth_from, depth_to)
        (int(16000 * k), (7, 14), 1, 0.0, 0.16, 0.50, 0.70),
        (int(6500 * k), (16, 30), 1, 0.0, 0.22, 0.20, 0.36),
        (int(1500 * k), (45, 85), 1, 0.7, 0.30, 0.0, 0.08),
        (int(260 * k), (110, 190), 3, 1.8, 0.24, 0.0, 0.0),
        (int(40 * k), (220, 360), 6, 3.5, 0.13, 0.0, 0.0),
    ]
    total = np.zeros((H, W), np.float32)
    for n, length, th, bs, alpha, d0, d1 in layers:
        lay = streak_layer(rng, n, length, th, angle, accept=sh, blur_s=bs)
        vis = smooth(S.depth_s, d0 - 0.05, d1) if d1 > 0 else 1.0
        total += lay * alpha * vis
    # streak colour: brighter than its surroundings, warm where it crosses lantern light
    env = S.env
    # a drop refracts the whole sky dome toward the viewer: its brightness is the ambient sky
    # light (plus any lantern light nearby), not the background directly behind it
    col = S.amb[None, None] * 1.08 + (0.11 + 0.03 * storm) * (1 - 0.75 * S.day) + env * 0.15 + S.glow * 1.6
    # contrast: visible over dark things, nearly invisible over bright sky
    vis = np.clip((lum(col) - lum(img)) * 3.5 + 0.06, 0, 1) + np.clip(lum(S.glow), 0, 1)
    a = np.clip(total * vis * (0.8 + 0.4 * I) * (1 + 2.5 * np.clip(lum(S.glow), 0, 1)), 0, 0.85)
    return mix(img, np.clip(col, 0, 1.2), a)


# ---------------------------------------------------------------- splashes and drips
def splashes(img, S, G, I, storm, rng):
    layer = np.zeros((H, W), np.uint8)
    walk = G["walk"]
    ys, xs = np.nonzero(walk[::2, ::2] > 0.8)
    ys, xs = ys * 2, xs * 2
    n = int((70 + 200 * I) * (1.4 if storm else 1.0))
    if len(ys):
        idx = rng.integers(0, len(ys), n)
        for i in idx:
            x, y = int(xs[i]), int(ys[i])
            s = 0.6 + 1.6 * (y - 1270) / 170.0              # bigger nearer the viewer
            v = int(110 + 145 * rng.random())
            r = max(2, int(3 * s * (0.7 + 0.6 * rng.random())))
            cv2.ellipse(layer, (x, y), (r, max(1, r // 3)), 0, 0, 360, v // 2, 1, cv2.LINE_AA)
            # crown: little droplets thrown up in an arc
            for j in range(int(rng.integers(2, 5))):
                ang = math.pi * (0.15 + 0.7 * rng.random())
                d = r * (0.8 + 0.9 * rng.random())
                px = int(x + math.cos(ang) * d * 1.2)
                py = int(y - math.sin(ang) * d * 1.3 - 1)
                cv2.circle(layer, (px, py), 1 if s < 1.4 else 1, v, -1, cv2.LINE_AA)
            cv2.line(layer, (x, y - 1), (x, y - int(2 + 2 * s)), int(v * 0.7), 1, cv2.LINE_AA)
    # spray on railing tops
    ys, xs = np.nonzero(G["railtop"] > 0.3)
    if len(ys):
        idx = rng.integers(0, len(ys), int((60 + 160 * I) * (1.4 if storm else 1.0)))
        for i in idx:
            x, y = int(xs[i]), int(ys[i])
            v = int(100 + 150 * rng.random())
            for j in range(int(rng.integers(1, 4))):
                cv2.circle(layer, (x + int(rng.integers(-3, 4)), y - int(rng.integers(1, 5))), 0, v, -1, cv2.LINE_AA)
    # spray on lantern roofs
    for (cx, cy), rx, ry in LANTERN_CAPS:
        for j in range(int(18 + 40 * I)):
            t = rng.uniform(-1, 1)
            x = int(cx + t * rx)
            y = int(cy - ry * math.sqrt(max(0.0, 1 - t * t)) * 0.6 - rng.random() * 5)
            v = int(90 + 150 * rng.random())
            cv2.circle(layer, (x, y), int(rng.integers(0, 2)), v, -1, cv2.LINE_AA)
    ys = np.nonzero(layer.any(axis=1))[0]
    if not len(ys):
        return img
    r0, r1 = max(0, ys.min() - 2), min(H, ys.max() + 3)
    a = blur(layer[r0:r1].astype(np.float32) / 255, 0.5) * (0.30 + 0.25 * I)
    gl = S.glow[r0:r1]
    a = a * np.clip(0.25 + 0.75 * S.day + lum(gl) * 3.0, 0, 1.2)
    col = np.clip(S.env[r0:r1] * 1.6 + 0.08, 0, 1) + gl * 2.0
    img[r0:r1] = mix(img[r0:r1], np.clip(col, 0, 1), np.clip(a, 0, 1))
    return img


def eave_drips(img, S, I, storm, rng):
    """Water running off the pavilion eave: beads on the tile edge, thin broken streams and
    single falling drops, irregularly spaced (more at the tile valleys)."""
    layer = np.zeros((H, W), np.uint8)
    pts = np.array(EAVE, np.float32)
    nd = int(8 + 8 * I + (6 if storm else 0))
    xs = np.sort(rng.uniform(pts[0, 0] + 6, pts[-1, 0] - 4, nd * 2))
    keep = np.ones(len(xs), bool)
    keep[1:] = np.diff(xs) > 9                                   # no two drips side by side
    hx = HANG_LANTERN[0]
    keep &= (np.abs(xs - hx) > 55) | (rng.random(len(xs)) < 0.15)  # don't pour onto the lantern
    xs = xs[keep][:nd]
    wind = 0.22 if storm else 0.05
    for x in xs:
        y = float(np.interp(x, pts[:, 0], pts[:, 1]))
        xi = int(x)
        v0 = int(170 + 80 * rng.random())
        cv2.ellipse(layer, (xi, int(y) + 2), (1, 2), 0, 0, 360, v0, -1, cv2.LINE_AA)   # bead
        fall = 60 + rng.random() ** 0.7 * (230 + 200 * I)
        stream = rng.random() < 0.35 * (0.5 + I)
        yy = y + 4 + rng.random() * 10
        if stream:
            # a thin continuous trickle that breaks up into drops lower down
            L = fall * rng.uniform(0.25, 0.5)
            p0 = (int(xi * 4), int(yy * 4))
            p1 = (int((xi + wind * L) * 4), int((yy + L) * 4))
            cv2.line(layer, p0, p1, int(v0 * 0.75), 1, cv2.LINE_AA, 2)
            yy += L + 4
        drift = (yy - y) * wind
        while yy < y + fall:
            L = 2 + (yy - y) * 0.06 * rng.uniform(0.7, 1.3)
            v = int(v0 * rng.uniform(0.6, 1.0))
            cv2.line(layer, (int((xi + drift) * 4), int(yy * 4)), (int((xi + drift + wind * L) * 4), int((yy + L) * 4)), v, 1, cv2.LINE_AA, 2)
            gap = L + 4 + rng.random() * (10 + (yy - y) * 0.35)
            yy += gap
            drift += wind * gap
    r0, r1 = 400, 1100
    a = layer[r0:r1].astype(np.float32) / 255 * (0.55 + 0.3 * I)
    col = np.clip(S.amb * 1.25 + 0.10 + S.env[r0:r1] * 0.25, 0, 1) + S.glow[r0:r1] * 2.0
    img[r0:r1] = mix(img[r0:r1], np.clip(col, 0, 1), np.clip(a, 0, 1))
    return img


# ---------------------------------------------------------------- storm: lightning + debris
def lightning(S, rng):
    """Branching bolt from the cloud base down behind the mountain / far hills (the terrain and
    the low cloud bank hide its lower end). Returns (core, glow) at output size."""
    canvas = np.zeros((H, W), np.float32)
    x0 = rng.uniform(260, 1750)
    y0 = rng.uniform(200, 420)
    x1 = float(np.clip(x0 + rng.uniform(-220, 220), 200, 1800))
    y1 = HORIZON_Y + rng.uniform(30, 110)

    def bolt(p, q, disp, depth, width, val):
        segs = [p, q]
        d = disp
        for _ in range(8):
            new = [segs[0]]
            for a, b in zip(segs, segs[1:]):
                mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
                L = math.hypot(b[0] - a[0], b[1] - a[1])
                nx, ny = -(b[1] - a[1]) / (L + 1e-6), (b[0] - a[0]) / (L + 1e-6)
                off = rng.normal(0, d)
                new += [(mx + nx * off, my + ny * off), b]
            segs = new
            d *= 0.52
        arr = np.array(segs, np.float32)
        cv2.polylines(canvas, [np.round(arr * 4).astype(np.int32)], False, val, width, cv2.LINE_AA, 2)
        if depth < 3:
            nb = [int(rng.integers(3, 6)), int(rng.integers(1, 3)), int(rng.integers(0, 2))][depth]
            for _ in range(nb):
                i = int(rng.integers(len(arr) // 8, len(arr) * 3 // 4))
                a = arr[i]
                ang = math.atan2(q[1] - p[1], q[0] - p[0]) + rng.choice([-1, 1]) * rng.uniform(0.3, 1.0)
                L = math.hypot(q[0] - p[0], q[1] - p[1]) * rng.uniform(0.15, 0.4) * (0.7 ** depth)
                b = (a[0] + math.cos(ang) * L, a[1] + math.sin(ang) * L)
                bolt(tuple(a), b, disp * 0.4, depth + 1, 1, val * rng.uniform(0.45, 0.7))

    bolt((x0, y0), (x1, y1), 38.0, 0, 2, 1.0)
    # the lower end thins out in the rain haze instead of ending on a hard line
    canvas *= (1.0 - 0.85 * smooth(np.arange(H, dtype=np.float32), HORIZON_Y - 150, HORIZON_Y - 20))[:, None]
    core = np.clip(canvas + blur(canvas, 1.2) * 0.8, 0, 1)
    small = cv2.resize(canvas, (W // 8, H // 8), interpolation=cv2.INTER_AREA)
    g = 0
    for sg, wgt in ((1.5, 0.55), (6.0, 0.35), (22.0, 0.30)):
        b = blur(small, sg)
        g = g + b / (b.max() + 1e-6) * wgt
    glow = cv2.resize(g, (W, H), interpolation=cv2.INTER_LINEAR)
    return core, glow, (x1, y1)


def _petal(size, rng):
    """Sakura petal outline: a rounded oval with a notch at the outer tip (unit: px)."""
    t = np.linspace(0, 2 * np.pi, 28, endpoint=False)
    x = np.cos(t) * size
    y = np.sin(t) * size * 0.62 * (1 - 0.25 * np.cos(t))
    notch = np.exp(-(((t + np.pi) % (2 * np.pi) - np.pi) / 0.35) ** 2)
    x = x - notch * size * 0.35
    return np.stack([x, y], 1)


def _leaf(size, rng, maple):
    if maple:   # five pointed lobes
        t = np.linspace(0, 2 * np.pi, 10, endpoint=False) - np.pi / 2
        r = np.where(np.arange(10) % 2 == 0, size, size * 0.45)
        r[[4, 6]] *= 0.75
        pts = np.stack([np.cos(t) * r, np.sin(t) * r], 1)
        return np.vstack([pts, [[0, size * 0.55]]])
    t = np.linspace(0, 2 * np.pi, 24, endpoint=False)
    x = np.cos(t) * size
    y = np.sin(t) * size * 0.38 * np.abs(np.sin(t)) ** 0.2
    return np.stack([x, y], 1)


def storm_debris(img, S, rng, angle):
    """Leaves / petals torn off and blown along the wind, most small and far, a few big and
    close (motion-blurred). None in winter."""
    season = S.season
    if season == "winter":
        return img
    pal = {"spring": [C(0.98, 0.80, 0.87), C(0.96, 0.68, 0.80), C(1.0, 0.90, 0.93)],
           "summer": [C(0.34, 0.60, 0.20), C(0.46, 0.68, 0.26), C(0.26, 0.48, 0.16)],
           "autumn": [C(0.86, 0.20, 0.08), C(0.95, 0.48, 0.10), C(0.92, 0.68, 0.16), C(0.68, 0.14, 0.08)]}[season]
    out = img.copy()
    wind = math.radians(90 + angle + 30)        # blown sideways much more than the rain falls
    n = 110
    amb = 0.5 + 0.5 * S.day
    for k in range(n):
        near = rng.random() ** 2.4             # most far / small, a few big and near
        size = 2.2 + near * 13
        # more where the tree is (upper right), carried left and down by the wind
        if rng.random() < 0.55:
            x, y = rng.uniform(900, W), rng.uniform(0, H * 0.65)
        else:
            x, y = rng.uniform(0, W), rng.uniform(0, H * 0.95)
        ix, iy = int(np.clip(x, 0, W - 1)), int(np.clip(y, 0, H - 1))
        if near < 0.35 and S.depth_s[iy, ix] < 0.3 - near:
            continue
        if S.warm[max(0, iy - 30):iy + 30, max(0, ix - 30):ix + 30].max() > 0.3:
            continue                           # small (far) ones can't be in front of near things
        if season == "spring":
            pts = _petal(size, rng)
        else:
            pts = _leaf(size, rng, season == "autumn" and size > 6 and rng.random() < 0.6)
        a = rng.uniform(0, 2 * np.pi)
        sq = rng.uniform(0.35, 1.0)             # tumbling: foreshortened
        R = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
        pts = (pts * [1, sq]) @ R.T
        blen = int(2 + near * (7 if season == "spring" else 12))
        pad = int(size * 1.5 + blen + 4)
        spr = np.zeros((2 * pad, 2 * pad), np.float32)
        shade = np.zeros_like(spr)
        cv2.fillPoly(spr, [np.round((pts + pad) * 4).astype(np.int32)], 1.0, cv2.LINE_AA, 2)
        # light from above-left, darker toward the far edge; central vein
        g = np.linspace(1.1, 0.75, 2 * pad, dtype=np.float32)
        shade[:] = g[:, None] * (0.9 + 0.1 * rng.random())
        if season != "spring" and size > 5:
            p0 = (pts[0] * 0.9 + pad) * 4
            cv2.line(shade, tuple(np.round(p0).astype(int)), (pad * 4, pad * 4), 0.6, 1, cv2.LINE_AA, 2)
        # motion blur along the wind
        kl = blen * 2 + 1
        ker = np.zeros((kl, kl), np.float32)
        cv2.line(ker, (int(kl / 2 - math.cos(wind) * blen), int(kl / 2 - math.sin(wind) * blen)),
                 (int(kl / 2 + math.cos(wind) * blen), int(kl / 2 + math.sin(wind) * blen)), 1.0, 1, cv2.LINE_AA)
        ker /= ker.sum()
        alpha = cv2.filter2D(spr, -1, ker)
        shade = cv2.filter2D(spr * shade, -1, ker) / (alpha + 1e-4)
        alpha = np.clip(alpha * (1.2 + 0.2 * near), 0, 1) * (0.8 + 0.2 * near)
        x0, y0 = int(x) - pad, int(y) - pad
        xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + 2 * pad), min(H, y0 + 2 * pad)
        if xb <= xa or yb <= ya:
            continue
        al = alpha[ya - y0:yb - y0, xa - x0:xb - x0]
        sh = shade[ya - y0:yb - y0, xa - x0:xb - x0]
        col = pal[int(rng.integers(len(pal)))] * rng.uniform(0.8, 1.05)
        light = amb + lum(S.glow[iy, ix][None, None])[0, 0] * 1.5
        c = col[None, None] * (sh[..., None] * light) + S.glow[ya:yb, xa:xb] * 0.4
        # far leaves sit inside the haze
        hz = smooth(S.depth_s[iy, ix], 0.5, 1.0) * (1 - near) * 0.5
        c = mix(c, np.broadcast_to(S.amb, c.shape), np.full(al.shape, hz, np.float32))
        out[ya:yb, xa:xb] = mix(out[ya:yb, xa:xb], np.clip(c, 0, 1), al)
    return out


# ---------------------------------------------------------------- main
def _rain(img, ctx, storm):
    S = Scene(img, ctx)
    I = float(np.clip(ctx.get("intensity", 1.0), 0, 1))
    if storm:
        I = max(I, 0.85)
    rng = np.random.default_rng(seed_of(S.when, 1 + storm))
    G = geometry(S)
    S.sky = np.maximum(S.sky, G["extra_sky"])
    out = img.astype(np.float32).copy()

    # 1. overall grade: darker, flatter, less saturated (wet light under heavy cloud)
    g = lum(out)[..., None]
    out = g + (out - g) * (1 - 0.22 * I - 0.1 * storm)
    out = out * (1 - (0.16 + 0.08 * storm) * I * (0.4 + 0.6 * S.day))

    # 2. sky: low textured rain cloud
    sky_layer = ctx.get("sky")
    if sky_layer is None:
        sky_layer = out
    out, ctex, rsky = rain_sky(out, S, sky_layer * (1 - (0.12 + (0.10 + 0.22 * S.day) * storm) * I), I, storm, rng)
    hr = int(HORIZON_Y)
    rows = out[hr - 60:hr, :]
    smask = S.sky[hr - 60:hr, :, None]
    sky_col = (rows * smask).sum(axis=(0, 1)) / (smask.sum() + 1e-3)
    if smask.sum() < 50:
        sky_col = sky_layer[hr - 30:hr].reshape(-1, 3).mean(axis=0)
    haze_col = sky_col * (0.95 + 0.05 * S.day)
    S.amb = rsky[60:int(HORIZON_Y)].reshape(-1, 3)[::97].mean(axis=0)

    bolt_core = None
    glow = None
    if storm:
        core, glow, (bx, by) = lightning(S, np.random.default_rng(seed_of(S.when, 77)))
        core = core * S.sky
        # clouds near the bolt lit from inside: the glow follows the billows of the cloud texture
        bill = smooth(ctex, 0.25, 0.85)
        lit = glow[..., None] * C(0.70, 0.74, 0.95) * (0.15 + 1.1 * bill[..., None])
        sky_part = screen(out, np.clip(lit * (0.85 - 0.35 * S.day), 0, 1))
        sky_part = mix(sky_part, np.broadcast_to(C(0.93, 0.95, 1.0), out.shape), core)
        out = mix(out, sky_part, S.sky)
        bolt_core = (core[..., None] * C(0.9, 0.92, 1.0) + (glow * S.sky)[..., None] * 0.2 * C(0.7, 0.75, 1.0))
        # cold flash on the scene: strongest on surfaces facing the sky and in the open
        flash = 0.035 + 0.11 * (1 - S.day)
        up = np.clip(S.A.day.astype(np.float32), 0, 1)
        Lu = lum(up)
        facing = np.clip(0.3 + (Lu - blur(Lu, 6)) * 3 + 0.4 * Lu, 0, 1.2)
        reach = 0.6 + 0.4 * smooth(S.depth_s, 0.1, 0.9)
        fl = (facing * reach * (1 - S.sky))[..., None] * up * C(0.80, 0.86, 1.0) * flash
        out = screen(out, np.clip(fl * 2.0, 0, 1))
        # the strike lights the ridge, hills and cloud base around where it lands
        gx = np.exp(-(((np.arange(W, dtype=np.float32) - bx) / 420.0) ** 2))[None, :]
        gy = np.exp(-(((np.arange(H, dtype=np.float32) - by) / 170.0) ** 2))[:, None]
        land = (gx * gy * (1 - S.sky) * smooth(S.depth_s, 0.5, 0.8))[..., None] * C(0.62, 0.68, 0.95)
        out = screen(out, np.clip(land * (0.9 - 0.5 * S.day), 0, 1))
        rsky = screen(rsky, np.clip(lit * 0.35, 0, 1))

    # 3. distance haze and the low cloud bank on the mountain
    out = haze_and_cloudbank(out, S, haze_col, I, storm, rng, glow)
    # 4. lake: dimpled, broken reflections, rings, haze (whitecaps in a storm)
    out = lake(out, S, I, storm, rng, sky_col, bolt_core)
    # 5. wet world
    out = wet_world(out, S, G, I, storm, rng, rsky)
    # 6. splashes + eave drips (near field)
    out = splashes(out, S, G, I, storm, rng)
    out = eave_drips(out, S, I, storm, rng)
    # 7. falling rain
    out = rain_streaks(out, S, I, storm, rng)
    if storm:
        out = storm_debris(out, S, rng, 18.0)
    return np.clip(out, 0, 1)


class _SmallAssets:
    """View of timeofday.Assets with every full-frame array resized to this module's 2560x1441 grid."""
    def __init__(self, A, shape):
        self._A = A
        for k, v in vars(A).items():
            if isinstance(v, np.ndarray) and v.ndim >= 2 and v.shape[:2] == shape:
                v = cv2.resize(v, (W, H), interpolation=cv2.INTER_AREA)
            setattr(self, k, v)


def _at_native(img, ctx, storm):
    """The effect is tuned on a 2560x1441 grid. For any other frame size run it there and add the
    change back onto the full-resolution frame (so the 4K detail of the plate is kept)."""
    if img.shape[1] == W and img.shape[0] == H:
        return _rain(img, ctx, storm)
    shape = img.shape[:2]
    small = cv2.resize(img, (W, H), interpolation=cv2.INTER_AREA)
    c2 = dict(ctx)
    c2["A"] = _SmallAssets(ctx["A"], shape)
    if c2.get("sky") is not None and c2["sky"].shape[:2] == shape:
        c2["sky"] = cv2.resize(c2["sky"], (W, H), interpolation=cv2.INTER_AREA)
    if c2.get("sun_xy") is not None:
        k = W / shape[1]
        c2["sun_xy"] = (c2["sun_xy"][0] * k, c2["sun_xy"][1] * k)
    out = _rain(small, c2, storm)
    delta = cv2.resize(out - small, (shape[1], shape[0]), interpolation=cv2.INTER_CUBIC)
    return np.clip(img + delta, 0, 1)


def apply(img, ctx):
    return _at_native(img, ctx, False)


def apply_storm(img, ctx):
    return _at_native(img, ctx, True)
