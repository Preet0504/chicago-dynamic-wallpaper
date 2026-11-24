"""Snowfall:  apply(img, ctx) -> img   (see effects/__init__.py for ctx; shares air + lights with fog.py)

  * falling flakes in depth layers: many tiny dim ones far away (only seen against sky / far hills),
    a few big, blurred ones close to the lens; a flake is hidden by anything nearer than itself
  * low visibility: depth haze with drifting banks, mountain and far shore fade
  * fresh snow lying on upward-facing surfaces only (roof tiles, rail tops, lantern caps, kerb
    drift, patches on the paving), as a thin dusting on non-winter templates; winter templates
    already carry old snow so they only get a lighter top-up
  * light: flakes and snow take the ambient light, glow warm near lit lanterns, lights get halos
"""
import os
import numpy as np, cv2

try:
    from . import fog as F
except ImportError:  # run as a plain module
    import fog as F

W, H = 2560, 1441
SX = W / 1672
LAB = dict(farhill=2, farshore=3, hill=5, town=7, small_pagoda=8, pagoda=9, fg_roof=10, railing=11,
           walkway=12, lantern1=13, lantern2=14, shrub=15, pavilion=18, hanging_lantern=19, near_houses=22)
_CACHE = {}


def smooth_a(x, e0, e1):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def blur(a, s, sy=None):
    return cv2.GaussianBlur(a, (0, 0), s, sigmaY=sy if sy is not None else s)


def mix(a, b, t):
    if np.ndim(t) == 2:
        t = t[..., None]
    return a + (b - a) * t


def labels():
    if "lab" not in _CACHE:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "depth_labels.npy")
        l = np.load(p)
        _CACHE["lab"] = cv2.resize(l, (W, H), interpolation=cv2.INTER_NEAREST)
    return _CACHE["lab"]


def top_run(m):
    """For a boolean mask: pixels below the top edge of the mask in each column run (0 at the edge)."""
    rows = np.arange(H, dtype=np.int32)[:, None]
    start = m & ~np.roll(m, 1, axis=0)
    idx = np.where(start, rows, 0)
    st = np.maximum.accumulate(idx, axis=0)
    return np.where(m, rows - st, 9999).astype(np.float32)


def noise(shape, seed, cells, octaves=4, persist=0.55):
    return F.up(F.fbm((shape[0], shape[1]), seed, cells=cells, octaves=octaves, persist=persist))


# ---------------------------------------------------------------- fresh snow on top surfaces
def snow_cover(ctx, P, season, I, seed):
    """Returns cover (0..1, H x W): where fresh snow lies, with thickness-based softness."""
    A = ctx["A"]
    lab = labels()
    d = P["dns"]
    D = (0.45 + 0.55 * I) * (0.55 if season == "winter" else 1.0)
    cover_noise = noise((H // 4, W // 4), seed + 1, (3, 5), 5)
    grain = noise((H // 2, W // 2), seed + 2, (24, 40), 3, 0.6)
    # coverage threshold: thin dusting is patchy, heavy snow is continuous
    patch = smooth_a(cover_noise * 0.7 + grain * 0.3, 1.0 - D * 1.15, 1.0 - D * 1.15 + 0.22)
    day = A.day.astype(np.float32)
    B, G, R = day[..., 0], day[..., 1], day[..., 2]
    L = F.lum(day)
    sat = day.max(-1) - day.min(-1)
    tile = (((B > R + 0.03) & (B >= G - 0.02) & (L < 0.5)) | ((sat < 0.14) & (L < 0.55) & (L > 0.05)))
    tile = (tile & (P["sky"] < 0.2)).astype(np.float32)
    joint = np.clip((blur(L, 2.5) - L) * 7.0, 0, 1)             # dark tile joints stay bare longer
    out = np.zeros((H, W), np.float32)
    # roofs
    roofs = np.isin(lab, [LAB[k] for k in ("pagoda", "small_pagoda", "fg_roof", "pavilion", "town", "near_houses")])
    roof = blur(tile * roofs, 0.8)
    out = np.maximum(out, roof * np.clip(0.45 + 0.7 * patch - 0.5 * joint * (1 - D), 0, 1) * (0.6 + 0.4 * D))
    # top edges: rail, stone-lantern caps, hanging lantern roof, kerb drift, shrubs
    for key, base, depth_scale in (("railing", 12, 1), ("lantern1", 18, 1), ("lantern2", 12, 1),
                                   ("hanging_lantern", 10, 1)):
        m = lab == LAB[key]
        thick = (base * (1.0 - 0.6 * d) * (0.6 + 0.8 * D) * (0.7 + 0.6 * grain)) * depth_scale
        t = top_run(m)
        a = np.clip((thick - t) / 2.0, 0, 1) * m
        out = np.maximum(out, blur(a, 0.7) * (0.55 + 0.45 * smooth_a(cover_noise, 0.2, 0.5)))
    wk = lab == LAB["walkway"]
    t = top_run(wk)
    drift = np.clip((45 * (0.5 + 0.7 * D) * (0.6 + 0.8 * cover_noise) - t) / 30.0, 0, 1) * wk      # drift along the kerb
    # paving: stone tops go pale in soft drifts, grout lines hold the most snow (texture stays)
    paving = wk * smooth_a(cover_noise, 1.0 - D * 0.8, 1.0 - D * 0.8 + 0.5) * (0.5 + 0.5 * grain)
    out = np.maximum(out, np.maximum(drift * 0.85, paving * 0.45 * (0.3 + 0.7 * D)))
    sh = np.isin(lab, [LAB["shrub"]])
    t = top_run(sh)
    out = np.maximum(out, blur(np.clip((9 * D * (0.6 + 0.8 * grain) - t) / 3.0, 0, 1) * sh, 0.8) * 0.8)
    return np.clip(out, 0, 1)


def apply_cover(img, cover, amb, glow, ctx):
    L = F.lum(img)
    # keep the painted structure: tile joints / grout / planks darken the snow a little
    shade = np.clip(0.90 + (L - blur(L, 3.0)) * 2.2, 0.70, 1.08)
    base = amb * (1.0 + 0.12 * ctx["st"]["sun_alt"] / 60) + np.float32(0.10)
    snow = np.clip(base[None, None] * shade[..., None] + glow, 0, 1)
    # thickness cue: underside of each deposit in shadow, upper lip bright
    lower = np.clip(cover - np.roll(cover, -3, axis=0), 0, 1)
    upper = np.clip(cover - np.roll(cover, 3, axis=0), 0, 1)
    snow = snow * (1 - 0.32 * blur(lower, 0.8)[..., None]) + 0.05 * blur(upper, 0.8)[..., None]
    a = cover * 0.93
    return mix(img, snow, a)


# ---------------------------------------------------------------- falling flakes
def flakes(img, S_depth, amb, glow, I, rng, season_day):
    k = 0.55 + 1.0 * I
    # (layer depth, count, radius px, blur sigma, alpha)
    layers = [(0.93, 7000, 1.0, 0.0, 0.45), (0.78, 3800, 1.5, 0.0, 0.55), (0.58, 1600, 2.2, 0.4, 0.62),
              (0.38, 420, 3.6, 0.9, 0.70), (0.20, 110, 7.0, 2.4, 0.65), (0.10, 26, 16.0, 6.0, 0.40),
              (0.03, 6, 32.0, 13.0, 0.28)]
    q = cv2.resize(img, (W // 8, H // 8), interpolation=cv2.INTER_AREA)
    bg = cv2.resize(blur(q, 2), (W, H), interpolation=cv2.INTER_LINEAR)
    col = np.maximum(amb[None, None] * 1.12 + 0.05 + 0.10 * (1 - season_day), bg + 0.07 + 0.08 * (1 - season_day)) + glow * 2.4
    col = np.clip(col, 0, 1)
    gust = cv2.resize(F.fbm((H // 16, W // 16), int(rng.integers(1, 1 << 30)), cells=(2, 3), octaves=3), (W, H))
    out = img
    for dl, n, r, bs, al in layers:
        n = int(n * k)
        x = rng.random(n) * (W + 80) - 40
        y = rng.random(n) * (H + 80) - 40
        keep = rng.random(n) < 0.45 + 0.9 * gust[np.clip(y, 0, H - 1).astype(int), np.clip(x, 0, W - 1).astype(int)]
        x, y = x[keep], y[keep]
        cv = np.zeros((H, W), np.float32)
        val = 0.55 + 0.45 * rng.random(len(x))
        rr = r * (0.7 + 0.6 * rng.random(len(x)))
        wind = 0.18 + 0.1 * rng.random(len(x))
        for xi, yi, vi, ri, wi in zip(x, y, val, rr, wind):
            if ri < 1.5:           # distant flakes: short motion streaks
                ln = 1.0 + 2.0 * (1 - dl)
                cv2.line(cv, (int(xi * 4), int(yi * 4)), (int((xi + wi * ln) * 4), int((yi + ln) * 4)), float(vi),
                         1, cv2.LINE_AA, 2)
            else:
                cv2.circle(cv, (int(xi * 16), int(yi * 16)), max(1, int(ri * 16)), float(vi), -1, cv2.LINE_AA, 4)
        if bs:
            cv = blur(cv, bs, bs * 1.3)
        vis = smooth_a(S_depth - dl, -0.07, 0.03)
        a = np.clip(cv * al * vis * (1 - 0.45 * dl), 0, 1)
        out = mix(out, col, a)
    return out


# ---------------------------------------------------------------- main
def apply(img, ctx):
    A, st = ctx["A"], ctx["st"]
    I = float(np.clip(ctx.get("intensity", 1.0), 0, 1))
    season = ctx.get("season", "winter")
    when = ctx["when"]
    seed = F.seed_of(when, 303)
    rng = np.random.default_rng(seed)
    P = F.prep(A)
    day = float(smooth_a(st["sun_alt"], -6, 6))
    out = img.astype(np.float32).copy()

    # ambient light (colour of the overcast sky, with a floor for snow-lit night air)
    sky = ctx["sky"]
    amb = sky[100:int(H * 0.6):6, ::16].reshape(-1, 3).mean(axis=0).astype(np.float32)
    amb = np.maximum(amb, F.C(0.12, 0.135, 0.19) * (1 - day) + 0.0)
    srcq = F.light_sources(out, ctx)
    glow_wide = np.zeros_like(out)
    if srcq is not None:
        glow_wide = np.clip(F.halos(srcq, 0.8, wide=0.6) * 0.5, 0, 0.6)

    # 1. soft grade: flat, slightly cool, less saturated
    g = F.lum(out)[..., None]
    hl = smooth_a(g, 0.5, 0.8)            # no warm sunlit patches under a snow sky
    out = g + (out - g) * (1 - 0.12 * I - 0.35 * hl * day)

    # 2. fresh snow on top surfaces
    cover = snow_cover(ctx, P, season, I, seed)
    out = apply_cover(out, cover, amb, glow_wide * 0.8, ctx)
    # no wet-stone look while it snows: cap the paving at snow brightness (kills the glossy lantern
    # streaks), take the colour out, and leave only a soft warm pool of light around the lanterns
    wkm = blur((labels() == LAB["walkway"]).astype(np.float32), 1.5)
    cap = F.lum((amb * 1.15 + 0.06)[None, None])[0, 0] + F.lum(glow_wide) * 0.9
    Lw = F.lum(out)
    out = mix(out, out * np.minimum(1.0, cap / (Lw + 1e-4))[..., None], wkm * 0.9)
    gw = F.lum(out)[..., None]
    out = mix(out, gw + (out - gw) * 0.55, wkm)
    out = out + (wkm * 0.35)[..., None] * glow_wide

    # 3. low visibility haze (depth based, drifting banks)
    fogcol = F.fog_colour(st, sky)
    tau, bank = F.optical_depth(P, ctx, 0.04 + 0.30 * I ** 0.9, bank_amt=0.5, seed_salt=5)
    a = (1 - np.exp(-tau))[..., None]
    Fc = np.broadcast_to(fogcol, out.shape) * (0.95 + 0.08 * bank)[..., None]
    out = out * (1 - a) + Fc * a
    if srcq is not None:
        h = F.halos(srcq, 0.35 + 0.45 * I)
        hw = np.clip(a[..., 0] * 1.2 + 0.3, 0, 1)[..., None]
        out = F.screen(np.clip(out, 0, 1), np.clip(h * hw, 0, 1))

    # 4. falling flakes (depth layered)
    dsc = cv2.resize(blur(cv2.resize(P["deff"], (W // 4, H // 4), interpolation=cv2.INTER_AREA), 2), (W, H))
    out = flakes(out, dsc, fogcol, glow_wide, I, rng, day)
    return np.clip(out, 0, 1)
