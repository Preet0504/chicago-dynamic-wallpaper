"""Builds the scene masks for base.png once (sky, blossoms, warm lights, water, ground)."""
import numpy as np, cv2, os
HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, "..", "templates", "spring_clear_night.png")  # the original painting

# horizon polyline (x, y) in base.png coordinates: mountains + hills silhouette, slightly below
HORIZON = [(0, 560), (240, 640), (330, 600), (420, 545), (470, 515), (520, 512), (600, 545),
           (700, 590), (800, 615), (900, 625), (1000, 632), (1100, 630), (1200, 625), (1300, 600),
           (1400, 570), (1500, 560), (1672, 560)]
# rough cores of structures that must never be sky
PAGODA = [(147, 300), (157, 300), (162, 470), (200, 470), (200, 760), (100, 760), (100, 470), (142, 470)]
PAVILION = [(1245, 350), (1400, 318), (1530, 262), (1560, 200), (1672, 168), (1672, 941), (1485, 941),
            (1485, 440), (1250, 405)]
MOON = ((446, 127), 58)


def build():
    im = cv2.imread(BASE)
    h, w = im.shape[:2]
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV_FULL).astype(np.int32)
    H, S, V = hsv[..., 0], hsv[..., 1], hsv[..., 2]

    warm = (((H < 45) | (H > 248)) & (S > 70) & (V > 150)).astype(np.uint8)
    warm_near = cv2.dilate(warm, np.ones((9, 9), np.uint8)) > 0
    pink = (H > 195) & (H < 248) & (S > 45) & (V > 95) & ~warm_near

    # --- sky via GrabCut
    gc = np.full((h, w), cv2.GC_PR_BGD, np.uint8)
    below = np.zeros((h, w), np.uint8)
    poly = np.array(HORIZON + [(w, h), (0, h)], np.int32)
    cv2.fillPoly(below, [poly], 1)
    gc[below == 0] = cv2.GC_PR_FGD
    gc[:60, :780] = cv2.GC_FGD
    gc[200:460, 380:1150] = cv2.GC_FGD
    gc[(below == 1)] = cv2.GC_BGD
    st = np.zeros((h, w), np.uint8)
    cv2.fillPoly(st, [np.array(PAGODA, np.int32), np.array(PAVILION, np.int32)], 1)
    gc[st == 1] = cv2.GC_BGD
    gc[pink] = cv2.GC_BGD
    # definite-sky seeds: clearly blue pixels in the upper sky away from blossoms/branches
    B, G, R = [im[..., i].astype(np.int32) for i in range(3)]
    far_pink = cv2.dilate(pink.astype(np.uint8), np.ones((15, 15), np.uint8)) == 0
    blue = (B > R + 22) & (B > G + 10) & (V < 140) & far_pink & (st == 0)
    upper = np.zeros((h, w), bool); upper[:330] = True
    gc[blue & upper] = cv2.GC_FGD
    # pale cloud pixels above the horizon, away from structures, are sky too
    st_far = cv2.dilate(st, np.ones((25, 25), np.uint8)) == 0
    cloud = (V > 60) & (B >= R) & (S < 130) & far_pink & st_far & (below == 0)
    gc[cloud] = cv2.GC_FGD
    cv2.circle(gc, MOON[0], MOON[1], int(cv2.GC_FGD), -1)
    bgd = np.zeros((1, 65), np.float64); fgd = np.zeros((1, 65), np.float64)
    cv2.grabCut(im, gc, None, bgd, fgd, 6, cv2.GC_INIT_WITH_MASK)
    sky = ((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)).astype(np.uint8)
    # keep only components connected to the top band
    n, lab = cv2.connectedComponents(sky)
    keep = set(np.unique(lab[:5][sky[:5] == 1]))
    sky = np.isin(lab, list(keep - {0})).astype(np.uint8)
    sky = cv2.morphologyEx(sky, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    cv2.circle(sky, MOON[0], MOON[1] + 2, 1, -1)

    water = np.zeros((h, w), np.uint8)
    cv2.fillPoly(water, [np.array([(265, 700), (900, 690), (1250, 700), (1260, 790), (900, 800), (390, 790), (265, 760)], np.int32)], 1)

    np.savez_compressed(os.path.join(HERE, "masks.npz"), sky=sky, pink=pink.astype(np.uint8),
                        warm=warm, water=water, below=below)
    return im, sky, pink, warm, water


if __name__ == "__main__":
    im, sky, pink, warm, water = build()
    vis = im.copy()
    vis[sky == 1] = (vis[sky == 1] * 0.3 + np.array([0, 160, 0]) * 0.7).astype(np.uint8)
    vis[pink] = (255, 0, 255)
    vis[warm == 1] = (0, 220, 255)
    vis[water == 1] = (vis[water == 1] * 0.5 + np.array([255, 120, 0]) * 0.5).astype(np.uint8)
    import sys
    cv2.imwrite(sys.argv[1], vis)
