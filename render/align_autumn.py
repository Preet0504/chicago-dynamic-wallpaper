"""Align templates/autumn_clear_golden.png to the shared (spring) geometry with a smooth non-rigid warp.

  .venv/bin/python render/align_autumn.py            # build (keeps raw copy), write aligned + sky mask
  .venv/bin/python render/align_autumn.py --report   # only print per-region offsets raw vs aligned

The painting is the raw file templates/originals/autumn_clear_golden_raw.png.  A dense displacement field is
measured by windowed phase correlation on blurred edge maps against spring_clear_night.png (iterated, coarse-to-fine),
robustly fitted (confidence-weighted Gaussian smoothing, so it is smooth and never folds), and applied with
cv2.remap.  Border strip revealed at the top is filled by reflecting the sky-only rows.
"""
import os, sys, shutil
import cv2, numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = os.path.join(ROOT, "templates")
SPRING = os.path.join(T, "spring_clear_night.png")
RAW = os.path.join(T, "originals", "autumn_clear_golden_raw.png")
OUT = os.path.join(T, "autumn_clear_golden.png")
SKY = os.path.join(T, "autumn_clear_golden_sky.png")
H, W = 941, 1672

# evaluation regions (x, y, w, h) in base px
REGIONS = {"pagoda": (40, 260, 220, 500), "mountain": (330, 470, 560, 170), "far shore/town": (260, 640, 700, 120),
           "pavilion": (1480, 330, 192, 470), "hanging lantern": (1260, 460, 100, 130),
           "stone lanterns L": (850, 770, 150, 150), "stone lantern R": (1220, 735, 100, 120),
           "railing": (700, 800, 560, 140), "left town roofs": (0, 740, 330, 200)}


def edge_map(im):
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32)
    g = cv2.GaussianBlur(g, (0, 0), 1.5)
    m = np.hypot(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))
    m = np.sqrt(m)  # compress so faint structure counts as much as the glowing windows
    return m / (np.percentile(m, 99) + 1e-6)


def measure(es, ea, B, step, ncc=False):
    """Windowed phase correlation spring->autumn; returns sample list (cx, cy, dx, dy, conf)."""
    win = cv2.createHanningWindow((B, B), cv2.CV_32F)
    out = []
    for y in range(0, H - B + 1, step):
        for x in range(0, W - B + 1, step):
            a, b = es[y:y + B, x:x + B].copy(), ea[y:y + B, x:x + B].copy()
            if a.std() < 0.03 or b.std() < 0.03:
                continue
            (dx, dy), r = cv2.phaseCorrelate(a, b, win)
            if ncc:  # confidence = normalised correlation of the structure after applying the estimated shift
                M = np.float32([[1, 0, -dx], [0, 1, -dy]])
                bs = cv2.warpAffine(b, M, (B, B), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
                c = (a - a.mean()) * (bs - bs.mean())
                r = float(c.mean() / (a.std() * bs.std() + 1e-6))
            out.append((x + B / 2, y + B / 2, dx, dy, r))
    return np.array(out, np.float32).reshape(-1, 5)


def fit_field(samples, sigma, rlim, maxd):
    """Confidence-weighted Gaussian interpolation of sparse (dx,dy) samples into a dense smooth field."""
    wsum = np.zeros((H, W), np.float32); fx = np.zeros((H, W), np.float32); fy = np.zeros((H, W), np.float32)
    # accumulate on a 1/8 grid for speed
    s = 8; h, w = H // s, W // s
    ws = np.zeros((h, w), np.float32); xs = np.zeros((h, w), np.float32); ys = np.zeros((h, w), np.float32)
    for cx, cy, dx, dy, r in samples:
        if r < rlim or abs(dx) > maxd or abs(dy) > maxd:
            continue
        i, j = min(int(cy / s), h - 1), min(int(cx / s), w - 1)
        wgt = r * r
        ws[i, j] += wgt; xs[i, j] += wgt * dx; ys[i, j] += wgt * dy
    k = sigma / s
    gw = cv2.GaussianBlur(ws, (0, 0), k); gx = cv2.GaussianBlur(xs, (0, 0), k); gy = cv2.GaussianBlur(ys, (0, 0), k)
    # wide fallback where there is no measurement nearby (sky / featureless): blend toward the broad average
    k2 = sigma * 3 / s
    gw2 = cv2.GaussianBlur(ws, (0, 0), k2); gx2 = cv2.GaussianBlur(xs, (0, 0), k2); gy2 = cv2.GaussianBlur(ys, (0, 0), k2)
    a = np.clip(gw / (gw.max() * 0.08 + 1e-9), 0, 1)
    dx_ = a * gx / (gw + 1e-9) + (1 - a) * gx2 / (gw2 + 1e-9)
    dy_ = a * gy / (gw + 1e-9) + (1 - a) * gy2 / (gw2 + 1e-9)
    up = lambda f: cv2.GaussianBlur(cv2.resize(f, (W, H), interpolation=cv2.INTER_CUBIC), (0, 0), s / 2)
    return up(dx_), up(dy_)


def warp(im, fx, fy, interp=cv2.INTER_CUBIC, border=cv2.BORDER_REFLECT):
    """Output(p) = im(p + f(p)); f = measured autumn-minus-spring offset, so content moves by -f."""
    gx, gy = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    return cv2.remap(im, gx + fx, gy + fy, interp, borderMode=border)


def structure_gate():
    """1 where the painting has real structure to register (town, shore, pagoda, pavilion), 0 in open sky and across the
    maple branch, where only the coarse pass applies so leaves are never squashed."""
    g = np.zeros((H, W), np.uint8)
    hor = [(0, 560), (240, 640), (330, 600), (420, 545), (470, 515), (520, 512), (600, 545), (700, 590), (800, 615), (900, 625),
           (1000, 632), (1100, 630), (1200, 625), (1300, 600), (1400, 570), (1500, 560), (1672, 560)]  # = masks.HORIZON
    xs = np.arange(W); hy = np.interp(xs, [p[0] for p in hor], [p[1] for p in hor]) - 60
    g[np.arange(H)[:, None] >= hy[None, :]] = 1
    g[330:, 1245:] = 1  # pavilion, hanging lantern, hill
    cv2.fillPoly(g, [np.array([(60, 280), (260, 280), (260, 340), (60, 340)], np.int32)], 1)           # pagoda spire / upper tiers
    cv2.fillPoly(g, [np.array([(1250, 330), (1400, 318), (1530, 262), (1560, 200), (1672, 160), (1672, 340), (1250, 340)], np.int32)], 1)  # pavilion roof
    return cv2.GaussianBlur(g.astype(np.float32), (0, 0), 14)


def solve(es, raw):
    gate = structure_gate()
    fx = np.zeros((H, W), np.float32); fy = np.zeros((H, W), np.float32)
    # coarse -> fine: big windows give the global layering, small ones the local structure
    for B, step, sigma, rlim in [(192, 64, 90, 0.15), (128, 48, 60, 0.15), (96, 32, 42, 0.15), (96, 32, 36, 0.15), (64, 24, 22, 0.2), (64, 24, 18, 0.25)]:
        cur = edge_map(warp(raw, fx, fy))
        samp = measure(es, cur, B, step, ncc=False)
        ddx, ddy = fit_field(samp, sigma, rlim, 30)
        if B <= 96:
            ddx, ddy = ddx * gate, ddy * gate
        # compose: residual measured on warped image is defined in warped coordinates
        gx, gy = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
        fx = fx + cv2.remap(ddx, gx + fx, gy + fy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        fy = fy + cv2.remap(ddy, gx + fx, gy + fy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        print("pass B=%d: %d samples, field dy range %.1f..%.1f" % (B, len(samp), fy.min(), fy.max()))
    return fx, fy


def region_offsets(es, im):
    ea = edge_map(im); res = {}
    for k, (x, y, w, h) in REGIONS.items():
        win = cv2.createHanningWindow((w, h), cv2.CV_32F)
        (dx, dy), r = cv2.phaseCorrelate(es[y:y + h, x:x + w].copy(), ea[y:y + h, x:x + w].copy(), win)
        res[k] = (dx, dy, r)
    return res


def report(spring, raw, new=None):
    es = edge_map(spring); r0 = region_offsets(es, raw); r1 = region_offsets(es, new) if new is not None else None
    for k in REGIONS:
        line = "%-18s raw (%+5.1f,%+5.1f) r=%.2f" % (k, *r0[k])
        if r1: line += "   aligned (%+5.1f,%+5.1f) r=%.2f" % tuple(r1[k])
        print(line)


def sky_mask(img):
    """Exact sky of the aligned painting.  Sky = smooth area above the horizon whose colour matches a smooth sky model
    fitted from the open (edge-free) sky; leaves, roofs, spire and glow-lit structure are rejected by edges / colour."""
    f = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    g = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32), (0, 0), 0.8)
    grad = np.hypot(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))
    smooth = (grad < 7).astype(np.uint8)
    xs = np.arange(W)
    hor = np.interp(xs, [0, 240, 330, 420, 470, 520, 600, 700, 800, 900, 1000, 1100, 1200, 1300, 1400, 1500, 1672],
                    [560, 640, 600, 545, 515, 512, 545, 590, 615, 625, 632, 630, 625, 600, 570, 560, 560])
    above = (np.arange(H)[:, None] < (hor[None, :] - 2)).astype(np.uint8)
    # open sky: smooth everywhere in a 21 px neighbourhood
    dense = cv2.dilate((grad >= 7).astype(np.uint8), np.ones((21, 21), np.uint8))
    seeds = smooth & above & (dense == 0)
    wt = cv2.GaussianBlur(seeds.astype(np.float32), (0, 0), 30)
    model = np.stack([cv2.GaussianBlur(f[..., c] * seeds, (0, 0), 30) for c in range(3)], -1) / (wt[..., None] + 1e-6)
    wt2 = cv2.GaussianBlur(seeds.astype(np.float32), (0, 0), 160)
    model2 = np.stack([cv2.GaussianBlur(f[..., c] * seeds, (0, 0), 160) for c in range(3)], -1) / (wt2[..., None] + 1e-6)
    a = np.clip(wt / 0.05, 0, 1)[..., None]
    model = a * model + (1 - a) * model2
    dist = np.sqrt(((f - model) ** 2 * np.array([1.0, 2.0, 2.0], np.float32)).sum(-1))
    cand = (dist < 26) & (smooth > 0) & (above > 0)
    cand = cv2.morphologyEx(cand.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    n, lab = cv2.connectedComponents(cand, connectivity=4)
    top = set(np.unique(lab[:3][cand[:3] == 1])) - {0}
    sky = np.isin(lab, list(top)).astype(np.uint8)
    # gaps between leaves that are enclosed but still sky-coloured (not touching the top row): keep if reasonably large
    cnt = np.bincount(lab.ravel(), minlength=n)
    for k in range(1, n):
        if k not in top and cnt[k] >= 6:
            sky[lab == k] = 1
    # Outside the maple-branch zone the aligned painting has the spring layout, so the spring sky mask (which already
    # includes the painted horizon glow / cloud streaks) is the exact sky there.  Refine it against this image:
    # drop falling leaves (saturated flecks that differ from their surroundings) and pixels sitting on strong edges
    # (the small painted differences along the hanging lantern, pagoda spire, roof crest).
    sp = np.load(os.path.join(ROOT, "render", "cache_tod.npz"))["sky"].astype(np.uint8) if os.path.exists(
        os.path.join(ROOT, "render", "cache_tod.npz")) else None
    if sp is not None:
        zone = np.zeros((H, W), np.uint8); zone[:345, 740:] = 1
        w0 = sp.astype(np.float32) * (1 - zone)
        k = 9
        loc = np.stack([cv2.GaussianBlur(f[..., c] * w0, (0, 0), k) for c in range(3)], -1) / (cv2.GaussianBlur(w0, (0, 0), k)[..., None] + 1e-6)
        fleck = (np.sqrt(((f - loc) ** 2 * np.array([0.5, 1, 1], np.float32)).sum(-1)) > 20).astype(np.uint8)
        fleck = cv2.dilate(fleck, np.ones((3, 3), np.uint8))
        edge = cv2.dilate((grad > 70).astype(np.uint8), np.ones((2, 2), np.uint8))
        # the tests misfire on the bright glow streaks beside the sun, so only apply them where leaves / structures are
        # near the sky edge: above y=470, around the hanging lantern, and around the pagoda
        chk = np.zeros((H, W), np.uint8); chk[:470] = 1; chk[:600, 1230:1390] = 1; chk[:, :900] = 1
        low = sp & (1 - (fleck | edge) * chk) & (1 - zone)
        low = cv2.morphologyEx(low, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        sky = np.where(zone > 0, sky, low).astype(np.uint8)
        # the autumn right hill sits lower than the spring one: the glow above it (and the sun disc) is sky that the spring
        # mask does not know about.  Grow into bright, low-gradient pixels connected to the sky (forest is dense in edges).
        hb = np.zeros((H, W), np.uint8); hb[455:590, 1245:1375] = 1       # hanging lantern box
        pav = np.zeros((H, W), np.uint8)
        cv2.fillPoly(pav, [np.array([(1245, 350), (1400, 318), (1530, 262), (1560, 200), (1672, 168), (1672, 941), (1485, 941),
                                     (1485, 440), (1250, 405)], np.int32)], 1)
        win = np.zeros((H, W), np.uint8); win[300:696, 900:1500] = 1
        grow = ((f[..., 0] > 138) & (grad < 55)).astype(np.uint8) & win & (1 - hb) & (1 - pav)
        grow = cv2.morphologyEx(grow, cv2.MORPH_OPEN, np.ones((4, 4), np.uint8))
        gl = cv2.connectedComponents(grow | sky, connectivity=4)[1]
        gk = np.unique(gl[sky == 1]); gk = gk[gk > 0]
        sky = np.maximum(sky, (np.isin(gl, gk) & (grow == 1)).astype(np.uint8))
        # keep only what connects to the top-row sky (no floating islands on structures)
        nn, ll = cv2.connectedComponents(sky, connectivity=4)
        sky = np.isin(ll, [k for k in np.unique(ll[:3][sky[:3] == 1]) if k]).astype(np.uint8)
    # enclosed leftovers inside the sky (small cloud streaks, the sun disc, falling-leaf specks are handled elsewhere):
    # fill non-sky islands below the foliage zone that are small and bright
    nn2, l2, st2, _ = cv2.connectedComponentsWithStats(1 - sky, connectivity=4)
    for k in range(1, nn2):
        x, y, w, h, a = st2[k]
        if a < 900 and y > 340 and y + h < 700 and w < 90 and h < 45 and 900 < x < 1500 and f[..., 0][l2 == k].mean() > 150:
            sky[l2 == k] = 1
    # close pinholes, then drop the 1 px halo where the sky meets structure (paint outlines belong to the structure)
    sky = cv2.morphologyEx(sky, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    return sky


def main():
    spring = cv2.imread(SPRING)
    os.makedirs(os.path.dirname(RAW), exist_ok=True)
    if not os.path.exists(RAW):
        shutil.copy(OUT, RAW)
    raw = cv2.imread(RAW)
    assert raw.shape[:2] == (H, W)
    if "--report" in sys.argv:
        report(spring, raw, cv2.imread(OUT)); return
    es = edge_map(spring)
    fx, fy = solve(es, raw)
    new = warp(raw, fx, fy)
    cv2.imwrite(OUT, new)
    cv2.imwrite(SKY, sky_mask(new) * 255)
    np.save(os.path.join(os.path.dirname(os.path.abspath(__file__)), "autumn_field.npy"), np.stack([fx, fy]))
    report(spring, raw, new)


if __name__ == "__main__":
    main()
