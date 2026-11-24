# template-creator — round 2
templates/autumn_clear_golden.png (a real painting) sits 19-27 px higher than the shared geometry almost everywhere
(phase-correlation: pagoda (+2,-25), mountain (+3,-27), pavilion (-3,-3), hanging lantern (-3,-11), stone lanterns
(0,-19), railing (0,-19)), while all masks/polygons (lake LAKE, lanterns, horizon, depth) come from the spring layout.
This causes most autumn artifacts in ../realism.md (sky holes in foliage beside the pagoda, fringe on the pavilion roof
crest, straight-topped yellow band on the hill crest, doubled far shore, ghost pagoda stubs).
Task: produce an aligned autumn template that matches spring geometry within ~2 px for all structures, by a smooth
non-rigid warp (e.g. dense registration on edge maps/structure, regularised; pavilion barely moves, rest moves ~20 px)
— keep the original in templates/originals/autumn_clear_golden_raw.png, write the aligned one to
templates/autumn_clear_golden.png, script in render/align_autumn.py. Fill any revealed border strip plausibly (no
smears). Verify per-region offsets after warping and render autumn 09:00 / 17:45 / 22:00 via render/preview.py.
Also write templates/autumn_clear_golden_sky.png (exact sky mask for the aligned image) — the engine uses it if present.
