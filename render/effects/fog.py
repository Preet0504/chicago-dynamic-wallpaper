"""Fog / mist weather effect:  apply(img, ctx) -> img   (see effects/__init__.py for ctx).

  * exponential depth fog, optical depth = density * depth^1.8 (near things stay crisp,
    the far shore and the mountain fade out), modulated by large, slowly drifting fog banks
  * a low-lying mist sheet on the lake surface that creeps into the town (stronger mornings)
  * fog colour from the light: grey-white by day, warm grey at golden hour, blue-grey at night,
    warmed by the town's lights; lights get wide soft halos, and the lanterns throw beams
  * by day the sun is at most a pale disk behind the fog

Helpers here are shared with snow.py (same air, same lights).
"""
import math
import numpy as np, cv2

OUT_W, OUT_H = 2560, 1441
SX = OUT_W / 1672
Q = 4  # glow / noise work at 1/Q resolution

# lantern centres (template px): hanging lantern, stone lantern 1, stone lantern 2
LANTERNS = [(1307, 522), (925, 860), (1270, 800)]


def C(r, g, b):
    return np.array([b, g, r], np.float32)


def smooth(e, e0, e1):
    t = min(1.0, max(0.0, (e - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def smooth_a(x, e0, e1):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def lerp_keys(keys, x):
    if x <= keys[0][0]:
        return keys[0][1]
    for (x0, v0), (x1, v1) in zip(keys, keys[1:]):
        if x <= x1:
            t = (x - x0) / (x1 - x0)
            return v0 * (1 - t) + v1 * t
    return keys[-1][1]


def lum(img):
    return img[..., 0] * 0.114 + img[..., 1] * 0.587 + img[..., 2] * 0.299


def screen(a, b):
    return 1 - (1 - a) * (1 - b)


def seed_of(when, salt=0):
    return int(when.strftime("%Y%m%d")) * 7 + salt


def minutes_of(when):
    return when.hour * 60 + when.minute


# ---------------------------------------------------------------- per-template cached geometry
_PREP = {}


def prep(A):
    key = (getattr(A, "name", "?"), id(A))
    if key in _PREP:
        return _PREP[key]
    h, w = OUT_H, OUT_W
    d = A.depth if A.depth is not None else np.full((h, w), 0.5, np.float32)
    # depth of non-sky pixels; where the spring depth says "sky" but this template paints
    # something (other foliage), borrow the nearest object's depth
    qs = (w // Q, h // Q)
    dq = cv2.resize(d, qs, interpolation=cv2.INTER_AREA)
    fill = dq.copy()
    for _ in range(4):
        fill = np.where(fill > 0.985, cv2.erode(fill, np.ones((9, 9), np.uint8)), fill)
    fill = cv2.resize(fill, (w, h), interpolation=cv2.INTER_LINEAR)
    dns = np.where(d > 0.985, fill, d)
    yy = np.repeat(np.arange(h, dtype=np.float32)[:, None] / SX, w, 1)
    xx = np.repeat(np.arange(w, dtype=np.float32)[None, :] / SX, h, 0)
    tree = (yy < 350) & (xx > 735)
    tree = tree.astype(np.float32)
    dns = np.where((tree > 0) & (dns > 0.6), 0.04, dns)
    dns = np.where(dns > 0.985, 0.95, dns)
    sky = A.sky
    # the depth map's sky is better than the template's GrabCut mask around the pagoda; trust it
    # everywhere except the foliage of the top-right tree, which differs between templates
    dsky = np.clip((d - 0.97) / 0.03, 0, 1) * (1 - tree)
    sky = np.maximum(sky, dsky)
    deff = sky + (1 - sky) * dns
    P = dict(deff=deff.astype(np.float32), dns=dns.astype(np.float32), sky=sky, yy=yy, xx=xx,
             skyq=cv2.resize(sky, qs, interpolation=cv2.INTER_AREA),
             deffq=cv2.resize(deff, qs, interpolation=cv2.INTER_AREA))
    _PREP[key] = P
    return P


# ---------------------------------------------------------------- noise
def fbm(shape, seed, cells=(3, 5), octaves=5, offset=(0.0, 0.0), persist=0.55):
    """Smooth fractal noise in [0,1] at `shape` (h, w); cells = coarsest grid (rows, cols).
    offset (in fractions of the frame) slides the pattern: used to drift fog banks."""
    h, w = shape
    rng = np.random.default_rng(seed)
    acc = np.zeros((h, w), np.float32)
    tot = 0.0
    for o in range(octaves):
        ch, cw = cells[0] * 2 ** o, cells[1] * 2 ** o
        g = rng.random((ch + 3, cw + 3)).astype(np.float32)
        # continuous offset: sample the grid with a sub-cell shift
        oy, ox = offset[0] * ch, offset[1] * cw
        M = np.float32([[cw / w, 0, 1 + (ox % 1)], [0, ch / h, 1 + (oy % 1)]])
        gi = np.roll(g, (-int(oy), -int(ox)), (0, 1))
        layer = cv2.warpAffine(gi, M, (w, h), flags=cv2.INTER_CUBIC | cv2.WARP_INVERSE_MAP,
                               borderMode=cv2.BORDER_WRAP)
        amp = persist ** o
        acc += layer * amp
        tot += amp
    acc /= tot
    lo, hi = np.percentile(acc[::4, ::4], (1, 99))
    return np.clip((acc - lo) / (hi - lo + 1e-6), 0, 1)


def up(a):
    return cv2.resize(a, (OUT_W, OUT_H), interpolation=cv2.INTER_LINEAR)


# ---------------------------------------------------------------- light
def fog_colour(st, sky):
    """Colour of lit fog for this moment (BGR)."""
    sa = st["sun_alt"]
    col = lerp_keys([(-90, C(0.125, 0.135, 0.185)), (-12, C(0.13, 0.14, 0.19)),
                     (-7, C(0.18, 0.19, 0.25)), (-3, C(0.33, 0.31, 0.36)),
                     (0, C(0.52, 0.46, 0.44)), (3, C(0.64, 0.57, 0.51)),
                     (7, C(0.72, 0.67, 0.61)), (14, C(0.77, 0.76, 0.74)),
                     (30, C(0.80, 0.81, 0.82)), (90, C(0.82, 0.83, 0.85))], sa)
    # a little of the real horizon colour so the fog belongs to this sky
    hz = np.median(sky[int(OUT_H * 0.55):int(OUT_H * 0.62):4, ::8].reshape(-1, 3), axis=0)
    hl = lum(hz[None, None])[0, 0]
    tint = hz / (hl + 1e-3) * lum(col[None, None])[0, 0]
    col = col * 0.8 + np.clip(tint, 0, 1) * 0.2
    if st.get("moon_alt", -90) > 0 and sa < -6:
        col = col + C(0.02, 0.025, 0.035) * st.get("moon_illum", 0)
    return col.astype(np.float32)


def light_sources(img, ctx):
    """Emitted light (lanterns, windows, far-shore lights) at 1/Q res, BGR."""
    A = ctx["A"]
    L = ctx.get("lights_on", 0.0)
    if L <= 0.01:
        return None
    src = img * A.warm[..., None] * L
    return cv2.resize(src, (OUT_W // Q, OUT_H // Q), interpolation=cv2.INTER_AREA)


def halos(srcq, strength, wide=1.0):
    """Soft multi-scale glow of the light sources, full res BGR (additive light)."""
    if srcq is None or strength <= 0:
        return None
    s = SX / Q
    g = (cv2.GaussianBlur(srcq, (0, 0), 3.0 * s) * 0.55
         + cv2.GaussianBlur(srcq, (0, 0), 10 * s) * 1.1
         + cv2.GaussianBlur(srcq, (0, 0), 28 * s) * 2.2 * wide
         + cv2.GaussianBlur(srcq, (0, 0), 70 * s) * 3.5 * wide)
    return up(g * strength)


def beams(img, ctx, strength, reach=0.55, samples=28):
    """Light shafts through the lantern lattices (radial-blur volumetric scattering)."""
    A = ctx["A"]
    L = ctx.get("lights_on", 0.0)
    if L <= 0.01 or strength <= 0:
        return None
    out = np.zeros((OUT_H, OUT_W, 3), np.float32)
    src_full = img * A.warm[..., None]
    for (lx, ly), R in zip(LANTERNS, (300, 330, 250)):
        cx, cy = lx * SX, ly * SX
        R = int(R * SX)
        x0, x1 = max(0, int(cx - R)), min(OUT_W, int(cx + R))
        y0, y1 = max(0, int(cy - R)), min(OUT_H, int(cy + R))
        sub = src_full[y0:y1, x0:x1]
        # only this lantern's own light: a disc around its centre
        hh, ww = sub.shape[:2]
        Y, X = np.mgrid[0:hh // 2, 0:ww // 2].astype(np.float32) * 2
        Y += y0; X += x0
        sub2 = cv2.resize(sub, (ww // 2, hh // 2), interpolation=cv2.INTER_AREA)
        dist = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
        sub2 = sub2 * (dist < 70 * SX)[..., None]
        acc = np.zeros_like(sub2)
        ccx, ccy = (cx - x0) / 2, (cy - y0) / 2
        gx, gy = np.meshgrid(np.arange(ww // 2, dtype=np.float32), np.arange(hh // 2, dtype=np.float32))
        wsum = 0.0
        for k in range(samples):
            t = 1 - reach * k / samples
            mx = ccx + (gx - ccx) * t
            my = ccy + (gy - ccy) * t
            wk = 0.965 ** k
            acc += cv2.remap(sub2, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT) * wk
            wsum += wk
        acc /= wsum
        # fade the shafts out with distance from the lantern (no visible crop edge)
        fall = np.clip(1 - dist / (R * 0.98), 0, 1) ** 1.6
        acc = acc * fall[..., None]
        acc = cv2.GaussianBlur(acc, (0, 0), 1.5)
        out[y0:y0 + acc.shape[0] * 2, x0:x0 + acc.shape[1] * 2] += cv2.resize(acc, (acc.shape[1] * 2, acc.shape[0] * 2))
    return out * strength * L


# ---------------------------------------------------------------- fog
def optical_depth(P, ctx, density, bank_amt=0.6, seed_salt=0):
    """Fog optical depth per pixel (full res): depth fog with drifting banks."""
    when = ctx["when"]
    h, w = OUT_H, OUT_W
    deff = P["deff"]
    # banks: big, horizontally stretched, sliding slowly with the time of day
    drift = minutes_of(when) / 1440.0
    nq = fbm((h // Q, w // Q), seed_of(when, 11 + seed_salt), cells=(2, 3), octaves=4,
             offset=(0.0, drift * 1.7))
    n = up(nq)
    tau = density * 5.0 * deff ** 1.8
    tau *= (1 - bank_amt * 0.5) + bank_amt * n
    # thinner high in the sky
    elev = np.clip((P["yy"] - 120) / 480, 0, 1)
    tau *= 1 - P["sky"] * (1 - elev) * 0.45
    return tau, n


def mist_layer(P, ctx, amount):
    """Low-lying mist sheet over the lake surface, seeping into the town (optical depth)."""
    when = ctx["when"]
    h, w = OUT_H, OUT_W
    yy, d = P["yy"], P["deff"]
    drift = minutes_of(when) / 1440.0
    wq = fbm((h // Q, w // Q), seed_of(when, 23), cells=(10, 3), octaves=4,
             offset=(0.0, drift * 3.1), persist=0.6)
    wisp = up(wq)
    # the sheet seen at grazing angles: thickest along the far shore, thinner close below us
    lake = smooth_a(d, 0.40, 0.55) * (1 - smooth_a(d, 0.86, 0.97))
    shore = np.exp(-((yy - 698) / 22) ** 2)                # bright band hugging the far waterline
    over_water = smooth_a(yy, 640, 690) * (1 - smooth_a(yy, 805, 860))
    town = smooth_a(d, 0.28, 0.40) * (1 - smooth_a(d, 0.50, 0.6)) * smooth_a(yy, 740, 800) * (1 - smooth_a(yy, 860, 920))
    shape = lake * over_water * (0.45 + 0.9 * shore) + town * 0.55
    tau = amount * shape * (0.25 + 1.5 * wisp ** 1.5)
    return tau


def sun_disk(out, P, ctx, fogcol, intensity):
    st = ctx["st"]
    sa = st["sun_alt"]
    sx, sy = ctx["sun_xy"]
    if sa < -1 or not (-200 < sx < OUT_W + 200 and -200 < sy < OUT_H * 0.75):
        return out
    vis = smooth(sa, -1, 4) * max(0.0, 1 - 0.9 * intensity)
    X = P["xx"] * SX
    Y = P["yy"] * SX
    dd = np.sqrt((X - sx) ** 2 + (Y - sy) ** 2)
    r = 24 * SX
    disk = np.clip((r - dd) / 2.5, 0, 1) * vis * 0.55
    glow = np.exp(-(dd / (260 * SX)) ** 2) * (0.10 + 0.12 * (1 - intensity)) * smooth(sa, -2, 3)
    col = C(1.0, 0.98, 0.93) if sa > 8 else C(1.0, 0.90, 0.75)
    out = out + (glow * P["sky"] * 0.5 + glow * 0.5)[..., None] * fogcol * 0.6
    disk = disk * P["sky"]
    return out * (1 - disk[..., None]) + col * 0.92 * disk[..., None]


def apply(img, ctx):
    A, st = ctx["A"], ctx["st"]
    I = float(np.clip(ctx.get("intensity", 1.0), 0, 1))
    P = prep(A)
    sa = st["sun_alt"]
    when = ctx["when"]
    fogcol = fog_colour(st, ctx["sky"])
    dens = 0.08 + 0.92 * I ** 0.85
    tau, bank = optical_depth(P, ctx, dens, bank_amt=0.8)
    # morning radiation mist is heavier
    hr = when.hour + when.minute / 60
    morning = math.exp(-((hr - 7.0) / 2.2) ** 2)
    tau = tau + mist_layer(P, ctx, (0.35 + 0.9 * morning) * (0.5 + 0.7 * I))
    T = np.exp(-tau)
    # overcast air: no warm sunlit patches (golden light on the paving) under a fog sky
    g = lum(img)[..., None]
    dayf = smooth(sa, -4, 8)
    img = g + (img - g) * (1 - 0.35 * np.clip((g - 0.5) / 0.3, 0, 1) * dayf)
    a = (1 - T)[..., None]

    # fog colour field: slightly brighter low down, banks a little brighter, warm near lights
    F = np.broadcast_to(fogcol, img.shape).copy()
    # brighter toward the horizon (more air in the line of sight), darker overhead; banks vary it
    hz = np.exp(-((P["yy"] - 640) / 330.0) ** 2)
    F *= (0.80 + 0.20 * hz + 0.22 * bank)[..., None]
    srcq = light_sources(img, ctx)
    out = img * (1 - a) + F * a
    if srcq is not None:
        Lq = ctx["lights_on"]
        # the town's lights warm the fog around them (wide scatter), stronger in thicker fog
        warm = up(cv2.GaussianBlur(srcq, (0, 0), 55 * SX / Q)) * 3.2
        out = out + warm * a * (0.5 + 0.5 * I)
        h = halos(srcq, 0.55 + 0.75 * I)
        # halos live in the air: strong where there is fog in front of the surface, but every
        # light (also the near lanterns) gets some glow
        hw = np.clip(a[..., 0] * 1.3 + 0.35, 0, 1)[..., None]
        out = screen(np.clip(out, 0, 1), np.clip(h * hw, 0, 1))
        b = beams(img, ctx, 0.9 + 0.8 * I)
        if b is not None:
            out = screen(out, np.clip(b, 0, 1))
    out = sun_disk(out, P, ctx, fogcol, I)
    # overall: fog lifts the blacks a touch and lowers contrast
    return np.clip(out, 0, 1)
