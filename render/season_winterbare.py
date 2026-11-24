"""Snowless winter template (Chicago Dec-Feb with < 2 cm snow depth): templates/winterbare_clear_night.png
(+ _sky.png). A cheap variation of season_autumnlate.py:

  .venv/bin/python render/season_winterbare.py

  - Branch: completely bare twigs from a FLUX.2-klein edit (templates/ai/winterbare_edit_branch.png),
    soft de-haloed matte, no leaves, no snow.
  - Shrubs: the late-autumn AI shrubs (templates/ai/autumnlate_tile_*.png, no extra AI run) turned
    dormant: leaves stripped of colour -> grey-brown twiggy masses, darker and colder.
  - Grass / bed plants under the railing and around the pavilion base -> dormant straw.
  - Walkway: original stones, no leaf litter (the AI litter is not used).
"""
import os, sys
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import season_winter as WS
import season_summer as SU
import season_autumnlate as AL
from season_winter import W, H, poly, dil, soft, lum, blend, Scene, PATH, AI

NAME = "winterbare"
BUSH_DARK = np.array([0.07, 0.08, 0.09], np.float32)
BUSH_LIT = np.array([0.17, 0.20, 0.23], np.float32)


def build_guide(S):
    _, edit, _ = AL.paths(NAME)
    g, gm = AL.build_guide(S, NAME, (BUSH_DARK, BUSH_LIT), do_litter=False)
    return g, gm


def dormant(img, mask, S):
    """Colour out of foliage: grey-brown, a little darker, cold."""
    L = lum(img)[..., None]
    straw = L * np.array([0.95, 0.97, 1.02], np.float32)          # BGR: near-neutral grey-brown
    return blend(img, straw * 0.62, mask)


def compose(S, guide, gm):
    SU.TILE = os.path.join(AI, "autumnlate_tile_%s.png")
    ai, wsum = SU.merge_tiles(guide)
    ok = (wsum > 0.5).astype(np.float32)
    take = np.maximum(soft(dil(gm["sh"], 5), 1.5), soft(poly([SU.BEHIND]), 3.0)) * ok
    take = np.maximum(take, soft(dil(gm["pet"], 3), 1.5) * ok)
    ai = dormant(ai, np.ones((H, W), np.float32), S)
    img = blend(guide, ai, take)
    # dormant grass / bed plants: green and yellow-green foliage near the ground -> straw
    ground = poly([WS.RAIL_ENV, WS.PAV_BASE]) | ((S.yy > 860) & (S.xx > 1440)) | ((S.yy > 880) & (S.xx < 300))
    gr = ground & (S.Hh > 30) & (S.Hh < 120) & (S.S > 35) & ~dil(S.warm, 3)
    img = blend(img, lum(img)[..., None] * np.array([0.55, 0.80, 0.98], np.float32), soft(gr, 0.8) * 0.9)
    keep = dil(S.warm, 3) | dil(S.sky & ~S.tz, 2) | S.water
    _, edit, _ = AL.paths(NAME)
    _, bm = WS.branch_layer(S, img, edit, 1.0, soft_edge=True)
    img = WS.depink(img, keep)
    near = dil(gm["sh"] | gm["bp"], 25) & ~dil(S.warm, 3)
    img = blend(img, WS.depink(img, ~near), near.astype(np.float32))
    skym = (S.tod_sky | gm["holes"] | (S.tz & ~S.pav)) & (bm < 0.35)
    n, lab, st, _ = cv2.connectedComponentsWithStats((~skym).astype(np.uint8), connectivity=4)
    isl = np.zeros(n, bool); isl[1:] = (st[1:, cv2.CC_STAT_AREA] < 400) & (st[1:, cv2.CC_STAT_TOP] + st[1:, cv2.CC_STAT_HEIGHT] < 620)
    skym |= isl[lab] & (bm < 0.35)
    return np.clip(img, 0, 1), skym


if __name__ == "__main__":
    AL.run(sys.argv[1:], NAME, build_guide, compose)
