"""Weather effect registry. Each module exposes apply(img, ctx) -> img.

img: float32 BGR in [0,1], shape (1441, 2560, 3) — the fully lit, composited frame.
ctx keys:
  A          timeofday.Assets: A.sky, A.water, A.warm, A.depth (0 near..1 sky), A.day, A.night,
             A.far (distance-haze band); all float32 (1441, 2560) masks in [0,1]
  st         astro state: sun_alt, sun_az, moon_alt, moon_az, moon_illum, moon_phase_angle
  sky        float32 BGR sky layer used for this frame
  when       aware datetime (America/Chicago)
  season     'spring' | 'summer' | 'autumn' | 'winter'
  cover      cloud cover 0..1 (>= 0.92 for weather effects)
  lights_on  0..1 lanterns/windows lit
  intensity  0..1 strength of the weather (light rain .. downpour)
  sun_xy     sun position in output pixels (may be off-frame)
"""
import importlib
import cv2
import numpy as np

MODULES = {"rain": ("rain", "apply"), "storm": ("rain", "apply_storm"),
           "fog": ("fog", "apply"), "snow": ("snow", "apply")}


GRID = (2560, 1441)          # resolution the fog/snow effects were written for
NATIVE_4K = {"rain"}         # modules that handle any output size themselves


class _Scaled:
    """Proxy for timeofday.Assets: every full-frame array is resized to the effect grid on first use."""
    def __init__(self, A, shape):
        self._A, self._shape, self._cache = A, shape, {}

    def __getattr__(self, name):
        if name in self._cache:
            return self._cache[name]
        v = getattr(self._A, name)
        if isinstance(v, np.ndarray) and v.ndim >= 2 and v.shape[:2] == self._shape:
            v = cv2.resize(v, GRID, interpolation=cv2.INTER_AREA)
        self._cache[name] = v
        return v


def apply(weather, img, ctx):
    mod, fn = MODULES[weather]
    try:
        m = importlib.import_module("effects." + mod)
    except ModuleNotFoundError:
        return img  # effect not built yet
    h, w = img.shape[:2]
    if mod in NATIVE_4K or (w, h) == GRID:
        return getattr(m, fn)(img, ctx)
    # run on the effect grid, then add only the change back onto the full-resolution frame
    small = cv2.resize(img, GRID, interpolation=cv2.INTER_AREA)
    c2 = dict(ctx)
    c2["A"] = _Scaled(ctx["A"], (h, w))
    if isinstance(ctx.get("sky"), np.ndarray):
        c2["sky"] = cv2.resize(ctx["sky"], GRID, interpolation=cv2.INTER_AREA)
    if ctx.get("sun_xy"):
        c2["sun_xy"] = (ctx["sun_xy"][0] * GRID[0] / w, ctx["sun_xy"][1] * GRID[1] / h)
    out = getattr(m, fn)(small, c2)
    delta = cv2.resize(out - small, (w, h), interpolation=cv2.INTER_CUBIC)
    return np.clip(img + delta, 0, 1)
