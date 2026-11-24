# season-modifier — round 1 (from run-1 punchlist.md + realism.md)
Baseline: winter renders 19-24 ALL rejected (realism 1-2), summer 08-12 ALL rejected. Read the winter/summer
sections of ../punchlist.md and ../realism.md for exact locations.

Must fix (priority order):
1. WINTER template: replace procedural snow with the local AI edit path. Known: a plain FLUX.2 klein edit of
   spring_clear_night.png (aigen/test_winter_klein4b.png — look at it) gives believable bare snowy branches, snow-laden
   shrubs, snow on roofs — BUT it drifts the composition (zoomed out, pagoda moved). Fix alignment by one of:
   (a) mflux-generate-fill / masked inpainting so unmasked pixels stay identical; (b) register the AI output onto the
   original (feature matching + homography/ECC per region) and composite only the regions that should change;
   (c) prompt/seed search for minimal drift. Measure alignment numerically. Required: no popcorn texture, no snow on
   vertical walls, real bare branch present, walkway snow with soft natural shading, shore ice irregular, zero pink.
2. SUMMER template: same AI path. Dense green leaves ON a visible branch (no floating clip-art polygons), shrubs green
   (zero pink), no falling petals, mountain snow reduced to summit streaks.
3. Spring blossoms bleach to white in daytime → tell time-modifier if it's the day-plate grade (it owns that); you own
   the templates only.
4. autumn_clear_golden.png pagoda/pavilion proportions differ slightly from spring — report the per-region offsets; do
   not alter the autumn painting unless offsets > 3 px.
Generator scripts: render/season_winter.py and render/season_summer.py (rewrite freely); keep chosen AI outputs in
templates/ai/. One mflux process at a time.
