"""Plate-building helpers for render/timeofday.py (base px, 1672x941, float32 BGR in [0,1]).

Everything here is generic: it works on any season template with the shared composition.
  - detect_lights   : lantern / window paper panels, far-shore dots, light spill on the path
  - lights_off      : daytime version of the lights (solid unlit paper lanterns, glow removed)
  - calm_water      : lake without any painted reflections (clean base for day / golden plates)
  - night_grade     : day-for-night grade that keeps hue (red leaves stay red, only darker/cooler)
  - light_reflections: thin, broken, shimmering reflections of the shore lights on the lake
"""
import numpy as np, cv2

BW, BH = 1672, 941
# walkway and stone-lantern bodies (base px, same as render/render.py)
PATH = [(790, 941), (800, 915), (900, 888), (1000, 868), (1100, 857), (1200, 848), (1300, 838),
        (1390, 828), (1400, 860), (1440, 900), (1480, 941)]
LANTERN_BODIES = [[(893, 790), (958, 790), (958, 896), (893, 896)],
                  [(1246, 752), (1291, 752), (1291, 836), (1246, 836)]]


def lum(img):
    return img[..., 0] * 0.114 + img[..., 1] * 0.587 + img[..., 2] * 0.299


def feather(m, s):
    return cv2.GaussianBlur(m.astype(np.float32), (0, 0), s)


def mix(a, b, t):
    if np.ndim(t) == 2:
        t = t[..., None]
    return a * (1 - t) + b * t


def C(r, g, b):
    return np.array([b, g, r], np.float32)


def disk(r):
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))


def poly_mask(polys, shape=(BH, BW)):
    m = np.zeros(shape, np.uint8)
    cv2.fillPoly(m, [np.array(p, np.int32) for p in polys], 1)
    return m


def normconv(img, w, sx, sy=None):
    """Weighted blur: average of img over pixels where w > 0 (fills holes smoothly)."""
    sy = sx if sy is None else sy
    w = w.astype(np.float32)
    num = cv2.GaussianBlur(img * (w[..., None] if img.ndim == 3 else w), (0, 0), sigmaX=sx, sigmaY=sy)
    den = cv2.GaussianBlur(w, (0, 0), sigmaX=sx, sigmaY=sy)
    return num / (den[..., None] + 1e-6 if img.ndim == 3 else den + 1e-6), den


# ---------------------------------------------------------------- water
def refine_water(img8, poly):
    """Polygon -> exact water outline (GrabCut in a thin band around the polygon edge)."""
    gc = np.full(poly.shape, cv2.GC_BGD, np.uint8)
    gc[cv2.dilate(poly, np.ones((13, 13), np.uint8)) == 1] = cv2.GC_PR_BGD
    gc[poly == 1] = cv2.GC_PR_FGD
    gc[cv2.erode(poly, np.ones((21, 21), np.uint8)) == 1] = cv2.GC_FGD
    bgd = np.zeros((1, 65), np.float64); fgd = np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(img8, gc, None, bgd, fgd, 4, cv2.GC_INIT_WITH_MASK)
    except cv2.error:
        return poly
    w = ((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)).astype(np.uint8)
    w = cv2.morphologyEx(w, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(w)
    keep = [i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] > 400]
    return np.isin(lab, keep).astype(np.uint8)


def shoreline(water):
    """Per-column y of the far shore (top edge of the water), smoothed; -1 where no water."""
    has = water.any(0)
    top = np.where(has, water.argmax(0), -1).astype(np.float32)
    xs = np.arange(water.shape[1])
    if has.sum() < 2:
        return top
    t = np.interp(xs, xs[has], top[has])
    t = cv2.GaussianBlur(t[None], (0, 0), 6)[0]
    return np.where(has, t, -1)


def calm_water(d, water, seed=7):
    """Replace the lake with calm water: the painted reflections (moon column, light streaks,
    sun glitter, mist) are removed; a smooth colour field plus fine horizontal ripples remain."""
    w = water.astype(bool)
    if not w.any():
        return d
    Lw = lum(d)
    rows = np.where(w.any(1))[0]
    med = np.zeros(BH, np.float32)
    for y in rows:
        med[y] = np.median(Lw[y][w[y]])
    good = w & (Lw < med[:, None] * 1.06 + 0.01) & (Lw > med[:, None] * 0.7)
    low, den = normconv(d, good, 45, 3)
    low2, _ = normconv(d, good, 120, 8)
    low = np.where((den < 0.05)[..., None], low2, low)
    # painted fine texture with highlights clipped away
    hp = Lw - cv2.GaussianBlur(Lw, (0, 0), 2.0)
    hp = np.clip(hp, -0.025, 0.012) * good
    # fine procedural ripples: long thin horizontal streaks, larger toward the viewer
    rng = np.random.default_rng(seed)
    n1 = cv2.GaussianBlur(rng.standard_normal((BH, BW)).astype(np.float32), (0, 0), sigmaX=5, sigmaY=0.6)
    n2 = cv2.GaussianBlur(rng.standard_normal((BH, BW)).astype(np.float32), (0, 0), sigmaX=10, sigmaY=1.1)
    n1 /= n1.std() + 1e-6; n2 /= n2.std() + 1e-6
    yy = np.arange(BH, dtype=np.float32)[:, None]
    y0, y1 = rows.min(), rows.max()
    near = np.clip((yy - y0) / max(1, y1 - y0), 0, 1)
    rip = (n1 * (1 - near) + n2 * near) * (0.018 + 0.02 * near)
    clean = np.clip(low * (1 + rip[..., None] + hp[..., None] * 1.5), 0, 1)
    return mix(d, clean, np.clip(feather(w, 0.8) * 1.2, 0, 1) * w)


# ---------------------------------------------------------------- lights
def detect_lights(img8, sky, water, depth, prior=None):
    """Returns uint8 masks (base px): panel (lit paper lanterns / windows, holes filled),
    dot (small far lights), spill (painted lamp light on the walkway), core (all bright lights)."""
    hsv = cv2.cvtColor(img8, cv2.COLOR_BGR2HSV_FULL).astype(np.int32)
    H, S, V = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    L = lum(img8.astype(np.float32) / 255)
    loc = L - cv2.GaussianBlur(L, (0, 0), 8)
    warmh = (H < 52) | (H > 245)
    ok = (sky == 0) & (cv2.dilate(water, np.ones((3, 3), np.uint8)) == 0)
    core = warmh & (V >= 232) & (S > 25) & (S < 205) & (loc > 0.03) & ok & (depth < 0.6)
    cand = (warmh & (V > 165) & (S > 25) & ok & (depth < 0.62)).astype(np.uint8)
    n, lab = cv2.connectedComponents(cand)
    keep = np.unique(lab[core]); keep = keep[keep > 0]
    lit = np.isin(lab, keep) & (cv2.dilate(core.astype(np.uint8), disk(4)) > 0)
    if prior is not None:  # lights of the reference painting (same composition, small shifts)
        lit &= cv2.dilate(prior.astype(np.uint8), disk(14)) > 0
    onpath = (poly_mask([PATH]) == 1) & (cv2.dilate(poly_mask(LANTERN_BODIES), disk(4)) == 0)
    spill = (lit & onpath).astype(np.uint8)
    pan = (lit & ~onpath).astype(np.uint8)
    pan = cv2.morphologyEx(pan, cv2.MORPH_CLOSE, disk(2))
    cs, _ = cv2.findContours(pan, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    panel = np.zeros_like(pan)
    for c in cs:
        if cv2.contourArea(c) >= 3:
            cv2.drawContours(panel, [c], -1, 1, -1)
    panel &= (sky == 0).astype(np.uint8)
    # far lights: small warm points on the far shore / town across the lake
    dotc = warmh & (S > 40) & (V > 105) & (loc > 0.03) & ok & (depth >= 0.40) & (depth < 0.88)
    dotc &= cv2.dilate(panel, disk(2)) == 0
    if prior is not None:
        dotc &= cv2.dilate(prior.astype(np.uint8), disk(8)) > 0
    dotc = dotc.astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(dotc)
    small = np.zeros(n, bool); small[1:] = stats[1:, cv2.CC_STAT_AREA] <= 90
    dot = (small[lab] & (dotc == 1)).astype(np.uint8)
    # the small pagoda across the lake: its lit windows are panels whatever the reference painting says
    wbox = np.zeros((BH, BW), bool); wbox[722:790, 318:392] = True
    wp = (wbox & warmh & (V > 150) & (S > 25) & (sky == 0)).astype(np.uint8)
    wp = cv2.morphologyEx(wp, cv2.MORPH_CLOSE, disk(2))
    panel = np.maximum(panel, cv2.dilate(wp, disk(1)))
    corem = (core | (dot == 1) | (spill == 1) | (panel == 1)).astype(np.uint8)
    return dict(panel=panel, dot=dot, spill=spill, core=corem)


def deglow(d, lights, sky, rad, strength=1.0, protect=None):
    """Remove the light a lamp adds to its surroundings by dividing out the low-frequency
    brightening relative to the unlit surroundings (texture is kept, no dark halo)."""
    lights = lights.astype(np.uint8)
    zone = cv2.dilate(lights, disk(rad))
    nonsky = (sky == 0)
    outside = (zone == 0) & nonsky
    bg, _ = normconv(d, outside, rad * 0.9)
    inner = (cv2.dilate(lights, disk(2)) == 0) & nonsky
    loc, _ = normconv(d, inner, max(2.0, rad * 0.22))
    r = np.clip((loc + 0.02) / (bg + 0.02), 1.0, 5.0)
    r = cv2.GaussianBlur(r, (0, 0), max(1.0, rad * 0.12))
    # where almost no unlit surroundings exist (a lantern hanging in the sky) the ratio is
    # meaningless: there the lit wood is toned down to plain dark wood instead
    sup = np.clip((cv2.GaussianBlur(nonsky.astype(np.float32), (0, 0), rad * 0.7) - 0.35) / 0.25, 0, 1)
    wgt = feather(zone, max(1.0, rad * 0.3)) * nonsky * strength
    if protect is not None:
        wgt = wgt * (1 - protect)
    out = d / (1 + (r - 1) * wgt[..., None])
    lw = (1 - sup) * wgt
    if lw.max() > 0.01:
        Lo = lum(out)[..., None]
        wood = C(0.30, 0.20, 0.14) / 0.218 * np.minimum(Lo * 0.55, 0.20)
        out = mix(out, wood, np.clip(lw * 1.3, 0, 1))
    return out, r


def unlit_paper(d, img8, panel, sky):
    """Lit paper panels -> unlit cream paper in daylight, keeping the painted lattice/frame."""
    base = img8.astype(np.float32) / 255
    Lb = lum(base)
    mx = cv2.GaussianBlur(cv2.dilate(Lb, disk(3)), (0, 0), 1.0)
    t = np.clip((Lb / (mx + 1e-4) - 0.50) / 0.38, 0, 1)
    t = t * t * (3 - 2 * t)
    out = d.copy()
    n, lab, stats, _ = cv2.connectedComponentsWithStats(panel)
    Ld = lum(d)
    ring_all = (cv2.dilate(panel, disk(4)) == 1) & (panel == 0) & (sky == 0)
    # wood: the darker pixels of the frame right around the panels (already daylight-graded)
    rv = d[ring_all & (Ld < np.percentile(Ld[ring_all], 45))] if ring_all.any() else np.zeros((0, 3))
    wood = np.median(rv, 0) if len(rv) > 20 else C(0.22, 0.15, 0.11)
    wood = np.clip(wood, 0.04, 0.30) * 0.8
    yy = np.arange(BH, dtype=np.float32)[:, None] * np.ones((1, BW), np.float32)
    s = np.ones((BH, BW), np.float32)
    for i in range(1, n):
        x, y, w, h, a = stats[i]
        m = lab[y:y + h, x:x + w] == i
        yr = (yy[y:y + h, x:x + w] - y) / max(1, h - 1)
        # a little darker at the top (under the cap / eave), lighter low down
        s[y:y + h, x:x + w][m] = (0.86 + 0.16 * np.clip(yr, 0, 1))[m]
    hp = Lb - cv2.GaussianBlur(Lb, (0, 0), 1.5)
    paper = C(0.88, 0.78, 0.66)[None, None] * (0.70 * s + np.clip(hp, -0.05, 0.05) * 0.6)[..., None]
    unlit = wood[None, None] * (1 - t[..., None]) + paper * t[..., None]
    m = np.clip(feather(panel, 0.6) * 1.15, 0, 1) * (1 - sky)
    return mix(out, unlit, m)


def lights_off(d, img8, L, sky, water):
    """Daytime: lanterns/windows unlit, far lights gone, painted glow removed."""
    pan, dot, spill = L["panel"], L["dot"], L["spill"]
    # far dots: grey-opening (removes small bright points, keeps the town's structure)
    dm = cv2.dilate(dot, disk(2))
    op = np.stack([cv2.morphologyEx(d[..., c], cv2.MORPH_OPEN, disk(3)) for c in range(3)], -1)
    d = mix(d, op, np.clip(feather(dm, 0.8) * 1.3, 0, 1) * (1 - water))
    # glow of near lamps (on walls, caps, the walkway) and of far dots
    near = ((pan | spill) > 0).astype(np.uint8)
    d, r_near = deglow(d, near, sky, 22, 1.0, protect=feather(pan, 0.7))
    d, _ = deglow(d, dot, sky, 6, 1.0)
    d = unlit_paper(d, img8, pan, sky)
    d = even_path(d, pan)
    return np.clip(d, 0, 1), r_near


def even_path(d, panel):
    """Walkway: remove painted light pools / streaks / long cast shadows (they belong to the
    painting's light, not to daylight), keep the stone texture."""
    pm = poly_mask([PATH]) & (cv2.dilate(poly_mask(LANTERN_BODIES), disk(3)) == 0) & (panel == 0)
    L = lum(d) + 0.02
    lo, _ = normconv(L, pm, 7)
    tgt, _ = normconv(L, pm, 45)
    g = np.clip(tgt / (lo + 1e-4), 0.55, 1.8)
    w = feather(pm, 3) * pm
    return np.clip(d * (1 + (g - 1) * w)[..., None], 0, 1)


# ---------------------------------------------------------------- night
def night_grade(d):
    """Day-for-night that keeps hue: luminance follows the original night painting's tone curve
    (measured on the spring painting), chroma is reduced a little, a moonlit blue-violet cast
    is added mostly in the shadows."""
    lab = cv2.cvtColor(np.clip(d, 0, 1).astype(np.float32), cv2.COLOR_BGR2Lab)
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    Ln = 40.0 * (L / 100.0) ** 1.85
    k = 0.62  # chroma kept
    sh = 1 - np.clip(Ln / 40.0, 0, 1)  # shadows get more of the moonlight cast
    a2 = a * k + 4.0 + 2.0 * sh
    b2 = b * k - 7.0 - 6.0 * sh
    out = cv2.cvtColor(np.stack([Ln, a2, b2], -1).astype(np.float32), cv2.COLOR_Lab2BGR)
    return np.clip(out, 0, 1)


def light_reflections(lights, water, shore, seed=11):
    """Reflections of the lights along the far shore: thin vertical streaks under each light,
    broken by ripples, shimmering sideways, fading with distance from the shore."""
    out = np.zeros((BH, BW, 3), np.float32)
    w = water.astype(bool)
    if not w.any():
        return out
    rng = np.random.default_rng(seed)
    xs = np.arange(BW)
    has = shore >= 0
    # source intensity per column: brightest light within a band just above the shore line
    src = np.zeros((BW, 3), np.float32)
    ys = np.arange(BH)[:, None]
    band = (ys >= shore[None, :] - 26) & (ys <= shore[None, :] + 3) & has[None, :]
    lb = lights * band[..., None]
    src = lb.max(0)
    if not src.any():
        return out
    src = cv2.GaussianBlur(src[None], (0, 0), sigmaX=0.6, sigmaY=0.01)[0]
    rows = np.where(w.any(1))[0]
    y0, y1 = rows.min(), rows.max()
    # ripple pattern: thin horizontal dashes -> streaks broken into segments
    nz = cv2.GaussianBlur(rng.standard_normal((BH, BW)).astype(np.float32), (0, 0), sigmaX=1.2, sigmaY=0.55)
    nz /= nz.std() + 1e-6
    seg = np.clip((nz + 0.35) * 1.4, 0, 1)
    jit = cv2.GaussianBlur(rng.standard_normal(BH).astype(np.float32)[None], (0, 0), sigmaX=1.0)[0]
    jit = jit / (jit.std() + 1e-6)
    for y in rows:
        dy = y - shore
        valid = w[y] & has & (dy > 0)
        if not valid.any():
            continue
        amp = 0.9 + 0.12 * (y - y0) / max(1, y1 - y0)
        sx = np.clip(xs + jit[y] * amp * (0.6 + dy * 0.012), 0, BW - 1)
        row = np.stack([np.interp(sx, xs, src[:, c]) for c in range(3)], -1)
        fall = np.exp(-np.maximum(dy, 0) / 38.0) * (0.35 + 0.65 * np.exp(-np.maximum(dy, 0) / 9.0))
        out[y] = row * (fall * seg[y] * valid)[:, None]
    # widen slightly with distance (perspective), keep thin
    out = cv2.GaussianBlur(out, (0, 0), sigmaX=0.7, sigmaY=0.3)
    return np.clip(out * 1.1, 0, 1) * feather(w, 0.6)[..., None]


# ---------------------------------------------------------------- sky
# thin structure cores that must never become sky (spring geometry; robust to small shifts)
SPINE = [(150, 300), (154, 300), (160, 470), (144, 470)]
BODY = [(122, 470), (180, 470), (182, 760), (118, 760)]
CHAIN = [(1298, 400), (1316, 400), (1316, 482), (1298, 482)]


def sky_model(lab, m, deg=4, iters=3):
    """Smooth sky colour everywhere: robust 2-D polynomial fit to the pixels in mask m."""
    ys, xs = np.nonzero(m)
    sel = np.random.default_rng(0).choice(len(ys), min(len(ys), 40000), replace=False)
    ys, xs = ys[sel], xs[sel]
    def basis(x, y):
        x = x / BW * 2 - 1; y = y / BH * 2 - 1
        return np.stack([x ** i * y ** j for i in range(deg + 1) for j in range(deg + 1 - i)], -1)
    A = basis(xs.astype(np.float64), ys.astype(np.float64))
    v = lab[ys, xs].astype(np.float64)
    keep = np.ones(len(ys), bool)
    for _ in range(iters):
        coef, *_ = np.linalg.lstsq(A[keep], v[keep], rcond=None)
        res = np.linalg.norm(A @ coef - v, axis=1)
        keep = res < max(6.0, 2.0 * np.median(res[keep]))
    gy, gx = np.mgrid[0:BH, 0:BW]
    return (basis(gx.ravel().astype(np.float64), gy.ravel().astype(np.float64)) @ coef).reshape(BH, BW, 3).astype(np.float32)


def build_sky_mask(img8, prior, below, keep_polys, force_circles=()):
    """Sky mask for any template: GrabCut seeded by a prior sky (the spring mask) but checked
    against this image's own sky colours, so structures that moved between paintings are kept."""
    lab = cv2.cvtColor(img8, cv2.COLOR_BGR2Lab).astype(np.float32)
    er = cv2.erode(prior, np.ones((9, 9), np.uint8)).astype(bool)
    model = sky_model(lab, er)
    dE = np.linalg.norm(lab - model, axis=-1)
    chroma = lambda L: np.hypot(L[..., 1] - 128, L[..., 2] - 128)
    dull = chroma(lab) < chroma(model) - 12  # less colourful than the sky there (snow, rock)
    shift = lambda m, k: np.vstack([np.zeros((k, BW), m.dtype), m[:-k]]) if k > 0 else np.vstack([m[-k:], np.ones((-k, BW), m.dtype)])
    gc = np.full(prior.shape, cv2.GC_PR_BGD, np.uint8)
    gc[cv2.dilate(prior, np.ones((5, 5), np.uint8)) == 1] = cv2.GC_PR_FGD
    gc[er & (dE < 14) & (shift(below, -40) == 0)] = cv2.GC_FGD
    gc[shift(below, 25) == 1] = cv2.GC_BGD
    gc[poly_mask([SPINE, BODY]) == 1] = cv2.GC_BGD
    if keep_polys:  # structure outlines from the spring painting: only their cores are certain
        gc[cv2.erode(poly_mask(keep_polys), disk(14)) == 1] = cv2.GC_BGD
    # tree zone (branch across the top right): leaves are never sky, smooth sky-coloured gaps are
    hsv = cv2.cvtColor(img8, cv2.COLOR_BGR2HSV_FULL).astype(np.int32)
    H, S, V = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    fol = (S > 110) & (V > 70) & (((H < 30) | (H > 235)) | ((H > 50) & (H < 120)) | ((H > 195) & (H < 250)))
    zone = np.zeros((BH, BW), bool); zone[:345, 740:] = True
    Lg = cv2.morphologyEx(lab[..., 0], cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    gc[zone & (gc != cv2.GC_BGD) & ~fol & (dE < 10) & (Lg < 6)] = cv2.GC_FGD
    gc[zone & fol & (dE > 18)] = cv2.GC_BGD
    near_prior = (cv2.dilate(prior, disk(20)) == 1) & (prior == 0) & (shift(below, -10) == 0)
    gc[near_prior & (gc != cv2.GC_BGD) & (dE < 8) & (Lg < 4)] = cv2.GC_FGD
    for (cx, cy), r in force_circles:
        cv2.circle(gc, (cx, cy), r, int(cv2.GC_FGD), -1)
    bgd = np.zeros((1, 65), np.float64); fgd = np.zeros((1, 65), np.float64)
    cv2.grabCut(img8, gc, None, bgd, fgd, 5, cv2.GC_INIT_WITH_MASK)
    s = ((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)).astype(np.uint8)
    # painted sun / glare right on the horizon is sky too
    hsv = cv2.cvtColor(img8, cv2.COLOR_BGR2HSV_FULL)
    for (cx, cy), r in force_circles:
        cv2.circle(s, (cx, cy), r + 1, 1, -1)
    glare = (hsv[..., 2] > 232) & (hsv[..., 1] < 140) & (shift(below, 8) == 0) & (gc != cv2.GC_BGD)
    s |= cv2.morphologyEx(glare.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    # horizon band: let the sky run down until the colour really changes (the silhouette)
    band = (shift(below, -60) == 1) & (shift(below, 25) == 0) & (gc != cv2.GC_BGD)
    rows = np.where(band.any(1))[0]
    for y in rows[rows > 0]:
        cont = (s[y - 1].astype(bool) & band[y] & (np.linalg.norm(lab[y] - lab[y - 1], axis=-1) < 5.0)
                & ((dE[y] < 16) | ~dull[y]))
        s[y] |= cont.astype(np.uint8)
    s[(shift(below, -60) == 1) & dull & (dE > 22) & (Lg > 6) & (gc != cv2.GC_FGD)] = 0
    n, lab_ = cv2.connectedComponents(s)
    keep = set(np.unique(lab_[:5][s[:5] == 1])) - {0}
    s = np.isin(lab_, list(keep)).astype(np.uint8)
    # small sky holes between the leaves are not connected to the open sky
    s |= (zone & ~fol & (dE < 12) & (Lg < 10) & (gc != cv2.GC_BGD)).astype(np.uint8)
    s = cv2.morphologyEx(s, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    # the hanging lantern's chain: anything clearly darker than the sky there is chain
    ch = poly_mask([CHAIN]) == 1
    xs = np.r_[1288:1297, 1318:1327]
    for y in np.where(ch.any(1))[0]:
        side = lab[y, xs][s[y, xs] == 1]
        if len(side) >= 3:
            d = np.linalg.norm(lab[y] - np.median(side, 0), axis=-1)
            s[y][ch[y] & (d > 10)] = 0
    return s


def painted_sun(img8, sky):
    """Mask of a sun painted low in the sky (golden-hour templates), or None."""
    hsv = cv2.cvtColor(img8, cv2.COLOR_BGR2HSV_FULL)
    m = ((hsv[..., 2] > 245) & (hsv[..., 1] < 120) & (sky == 1)).astype(np.uint8)
    m[:430] = 0
    n, lab, stats, cent = cv2.connectedComponentsWithStats(m)
    if n < 2:
        return None
    best, bi = 0, None
    for i in range(1, n):
        x, y, w, h, a = stats[i]
        fill = a / float(w * h)
        if a >= 40 and fill > 0.45 and max(w, h) < 3 * min(w, h) and a > best:
            best, bi = a, i
    if bi is None:
        return None
    i = bi
    return cv2.dilate((lab == i).astype(np.uint8), disk(6))


def sky_matte(img8, sky):
    """Soft sky alpha for a painted template whose binary sky mask stops a few px short of the silhouettes
    (leaves, roof edges, spires): the pale painted-sky colour left on the foreground side becomes a fringe
    once the sky is replaced. For every pixel near the sky, the colour is expressed as a mix of the local
    sky colour and the local foreground colour (unmixing along that line); the sky share is the alpha.
    Real silhouettes are not moved: pixels that are not on the sky-foreground line keep alpha 0.
    Returns (alpha float32 0..1, fg float32 mask of pixels certainly foreground)."""
    lab = cv2.cvtColor(img8, cv2.COLOR_BGR2Lab).astype(np.float32)
    skyb = (sky > 0).astype(np.uint8)
    dist = cv2.distanceTransform(1 - skyb, cv2.DIST_L2, 3)             # distance of foreground pixels to the sky
    near = (skyb == 0) & (dist <= 10)
    zone = np.zeros((BH, BW), bool); zone[:345, 740:] = True            # leaves: sky shows through everywhere
    cand = near | (zone & (skyb == 0))
    orange = lab[..., 1] > 142                                           # leaf reds / oranges (small leaves have no deep core)
    # painted sky seen through the leaf gaps (tree zone): not orange, close to the global sky model there
    a_extra = np.zeros((BH, BW), np.float32)
    try:
        er = cv2.erode(skyb, np.ones((9, 9), np.uint8)).astype(bool)
        model = sky_model(lab, er)
        dE = np.linalg.norm(lab - model, axis=-1)
        gap = zone & (skyb == 0) & ~orange & (dE < 22)
        a_extra = np.where(gap, 1 - np.clip((dE - 8.0) / 10.0, 0, 1), 0).astype(np.float32)
    except Exception:
        model = None
    fgc = ((skyb == 0) & ((dist >= 3.0) | ((dist >= 1.5) & orange)) & (a_extra < 0.3)).astype(np.uint8)
    # the sky colour just beyond the pixel and the foreground colour deeper in
    Cs, ds = normconv(lab, skyb, 14.0)
    Cs2, _ = normconv(lab, skyb, 40.0)
    Cs = np.where((ds < 0.03)[..., None], Cs2, Cs)
    if model is not None:
        Cs = np.where(zone[..., None] & (ds < 0.25)[..., None], model, Cs)
    Cf, df = normconv(lab, fgc, 3.0)
    Cf2, _ = normconv(lab, fgc, 9.0)
    Cf = np.where((df < 0.05)[..., None], Cf2, Cf)
    v = Cs - Cf
    vv = (v ** 2).sum(-1)
    w = lab - Cf
    t = (w * v).sum(-1) / np.maximum(vv, 1e-3)
    res = np.linalg.norm(w - t[..., None] * v, axis=-1)
    ok = cand & (vv > 12.0 ** 2) & (res < 17.0) & (t > 0.14)
    a = np.where(ok, np.clip(t, 0, 1), 0).astype(np.float32)
    a = np.maximum(a, a_extra)
    # halos lighter than the sky are off the sky-foreground line: pixels clearly nearer to the sky colour than
    # to the foreground colour (close to the sky) count as sky as well
    dS = np.linalg.norm(lab - Cs, axis=-1)
    dF = np.linalg.norm(lab - Cf, axis=-1)
    a = np.maximum(a, ((dS < 0.6 * dF) & (dist <= 7) & (vv > 12.0 ** 2) & cand).astype(np.float32))
    a = np.where(a < 0.3, a * (a / 0.3), a)                            # fade the weak end (no dust on real leaves)
    a = np.clip((a - 0.04) / 0.96, 0, 1)
    out = np.maximum(skyb.astype(np.float32), a)
    # leaves / branches are never turned into sky: the opened core of the foreground stays opaque
    out = out * (1 - cv2.erode(fgc, np.ones((3, 3), np.uint8)).astype(np.float32) * (dist > 5) * (a_extra < 0.3))
    return cv2.GaussianBlur(out, (0, 0), 0.5).astype(np.float32), fgc


def decontaminate(plate, alpha, fgc):
    """Foreground plate colour with the sky share removed: where alpha > 0 the colour is pulled to the
    nearby certain-foreground colour (texture-preserving: the plate's own detail is kept in proportion)."""
    fg_fill, den = normconv(plate, fgc, 2.2)
    fg_fill2, _ = normconv(plate, fgc, 7.0)
    fg_fill = np.where((den < 0.05)[..., None], fg_fill2, fg_fill)
    m = np.clip(alpha * 1.25, 0, 1) * (1 - fgc.astype(np.float32) * 0)
    return plate + (fg_fill - plate) * m[..., None]
