"""scenekit: generic building blocks for rendering ANY scene package at any moment and weather.

Runtime dependencies: numpy + opencv only (same as the original runtime). A scene package is the folder written by
the pipeline (05_package): manifest.json, plates/<key>.png (+ plates4k/), layers.npz. A per-scene file
`scene_renderer.py` (written by the local code model) composes these primitives; `default_render` is the reference
composition it starts from.

Conventions: images are float32 BGR in [0,1] at output size (OUT_H, OUT_W); masks float32 HxW in [0,1].
Colours are written as RGB with C(r,g,b) and stored BGR. Angles in degrees. Azimuth 0 = north, clockwise.
"""
import datetime as dt
import json
import math
import os
from zoneinfo import ZoneInfo

import cv2
import numpy as np

from . import astro

OUT_W, OUT_H = 3840, 2160


# ------------------------------------------------------------------------------------------ small helpers
def C(r, g, b):
    return np.array([b, g, r], np.float32)


def lum(img):
    return img[..., 0] * 0.114 + img[..., 1] * 0.587 + img[..., 2] * 0.299


def mix(a, b, t):
    t = np.asarray(t, np.float32)
    if t.ndim == 2:
        t = t[..., None]
    return a * (1 - t) + b * t


def screen(a, b):
    return 1 - (1 - a) * (1 - b)


def smooth(x, e0, e1):
    t = np.clip((np.asarray(x, np.float32) - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def lerp_keys(keys, x):
    if x <= keys[0][0]:
        return keys[0][1]
    for (x0, v0), (x1, v1) in zip(keys, keys[1:]):
        if x <= x1:
            t = (x - x0) / (x1 - x0)
            return v0 * (1 - t) + v1 * t
    return keys[-1][1]


def up(a, interp=cv2.INTER_LINEAR):
    return cv2.resize(a, (OUT_W, OUT_H), interpolation=interp)


def feather(m, s):
    return cv2.GaussianBlur(m.astype(np.float32), (0, 0), s) if s > 0 else m


# ------------------------------------------------------------------------------------------------ scene
class Scene:
    """Loads a scene package. Plates are loaded lazily and cached at output size."""

    def __init__(self, pkg_dir):
        self.dir = pkg_dir
        self.m = json.load(open(os.path.join(pkg_dir, "manifest.json")))
        self.tz = ZoneInfo(self.m["location"]["timezone"])
        self.lat, self.lon = self.m["location"]["lat"], self.m["location"]["lon"]
        self._z = np.load(os.path.join(pkg_dir, "layers.npz"))
        self.layers = _LazyLayers(self._z)
        self._plates = {}
        self.cam = self.m["camera"]

    def layer(self, name):
        return self.layers.get(name, np.zeros((OUT_H, OUT_W), np.float32))

    def sky_mask(self, F, wday=None):
        """Sky matte for this frame: each plate has its own (its own sky colour spills past the shared matte by a few
        pixels); blended like the plates."""
        d, n = self.layers.get("sky_%s_day" % F.phase), self.layers.get("sky_%s_night" % F.phase)
        if d is None or n is None:
            return self.layer("sky")
        if wday is None:
            wday = float(lerp_keys([(k[0], np.array([k[1]], np.float32)) for k in LIGHT_KEYS], F.sun_alt)[0])
        return d * wday + n * (1 - wday)

    def plate(self, key):
        if key not in self._plates:
            p4 = os.path.join(self.dir, "plates4k", key + ".png")
            p = p4 if os.path.exists(p4) else os.path.join(self.dir, "plates", key + ".png")
            im = cv2.imread(p)
            if im is None:
                raise FileNotFoundError(p)
            self._plates[key] = cv2.resize(im, (OUT_W, OUT_H), interpolation=cv2.INTER_AREA if im.shape[1] > OUT_W
                                           else cv2.INTER_CUBIC).astype(np.float32) / 255
        return self._plates[key]

    def phase_for(self, when, snow_depth_m=None):
        m = self.m
        avail = set(m.get("plates") or [])
        # a preview package holds only some phases: fall back to the latest phase that has both plates
        has = lambda pid: not avail or (pid + "_day" in avail and pid + "_night" in avail)
        if m.get("snow_template") and has("snow") and snow_depth_m is not None and \
                snow_depth_m * 100 >= m.get("snow_min_depth_cm", 2):
            return "snow"
        key = when.strftime("%m-%d")
        phases = [p for p in m["phases"] if has(p["id"])] or m["phases"]
        cur = phases[-1]["id"]
        for p in phases:
            if p["start_mmdd"] <= key:
                cur = p["id"]
        return cur


class _LazyLayers(dict):
    """Layer arrays upscaled to output size on first use (a package can hold many per-plate mattes)."""

    def __init__(self, z):
        super().__init__()
        self._z = z

    def __contains__(self, k):
        return k in self._z.files

    def get(self, k, default=None):
        if k not in self._z.files:
            return default
        if not dict.__contains__(self, k):
            dict.__setitem__(self, k, up(self._z[k].astype(np.float32)))
        return dict.__getitem__(self, k)

    def __getitem__(self, k):
        v = self.get(k)
        if v is None:
            raise KeyError(k)
        return v

    def keys(self):
        return list(self._z.files)


class Frame:
    """Everything one render needs. Build with Frame.at(scene, when, cover, weather, intensity, snow_depth_m)."""

    def __init__(self, scene, when, st, cover, weather, intensity, phase):
        self.scene, self.when, self.st, self.cover = scene, when, st, cover
        self.weather, self.intensity, self.phase = weather, intensity, phase
        self.sun_alt = st["sun_alt"]

    @classmethod
    def at(cls, scene, when, cover=0.3, weather=None, intensity=1.0, snow_depth_m=None, phase=None):
        if when.tzinfo is None:
            when = when.replace(tzinfo=scene.tz)
        st = astro.sky_state(when, scene.lat, scene.lon)
        st["when"] = when
        if weather in ("rain", "storm", "snow", "fog"):
            cover = max(cover, 0.92 if weather != "fog" else 0.7)
        return cls(scene, when, st, cover, weather, intensity, phase or scene.phase_for(when, snow_depth_m))


# -------------------------------------------------------------------------------------------- camera
def sky_xy(cam, alt, az):
    """Sky direction -> output pixel (may be off-frame). cam: view_az, hfov, horizon (0..1 of height)."""
    daz = (az - cam["view_az"] + 540) % 360 - 180
    x = (0.5 + daz / cam["hfov"]) * OUT_W
    vfov = cam["hfov"] * OUT_H / OUT_W
    hy = cam["horizon"] * OUT_H
    y = hy - alt / vfov * OUT_H
    return x, y


# ------------------------------------------------------------------------------------------- sky model
SKY_KEYS = [  # (sun alt, zenith, horizon toward sun, horizon away from sun) - from the hand-tuned Chicago renderer
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
LIGHT_KEYS = [  # (sun alt, day-plate weight, tint, exposure)
    (-90, 0.0, C(1, 1, 1), 1.0), (-12, 0.0, C(1, 1, 1), 1.0), (-6, 0.18, C(0.62, 0.62, 0.92), 0.55),
    (-2, 0.40, C(0.88, 0.72, 0.85), 0.72), (1, 0.62, C(1.05, 0.80, 0.66), 0.85), (5, 0.85, C(1.08, 0.90, 0.74), 0.95),
    (12, 1.0, C(1.03, 0.98, 0.92), 1.0), (30, 1.0, C(1.0, 1.0, 1.0), 1.03), (90, 1.0, C(1.0, 1.0, 1.0), 1.05)]


def sun_color(alt):
    return lerp_keys([(-2, C(1.0, 0.35, 0.12)), (2, C(1.0, 0.55, 0.25)), (8, C(1.0, 0.82, 0.55)),
                      (20, C(1.0, 0.96, 0.88)), (90, C(1.0, 1.0, 0.98))], alt)


_CACHE = {}


def _fbm(seed, size=1024, octaves=(5, 10, 20, 40, 80, 160)):
    key = ("fbm", seed, size)
    if key not in _CACHE:
        rng = np.random.default_rng(seed)
        t = np.zeros((size, size), np.float32)
        for o, g in enumerate(octaves):
            t += cv2.resize(rng.random((g, g)).astype(np.float32), (size, size), interpolation=cv2.INTER_CUBIC) * 0.55 ** o
        lo, hi = np.percentile(t, (3, 99))
        _CACHE[key] = np.clip((t - lo) / (hi - lo), 0, 1)
    return _CACHE[key]


def star_field(cam, n=430, seed=42):
    key = ("stars", cam["horizon"], n, seed)
    if key in _CACHE:
        return _CACHE[key]
    rng = np.random.default_rng(seed)
    f = np.zeros((OUT_H, OUT_W), np.float32)
    hz = cam["horizon"] * OUT_H
    for x, y, m in zip(rng.uniform(0, OUT_W, n), hz * rng.random(n) ** 1.35, 0.18 + 0.82 * rng.random(n) ** 4.5):
        m *= 0.35 + 0.65 * min(1.0, y / (0.55 * hz + 1))
        ix, iy, sg = int(x), int(y), 0.7 + 0.9 * m
        r = 3 if m < 0.6 else 5
        x0, x1, y0, y1 = max(0, ix - r), min(OUT_W, ix + r + 1), max(0, iy - r), min(OUT_H, iy + r + 1)
        gx = np.exp(-((np.arange(x0, x1) - x) ** 2) / (2 * sg ** 2))
        gy = np.exp(-((np.arange(y0, y1) - y) ** 2) / (2 * sg ** 2))
        f[y0:y1, x0:x1] = np.maximum(f[y0:y1, x0:x1], m * gy[:, None] * gx[None, :])
    _CACHE[key] = np.clip(f * 1.15, 0, 1)
    return _CACHE[key]


def clouds(F, cam, cover):
    """Painted cumulus in perspective, pattern changes daily and drifts with the hour. -> (alpha, shade)."""
    when = F.when
    w, h = OUT_W // 2, OUT_H // 2
    seed = (when.year * 400 + when.timetuple().tm_yday) % 100000
    tex = _fbm(seed)
    hours = when.hour + when.minute / 60.0
    X = (np.arange(w, dtype=np.float32)[None, :] + 0.5) * 2
    Y = (np.arange(h, dtype=np.float32)[:, None] + 0.5) * 2
    hz = max(cam["horizon"] * OUT_H, OUT_H * 0.25)
    iso = float(smooth(min(1.0, cover), 0.5, 1.0))

    def sample(dy):
        yh = np.maximum(hz - (Y + dy), 0) + 700
        tu = (X - OUT_W / 2) / yh * 330 * (1 - iso) + (X - OUT_W / 2) * 0.30 * iso + 512 + hours * 38 + (seed % 97) * 5
        tv = 300000 / yh * (1 - iso) + (hz - (Y + dy)) * 0.30 * iso + 300 * iso + (seed % 53) * 3
        return cv2.remap(tex, (tu * np.ones_like(tv)).astype(np.float32), (tv * np.ones_like(tu)).astype(np.float32),
                         cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    n, nb = sample(0), sample(10)
    c = min(1.0, cover)
    cov = float(np.interp(c, [0, 0.12, 0.35, 0.7, 1.0], [0.015, 0.09, 0.36, 0.72, 0.97]))
    thr = float(np.quantile(n[: max(2, int(hz / 2))], 1 - cov))
    a = np.clip((n - thr) / (0.035 + 0.12 * iso), 0, 1)
    a = a * (0.55 + 0.45 * float(smooth(c, 0.0, 0.25))) * float(smooth(c, 0.03, 0.14))
    a = a * (0.55 + 0.45 * np.clip(np.maximum(hz - Y, 0) / 300, 0, 1)) * np.ones_like(n)
    a = cv2.GaussianBlur(a, (0, 0), 0.9)
    sh = np.clip(0.55 + (nb - n) * 6.0 * (1 - 0.6 * iso), 0, 1) * (1 - 0.40 * np.clip((n - thr) / 0.35, 0, 1))
    st3 = lambda x, e: np.clip((x - e) / 0.06, 0, 1)
    shade = 0.12 + 0.28 * st3(sh, 0.34) + 0.30 * st3(sh, 0.50) + 0.30 * st3(sh, 0.66)
    flat = np.clip(0.60 + (nb - n) * 1.6, 0, 1)
    shade = cv2.GaussianBlur(shade * (1 - iso) + flat * iso, (0, 0), 1.0 + 3.0 * iso)
    return np.clip(up(a), 0, 1), np.clip(up(shade), 0, 1)


def moon_texture(r):
    key = ("moon", r)
    if key not in _CACHE:
        rng = np.random.default_rng(11)
        yy, xx = np.mgrid[-r:r, -r:r].astype(np.float32) / r
        t = 0.82 + 0.10 * (cv2.resize(_fbm(5, 256), (2 * r, 2 * r)) - 0.5)
        for _ in range(7):   # maria: soft darker patches
            cx, cy, rr = rng.uniform(-0.55, 0.55), rng.uniform(-0.55, 0.55), rng.uniform(0.15, 0.38)
            t -= 0.13 * np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (rr * rr))
        _CACHE[key] = np.clip(t, 0, 1)
    return _CACHE[key]


def sky(F, cam, cover, stars=True, sun_disk=True, moon=True, cloud=True, moon_size=1.0):
    """Full procedural sky for this frame -> (sky BGR, sun_xy)."""
    st, sa = F.st, F.sun_alt
    zen = lerp_keys([(k[0], k[1]) for k in SKY_KEYS], sa)
    hs = lerp_keys([(k[0], k[2]) for k in SKY_KEYS], sa)
    ha = lerp_keys([(k[0], k[3]) for k in SKY_KEYS], sa)
    sx, sy = sky_xy(cam, sa, st["sun_az"])
    X = np.arange(OUT_W, dtype=np.float32)[None, :]
    Y = np.arange(OUT_H, dtype=np.float32)[:, None]
    toward = np.exp(-((X - sx) / (0.55 * OUT_W)) ** 2)
    hor = ha[None, None] * (1 - toward[..., None]) + hs[None, None] * toward[..., None]
    t = np.clip(Y / max(1.0, cam["horizon"] * OUT_H), 0, 1.15) ** 1.6
    s = zen[None, None] * (1 - t[..., None]) + hor * t[..., None]
    s = np.broadcast_to(s, (OUT_H, OUT_W, 3)).copy()
    grey = lum(s)[..., None] * C(0.92, 0.94, 1.0) * (0.85 + 0.15 * float(smooth(sa, -6, 10)))
    s = mix(s, grey, 0.85 * cover)
    night = 1 - float(smooth(sa, -14, -6))
    if stars and night > 0:
        f = star_field(cam)
        if st["moon_alt"] > 0:
            mx, my = sky_xy(cam, st["moon_alt"], st["moon_az"])
            f = f * (1 - 0.8 * st["moon_illum"] * np.exp(-(np.hypot(X - mx, Y - my) / 1000) ** 2))
        s = screen(s, (f * night * max(0.0, 1 - 1.6 * cover))[..., None] * C(0.92, 0.94, 1.0))
    d = np.sqrt((X - sx) ** 2 + (Y - sy) ** 2)
    scol = sun_color(sa)
    if sa > -8:
        vis, hi = float(smooth(sa, -8, -1)), float(smooth(sa, 10, 35))
        glow = np.exp(-(d / (0.35 * OUT_W)) ** 2) * (0.35 - 0.15 * hi) + np.exp(-(d / ((0.08 - 0.03 * hi) * OUT_W)) ** 2) * (0.45 - 0.15 * hi)
        s = screen(s, (glow * vis * (1 - 0.7 * cover))[..., None] * scol)
        if sun_disk and sa > -1.0:
            R = 0.0155 * OUT_W
            disk = np.clip((R - d) / 3, 0, 1)
            corona = np.exp(-(d / (R * 2.3)) ** 2)
            s = screen(s, ((disk + corona * 0.6) * max(0.0, 1 - 1.4 * cover))[..., None] * (scol * 0.5 + 0.5))
    s = np.clip(s, 0, 1)
    if cloud:
        ca, cs = clouds(F, cam, cover)
        if cover > 0.6:
            rng = np.random.default_rng(3)
            nn = sum(cv2.resize(rng.random((3 * 2 ** o, 5 * 2 ** o)).astype(np.float32), (OUT_W, OUT_H),
                                interpolation=cv2.INTER_CUBIC) * 0.5 ** o for o in range(6))
            nn = (nn - nn.min()) / (nn.max() - nn.min())
            ca = np.maximum(ca, np.clip((cover - 0.6) / 0.4 * (0.75 + 0.35 * nn), 0, 1))
        lit = lerp_keys([(-90, C(0.36, 0.40, 0.55)), (-8, C(0.40, 0.38, 0.55)), (-3, C(0.98, 0.55, 0.50)),
                         (1, C(1.0, 0.68, 0.45)), (6, C(1.0, 0.86, 0.70)), (15, C(0.98, 0.98, 0.98)), (90, C(1, 1, 1))], sa)
        shadow = lerp_keys([(-90, C(0.08, 0.10, 0.20)), (-8, C(0.12, 0.12, 0.26)), (-3, C(0.38, 0.30, 0.48)),
                            (2, C(0.55, 0.45, 0.55)), (12, C(0.70, 0.74, 0.82)), (90, C(0.74, 0.78, 0.86))], sa)
        nearsun = np.exp(-(d / (0.45 * OUT_W)) ** 2) * (1 - cover) * float(smooth(sa, -6, 0))
        ccol = mix(np.broadcast_to(shadow, s.shape), np.broadcast_to(lit, s.shape), np.clip(cs * 0.75 + nearsun * 0.5, 0, 1))
        if cover > 0.6:
            og = lerp_keys([(-90, C(0.11, 0.11, 0.14)), (-6, C(0.18, 0.18, 0.23)), (0, C(0.40, 0.38, 0.42)),
                            (10, C(0.66, 0.68, 0.72)), (90, C(0.74, 0.76, 0.80))], sa)
            ccol = mix(ccol, og[None, None] * (0.85 + 0.25 * cs)[..., None], (cover - 0.6) / 0.4)
        s = mix(s, ccol, ca)
    if moon:
        _moon(s, F, cam, cover, moon_size)
    return np.clip(s, 0, 1), (sx, sy)


def _moon(s, F, cam, cover, size):
    st = F.st
    ma = st["moon_alt"]
    if ma < -3:
        return
    mx, my = sky_xy(cam, ma, st["moon_az"])
    r = int(0.0125 * OUT_W * size)
    if not (-r < mx < OUT_W + r and -r < my < OUT_H + r):
        return
    tex = moon_texture(r)
    yy, xx = np.mgrid[-r:r, -r:r].astype(np.float32) / r
    disk = np.clip((1 - np.sqrt(xx ** 2 + yy ** 2)) * r / 1.5, 0, 1)
    sx, sy = sky_xy(cam, st["sun_alt"], st["sun_az"])
    ang = math.atan2(sy - my, sx - mx)
    u = xx * math.cos(ang) + yy * math.sin(ang)
    v = -xx * math.sin(ang) + yy * math.cos(ang)
    edge = -math.cos(math.radians(st["moon_phase_angle"])) * np.sqrt(np.clip(1 - v ** 2, 0, 1))
    lit = np.clip((u - edge) * r / 2.0, 0, 1)
    day = float(smooth(st["sun_alt"], -8, 6))
    col = C(0.97, 0.96, 0.92)[None, None] * tex[..., None]
    a = disk * (lit + 0.06 * (1 - day) * (1 - lit)) * max(0.0, 1 - 1.4 * cover) * (1 - 0.55 * day) * float(smooth(ma, -2, 3))
    x0, y0 = int(mx) - r, int(my) - r
    xs0, ys0, xs1, ys1 = max(0, -x0), max(0, -y0), min(2 * r, OUT_W - x0), min(2 * r, OUT_H - y0)
    if xs1 <= xs0 or ys1 <= ys0:
        return
    sl = (slice(y0 + ys0, y0 + ys1), slice(x0 + xs0, x0 + xs1))
    sub = (slice(ys0, ys1), slice(xs0, xs1))
    reg = s[sl]
    reg[:] = mix(reg, col[sub] if day < 0.5 else screen(reg, col[sub] * 0.9), a[sub])
    if day < 1:
        Y, X = np.ogrid[:OUT_H, :OUT_W]
        dd = np.sqrt((X - mx) ** 2 + (Y - my) ** 2).astype(np.float32)
        halo = np.exp(-(dd / (r * 2.6)) ** 2) * 0.22 * st["moon_illum"] * (1 - day) * max(0.0, 1 - 1.4 * cover) * float(smooth(ma, -2, 3))
        s[:] = screen(s, halo[..., None] * C(0.8, 0.85, 1.0))


# ------------------------------------------------------------------------------------ foreground light
def day_night(F, day, night, keys=LIGHT_KEYS):
    """Blend the day and night plates by sun altitude and apply the light's tint/exposure."""
    sa = F.sun_alt
    wday = float(lerp_keys([(k[0], np.array([k[1]], np.float32)) for k in keys], sa)[0])
    tint = lerp_keys([(k[0], k[2]) for k in keys], sa)
    expo = float(lerp_keys([(k[0], np.array([k[3]], np.float32)) for k in keys], sa)[0])
    return (day * wday + night * (1 - wday)) * tint[None, None] * expo, wday


def overcast(img, F, cover, strength=0.7):
    g = lum(img)[..., None]
    flat = (g + (img - g) * 0.6 - 0.5) * 0.85 + 0.5 - 0.06
    return mix(img, flat, strength * cover * float(smooth(F.sun_alt, -6, 6)))


def low_sun(img, F, sun_xy, cover, strength=0.35):
    sa = F.sun_alt
    if not (-4 < sa < 14) or cover >= 0.8:
        return img
    X = np.arange(OUT_W, dtype=np.float32)[None, :]
    side = np.clip(1 - np.abs(X - sun_xy[0]) / (1.1 * OUT_W), 0, 1) ** 2 * np.ones((OUT_H, 1), np.float32)
    k = (1 - float(smooth(sa, 6, 14))) * float(smooth(sa, -4, 1)) * (1 - cover) * strength
    return screen(img, (side * k)[..., None] * sun_color(sa))


def haze(img, F, depth, sky_img, cover, amount=0.18, horizon=None):
    """Distance haze toward the sky colour near the horizon; depth 0 near .. 1 far."""
    hr = int((horizon if horizon is not None else 0.5) * OUT_H)
    band = sky_img[max(0, hr - 60):min(OUT_H, hr + 1)]
    col = np.median(band.reshape(-1, 3), axis=0) if band.size else C(0.5, 0.55, 0.6)
    far = np.clip((depth - 0.55) / 0.45, 0, 1) ** 1.5
    return mix(img, col[None, None], far * (amount + 0.25 * cover))


def lights_on(F, threshold):
    """0..1 how much lamps are on: fully on below `threshold`-1 deg, off above threshold+6."""
    return 1 - float(smooth(F.sun_alt, threshold - 1, threshold + 6))


def light_glow(img, night, light_mask, on, glow=1.0):
    """Lamps/windows: take their lit colour from the night plate and add a soft bloom."""
    if on <= 0 or light_mask.max() <= 0:
        return img
    lamps = night * light_mask[..., None]
    img = mix(img, np.maximum(img, lamps * 1.05), light_mask * on)
    lit = lamps * C(1.15, 0.85, 0.55)
    q = cv2.resize(lit, (OUT_W // 4, OUT_H // 4), interpolation=cv2.INTER_AREA)
    g = cv2.GaussianBlur(q, (0, 0), 11) * 0.8 + cv2.GaussianBlur(q, (0, 0), 3) * 0.4
    return screen(img, np.clip(up(g, cv2.INTER_CUBIC) * on * glow, 0, 1))


def water(img, F, water_mask, sky_img, sun_xy, cover, plate=None, strength=0.9, light_mask=None, night=None, on=0.0):
    """Water reflects the sky mirrored about each column's shoreline, keeps the plate's ripples, plus sun/moon
    glitter and broken reflections of lit lamps."""
    if water_mask.max() < 0.3:
        return img
    wm = water_mask > 0.3
    cols = np.where(wm.any(0), wm.argmax(0), OUT_H).astype(np.float32)
    top = np.nanmedian(np.where(cols < OUT_H, cols, np.nan))
    cols = np.where(cols < OUT_H, cols, top)
    cols = cv2.GaussianBlur(cols[None, :], (0, 0), 25)[0]
    rows = np.arange(OUT_H, dtype=np.float32)[:, None]
    src = np.clip(cols[None, :] - (rows - cols[None, :]) * 2.2 - 8, 0, OUT_H - 1)
    gx = np.broadcast_to(np.arange(OUT_W, dtype=np.float32)[None, :], (OUT_H, OUT_W))
    refl = cv2.remap(sky_img, gx.astype(np.float32), np.broadcast_to(src, (OUT_H, OUT_W)).astype(np.float32), cv2.INTER_LINEAR)
    refl = cv2.GaussianBlur(refl, (0, 0), sigmaX=6, sigmaY=1.5) * C(0.70, 0.78, 0.84)
    base = plate if plate is not None else img
    rip = lum(base) - cv2.GaussianBlur(lum(base), (0, 0), 4)
    w = np.clip(img * 0.45 + refl * 0.62 + rip[..., None] * 0.5, 0, 1)
    sa = F.sun_alt
    if sa > -1 and 0 < sun_xy[0] < OUT_W:
        w = screen(w, _glitter(sun_xy[0], 40, 0.9 * (1 - cover) * float(smooth(sa, -1, 3)), top)[..., None] * sun_color(sa))
    st = F.st
    if st["moon_alt"] > 3 and sa < -3 and cover < 0.7:
        mx, _ = sky_xy(F.scene.cam, st["moon_alt"], st["moon_az"])
        k = (0.25 + 0.75 * st["moon_illum"]) * (1 - cover / 0.7) * float(smooth(st["moon_alt"], 3, 8)) * 0.8
        w = screen(w, _glitter(mx, 26, k, top)[..., None] * C(0.85, 0.9, 1.0))
    if on > 0 and light_mask is not None and night is not None and light_mask.max() > 0:
        lit = night * light_mask[..., None]
        src2 = np.clip(cols[None, :] - (rows - cols[None, :]) / 2.2 + 4, 0, OUT_H - 1)
        lr = cv2.remap(lit, gx.astype(np.float32), np.broadcast_to(src2, (OUT_H, OUT_W)).astype(np.float32), cv2.INTER_LINEAR)
        lr = cv2.GaussianBlur(lr, (0, 0), sigmaX=2, sigmaY=14) * _dashes() [..., None] * 1.4
        w = screen(w, np.clip(lr * on, 0, 1))
    return mix(img, w, feather(water_mask, 1.5) * strength)


def _dashes():
    if "dash" not in _CACHE:
        rng = np.random.default_rng(5)
        n = cv2.GaussianBlur(rng.standard_normal((OUT_H, OUT_W)).astype(np.float32), (0, 0), sigmaX=7, sigmaY=1.1)
        _CACHE["dash"] = n / n.std()
    return np.clip(_CACHE["dash"] * 0.6 + 0.4, 0, 1)


def _glitter(cx, half_w, strength, top):
    n = _dashes() * 2.5 - 1
    X = np.arange(OUT_W, dtype=np.float32)[None, :]
    Y = np.arange(OUT_H, dtype=np.float32)[:, None]
    near = np.clip((Y - top) / (0.1 * OUT_H), 0, 1)
    width = half_w * OUT_W / 1672 * (0.45 + 0.8 * near)
    col = np.exp(-((X - cx) / width) ** 2)
    return col * np.clip((n - 0.9 + 0.6 * near) * 0.9, 0, 1) * strength * (1 - 0.35 * near)


def compose_sky(img, sky_img, sky_mask):
    return mix(img, sky_img, sky_mask)


def sun_bloom(out, F, sun_xy, cover, strength=0.35):
    sa = F.sun_alt
    if sa <= -2 or cover >= 0.9:
        return out
    X = np.arange(OUT_W, dtype=np.float32)[None, :]
    Y = np.arange(OUT_H, dtype=np.float32)[:, None]
    d = np.sqrt((X - sun_xy[0]) ** 2 + (Y - sun_xy[1]) ** 2)
    b = np.exp(-(d / (0.054 * OUT_W)) ** 2) * strength * (1 - cover) * float(smooth(sa, -2, 1))
    return screen(out, b[..., None] * sun_color(sa))


# ---------------------------------------------------------------------------------------------- weather
def _rng(F, salt):
    w = F.when
    return np.random.default_rng((w.year * 400 + w.timetuple().tm_yday) * 100 + w.hour * 3 + salt)


def streaks(F, n, length, angle_deg, thick, seed_salt):
    rng = _rng(F, seed_salt)
    h, w = OUT_H // 2, OUT_W // 2
    canvas = np.zeros((h, w), np.float32)
    a = math.radians(angle_deg)
    dx, dy = math.sin(a) * length / 2, math.cos(a) * length / 2
    for x, y, b in zip(rng.uniform(0, w, n), rng.uniform(0, h, n), rng.uniform(0.3, 1.0, n)):
        cv2.line(canvas, (int(x - dx), int(y - dy)), (int(x + dx), int(y + dy)), float(b), thick, cv2.LINE_AA)
    return up(cv2.GaussianBlur(canvas, (0, 0), 0.6))


def rain(img, F, L, intensity=1.0, storm=False):
    """L: dict of layers (ground, roof, water, depth, sky). Darker/wetter ground, rain streaks, distance mist."""
    I = float(np.clip(intensity, 0.1, 1.0))
    out = img * (1 - 0.12 * I) if not storm else img * (1 - 0.22 * I)
    g = lum(out)[..., None]
    out = mix(out, g + (out - g) * 0.75, 0.6)
    wet = np.clip(L["ground"] + L["roof"] * 0.7, 0, 1)
    if wet.max() > 0:   # wet surfaces: darker, glossier, reflect the bright sky a little
        sheen = cv2.GaussianBlur(out, (0, 0), 3) * 0.25
        out = mix(out, out * 0.82 + sheen, wet * 0.8 * I)
    mist_col = np.median(out[L["sky"] > 0.8].reshape(-1, 3), axis=0) if (L["sky"] > 0.8).any() else C(0.55, 0.58, 0.62)
    out = mix(out, mist_col[None, None], np.clip(L["depth"] - 0.4, 0, 1) * (0.35 + 0.3 * I))
    n = int(900 + 2600 * I)
    s1 = streaks(F, n, 34 + 30 * I, 12 if storm else 6, 1, 1)
    s2 = streaks(F, n // 3, 70 + 40 * I, 14 if storm else 8, 2, 2)
    col = np.clip(mist_col * 1.4 + 0.15, 0, 1)
    out = screen(out, (s1 * 0.16 + s2 * 0.22)[..., None] * I * col)
    if L["water"].max() > 0:
        rings = cv2.GaussianBlur(_rng(F, 9).random((OUT_H // 4, OUT_W // 4)).astype(np.float32), (0, 0), 0.8)
        rings = up(np.clip((rings - 0.75) * 4, 0, 1)) * L["water"] * 0.18 * I
        out = screen(out, rings[..., None] * col)
    if storm:
        rng = _rng(F, 17 + F.when.minute)
        if rng.random() < 0.35:   # a lightning flash lights the scene from above
            flash = np.clip(1 - np.arange(OUT_H, dtype=np.float32)[:, None] / OUT_H, 0, 1) * 0.25
            out = screen(out, flash[..., None] * C(0.75, 0.8, 1.0))
    return np.clip(out, 0, 1)


def fog(img, F, L, intensity=1.0, light_mask=None, on=0.0, night=None):
    I = float(np.clip(intensity, 0.1, 1.0))
    base_col = np.median(img[L["sky"] > 0.8].reshape(-1, 3), axis=0) if (L["sky"] > 0.8).any() else np.median(img.reshape(-1, 3), axis=0)
    fc = np.clip(lum(base_col[None, None])[0, 0] * C(0.95, 0.97, 1.0) * 1.1 + 0.04, 0, 0.88)
    d = L["depth"]
    dens = 1 - np.exp(-(0.05 + 2.2 * np.clip(d - 0.15, 0, 1) ** 1.8) * I)    # near stays clear, distance veils
    dens = np.maximum(dens, L["sky"] * 0.75 * I)
    out = mix(img, fc[None, None], np.clip(dens, 0, 0.85))
    if on > 0 and light_mask is not None and night is not None and light_mask.max() > 0:
        q = cv2.resize(night * light_mask[..., None], (OUT_W // 8, OUT_H // 8), interpolation=cv2.INTER_AREA)
        halo = up(cv2.GaussianBlur(q, (0, 0), 6), cv2.INTER_CUBIC) * 1.6 * I * on
        out = screen(out, np.clip(halo, 0, 1))
    return np.clip(out, 0, 1)


def snowfall(img, F, L, intensity=1.0, settle=True):
    I = float(np.clip(intensity, 0.1, 1.0))
    out = img
    if settle:   # light dusting on upward-facing surfaces (the full snow look comes from the snow template)
        up_faces = np.clip(L["ground"] + L["roof"] + L["vegetation"] * 0.5 + L["terrain"] * 0.6, 0, 1)
        n = up(_fbm(23, 512) ** 2)
        out = mix(out, np.maximum(out, C(0.90, 0.92, 0.96) * (0.55 + 0.45 * float(smooth(F.sun_alt, -8, 6)))),
                  up_faces * n * 0.35 * I)
    g = lum(out)[..., None]
    out = mix(out, g + (out - g) * 0.8, 0.5)
    amb = float(np.clip(np.median(lum(out)) * 1.6 + 0.25, 0.35, 1.0))
    for n, sz, salt, a in ((int(1800 * I), 2, 3, 0.7), (int(500 * I), 4, 4, 0.9), (int(90 * I), 8, 5, 0.75)):
        rng = _rng(F, salt)
        canvas = np.zeros((OUT_H, OUT_W), np.float32)
        for x, y in zip(rng.uniform(0, OUT_W, n), rng.uniform(0, OUT_H, n)):
            cv2.circle(canvas, (int(x), int(y)), sz, 1.0, -1, cv2.LINE_AA)
        canvas = cv2.GaussianBlur(canvas, (0, 0), sz * 0.6)
        out = screen(out, (canvas * a * amb)[..., None] * C(0.95, 0.96, 1.0))
    return np.clip(out, 0, 1)


# ---------------------------------------------------------------------------------- reference renderer
DEFAULTS = dict(
    lights_on_below_sun_alt=5.0,   # lamps switch on below this sun altitude
    glow=1.0,                      # lamp bloom strength
    haze=0.18,                     # distance haze
    overcast_flatten=0.7,          # how much clouds flatten the scene light
    low_sun_rake=0.35,             # warm side light near sunrise/sunset
    reflection=0.9,                # water reflection strength
    sun_bloom=0.35,
    moon_size=1.0,
    use_sky=True,                  # False for scenes without visible sky: the sky still drives the light
)


def layers_for(scene):
    L = {k: scene.layer(k) for k in ("sky", "water", "ground", "roof", "vegetation", "terrain", "structure", "lights")}
    L["depth"] = scene.layer("depth") if "depth" in scene.layers else np.full((OUT_H, OUT_W), 0.5, np.float32)
    return L


def default_render(F, P=None):
    P = dict(DEFAULTS, **(P or {}))
    S = F.scene
    cam, cover, L = S.cam, F.cover, layers_for(S)
    day, night = S.plate(F.phase + "_day"), S.plate(F.phase + "_night")
    sky_img, sun_xy = sky(F, cam, cover, moon_size=P["moon_size"])
    img, wday = day_night(F, day, night)
    img = overcast(img, F, cover, P["overcast_flatten"])
    img = low_sun(img, F, sun_xy, cover, P["low_sun_rake"])
    img = haze(img, F, L["depth"], sky_img, cover, P["haze"], cam["horizon"])
    on = lights_on(F, P["lights_on_below_sun_alt"])
    img = water(img, F, L["water"], sky_img, sun_xy, cover, plate=day * wday + night * (1 - wday),
                strength=P["reflection"], light_mask=L["lights"], night=night, on=on)
    img = light_glow(img, night, L["lights"], on, P["glow"])
    out = compose_sky(img, sky_img, S.sky_mask(F, wday)) if P["use_sky"] else img
    out = sun_bloom(out, F, sun_xy, cover, P["sun_bloom"]) if P["use_sky"] else out
    out = np.clip(out, 0, 1)
    if F.weather in ("rain", "storm"):
        out = rain(out, F, L, F.intensity, storm=F.weather == "storm")
    elif F.weather == "fog":
        out = fog(out, F, L, F.intensity, L["lights"], on, night)
    elif F.weather == "snow":
        out = snowfall(out, F, L, F.intensity)
    return np.clip(out, 0, 1)


def to8(img):
    return (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)


def parse_when(s, tz):
    return dt.datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=tz)
