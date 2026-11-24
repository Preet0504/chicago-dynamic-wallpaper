# Run 1 punchlist (baseline, overall 3.16 / 5)

Per-criterion means: style 3.12, composition 4.25, realism 2.88, structure 3.12, light 3.29, edges 2.62, depth 3.21, wallpaper 2.79.
Weakest: edges/artifacts, wallpaper-worthiness, realism rules. Best frames: 14 (autumn golden), 13, 16, 01, 06.

## season-modifier (highest impact)

1. WINTER (items 19-24, avg ~2.2): snow is popcorn/cotton-ball blobs in blocky clumps on roofs, pavilion posts and shrubs. Needs smooth snow with thickness lying on top surfaces, following roof lines.
2. WINTER: the tree branch is missing entirely (only stray dots top right). Rule: bare dark branches, connected and tapering, in the TREE_ZONE.
3. WINTER: walkway is a flat white/sepia sheet with railing buried: the exact "frosted sheet" the user rejected. Needs a drift at the railing, lantern-base mounds, footprints, stone pattern faintly present.
4. WINTER: lake ice shows as vertical frost columns/stripes under the near shore; make an irregular ice edge along the near shore only. Pagoda spire is solid black, snow on lantern caps is a blob.
5. WINTER 22/23: ghost white/grey blossom-shaped branch visible in sky (blossoms must not exist in winter).
6. SUMMER (items 8-12, avg ~2.5): only the top branch was recoloured, into jagged crystalline green polygons (off-style). Shrubs on the left, right and bottom corner are still pink blossoms; white petals still fall. Need real leaf clusters in painted style, green shrubs/trees, no petals.
7. SUMMER night: add fireflies (rule).
8. AUTUMN: composition differs slightly from the spring template (pagoda tiers/shape, pavilion scale, mountain size). Acceptable but keep the pagoda consistent across seasons if the template can be regenerated.
9. SPRING: blossoms on the branch bleach to white/grey in daytime (items 2, 5); keep pink saturation in day (time-modifier interaction).

## weather-modifier

1. SNOW (items 18, 22): the effect does not exist: no falling flakes, no fresh blanket, no haze. Item 18 (autumn + snow on Nov 20) additionally shows stars and a flat moon disc at 13:00 under a grey wash; item 22 has no flakes. Implement snow: layered flakes, mountain/far-shore haze, no stars, moon only a glow, warm lantern pools on snow, no wet reflections.
2. STORM/RAIN lake texture: choppy water renders as a repeating scale/cloud-pattern tile (items 6, 11); use directional ripples with depth-scaled size.
3. RAIN/STORM mountain cloud band has a hard horizontal edge (items 12, 16, 6); feather and break it up.
4. FOG: flat grey wash with no halos around lit lights; add soft halos at night/dusk and some low-contrast gradient with depth; keep foreground detail.
5. Lightning bolt terminates abruptly at the mountain (item 6, 11); end it at the horizon/ground with a flash glow.
6. RAIN day (05): lake reads as speckle noise; add ripple rings.

## time-modifier

1. NIGHT STARS/CLOUDS (items 4, 10, 15, 21): the painted-cloud layer at night renders as clumped white scribble streaks that read as noise, not stars or clouds. Fade clouds to near zero at night or tint them dark; keep clean point stars.
2. MOON: on clear nights no moon is drawn, yet a moon reflection patch sits on the lake at left (items 4, 21). Either draw the moon at its astro position with a glow or remove the reflection when it is below the horizon / hidden.
3. DAYTIME MOON/STARS under cloud: items 18 and 23 show stars and a moon disc at 11:00-13:00 under overcast. Suppress both by sky_cover and sun altitude.
4. DUSK LANTERNS: items 3, 9, 14 (sun 3-5 deg) have lanterns/windows off; rule says lanterns on at dusk/dawn. Light lanterns once sun < ~6 deg.
5. DAY LANTERNS: unlit lanterns are still ghostly translucent grey boxes with mist smudges around them (items 2, 5, 8, 13, 17, 23). Repaint them as opaque unlit lantern bodies (dark wood/paper), remove halo.
6. LAKE REFLECTIONS: blocky orange glyph-like reflections at night in autumn (15) and vertical ghost smudges (2, 13, 14) in daytime. Reflections should be thin horizontal-stretched streaks directly below their source.
7. Sun disc in item 13 sits directly behind the pagoda spire; consider sun azimuth offset or occlusion handling.

## detail-orienter

1. Hanging lantern: soft grey halo/ghost outline remains around it at dawn/night (items 1, 4); clean up the edge.
2. Pagoda base and lake edge: small light rectangle/ghost smudge near (262-310, 700-760) on left shore (visible in items 1-4); pale vertical ghost shapes near shore at x~1020-1200 y~760 (items 13-15, 17-18).
3. Roof of pavilion has a white snow-like lip at its left edge in autumn frames (13-18, x 1250-1300, y 330-390) even when not snowing.
4. Stray yellow-dot/dash fragments at top right in winter frames (19, 20, 24), and a faint curved line at the top (23).
5. Hard-edged haze band on the far hill at right in rain/storm frames.
6. Winter pagoda: rectangle patches of snow near its mid tiers and left tree stub with floating pieces.
