# weather-modifier — round 1 (from run-1 punchlist.md + realism.md, see weather sections there)
Must fix:
1. SNOW effect missing entirely: write render/effects/snow.py (falling flakes in depth layers, haze, halos on lights,
   light fresh dusting on non-winter templates). Item 18 also shows stars + moon at 13:00 (time-modifier owns that).
2. Storm lake: tiled fish-scale stamp (06, 11) → non-repeating chop that follows perspective; lightning must light
   the clouds/scene and not stop abruptly at the mountain.
3. Mountain mist/low cloud: flat band with straight hard edges cutting the cone (05, 06, 11, 12, 16) → soft, irregular,
   wraps the slopes, fades with depth.
4. Fog: one even beige sheet → depth-based fade (A.depth), drifting density, low mist over the lake, light halos at night.
5. depth.npy: snap to object outlines (no boxes). You own render/depth.py.
Prefer subtle and physically motivated; realism-critic penalises busy, procedural-looking effects.
