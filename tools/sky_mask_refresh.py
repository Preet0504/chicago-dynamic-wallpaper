#!/usr/bin/env python3
"""Refresh templates/<name>_sky.png inside a region after an AI region edit changed a silhouette against the sky
(the renderer rebuilds the sky only where this static mask says so).
Local sky colour is taken from pixels that were sky before and did not change in the edit; inside the region a
pixel is sky if it is smooth and matches that local sky colour, and is connected to the open sky.
Outside the region the mask is untouched.

  .venv/bin/python tools/sky_mask_refresh.py summer_clear_night templates/ai/masks/summer_branch.png \
      templates/ai/backup/summer_clear_night_<time>.png
"""
import os, sys
import cv2, numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda p: p if os.path.isabs(p) else os.path.join(ROOT, p)


def main(a):
    name, reg_p, old_p = a[0].replace(".png", ""), a[1], a[2]
    img = cv2.imread(os.path.join(ROOT, "templates", name + ".png")).astype(np.float32) / 255
    old = cv2.imread(P(old_p)).astype(np.float32) / 255
    sky_p = os.path.join(ROOT, "templates", name + "_sky.png")
    sky = cv2.imread(sky_p, 0) > 127
    reg = cv2.dilate((cv2.imread(P(reg_p), 0) > 127).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    same = np.abs(img - old).max(-1) < 0.02
    seed = (sky & same).astype(np.float32)
    seed = cv2.erode(seed, np.ones((3, 3), np.uint8))
    num = cv2.GaussianBlur(img * seed[..., None], (0, 0), 25)
    den = cv2.GaussianBlur(seed, (0, 0), 25)[..., None]
    loc = num / np.maximum(den, 1e-4)
    L = img @ np.array([0.114, 0.587, 0.299], np.float32)
    grad = cv2.morphologyEx(L, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    B, G, R = img[..., 0], img[..., 1], img[..., 2]
    blue = (B > G + 0.03) & (B > R + 0.05) & (L < 0.30)  # night sky between leaves (leaves are green-dominant)
    cand = ((np.abs(img - loc).max(-1) < 0.06) & (den[..., 0] > 0.01) | blue) & (grad < 0.05)
    cand = cv2.morphologyEx(cand.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))  # stars
    cand = cv2.morphologyEx(cand, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8)) > 0
    new = np.where(reg, cand, sky)
    # stars and other small non-green specks enclosed by sky are sky
    n, lab, st, _ = cv2.connectedComponentsWithStats((~new).astype(np.uint8), connectivity=4)
    grn = np.bincount(lab.ravel(), (G > B + 0.01).ravel().astype(np.float64), n) / np.maximum(st[:, 4], 1)
    spk = (st[:, 4] < 60) & (grn < 0.3); spk[0] = False
    new |= spk[lab] & reg
    # keep open sky and the sky holes between leaves (>= 8 px); drop specks
    n, lab, st, _ = cv2.connectedComponentsWithStats(new.astype(np.uint8))
    keep = set(np.unique(lab[new & ~reg])) | set(np.where(st[:, cv2.CC_STAT_AREA] >= 8)[0])
    keep.discard(0)
    new = np.isin(lab, list(keep))
    print("%s: sky px in region %d -> %d" % (name, int((sky & reg).sum()), int((new & reg).sum())))
    cv2.imwrite(sky_p, new.astype(np.uint8) * 255)


if __name__ == "__main__":
    main(sys.argv[1:])
