"""Put a generated image back onto the base image's exact geometry, and lock static structure to the base.

Image-edit models restyle well but nudge the framing (tens of pixels) and sometimes invent things. Two steps:
1. align()  - smooth non-rigid warp measured by windowed phase correlation of edge maps, coarse to fine
              (the method render/align_autumn.py used for the hand-painted autumn template, made generic:
              the hand-drawn gates are replaced by the perception masks).
2. lock()   - in static regions (buildings, railings, people…) the colours/lighting come from the generated
              image but the structure comes from the base (guided filter with the base as guide); in regions
              that are supposed to change (foliage, ground, water, sky) the aligned generation is used as is.
"""
import cv2
import numpy as np


def edge_map(im):
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32)
    g = cv2.GaussianBlur(g, (0, 0), 1.5)
    m = np.sqrt(np.hypot(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1)))
    return m / (np.percentile(m, 99) + 1e-6)


def _measure(es, ea, B, step):
    H, W = es.shape
    win = cv2.createHanningWindow((B, B), cv2.CV_32F)
    out = []
    for y in range(0, H - B + 1, step):
        for x in range(0, W - B + 1, step):
            a, b = es[y:y + B, x:x + B].copy(), ea[y:y + B, x:x + B].copy()
            if a.std() < 0.03 or b.std() < 0.03:
                continue
            (dx, dy), r = cv2.phaseCorrelate(a, b, win)
            out.append((x + B / 2, y + B / 2, dx, dy, r))
    return np.array(out, np.float32).reshape(-1, 5)


def _fit(samples, shape, sigma, rlim, maxd):
    H, W = shape
    s = 8
    h, w = H // s, W // s
    ws = np.zeros((h, w), np.float32); xs = np.zeros((h, w), np.float32); ys = np.zeros((h, w), np.float32)
    for cx, cy, dx, dy, r in samples:
        if r < rlim or abs(dx) > maxd or abs(dy) > maxd:
            continue
        i, j = min(int(cy / s), h - 1), min(int(cx / s), w - 1)
        ws[i, j] += r * r; xs[i, j] += r * r * dx; ys[i, j] += r * r * dy
    if ws.sum() == 0:
        return np.zeros(shape, np.float32), np.zeros(shape, np.float32)
    k, k2 = sigma / s, sigma * 3 / s
    gw, gx, gy = [cv2.GaussianBlur(a, (0, 0), k) for a in (ws, xs, ys)]
    gw2, gx2, gy2 = [cv2.GaussianBlur(a, (0, 0), k2) for a in (ws, xs, ys)]
    a = np.clip(gw / (gw.max() * 0.08 + 1e-9), 0, 1)
    gw2 = np.maximum(gw2, 1e-9)
    dx_ = a * gx / (gw + 1e-9) + (1 - a) * gx2 / gw2
    dy_ = a * gy / (gw + 1e-9) + (1 - a) * gy2 / gw2
    up = lambda f: cv2.GaussianBlur(cv2.resize(f, (W, H), interpolation=cv2.INTER_CUBIC), (0, 0), s / 2)
    return up(dx_), up(dy_)


def warp(im, fx, fy, interp=cv2.INTER_CUBIC):
    H, W = im.shape[:2]
    gx, gy = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    return cv2.remap(im, gx + fx, gy + fy, interp, borderMode=cv2.BORDER_REFLECT)


def align(base, gen, gate=None):
    """Returns (aligned gen, dict of quality numbers). gen is resized to base first. gate (HxW 0..1) limits the
    fine passes to areas with real structure (non-sky), so open sky and foliage are not squashed."""
    H, W = base.shape[:2]
    gen = cv2.resize(gen, (W, H), interpolation=cv2.INTER_AREA if gen.shape[1] > W else cv2.INTER_CUBIC)
    es, eg = edge_map(base), edge_map(gen)
    fx = np.zeros((H, W), np.float32); fy = np.zeros((H, W), np.float32)
    gate = np.ones((H, W), np.float32) if gate is None else cv2.GaussianBlur(gate.astype(np.float32), (0, 0), 14)
    maxd = 0.06 * max(H, W)
    sc = max(H, W) / 1672.0
    for B, step, sigma, rlim in [(256, 96, 140, 0.1), (192, 64, 90, 0.15), (128, 48, 60, 0.15),
                                 (96, 32, 42, 0.15), (64, 24, 22, 0.2)]:
        B, step, sigma = int(B * sc), int(step * sc), sigma * sc
        cur = edge_map(warp(gen, fx, fy))
        ddx, ddy = _fit(_measure(es, cur, B, step), (H, W), sigma, rlim, maxd)
        if B <= 96 * sc:
            ddx, ddy = ddx * gate, ddy * gate
        gx, gy = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
        fx = fx + cv2.remap(ddx, gx + fx, gy + fy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        fy = fy + cv2.remap(ddy, gx + fx, gy + fy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    out = warp(gen, fx, fy)
    return out, dict(edge_recall_before=edge_recall(base, gen), edge_recall_after=edge_recall(base, out),
                     max_shift_px=float(np.hypot(fx, fy).max()))


def edge_recall(base, img, mask=None, tol=3):
    ga = cv2.Canny(cv2.cvtColor(base, cv2.COLOR_BGR2GRAY), 50, 150) > 0
    gb = cv2.Canny(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 50, 150) > 0
    gb = cv2.dilate(gb.astype(np.uint8), np.ones((2 * tol + 1, 2 * tol + 1), np.uint8)) > 0
    if mask is not None:
        ga &= mask > 0.5
    n = ga.sum()
    return float((ga & gb).sum() / n) if n else 1.0


def guided(guide, src, r, eps):
    """He et al. guided filter; guide single-channel float, src multi-channel float."""
    box = lambda a: cv2.boxFilter(a, -1, (2 * r + 1, 2 * r + 1))
    mi = box(guide)
    var = box(guide * guide) - mi * mi
    out = np.empty_like(src)
    for c in range(src.shape[2]):
        p = src[..., c]
        mp = box(p)
        a = (box(guide * p) - mi * mp) / (var + eps)
        b = mp - a * mi
        out[..., c] = box(a) * guide + box(b)
    return out


def agreement(base, img, sigma=5):
    """Per-pixel structural agreement 0..1: local normalised correlation of edge maps, measured only where the base
    has structure (flat base areas count as agreeing)."""
    eb, ei = edge_map(base), edge_map(img)
    g = lambda a: cv2.GaussianBlur(a, (0, 0), sigma)
    mb, mi = g(eb), g(ei)
    cov = g(eb * ei) - mb * mi
    vb, vi = np.maximum(g(eb * eb) - mb * mb, 0), np.maximum(g(ei * ei) - mi * mi, 0)
    ncc = cov / np.sqrt(vb * vi + 1e-6)
    energy = np.clip(np.sqrt(vb) / 0.08, 0, 1)                  # how much structure the base has here
    return np.clip(1 - energy * (1 - np.clip(ncc * 1.6, 0, 1)), 0, 1)


def color_transfer(src, ref, mask):
    """Lab mean/std matching of src toward ref, statistics taken over mask."""
    s = cv2.cvtColor(src, cv2.COLOR_BGR2LAB).astype(np.float32)
    r = cv2.cvtColor(ref, cv2.COLOR_BGR2LAB).astype(np.float32)
    m = mask > 0.5
    if m.sum() < 500:
        m = np.ones(mask.shape, bool)
    out = np.empty_like(s)
    for c in range(3):
        ms, ss = s[..., c][m].mean(), s[..., c][m].std() + 1e-3
        mr, sr = r[..., c][m].mean(), r[..., c][m].std() + 1e-3
        out[..., c] = (s[..., c] - ms) * min(2.0, sr / ss) + mr
    return cv2.cvtColor(np.clip(out, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)


def lit_mask(img):
    """Bright, warm, saturated pixels: lamps, lanterns and lit windows."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
    warm = ((hsv[..., 0] < 35) | (hsv[..., 0] > 165)) & (hsv[..., 1] > 70) & (hsv[..., 2] > 150)
    return cv2.GaussianBlur(warm.astype(np.float32), (0, 0), 1.5)


def lock(base, aligned, static, change, thr=0.45, lights_off=False):
    """Keep the generated image wherever it preserved the base's static structure; where a static object was dropped
    or redrawn (low agreement), bring the base object back, relit to the generated image's light. With lights_off
    (day plates) any glowing lamp brought back from a night base is switched off."""
    agr = agreement(base, aligned)
    st = np.clip(static - change, 0, 1).astype(np.float32)
    good = (agr > 0.7) & (st > 0.5)
    relit = color_transfer(base, aligned, good.astype(np.float32)).astype(np.float32)
    if lights_off:
        lm = lit_mask(base)[..., None]
        ref = aligned.astype(np.float32)[good]
        paper = (np.median(ref, axis=0) if len(ref) else np.array([170, 180, 190], np.float32)) * 0.6 + \
            np.array([150, 170, 185], np.float32) * 0.4            # unlit paper/glass: pale, neutral, lit by day
        g = relit.mean(2, keepdims=True)
        unlit = paper[None, None] * (0.75 + 0.25 * g / (g.mean() + 1e-3))
        relit = relit * (1 - lm) + np.clip(unlit, 0, 255) * lm
    lost = np.clip((thr - agr) / thr, 0, 1) * st
    lost = cv2.morphologyEx(lost, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    w = np.clip(cv2.GaussianBlur(np.clip(lost * 1.5, 0, 1), (0, 0), 2.5) * 1.3, 0, 1)
    w = (w * cv2.GaussianBlur((st > 0.5).astype(np.float32), (0, 0), 0.8))[..., None]   # never past the silhouette
    out = relit * w + aligned.astype(np.float32) * (1 - w)
    return (np.clip(out, 0, 255) + 0.5).astype(np.uint8)
