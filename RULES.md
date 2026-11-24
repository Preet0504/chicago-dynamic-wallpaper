# Realism rules for each condition (Chicago)

Every rendered variant must satisfy these. The renderer in `render/render.py` implements them.

| Condition | Must be true |
|---|---|
| Winter (Dec–Feb, any weather) | No blossoms, leaves or petals anywhere: bare dark branches, dormant brown grass and shrubs. **Snow on the ground only when Chicago actually has snow cover** (Open-Meteo `snow_depth` ≥ 2 cm, any month) — otherwise the bare, snow-free winter template. Frost is fine on sub-zero clear mornings. |
| Snowing | Fresh, thick snow: a smooth blanket on the walkway with drifts at the railing and lantern bases, a trodden line of footprints, caps on every lantern and rail, heavy roofs. Falling flakes in layers (small and far, large and blurry near). Low visibility: haze on the mountain and far shore. No stars; the moon is only a glow. Lantern light pools warm on the snow. No wet-stone reflections. |
| Rain | Wet, glossy stones and puddles that reflect the lanterns, rain streaks, ripples on the lake, no stars, low cloud, mist on the mountain. |
| Storm | All of the rain rules, plus lightning, a very dark sky, choppy water, and leaves or petals blown around. |
| Fog | Mountain hidden, far shore faded, halos around lights, low contrast. |
| Spring (Mar–May) | Blossoms in April–May with falling petals. March has bare branches with buds. Fresh green. |
| Summer (Jun–Aug) | Full green leaves, no petals, lush hills, fireflies at night. |
| Autumn (Sep–Nov) | Red, orange and gold leaves, falling leaves, leaf litter on the path. Late November (from ~Nov 15) is mostly bare: few rust leaves, litter. |
| Snow on the ground | Decided by real snow depth, not the calendar: ≥ 2 cm → snowy template (any month); 0 cm → no lying snow even in January. |
| Clear night | Stars and moon visible; moon reflection on the lake. |
| Cloudy or overcast night | No stars; the moon is hidden or only a glow; no moon reflection. |
| Daytime | Lanterns and windows off, no stars, shadows that match the sun. |
| Dusk or dawn | Lanterns on, with a sky glow on the horizon. |
