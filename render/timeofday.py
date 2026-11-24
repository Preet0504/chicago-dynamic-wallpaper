"""Time-of-day renderer (no AI): lights the scene for any moment using the real sun and moon.

  .venv/bin/python render/timeofday.py "2026-11-14 15:30" [clear|partly|overcast] out.png

Night uses the original painting. Daylight uses a colour-recovered "day plate" of the same
painting. In between, the two are blended by sun altitude. The sky is rebuilt every time: a
gradient driven by the sun, the painting's own clouds (recoloured for the light), stars, and
a sun / moon placed where they really are over Chicago (moon with its real phase).
"""
import os, sys, math
import datetime as dt
import numpy as np, cv2
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import masks as M
import astro
import tod_plates as P

TZ = ZoneInfo("America/Chicago")
BW, BH = 1672, 941
OUT_W, OUT_H = int(os.environ.get("WALLPAPER_W", 3840)), int(os.environ.get("WALLPAPER_H", 2160))
SX = OUT_W / BW
CACHE = os.path.join(HERE, "cache_tod.npz")  # spring template + shared sky layers
ROOT = os.path.dirname(HERE)
# season -> template image. "lit" says how the template is painted (night or golden hour).
# Templates are the same composition, so every hand-placed coordinate applies to all of them.
TEMPLATES = {
    "spring": dict(file="templates/spring_clear_night.png", lit="night"),
    "autumn": dict(file="templates/autumn_clear_golden.png", lit="golden"),
    "summer": dict(file="templates/summer_clear_night.png", lit="night"),
    "winter": dict(file="templates/winter_clear_night.png", lit="night"),
    "autumnlate": dict(file="templates/autumnlate_clear_night.png", lit="night"),
    "winterbare": dict(file="templates/winterbare_clear_night.png", lit="night"),
}
BASE_SEASON = {"autumnlate": "autumn", "winterbare": "winter"}  # scene -> season for season-dependent logic
FALLBACK = {"spring": ["spring", "summer", "autumn"], "summer": ["summer", "spring", "autumn"],
            "autumn": ["autumn", "winter", "spring"], "winter": ["winter", "autumn", "spring"],
            "autumnlate": ["autumnlate", "autumn", "winterbare"], "winterbare": ["winterbare", "autumnlate", "autumn"]}


def template_for(season):
    for name in FALLBACK.get(season, FALLBACK["spring"]):
        if os.path.exists(os.path.join(ROOT, TEMPLATES[name]["file"])):
            return name
    return "spring"


def cache_path(name):
    return CACHE if name == "spring" else os.path.join(HERE, "cache_%s.npz" % name)

# Virtual camera: faces south, very wide, so the sun crosses the frame left -> right.
VIEW_AZ, HFOV = 180.0, 140.0
HORIZON_Y = 600.0      # base px where elevation 0 sits (just above the far hills)
TOP_ELEV = 52.0        # elevation at the top edge of the frame
HANG = (1250, 465, 1370, 580)  # hanging lantern box (base px)
MOON = (446, 127, 56)  # painted moon centre / radius (base px)
DEPTH = os.path.join(HERE, "depth.npy")  # 0 = nearest, 1 = sky (built by depth.py)
LAKE = [[(390, 700), (600, 699), (900, 702), (940, 712), (1000, 719), (1100, 727), (1150, 736),
         (1200, 744), (1265, 752), (1268, 790), (1100, 792), (900, 790), (700, 787), (560, 784),
         (500, 768), (430, 760), (392, 756)],
        [(262, 700), (392, 700), (392, 705), (305, 708), (262, 708)]]


# ---------------------------------------------------------------- utils
def up(a, interp=cv2.INTER_LINEAR):
    return cv2.resize(a, (OUT_W, OUT_H), interpolation=interp)


def feather(m, s):
    return cv2.GaussianBlur(m.astype(np.float32), (0, 0), s)


def lum(img):
    return img[..., 0] * 0.114 + img[..., 1] * 0.587 + img[..., 2] * 0.299


def mix(a, b, t):
    if np.ndim(t) == 2:
        t = t[..., None]
    return a * (1 - t) + b * t


def screen(a, b):
    return 1 - (1 - a) * (1 - b)


def C(r, g, b):  # colours are written as RGB for readability, stored BGR
    return np.array([b, g, r], np.float32)


def smooth(e, e0, e1):
    t = min(1.0, max(0.0, (e - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def lerp_keys(keys, x):
    """keys: sorted list of (x, value-array). Piecewise-linear interpolation."""
    if x <= keys[0][0]:
        return keys[0][1]
    for (x0, v0), (x1, v1) in zip(keys, keys[1:]):
        if x <= x1:
            t = (x - x0) / (x1 - x0)
            return v0 * (1 - t) + v1 * t
    return keys[-1][1]


def sky_xy(alt, az):
    """Map a sky direction to output pixel coords (can be off-frame)."""
    daz = (az - VIEW_AZ + 540) % 360 - 180
    x = (0.5 + daz / HFOV) * OUT_W
    y = (HORIZON_Y - alt / TOP_ELEV * HORIZON_Y) * SX
    return x, y


# ---------------------------------------------------------------- one-time analysis (cached)
def lake_mask(img8):
    poly = np.zeros((BH, BW), np.uint8)
    cv2.fillPoly(poly, [np.array(p_, np.int32) for p_ in LAKE], 1)
    w = P.refine_water(img8, poly)
    return w if w.sum() > 0.7 * poly.sum() else poly


def grow_sky(base, sky):
    """Sky the structure masks missed (small patches between roofs / beside the lantern): pixels
    right next to the sky that are smooth and match the local sky colour."""
    loc, den = P.normconv(base, sky, 14)
    near = cv2.dilate(sky, P.disk(14)) > 0
    L = lum(base)
    grad = cv2.morphologyEx(L, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    diff = np.abs(base - loc).max(-1)
    yy = np.arange(BH)[:, None] * np.ones((1, BW))
    cand = (sky == 0) & near & (den > 0.02) & (diff < 0.035) & (grad < 0.03) & (yy < 640)
    cand = cv2.morphologyEx(cand.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(cand)
    ok = [i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= 12]
    add = np.isin(lab, ok).astype(np.uint8)
    out = np.maximum(sky, cv2.dilate(add, P.disk(1)))
    # pale fringe of the old sky along the mountain and far ridge (not roofs: limited to that box)
    zbox = np.zeros((BH, BW), bool); zbox[300:640, 110:1300] = True
    fr = zbox & (out == 0) & (cv2.dilate(out, P.disk(3)) > 0) & (den > 0.02) & (diff < 0.10) & (L > lum(loc) - 0.02)
    out = np.maximum(out, fr.astype(np.uint8))
    # the painted glow flanking the hanging lantern is lit sky, not lantern: lighter than the sky, outside the paper panel
    x0, y0, x1, y1 = HANG
    box = np.zeros((BH, BW), bool); box[y0:y1, x0:x1] = True
    loc2, den2 = P.normconv(base, sky, 30)
    halo = box & (out == 0) & (den2 > 0.01) & (L > lum(loc2) + 0.015) & (np.abs(base - loc2).max(-1) < 0.30)
    halo = cv2.morphologyEx(halo.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    return np.maximum(out, halo)


def force_moon_sky(sky):
    """The painted moon is replaced by the real one, so its disc counts as sky."""
    cv2.circle(sky, MOON[:2], int(MOON[2] * 1.18) + 2, 1, -1)
    return sky


def fill_holes(d, mask, sigma):
    """Replace masked pixels by the local average of the unmasked ones (smooth, no inpaint streaks)."""
    m = mask.astype(np.uint8) > 0
    fill, den = P.normconv(d, ~m, sigma)
    fill2, _ = P.normconv(d, ~m, sigma * 3)
    fill = np.where((den < 0.08)[..., None], fill2, fill)
    return mix(d, fill, feather(m, 0.8) * (m | (feather(m, 0.8) > 0.2)))


def _plates(img8, sky, water, prior, lit, spring=False, matte=None):
    """Night plate, day plate, light-core mask and lake reflections of the lights (all base px).
    Generic: works for any template with the shared composition."""
    base = img8.astype(np.float32) / 255
    depth = np.load(DEPTH)
    L = P.detect_lights(img8, sky, water, depth, prior=prior)
    core = L["core"]
    hsv = cv2.cvtColor(img8, cv2.COLOR_BGR2HSV_FULL).astype(np.int32)
    H, S, V = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    nolight = cv2.dilate(core, np.ones((9, 9), np.uint8)) == 0
    if spring:  # day plate: undo the night grade (white balance + exposure + gentle shoulder)
        fg = (sky == 0) & nolight
        means = np.array([base[..., c][fg].mean() for c in range(3)])
        d = base * (means.mean() / means)
        d = d * (0.42 / np.median(lum(d)[fg]))
        d = d / (1 + d * 0.55) * 1.55
        g = lum(d)[..., None]
        d = np.clip(g + (d - g) * 1.10, 0, 1)
    else:
        fol = (S > 110) & (V > 70) & (((H < 30) | (H > 235)) | ((H > 50) & (H < 120)) | ((H > 195) & (H < 250)))
        neutral = (sky == 0) & ~fol & nolight & (V > 25)
        med = np.array([np.median(base[..., c][neutral]) for c in range(3)])
        d = base * np.clip(med.mean() / med, 0.6, 1.6)
        d = d * (0.40 / np.median(lum(d)[neutral]))
        d = np.clip(d / (1 + d * 0.45) * 1.45, 0, 1)
    d, _ = P.lights_off(d, img8, L, sky, water)
    # wide pools of lamp light on the ground / snow: divide out the low-frequency brightening and its warm cast
    yy_ = np.arange(BH)[:, None] * np.ones((1, BW))
    stone = (((L["panel"] | L["spill"]) > 0) & (yy_ > 740)).astype(np.uint8)
    if stone.any():
        d, _ = P.deglow(d, stone, sky, 70, 1.0, protect=feather(L["panel"], 0.7))
        zone = feather(cv2.dilate(stone, P.disk(60)), 25)
        hs = cv2.cvtColor((np.clip(d, 0, 1) * 255).astype(np.uint8), cv2.COLOR_BGR2HSV_FULL).astype(np.float32)
        warmth = np.clip((hs[..., 1] - 40) / 90, 0, 1) * ((hs[..., 0] < 45) | (hs[..., 0] > 240))
        g = lum(d)[..., None]
        d = mix(d, g * C(0.97, 0.97, 1.0), np.clip(zone * warmth * 0.7, 0, 0.7) * (1 - feather(L["panel"], 0.7)))
    # far-shore lights and their glow: inpaint away (small warm bright specks around each dot)
    spk = np.zeros((BH, BW), np.uint8)
    fix = (cv2.dilate(L["dot"], P.disk(2)) > 0)  # day plate: places where lights / glow were removed (the 4K detail must not bring them back)
    if lit == "night":
        # the town across the lake: every warm bright window / glow is painted out (generous mask
        # so no dark ring is left around the dots)
        band = np.zeros((BH, BW), bool); band[630:800, :1250] = True
        band &= depth > 0.5  # only the far town; pagodas and houses in front keep their paint
        Lb = lum(base)
        loc = Lb - cv2.GaussianBlur(Lb, (0, 0), 4)
        warmh = (H < 58) | (H > 246)
        th = cv2.morphologyEx(Lb, cv2.MORPH_TOPHAT, P.disk(3))
        # (a bright top-hat alone is not enough: pale tips of the conifers in front are not lights)
        spk = band & ((warmh & (S > 45) & (V > 85)) | ((th > 0.09) & warmh) | (warmh & (loc > 0.035))) & (sky == 0) & (water == 0)
        n_, lab_, st_ = cv2.connectedComponentsWithStats(spk.astype(np.uint8))[:3]
        spk = (st_[:, cv2.CC_STAT_AREA][lab_] <= 600) & spk   # lights are specks; big warm blobs are trees / roofs
        spk = spk & ((cv2.dilate(L["panel"], P.disk(3)) == 0) | (depth > 0.45))  # near windows are handled as paper
        spk |= (band & (V > 200) & (S < 90) & (cv2.dilate(spk.astype(np.uint8), P.disk(3)) > 0) & (water == 0))  # white window cores
        spk = cv2.dilate(spk.astype(np.uint8), P.disk(2))
        # the conifers left of the small pagoda carry warm / pale highlights: inpainting them leaves grey
        # smoke columns, so there only the bright specks are opened away (texture stays)
        tree = np.zeros((BH, BW), bool); tree[672:770, :345] = True
        opn = np.stack([cv2.morphologyEx(d[..., c], cv2.MORPH_OPEN, P.disk(2)) for c in range(3)], -1)
        opn3 = np.stack([cv2.morphologyEx(d[..., c], cv2.MORPH_OPEN, P.disk(3)) for c in range(3)], -1)
        d = mix(d, np.minimum(d, opn3), feather(spk * (~tree).astype(np.uint8), 0.8))  # (opening, not a blur fill: keeps the shore's structure)
        d = mix(d, opn, feather(cv2.dilate((spk & tree).astype(np.uint8), P.disk(1)), 0.7) * 0.9)
        fix |= spk > 0
        d8 = (np.clip(d, 0, 1) * 255).astype(np.uint8)  # leftover orange glow patches
        dh = cv2.cvtColor(d8, cv2.COLOR_BGR2HSV_FULL)
        gl = band & ((dh[..., 0] < 50) | (dh[..., 0] > 245)) & (dh[..., 1] > 50) & (dh[..., 2] > 105) & (water == 0) & (sky == 0)
        gl = cv2.dilate(gl.astype(np.uint8), P.disk(4))
        d = d8.astype(np.float32) / 255
        opn5 = np.stack([cv2.morphologyEx(d[..., c], cv2.MORPH_OPEN, P.disk(5)) for c in range(3)], -1)
        opn = np.stack([cv2.morphologyEx(d[..., c], cv2.MORPH_OPEN, P.disk(3)) for c in range(3)], -1)
        # glow patches: fill from the cool (blue-green) pixels around them only, so no brown smear is left
        cool = ((d[..., 2] - d[..., 0] < -0.03) & (gl == 0) & (spk == 0) & (sky == 0)).astype(np.uint8)
        cf, cden = P.normconv(d, cool, 5.0)
        cf2, _ = P.normconv(d, cool, 14.0)
        cf = np.where((cden < 0.05)[..., None], cf2, cf)
        gm = feather(gl * (~tree).astype(np.uint8), 1.6)
        # keep the patch's own light/dark structure but take the cool hue and cap the brightness
        Lcf = lum(cf)[..., None] + 1e-3
        newc = cf / Lcf * np.minimum(lum(d)[..., None], Lcf * 1.1)
        d = mix(d, newc, gm)
        d = mix(d, opn, feather(gl * tree.astype(np.uint8), 0.8))
        fix |= gl > 0
    # day: small warm bright specks (far-town lights, bulbs along the eaves / in the conifers) are unlit.
    # Detected on the day plate itself (the painted dots are pale on the template, warm once graded).
    sp_box = np.zeros((BH, BW), bool); sp_box[380:800, :470] = True; sp_box[600:800, :1250] = True
    Ld_ = lum(d)
    th_ = cv2.morphologyEx(Ld_, cv2.MORPH_TOPHAT, P.disk(3))
    sp = (sp_box & (th_ > 0.085) & (d[..., 2] > d[..., 0] + 0.0) & (sky == 0) & (water == 0)
          & (cv2.dilate(core, P.disk(1)) == 0)).astype(np.uint8)
    n_, lab_, st_ = cv2.connectedComponentsWithStats(sp)[:3]
    sp = ((st_[:, cv2.CC_STAT_AREA][lab_] <= 60) & (sp > 0)).astype(np.uint8)
    if sp.any():
        opn = np.stack([cv2.morphologyEx(d[..., c], cv2.MORPH_OPEN, P.disk(2)) for c in range(3)], -1)
        d = mix(d, opn, feather(cv2.dilate(sp, P.disk(1)), 0.7))
        fix |= cv2.dilate(sp, P.disk(2)) > 0
    d = P.calm_water(d, water)
    if lit != "night":  # golden painting: small bright town lights go too
        band = np.zeros((BH, BW), bool); band[630:800, :1250] = True
        Lb = lum(base)
        tiny = band & (depth > 0.5) & (cv2.morphologyEx(Lb, cv2.MORPH_TOPHAT, P.disk(2)) > 0.12) & (sky == 0) & (water == 0)
        d = fill_holes(d, cv2.dilate(tiny.astype(np.uint8), P.disk(2)), 2.5)
        fix |= cv2.dilate(tiny.astype(np.uint8), P.disk(2)) > 0
    wm = (water > 0) & (d[..., 2] > d[..., 0] - 0.02)  # warm specks left on the lake
    if wm.any():
        d = mix(d, cv2.medianBlur((np.clip(d, 0, 1) * 255).astype(np.uint8), 15).astype(np.float32) / 255,
                feather(cv2.dilate(wm.astype(np.uint8), P.disk(2)), 1.0) * (water > 0))
    if lit == "night":  # blossoms keep their pink in daylight (the exposure grade would bleach them)
        pink = ((H > 200) & (H < 252) & (S > 38) & (V > 110) & (sky == 0)).astype(np.uint8)
        pink = cv2.morphologyEx(pink, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
        pink &= (cv2.dilate(core, np.ones((5, 5), np.uint8)) == 0).astype(np.uint8)
        pink &= (cv2.dilate(spk, P.disk(2)) == 0).astype(np.uint8)
        h2 = hsv.astype(np.float32)
        h2[..., 1] = np.clip(h2[..., 1] * 1.12 + 14, 70, 190)
        h2[..., 2] = np.clip(h2[..., 2] * 0.97, 0, 238)
        pc = cv2.cvtColor(h2.astype(np.uint8), cv2.COLOR_HSV2BGR_FULL).astype(np.float32) / 255
        d = mix(d, pc, feather(pink, 0.7))
    lights = base * feather(core, 0.8)[..., None]
    if lit == "night":
        nt = P.calm_water(base, water)  # the painting itself; painted lake reflections are re-made live
    else:
        nt = P.night_grade(d)
        # the pixels hugging the sky edge still carry the painted orange glow: refill them from the ridge below
        ring = (cv2.dilate(sky, P.disk(6)) > 0) & (sky == 0)
        far_ring = ring & (depth > 0.5) & (np.arange(BH)[:, None] > 470)   # the far ridge only (not leaves up in the sky)
        nt = fill_holes(nt, far_ring | (cv2.dilate(far_ring.astype(np.uint8), P.disk(1)) > 0) & ring, 4.0)
        # far ridges lit orange by the painted sunset turn olive when graded: recolour them as moonlit blue-grey
        yy2 = np.arange(BH)[:, None] * np.ones((1, BW))
        ridge = (depth > 0.55) & (yy2 > 470) & (yy2 < 650) & (sky == 0) & (water == 0) & (nolight | True)
        hn = cv2.cvtColor((np.clip(nt, 0, 1) * 255).astype(np.uint8), cv2.COLOR_BGR2HSV_FULL)[..., 0]
        rm = feather(ridge & (hn > 12) & (hn < 110) & (cv2.dilate(core, P.disk(2)) == 0), 2.0)
        g = lum(nt)[..., None]
        nt = mix(nt, g * C(0.55, 0.68, 1.05) * 1.1, rm * 0.85)
        nt = np.maximum(nt, lights * 1.02)
    refl = P.light_reflections(lights, water, P.shoreline(water))
    if matte is not None:  # sky edge: remove the painted sky's colour from the foreground side of every silhouette
        nt = P.decontaminate(nt, matte[0], matte[1])
        d = P.decontaminate(d, matte[0], matte[1])
    return nt, d, core, refl, fix.astype(np.uint8)


def build_cache():
    if not os.path.exists(os.path.join(HERE, "masks.npz")):
        M.build()
    m = np.load(os.path.join(HERE, "masks.npz"))
    img8 = cv2.imread(M.BASE)
    base = img8.astype(np.float32) / 255
    sky = m["sky"].astype(bool)
    Bc, Rc = base[..., 0], base[..., 2]
    Lc = lum(base)
    zone = np.zeros((BH, BW), bool); zone[:340, 760:] = True
    gaps = zone & (Bc > Rc + 0.08) & (Lc < 0.22)
    gaps = cv2.morphologyEx(gaps.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8)).astype(bool)
    st_ = np.zeros((BH, BW), np.uint8)
    cv2.fillPoly(st_, [np.array(M.PAVILION, np.int32)], 1)
    sky = force_moon_sky(grow_sky(base, (sky | (gaps & (st_ == 0))).astype(np.uint8)))
    x, y, r = MOON
    moon_tex = base[y - r:y + r, x - r:x + r].copy()
    water = lake_mask(img8)
    night, day, core, refl, fix = _plates(img8, sky, water, None, "night", spring=True)
    _save_npz(CACHE, night=night.astype(np.float16), day=day.astype(np.float16), refl=refl.astype(np.float16),
              water=water, moon_tex=moon_tex.astype(np.float16), sky=sky, warm=core, below=m["below"], dayfix=fix)


def _save_npz(path, **arrays):
    """Atomic write so parallel renders never read a half-written cache."""
    tmp = path + ".%d.tmp.npz" % os.getpid()
    np.savez_compressed(tmp, **arrays)
    os.replace(tmp, path)


def build_template(name):
    """Masks + day/night plates for a non-spring template (same composition as spring)."""
    t = TEMPLATES[name]
    img = cv2.imread(os.path.join(ROOT, t["file"]))
    assert img is not None and img.shape[:2] == (BH, BW), "template must be %dx%d" % (BW, BH)
    base = img.astype(np.float32) / 255
    sp = np.load(CACHE)
    sky0, warm0 = sp["sky"].astype(np.uint8), sp["warm"].astype(np.uint8)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV_FULL).astype(np.int32)
    H, S, V = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    L = lum(base)

    # foliage = strongly coloured vegetation (autumn reds/oranges, spring pinks, summer greens)
    fol = (S > 110) & (V > 70) & (((H < 30) | (H > 235)) | ((H > 50) & (H < 120)) | ((H > 195) & (H < 250)))

    # --- sky: GrabCut seeded from the spring sky (layout is identical), refined on this image
    gc = np.full((BH, BW), cv2.GC_PR_BGD, np.uint8)
    gc[sky0 == 1] = cv2.GC_PR_FGD
    gc[cv2.erode(sky0, np.ones((15, 15), np.uint8)) == 1] = cv2.GC_FGD
    gc[sp["below"] == 1] = cv2.GC_BGD
    st = np.zeros((BH, BW), np.uint8)
    cv2.fillPoly(st, [np.array(M.PAGODA, np.int32), np.array(M.PAVILION, np.int32)], 1)
    gc[st == 1] = cv2.GC_BGD
    zone = np.zeros((BH, BW), bool); zone[:345, 740:] = True
    gc[fol & zone] = cv2.GC_BGD
    # clear smooth sky pixels in the tree zone (between leaves) are sky
    grad = cv2.morphologyEx(L, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    gc[zone & ~fol & (grad < 0.03) & (S < 200) & (base[..., 0] > base[..., 2])] = cv2.GC_FGD
    bgd = np.zeros((1, 65), np.float64); fgd = np.zeros((1, 65), np.float64)
    cv2.grabCut(img, gc, None, bgd, fgd, 5, cv2.GC_INIT_WITH_MASK)
    sky = ((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)).astype(np.uint8)
    n, lab = cv2.connectedComponents(sky)
    keep = set(np.unique(lab[:5][sky[:5] == 1])) - {0}
    sky = np.isin(lab, list(keep)).astype(np.uint8)
    sky = cv2.morphologyEx(sky, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    sky = force_moon_sky(grow_sky(base, sky) if t["lit"] == "night" else sky)  # (golden skies look like foliage)
    # exact sky mask written by the season generator (keeps e.g. the dark winter branch out of the sky)
    side = os.path.join(ROOT, t["file"].replace(".png", "_sky.png"))
    if os.path.exists(side):
        sky = force_moon_sky((cv2.imread(side, 0) > 127).astype(np.uint8))
    if t["lit"] == "golden":
        # the painted sunset clouds / horizon glow are sky too (the sky is rebuilt for the real time of day)
        hb = np.zeros((BH, BW), bool); hb[HANG[1]:HANG[3], HANG[0]:HANG[2]] = True
        g1 = cv2.morphologyEx(L, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
        cl = (sp["below"] == 0) & (st == 0) & ~(fol & zone) & ~hb & (sky == 0) & (g1 < 0.14) & (V > 110)
        cl = cv2.morphologyEx(cl.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        cl = cv2.morphologyEx(cl, cv2.MORPH_CLOSE, P.disk(2))
        n, lab, stats, _ = cv2.connectedComponentsWithStats(cl)
        touch = np.unique(lab[cv2.dilate(sky, P.disk(3)) > 0]); touch = touch[touch > 0]
        keep = [i for i in touch if stats[i, cv2.CC_STAT_AREA] > 40]
        sky = np.maximum(sky, cv2.dilate(np.isin(lab, keep).astype(np.uint8), P.disk(1)))
        # the painted sun disc on the ridge is sky too (the real sun is drawn live)
        sm = ((V > 232) & (S < 150) & (sky == 0)).astype(np.uint8); sm[:470] = 0; sm[640:] = 0
        sm = cv2.morphologyEx(sm, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        n, lab, stats, _ = cv2.connectedComponentsWithStats(sm)
        for i in range(1, n):
            x, y, w_, h_, a_ = stats[i]
            if 60 < a_ < 2500 and max(w_, h_) < 3 * min(w_, h_) and cv2.dilate(sky, P.disk(5))[y:y + h_, x:x + w_].any():
                sky = np.maximum(sky, cv2.dilate((lab == i).astype(np.uint8), P.disk(3)))

    water = lake_mask(img)
    matte = P.sky_matte(img, sky) if t["lit"] == "golden" else None
    night, day, core, refl, fix = _plates(img, sky, water, warm0, t["lit"], matte=matte)
    extra = dict(skya=matte[0].astype(np.float16)) if matte is not None else {}
    _save_npz(cache_path(name), night=night.astype(np.float16), day=day.astype(np.float16), refl=refl.astype(np.float16),
              sky=sky, warm=core, water=water, below=sp["below"], dayfix=fix, **extra)


class Assets:
    def __init__(self, name="spring"):
        if not os.path.exists(CACHE):
            build_cache()
        shared = np.load(CACHE)
        if name != "spring":
            src = os.path.join(ROOT, TEMPLATES[name]["file"])
            cp = cache_path(name)
            if not os.path.exists(cp) or os.path.getmtime(src) > os.path.getmtime(cp):
                build_template(name)
        c = np.load(cache_path(name))
        self.name = name

        def sharpen(img):
            img = up(img, cv2.INTER_LANCZOS4)
            return np.clip(img * 1.12 - cv2.GaussianBlur(img, (0, 0), 1.6) * 0.12, 0, 1)

        tfile = os.path.join(ROOT, TEMPLATES[name]["file"]) if name != "spring" else M.BASE
        master = os.path.join(ROOT, "templates", "4k", os.path.basename(TEMPLATES[name]["file"]))
        night_b, day_b = c["night"].astype(np.float32), c["day"].astype(np.float32)
        if os.path.exists(master):
            # 4K: plates are graded at base res, then the AI-upscaled master's fine detail is added back
            tm = cv2.imread(tfile).astype(np.float32) / 255
            hi = cv2.resize(cv2.imread(master), (OUT_W, OUT_H), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
            hp = hi - cv2.GaussianBlur(hi, (0, 0), 1.2 * SX)
            Lt = cv2.GaussianBlur(lum(tm), (0, 0), 2) + 0.02

            lights = cv2.dilate(((c["warm"] > 0) | ((c["dayfix"] > 0) if "dayfix" in c.files else False)).astype(np.uint8), np.ones((7, 7), np.uint8)).astype(np.float32)
            no_lights = 1 - cv2.GaussianBlur(lights, (0, 0), 2)

            def detailed(plate, day=False):
                Lp = cv2.GaussianBlur(lum(plate), (0, 0), 2) + 0.02
                gain = np.clip(Lp / Lt, 0, 3)
                r = (plate + 0.03) / (tm + 0.03)
                dev = np.abs(r - cv2.GaussianBlur(r, (0, 0), 6)).mean(axis=2)
                keep = np.clip(1 - (dev - 0.08) / 0.12, 0, 1)            # skip pixels the grade re-painted
                if day:
                    keep = keep * no_lights                               # no lit-lamp detail by day
                w = up(cv2.GaussianBlur(keep * gain, (0, 0), 1.0))
                base = up(plate, cv2.INTER_LANCZOS4)
                base = base - (base - cv2.GaussianBlur(base, (0, 0), 1.2 * SX)) * np.clip(w, 0, 1)[..., None]
                return np.clip(base + hp * w[..., None], 0, 1)

            self.night, self.day = detailed(night_b), detailed(day_b, day=True)
        else:
            self.night, self.day = sharpen(night_b), sharpen(day_b)
        if "skya" in c.files:   # soft matte (silhouettes keep their own edge, no painted-sky fringe)
            self.sky = np.clip(cv2.GaussianBlur(up(c["skya"].astype(np.float32), cv2.INTER_CUBIC), (0, 0), 0.8), 0, 1)
        else:
            self.sky = np.clip(feather(up(c["sky"].astype(np.float32)) > 0.5, 1.4), 0, 1)
        self.refl = up(c["refl"].astype(np.float32))  # reflections of the lights on the lake
        self.water = feather(up(c["water"].astype(np.float32)) > 0.5, 1.5)
        self.warm = feather(up(c["warm"].astype(np.float32)) > 0.5, 1.0)
        self.moon_tex = shared["moon_tex"].astype(np.float32)
        self.depth = up(np.load(DEPTH).astype(np.float32)) if os.path.exists(DEPTH) else None
        yy = np.arange(OUT_H, dtype=np.float32)[:, None] / SX * np.ones((1, OUT_W), np.float32)
        self.yy = yy
        # distance haze weight: far band (mountains, far shore) strongest
        band = np.clip(1 - np.abs(yy - 630) / 110, 0, 1)
        near = np.zeros((BH, BW), np.uint8)
        cv2.fillPoly(near, [np.array(M.PAGODA, np.int32), np.array(M.PAVILION, np.int32),
                            np.array([(0, 0), (262, 0), (262, 941), (0, 941)], np.int32),
                            np.array([(1290, 560), (1672, 560), (1672, 941), (1290, 941)], np.int32),
                            np.array([(250, 700), (420, 700), (420, 941), (250, 941)], np.int32)], 1)
        near = feather(up(cv2.dilate(near, np.ones((15, 15), np.uint8)).astype(np.float32)), 12)
        self.far = band * (1 - self.sky) * (1 - near)
        # leftover sky the GrabCut missed: above the horizon line, between structures
        self.below = up(c["below"].astype(np.float32))
        # per-column colour of the painting's own horizon haze (just above the far ridge): the night sky
        # blends into it so the sky mask edge never shows as a hard band
        sk = c["sky"] > 0
        rows = sk & (np.arange(BH)[:, None] < 650)
        yb = np.where(rows.any(0), BH - 1 - np.argmax(rows[::-1], 0), -1).astype(np.float32)
        ok = yb > 520
        nt = c["night"].astype(np.float32)
        hc = np.zeros((BW, 3), np.float32)
        for x in np.nonzero(ok)[0]:
            y1 = int(yb[x]) - 3
            hc[x] = nt[y1 - 9:y1, x].mean(0)
        xs = np.arange(BW)
        if ok.sum() > 20:
            yb = np.interp(xs, xs[ok], yb[ok]).astype(np.float32)
            yb = np.median(np.lib.stride_tricks.sliding_window_view(np.pad(yb, 15, mode='edge'), 31), axis=1).astype(np.float32)
            hc = np.stack([np.interp(xs, xs[ok], hc[ok, i]) for i in range(3)], -1)
            hc = cv2.GaussianBlur(hc[None], (0, 0), 30)[0]
            if TEMPLATES[name]["lit"] == "golden":
                # the painted horizon glow is orange: keep only its brightness, in a blue-grey night haze
                bg = C(0.10, 0.14, 0.30)
                lh = np.minimum(lum(hc), 0.14)[:, None]
                hc = bg[None] * (lh / lum(bg)).astype(np.float32)
            yb = np.full_like(yb, 600.0)  # a straight haze band above the horizon; colour follows the painting
            wcol = cv2.GaussianBlur(ok.astype(np.float32)[None], (0, 0), 10)[0]
            self.hor = (np.repeat(yb * SX, 1), np.repeat(hc, 1, 0), wcol)
            self.hor = (cv2.resize(yb[None] * SX, (OUT_W, 1), interpolation=cv2.INTER_LINEAR)[0],
                        cv2.resize(hc[None], (OUT_W, 1), interpolation=cv2.INTER_LINEAR)[0],
                        cv2.resize(wcol[None], (OUT_W, 1), interpolation=cv2.INTER_LINEAR)[0])
        else:
            self.hor = None


# ---------------------------------------------------------------- sky model
# sky colours keyed by sun altitude: (zenith, horizon-toward-sun, horizon-away-from-sun), RGB
SKY_KEYS = [
    (-90, C(0.012, 0.035, 0.11), C(0.04, 0.08, 0.20), C(0.035, 0.07, 0.18)),
    (-14, C(0.015, 0.04, 0.12), C(0.06, 0.10, 0.24), C(0.04, 0.08, 0.20)),
    (-8, C(0.05, 0.08, 0.22), C(0.38, 0.30, 0.42), C(0.10, 0.12, 0.28)),
    (-4, C(0.14, 0.20, 0.42), C(0.90, 0.52, 0.38), C(0.36, 0.32, 0.50)),
    (-1, C(0.24, 0.36, 0.62), C(1.00, 0.62, 0.36), C(0.62, 0.52, 0.62)),
    (3, C(0.30, 0.48, 0.78), C(1.00, 0.74, 0.46), C(0.66, 0.70, 0.82)),
    (10, C(0.26, 0.50, 0.86), C(0.92, 0.88, 0.78), C(0.68, 0.80, 0.93)),
    (25, C(0.20, 0.46, 0.88), C(0.78, 0.88, 0.97), C(0.66, 0.80, 0.95)),
    (90, C(0.17, 0.42, 0.86), C(0.72, 0.85, 0.97), C(0.64, 0.79, 0.95)),
]
# light falling on the scene: (day-plate weight, tint RGB, exposure)
LIGHT_KEYS = [
    (-90, 0.0, C(1, 1, 1), 1.0),
    (-12, 0.0, C(1, 1, 1), 1.0),
    (-6, 0.18, C(0.62, 0.62, 0.92), 0.55),
    (-2, 0.40, C(0.88, 0.72, 0.85), 0.72),
    (1, 0.62, C(1.05, 0.80, 0.66), 0.85),
    (5, 0.85, C(1.08, 0.90, 0.74), 0.95),
    (12, 1.0, C(1.03, 0.98, 0.92), 1.0),
    (30, 1.0, C(1.0, 1.0, 1.0), 1.03),
    (90, 1.0, C(1.0, 1.0, 1.0), 1.05),
]


def sun_color(alt):
    return lerp_keys([(-2, C(1.0, 0.35, 0.12)), (2, C(1.0, 0.55, 0.25)), (8, C(1.0, 0.82, 0.55)),
                      (20, C(1.0, 0.96, 0.88)), (90, C(1.0, 1.0, 0.98))], alt)


# ---------------------------------------------------------------- procedural stars and clouds
_STARS = {}


def star_field():
    """Sparse, uneven starfield (output px, single channel): many faint stars, a few bright ones,
    thinning toward the horizon."""
    if "f" in _STARS:
        return _STARS["f"]
    rng = np.random.default_rng(42)
    f = np.zeros((OUT_H, OUT_W), np.float32)
    hz = HORIZON_Y * SX
    n = 430
    xs = rng.uniform(0, OUT_W, n)
    ys = hz * rng.random(n) ** 1.35
    mag = 0.18 + 0.82 * rng.random(n) ** 4.5
    for x, y, m in zip(xs, ys, mag):
        m *= 0.35 + 0.65 * min(1.0, y / (0.55 * hz))  # extinction near the horizon
        ix, iy = int(x), int(y)
        sg = 0.7 + 0.9 * m
        r = 3 if m < 0.6 else 5
        x0, x1, y0, y1 = max(0, ix - r), min(OUT_W, ix + r + 1), max(0, iy - r), min(OUT_H, iy + r + 1)
        gx = np.exp(-((np.arange(x0, x1) - x) ** 2) / (2 * sg ** 2))
        gy = np.exp(-((np.arange(y0, y1) - y) ** 2) / (2 * sg ** 2))
        f[y0:y1, x0:x1] = np.maximum(f[y0:y1, x0:x1], m * gy[:, None] * gx[None, :])
    _STARS["f"] = np.clip(f * 1.15, 0, 1)
    return _STARS["f"]


def _fbm_tex(seed, size=1024):
    key = ("tex", seed)
    if key not in _STARS:
        rng = np.random.default_rng(seed)
        t = np.zeros((size, size), np.float32)
        for o, g in enumerate((5, 10, 20, 40, 80, 160)):
            t += cv2.resize(rng.random((g, g)).astype(np.float32), (size, size), interpolation=cv2.INTER_CUBIC) * 0.55 ** o
        lo, hi = np.percentile(t, (3, 99))
        _STARS[key] = np.clip((t - lo) / (hi - lo), 0, 1)
    return _STARS[key]


def cloud_layer(when, cover, sa):
    """Soft cumulus field in perspective (smaller toward the horizon). The pattern changes with the
    date and drifts through the day. Returns (alpha, shade) at output size; shade 0 = underside, 1 = lit top."""
    w, h = OUT_W // 2, OUT_H // 2
    seed = (when.year * 400 + when.timetuple().tm_yday) % 100000
    tex = _fbm_tex(seed)
    hours = when.hour + when.minute / 60.0
    X = (np.arange(w, dtype=np.float32)[None, :] + 0.5) * 2
    Y = (np.arange(h, dtype=np.float32)[:, None] + 0.5) * 2
    hz = HORIZON_Y * SX

    iso = smooth(min(1.0, cover), 0.5, 1.0)  # overcast: flat layer, no perspective streaks

    def sample(dy):
        yh = np.maximum(hz - (Y + dy), 0) + 700
        tu = (X - OUT_W / 2) / yh * 330 * (1 - iso) + (X - OUT_W / 2) * 0.30 * iso + 512 + hours * 38 + (seed % 97) * 5
        tv = 300000 / yh * (1 - iso) + (hz - (Y + dy)) * 0.30 * iso + 300 * iso + (seed % 53) * 3
        return cv2.remap(tex, (tu * np.ones_like(tv)).astype(np.float32), (tv * np.ones_like(tu)).astype(np.float32),
                         cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    n = sample(0)
    nb = sample(10)  # a little lower on screen: the cloud's side facing the ground
    c = min(1.0, cover)
    cov = float(np.interp(c, [0, 0.12, 0.35, 0.7, 1.0], [0.015, 0.09, 0.36, 0.72, 0.97]))
    thr = float(np.quantile(n[: int(hz / 2)], 1 - cov))  # fixed coverage, date-dependent pattern
    k = (n - thr) / (0.035 + 0.12 * iso)
    a = np.clip(k, 0, 1)
    a = a * (0.55 + 0.45 * smooth(c, 0.0, 0.25)) * smooth(c, 0.03, 0.14)  # a clear sky stays clear
    yh = np.maximum(hz - Y, 0)
    a = a * (0.55 + 0.45 * np.clip(yh / 300, 0, 1)) * np.ones_like(n)
    a = cv2.GaussianBlur(a, (0, 0), 0.9)
    # painted look: three flat tones (shadow base, body, sunlit rim) with soft steps
    sh = np.clip(0.55 + (nb - n) * 6.0 * (1 - 0.6 * iso), 0, 1) * (1 - 0.40 * np.clip((n - thr) / 0.35, 0, 1))
    st3 = lambda x, e: np.clip((x - e) / 0.06, 0, 1)
    shade = 0.12 + 0.28 * st3(sh, 0.34) + 0.30 * st3(sh, 0.50) + 0.30 * st3(sh, 0.66)
    flat = np.clip(0.60 + (nb - n) * 1.6, 0, 1)
    shade = cv2.GaussianBlur(shade * (1 - iso) + flat * iso, (0, 0), 1.0 + 3.0 * iso)
    return np.clip(up(a), 0, 1), np.clip(up(shade), 0, 1)


def build_sky(st, cover, A):
    h, w = OUT_H, OUT_W
    sa = st["sun_alt"]
    zen = lerp_keys([(k[0], k[1]) for k in SKY_KEYS], sa)
    hs = lerp_keys([(k[0], k[2]) for k in SKY_KEYS], sa)
    ha = lerp_keys([(k[0], k[3]) for k in SKY_KEYS], sa)
    sx, sy = sky_xy(sa, st["sun_az"])
    X = np.arange(w, dtype=np.float32)[None, :]
    Y = np.arange(h, dtype=np.float32)[:, None]
    # horizon colour depends on how close (in azimuth) we look toward the sun
    toward = np.exp(-((X - sx) / (0.55 * w)) ** 2)
    hor = ha[None, None] * (1 - toward[..., None]) + hs[None, None] * toward[..., None]
    t = np.clip(Y / (HORIZON_Y * SX), 0, 1.15) ** 1.6
    sky = zen[None, None] * (1 - t[..., None]) + hor * t[..., None]
    sky = np.broadcast_to(sky, (h, w, 3)).copy()

    # overcast: everything greys out
    grey = lum(sky)[..., None] * C(0.92, 0.94, 1.0) * (0.85 + 0.15 * smooth(sa, -6, 10))
    sky = mix(sky, grey, np.full((h, w), 0.85 * cover, np.float32))

    # night: the horizon takes the painting's own haze colour so the sky edge blends into it
    nf = 1 - smooth(sa, -8, 0)
    if A.hor is not None and nf > 0:
        hy, hcol, hw = A.hor
        dd = hy[None, :] - Y
        wy = np.where(dd >= 0, np.clip(1 - dd / (130 * SX), 0, 1) ** 1.6, 1.0) * hw[None, :]
        tcol = hcol[None, :, :] * np.ones((h, 1, 1), np.float32)
        sky = mix(sky, tcol * (1 - 0.5 * cover), wy * 0.85 * nf)

    # stars (fade with twilight and clouds)
    night = 1 - smooth(sa, -14, -6)
    if night > 0:
        stars = star_field()
        if st["moon_alt"] > 0:  # moonlight washes out the faint ones
            mx, my = sky_xy(st["moon_alt"], st["moon_az"])
            stars = stars * (1 - 0.8 * st["moon_illum"] * np.exp(-(np.hypot(X - mx, Y - my) / (330 * SX)) ** 2))
        sky = screen(sky, (stars * night * max(0.0, 1 - 1.6 * cover))[..., None] * C(0.92, 0.94, 1.0))

    # sun glow + disk
    d = np.sqrt((X - sx) ** 2 + (Y - sy) ** 2)
    scol = sun_color(sa)
    if sa > -8:
        vis = smooth(sa, -8, -1)
        hi = smooth(sa, 10, 35)
        glow = (np.exp(-(d / (0.35 * w)) ** 2) * (0.35 - 0.15 * hi) + np.exp(-(d / ((0.08 - 0.03 * hi) * w)) ** 2) * (0.45 - 0.15 * hi))
        sky = screen(sky, (glow * vis * (1 - 0.7 * cover))[..., None] * scol)
        if sa > -1.0:
            disk = np.clip((26 * SX - d) / 3, 0, 1)
            corona = np.exp(-(d / (60 * SX)) ** 2)
            sky = screen(sky, ((disk + corona * 0.6) * max(0.0, 1 - 1.4 * cover))[..., None] * mix(scol, C(1, 1, 1), np.full((1, 1), 0.5, np.float32)))
    sky = np.clip(sky, 0, 1)

    # painted clouds, relit for the current light
    calpha, cshade = cloud_layer(st["when"], cover, sa)
    alpha = calpha
    if cover > 0.6:
        rng = np.random.default_rng(3)
        n = sum(cv2.resize(rng.random((3 * 2 ** o, 5 * 2 ** o)).astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC) * 0.5 ** o for o in range(6))
        n = (n - n.min()) / (n.max() - n.min())
        alpha = np.maximum(alpha, np.clip((cover - 0.6) / 0.4 * (0.75 + 0.35 * n), 0, 1))
    day = smooth(sa, -6, 8)
    lit = lerp_keys([(-90, C(0.36, 0.40, 0.55)), (-8, C(0.40, 0.38, 0.55)), (-3, C(0.98, 0.55, 0.50)),
                     (1, C(1.0, 0.68, 0.45)), (6, C(1.0, 0.86, 0.70)), (15, C(0.98, 0.98, 0.98)),
                     (90, C(1.0, 1.0, 1.0))], sa)
    shadow = lerp_keys([(-90, C(0.08, 0.10, 0.20)), (-8, C(0.12, 0.12, 0.26)), (-3, C(0.38, 0.30, 0.48)),
                        (2, C(0.55, 0.45, 0.55)), (12, C(0.70, 0.74, 0.82)), (90, C(0.74, 0.78, 0.86))], sa)
    shade = cshade
    # clouds near the sun are lit more strongly (silver / golden linings)
    nearsun = np.exp(-(d / (0.45 * w)) ** 2) * (1 - cover) * smooth(sa, -6, 0)
    ccol = mix(shadow[None, None] * np.ones((h, w, 3), np.float32), lit[None, None] * np.ones((h, w, 3), np.float32),
               np.clip(shade * 0.75 + nearsun * 0.5, 0, 1))
    if cover > 0.6:
        og = lerp_keys([(-90, C(0.11, 0.11, 0.14)), (-6, C(0.18, 0.18, 0.23)), (0, C(0.40, 0.38, 0.42)),
                        (10, C(0.66, 0.68, 0.72)), (90, C(0.74, 0.76, 0.80))], sa)
        ccol = mix(ccol, og[None, None] * (0.85 + 0.25 * shade)[..., None], np.full((h, w), (cover - 0.6) / 0.4, np.float32))
    sky = mix(sky, ccol, alpha)
    if cover > 0.5 and sa < -4:  # city light reflecting off low cloud
        yy = np.clip(Y / (HORIZON_Y * SX), 0, 1.2) ** 3
        sky = screen(sky, (yy ** 1.5 * 0.08 * (cover - 0.5) * 2 * (1 - smooth(sa, -8, -4)))[..., None] * C(0.85, 0.66, 0.50))

    # moon
    moon_layer(sky, st, cover, A)
    return np.clip(sky, 0, 1), (sx, sy), alpha


def moon_layer(sky, st, cover, A):
    ma = st["moon_alt"]
    if ma < -3:
        return
    mx, my = sky_xy(ma, st["moon_az"])
    r = int(MOON[2] * SX * 0.9)
    if not (-r < mx < OUT_W + r and -r < my < OUT_H + r):
        return
    tex = cv2.resize(A.moon_tex, (2 * r, 2 * r), interpolation=cv2.INTER_CUBIC)
    yy, xx = np.mgrid[-r:r, -r:r].astype(np.float32) / r
    disk = np.clip((1 - np.sqrt(xx ** 2 + yy ** 2)) * r / 1.5, 0, 1)
    # phase: rotate so +x points toward the sun's projected position
    sx, sy = sky_xy(st["sun_alt"], st["sun_az"])
    ang = math.atan2(sy - my, sx - mx)
    u = xx * math.cos(ang) + yy * math.sin(ang)
    v = -xx * math.sin(ang) + yy * math.cos(ang)
    i = math.radians(st["moon_phase_angle"])
    edge = -math.cos(i) * np.sqrt(np.clip(1 - v ** 2, 0, 1))
    lit = np.clip((u - edge) * r / 2.0, 0, 1)
    sa = st["sun_alt"]
    day = smooth(sa, -8, 6)
    tex_l = lum(tex)
    tex_n = np.clip(tex_l / (tex_l.max() + 1e-4), 0, 1)
    moon_col = C(0.97, 0.96, 0.92)[None, None] * (0.55 + 0.45 * tex_n)[..., None]
    day0 = smooth(st["sun_alt"], -8, 6)
    a = disk * (lit + 0.06 * (1 - day0) * (1 - lit)) * max(0.0, 1 - 1.4 * cover)
    a = a * (1 - 0.55 * day0)  # paler in daylight; dark side invisible by day
    # horizon fade
    a = a * smooth(ma, -2, 3)
    x0, y0 = int(mx) - r, int(my) - r
    xs0, ys0 = max(0, -x0), max(0, -y0)
    xs1, ys1 = min(2 * r, OUT_W - x0), min(2 * r, OUT_H - y0)
    if xs1 <= xs0 or ys1 <= ys0:
        return
    sl = (slice(y0 + ys0, y0 + ys1), slice(x0 + xs0, x0 + xs1))
    sub = (slice(ys0, ys1), slice(xs0, xs1))
    region = sky[sl]
    region[:] = mix(region, moon_col[sub] if day < 0.5 else screen(region, moon_col[sub] * 0.9), a[sub])
    # halo at night
    if day < 1:
        Y, X = np.ogrid[:OUT_H, :OUT_W]
        dd = np.sqrt((X - mx) ** 2 + (Y - my) ** 2).astype(np.float32)
        halo = np.exp(-(dd / (r * 2.6)) ** 2) * 0.22 * st["moon_illum"] * (1 - day) * max(0.0, 1 - 1.4 * cover) * smooth(ma, -2, 3)
        sky[:] = screen(sky, halo[..., None] * C(0.8, 0.85, 1.0))


_GLIT = {}


def glitter(cx, half_w, strength):
    """Specular streak on the lake under the sun / moon at output column cx: horizontal dashes
    in a column of gaussian width half_w (base px), longer and denser toward the viewer."""
    if "n" not in _GLIT:
        rng = np.random.default_rng(5)
        n = cv2.GaussianBlur(rng.standard_normal((OUT_H, OUT_W)).astype(np.float32), (0, 0), sigmaX=7, sigmaY=1.1)
        _GLIT["n"] = n / n.std()
    n = _GLIT["n"]
    X = np.arange(OUT_W, dtype=np.float32)[None, :]
    Y = np.arange(OUT_H, dtype=np.float32)[:, None]
    near = np.clip((Y / SX - 690) / 100, 0, 1)
    width = half_w * SX * (0.45 + 0.8 * near)
    col = np.exp(-((X - cx) / width) ** 2)
    dash = np.clip((n - 0.9 + 0.6 * near) * 0.9, 0, 1)
    return col * dash * strength * (1 - 0.35 * near)


FIREFLY_ZONES = [(0, 520, 72, 780), (1290, 640, 1480, 830), (1420, 790, 1672, 941), (560, 770, 1250, 800),
                 (262, 760, 430, 800)]  # base px boxes: shrubs and trees at the edges of the scene


def fireflies(img, A, when):
    """A few dozen small warm glows drifting and blinking among the foreground greenery.
    Deterministic per date; blink phase follows the clock."""
    rng = np.random.default_rng((when.year * 400 + when.timetuple().tm_yday) % 100000 + 7)
    t = when.hour * 60 + when.minute
    pts = []
    for (x0, y0, x1, y1) in FIREFLY_ZONES:
        area = (x1 - x0) * (y1 - y0)
        for _ in range(max(3, int(area / 4500))):
            for _try in range(12):
                x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
                ix, iy = int(x * SX), int(y * SX)
                if A.sky[iy, ix] < 0.1 and A.water[iy, ix] < 0.1 and lum(A.night[iy:iy + 1, ix:ix + 1])[0, 0] < 0.28:
                    pts.append((x * SX, y * SX, rng.uniform(0, 1), rng.uniform(25, 70), rng.uniform(0.6, 1.0)))
                    break
    out = np.zeros(img.shape, np.float32)
    for x, y, ph, per, amp in pts:
        b = float(np.clip(math.sin(2 * math.pi * (t / per + ph)) * 2.2 + 0.7, 0, 1)) * amp  # blink (on ~60% of the time)
        if b < 0.02:
            continue
        x += 6 * math.sin(t / 9.0 + ph * 20); y += 4 * math.sin(t / 7.0 + ph * 11)  # slow drift
        r = 14
        x0, x1, y0, y1 = int(x) - r, int(x) + r + 1, int(y) - r, int(y) + r + 1
        if x0 < 0 or y0 < 0 or x1 > OUT_W or y1 > OUT_H:
            continue
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        d2 = (xx - x) ** 2 + (yy - y) ** 2
        g = np.exp(-d2 / (2 * 1.6 ** 2)) * 0.95 + np.exp(-d2 / (2 * 6.0 ** 2)) * 0.30
        out[y0:y1, x0:x1] += g[..., None] * C(1.0, 0.92, 0.45) * b
    return screen(img, np.clip(out, 0, 1))


# ---------------------------------------------------------------- scene lighting
_ASSETS = {}


def assets_for(season):
    name = template_for(season)
    if name not in _ASSETS:
        _ASSETS[name] = Assets(name)
    return _ASSETS[name]


def season_of(when):
    return {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring", 5: "spring",
            6: "summer", 7: "summer", 8: "summer"}.get(when.month, "autumn")


WEATHER_EFFECTS = ("rain", "storm", "fog", "snow")


def render(when, cover=0.3, A=None, season=None, weather=None, intensity=1.0):
    """weather: None/clear/partly_cloudy/overcast (handled by `cover`) or one of
    WEATHER_EFFECTS, which forces an overcast sky and then runs render/effects/<module>."""
    scene = season or season_of(when)
    season = BASE_SEASON.get(scene, scene)  # autumnlate -> autumn, winterbare -> winter
    A = A or assets_for(scene)
    if weather in WEATHER_EFFECTS:
        cover = max(cover, 0.92)
    st = astro.sky_state(when)
    st["when"] = when
    sa = st["sun_alt"]
    sky, (sx, sy), calpha = build_sky(st, cover, A)

    # --- foreground: blend night painting and day plate by sun altitude
    wday = float(lerp_keys([(k[0], np.array([k[1]], np.float32)) for k in LIGHT_KEYS], sa)[0])
    tint = lerp_keys([(k[0], k[2]) for k in LIGHT_KEYS], sa)
    expo = float(lerp_keys([(k[0], np.array([k[3]], np.float32)) for k in LIGHT_KEYS], sa)[0])
    night = A.night
    if wday < 1:
        # at twilight the night painting keeps its lights, with the sky's colour on it
        night_l = night.copy()
    img = A.day * wday + (night if wday < 1 else 0) * (1 - wday)
    img = img * tint[None, None] * expo
    # overcast: flatter, greyer, a bit darker
    g = lum(img)[..., None]
    img = mix(img, (g + (img - g) * 0.6 - 0.5) * 0.85 + 0.5 - 0.06, np.full(img.shape[:2], 0.7 * cover * smooth(sa, -6, 6), np.float32))
    # low sun: warm light raking from the sun's side of the frame
    if -4 < sa < 14 and cover < 0.8:
        X = np.arange(OUT_W, dtype=np.float32)[None, :]
        side = np.clip(1 - np.abs(X - sx) / (1.1 * OUT_W), 0, 1) ** 2 * np.ones((OUT_H, 1), np.float32)
        k = (1 - smooth(sa, 6, 14)) * smooth(sa, -4, 1) * (1 - cover) * 0.35
        img = screen(img, (side * k)[..., None] * sun_color(sa))
    # distance haze tinted by the horizon sky
    r0 = int(HORIZON_Y * SX) - 5
    hz = cv2.GaussianBlur(sky[r0 - 100:r0 + 100], (0, 0), 30)[100]
    haze_col = np.median(hz, axis=0)
    img = mix(img, haze_col[None, None], A.far * (0.18 + 0.25 * cover))

    # --- lake reflects the sky (mirrored about the far shore), with the original ripples
    wy = int(692 * SX)
    rows = np.arange(OUT_H, dtype=np.float32)
    src = np.clip(wy - (rows - wy) * 2.2 - 8 * SX, 0, OUT_H - 1)
    refl = sky[src.astype(int)]
    refl = cv2.GaussianBlur(refl, (0, 0), sigmaX=6, sigmaY=1.5) * C(0.70, 0.78, 0.84)
    plate = img
    ripple = lum(plate) - cv2.GaussianBlur(lum(plate), (0, 0), 4)
    water = np.clip(plate * 0.45 + refl * 0.62 + ripple[..., None] * 0.5, 0, 1)
    # sun / moon glitter path: broken horizontal dashes, thin and bright near the horizon
    if sa > -1 and 0 < sx < OUT_W:
        water = screen(water, glitter(sx, 40, 0.9 * (1 - cover) * smooth(sa, -1, 3))[..., None] * sun_color(sa))
    if st["moon_alt"] > 3 and sa < -3 and cover < 0.7:
        mx, _ = sky_xy(st["moon_alt"], st["moon_az"])
        k = (0.25 + 0.75 * st["moon_illum"]) * (1 - cover / 0.7) * smooth(st["moon_alt"], 3, 8) * 0.8
        water = screen(water, glitter(mx, 26, k)[..., None] * C(0.85, 0.9, 1.0))
    # reflections of the shore lights (thin, broken) only while they are on
    lights_on = 1 - smooth(sa, 5, 12)
    if lights_on > 0:
        water = screen(water, np.clip(A.refl * lights_on * (1 - 0.5 * cover * 0.0), 0, 1))
    img = mix(img, water, A.water * 0.9)

    # --- lights: on from dusk to dawn
    if lights_on > 0:
        lights = A.night * A.warm[..., None]
        img = mix(img, np.maximum(img, lights * 1.05), A.warm * lights_on)
        lit = A.night * A.warm[..., None] * C(1.15, 0.85, 0.55)
        q = cv2.resize(lit, (OUT_W // 4, OUT_H // 4), interpolation=cv2.INTER_AREA)  # glow is smooth: blur at 1/4 size
        glow = cv2.GaussianBlur(q, (0, 0), 20 * SX / 4) * 0.8 + cv2.GaussianBlur(q, (0, 0), 5 * SX / 4) * 0.4
        glow = cv2.resize(glow, (OUT_W, OUT_H), interpolation=cv2.INTER_CUBIC)
        img = screen(img, np.clip(glow * lights_on, 0, 1))

    if season == "summer" and sa < -9 and cover < 0.7 and weather not in WEATHER_EFFECTS:
        img = fireflies(img, A, when)

    # --- compose sky (and bleed the sun's bloom over silhouettes)
    out = mix(img, sky, A.sky)
    if sa > -2 and cover < 0.9:
        X = np.arange(OUT_W, dtype=np.float32)[None, :]
        Y = np.arange(OUT_H, dtype=np.float32)[:, None]
        d = np.sqrt((X - sx) ** 2 + (Y - sy) ** 2)
        bloom = np.exp(-(d / (90 * SX)) ** 2) * 0.35 * (1 - cover) * smooth(sa, -2, 1)
        out = screen(out, bloom[..., None] * sun_color(sa))
    out = np.clip(out, 0, 1)
    if weather in WEATHER_EFFECTS:
        import effects
        ctx = dict(A=A, st=st, sky=sky, when=when, cover=cover, season=season,
                   lights_on=lights_on, intensity=intensity, sun_xy=(sx, sy))
        out = np.clip(effects.apply(weather, out, ctx), 0, 1)
    return out, st


def to8(img):
    """Quantise with a little dither so smooth skies don't band."""
    n = np.random.default_rng(1).random(img.shape[:2], dtype=np.float32)[..., None] - 0.5
    return np.clip(img * 255 + n + 0.5, 0, 255).astype(np.uint8)


def parse_when(s):
    return dt.datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=TZ)


if __name__ == "__main__":
    when = parse_when(sys.argv[1])
    cover = {"clear": 0.0, "partly": 0.35, "overcast": 1.0}[sys.argv[2]]
    out, st = render(when, cover)
    cv2.imwrite(sys.argv[3], to8(out))
    print(sys.argv[3], {k: round(v, 1) if isinstance(v, float) else v for k, v in st.items()})
