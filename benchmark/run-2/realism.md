# Realism review — run 2

Coordinates are base px (1672x941). Multiply by 1.531 for output px.
Verdict key: accept / revise / reject. Score = 1-5 realism ("would a viewer believe this is the same painting at that moment").
Scale matches run 1. Accept needs >= 4 with no RULES violation.
Read every *_full.png once. Crop sheets used to confirm findings: 06, 08, 10, 13, 15, 17, 19, 22.

## Top 5 systemic issues

1. **The autumn template sits off the shared geometry** [template-creator] (13-18). Every mask built for the spring layout
   lands 19-27 px off the autumn painting, and the errors are visible in every autumn frame:
   - Two sky-coloured "bites" are cut out of the foliage between the pagoda and the small pagoda at x240-300 y640-760.
     They are pale in day frames (13, 14) and grey in 15 (all confirmed in crops).
   - A white/grey matte fringe runs along the pavilion roof crest at x1250-1420 y300-345 (13-18, confirmed in 13, 15
     and 17).
   - A yellow band with a straight top edge sits on the right hill crest at x1170-1340 y600-640. At 22:00 (15) it stays
     lit yellow-olive.
   - The lake layer has a straight top edge at y~668 and a straight bottom edge at y~785. It pastes a blurred, doubled
     copy of the far shore at x300-1250 y660-700, with a grey smear at x290-420 (13, 14, 15, 18).
   - Ghost pagoda tier stubs stick out on the pagoda's right at x225-270 y610-640 (17, confirmed in crops).
   - A pale vertical streak on the walkway at x1210-1240 y820-941 is the run-1 "ghost figure", now light instead of dark.
   - The autumn painting's own sun/cloud blob is left beside the pagoda at x55-110 y535-575. It glows yellow at 22:00
     (15) and orange in rain (16).
   - The mountain in 16 is jagged and twin-peaked, unlike the cone in the other seasons.

   Either re-register the autumn template to the shared geometry or give it its own masks. Recolouring cannot fix this.
2. **Light-removal residue in the day plate** [time-modifier] (02, 05, 08, 09, 11, 13, 17, 19, 23). The ghost lanterns
   are fixed, but the residue has moved elsewhere:
   - A pale square sits left of the small pagoda at x270-295 y705-740 (01-05, unchanged since run 1).
   - Summer and winter day frames now show black smoke columns beside the small pagoda at x270-300 y680-730, plus
     brown-orange burn smears along the far shore at x380-1300 y680-720 (08, 09, 11, 19, 23).
   - At noon and under overcast, warm lantern-light pools stay on the walkway at x1050-1300 y790-900 (02, 08, 19, 23).
     In 19 and 23 they make the whole snow walkway glow cream-yellow.
   - Pagoda and town windows are lit at 09:00 (13) and 13:00 (17).
   - The day grade is still over-sharpened HDR, with a cyan rim on the mountain and hills (02, 05, 08, 13).

   A daytime frame should have no warm pools, no lit windows and no smudges where lights were removed.
3. **Summer foliage is sticker clip-art, and summer details are broken** [season-modifier] (08-12). Removing the
   blossoms and connecting the twigs to a branch fixed the run-1 failure. The leaves now look wrong in a new way:
   - The leaves at x830-1672 y0-370 are large maple-shaped stickers, 35-45 px each, all the same size and evenly spaced.
     Each has a dark outline, a pale halo and a flat two-tone fill (confirmed in crops). They are coarser than the
     painting's foliage and stay bright green at sunset (09) and under a storm sky (11).
   - The hanging lantern's roof has become a black spiky flag shape at x1295-1345 y480-505 (08-12, confirmed).
   - One pagoda window glows green at (160,655) (10, 12).
   - The summer night (10) has no fireflies, confirmed in crops. That is a RULES failure.
4. **The winter ground plane is still a flat sheet** [season-modifier] (19-24). The new template is a big step up: bare
   tapering branches with snow on top, thick roof snow and snow-mound shrubs. What remains:
   - The walkway at x700-1400 y820-941 is a single smooth cream/grey plane. There are no drifts at the railing or at the
     lantern bases. The "footprints" are a scribbled grey stamp that reads like text (confirmed in the 19 crops).
   - The left foreground roof at x0-330 y740-941 is a blank white plane.
   - The near shore still has no ice. The lake is liquid and clear in January (RULES failure).
   - A white crescent swoosh sits beside the hanging lantern at x1320-1345 y500-560.
   - The pavilion roof snow reads as a detached white ribbon below the crest at x1240-1400 y320-345.
5. **Weather and sky effects with hard or CG edges** [weather-modifier / time-modifier].
   - Storm (06, 11): the low mist band has a straight top edge at y~615-630 across x330-1250 that cuts the mountain base
     like a ruler line. The lightning ends exactly on that line. The bolt is huge, crisp, centred and stock-brush
     branched, so it draws more attention than anything else in the frame. Lake chop is gone entirely: the water is
     smooth in a storm.
   - Partly cloudy (02, 09, 14): clouds are now Gaussian-blurred airbrush or motion-smeared masses. They are softer than
     anything in the painting. In 09 a cloud has a straight vertical edge at x~1010 y570-630.
   - Overcast (23): the sky is a uniform diagonal streak texture.
   - Autumn snow (18) is still recolour-only on the ground.
   - Rain at intensity 0.4 (12) is near-invisible. Rain splashes in 16 are thick glowing vertical bars over the far lake,
     the same size as the near ones.

Recurring local artifacts [detail-orienter]:
- A pale ragged matte notch on the mountain's left flank at x240-330 y585-640 (01-05, 08-12, 19-23).
- A lighter band with a ragged top hugging the far ridge at x800-1480 y590-635. It reads as a cut-out outline (01, 04,
  10, 21). A pale rectangle ends it at x1000-1030 y620-635 (10, confirmed).
- A teal/cyan blob on the pagoda's left silhouette at x225-270 y560-680 (05, 06, 07, 24).

## Scores (one line per render)

| # | render | run 1 | run 2 | verdict |
|---|---|---|---|---|
| 01 | spring clear 06:05 | 3.0 | 3.5 | revise |
| 02 | spring partly_cloudy 13:00 | 2.0 | 2.5 | revise |
| 03 | spring clear 19:10 | 2.5 | 3.0 | revise |
| 04 | spring clear 22:00 | 2.0 | 3.5 | revise |
| 05 | spring rain 13:00 | 2.5 | 3.0 | revise |
| 06 | spring storm 21:00 | 2.5 | 3.0 | revise |
| 07 | spring fog 07:00 | 2.5 | 3.5 | revise |
| 08 | summer clear 13:00 | 1.5 | 2.5 | revise |
| 09 | summer partly_cloudy 19:50 | 1.5 | 2.5 | revise |
| 10 | summer clear 22:30 | 1.5 | 2.5 | revise |
| 11 | summer storm 16:00 | 1.5 | 3.0 | revise |
| 12 | summer rain 22:00 | 2.0 | 3.5 | revise |
| 13 | autumn clear 09:00 | 2.5 | 2.5 | revise |
| 14 | autumn partly_cloudy 17:45 | 3.0 | 3.0 | revise |
| 15 | autumn clear 22:00 | 2.0 | 2.5 | revise |
| 16 | autumn rain 18:20 | 3.5 | 3.5 | revise |
| 17 | autumn fog 13:00 | 2.5 | 3.5 | revise |
| 18 | autumn snow 13:00 (Nov 20) | 1.0 | 2.0 | reject |
| 19 | winter clear 13:00 | 1.5 | 3.0 | revise |
| 20 | winter clear 16:45 | 2.0 | 3.5 | revise |
| 21 | winter clear 22:00 | 1.5 | 3.5 | revise |
| 22 | winter snow 22:00 | 1.0 | 3.0 | revise |
| 23 | winter overcast 11:00 | 1.0 | 2.5 | revise |
| 24 | winter fog 08:00 | 1.5 | 3.5 | revise |

Mean: 3.0 (run 1: 2.0). Verdicts: 0 accept, 23 revise, 1 reject (run 1: 0 / 11 / 13).
Closest to accept: 01, 04, 20, 21, 24. Removing the ridge/flank mattes (01, 04) and adding shore ice plus walkway
structure (20, 21, 24) would put them at 4.

## Fixed since run 1

- Winter template: the popcorn snow, vertical-wall snow, white-recoloured blossoms and the missing branch are all
  gone. The branches are bare and tapering with snow on top. Roofs and lantern caps carry thick snow, and the shrubs
  are snow mounds (19-24).
- Summer: the pink blossoms and falling petals are gone everywhere, and the foliage now hangs from a real branch with
  twigs (08-12).
- Unlit lanterns are opaque wood and paper instead of grey ghost boxes. Lanterns are lit at dusk and low sun (03, 09,
  14).
- The night sky has no scribble "bird-flock" clouds and no cross-sparkle star. The stars are sparser and vary in
  brightness (04, 10, 15, 21).
- Overcast and snow daytime frames no longer show stars or a moon disc (18, 23). The overcast winter frame no longer
  has blossoms.
- The storm fish-scale lake stamp is gone (06, 11). The mist bands in 05, 12 and 16 have soft, ragged tops.
- Fog has real depth falloff: the mountain is hidden, the far shore is gone, the near scene stays crisp, and the lights
  have halos (07, 17, 24).
- The blocky orange lake reflections in 15 are gone, and the autumn leaf "embers" at night are mostly gone.
- Falling snow exists, in layers with near and far size variation (18, 22). In 22 the mountain is hazed.
- The grey rectangle behind the pagoda spire is gone (01, 06).

## New problems introduced

- Summer maple-sticker leaves and the broken black lantern cap (08-12) [season-modifier].
- Black smoke columns at the small pagoda and brown burn smears on the far shore in summer and winter day plates. These
  replace the run-1 white mist blobs [time-modifier].
- Clouds are blurred airbrush or motion-smeared instead of painted (02, 09, 14), and the overcast sky is a uniform
  diagonal streak texture (23) [time-modifier].
- A ruler-straight mist edge at the mountain base in storms, the lightning terminating on it, and an oversized
  centre-frame bolt (06, 11) [weather-modifier].
- The storm lake has lost its chop entirely [weather-modifier].
- Lantern reflections mirrored on the snow in 22 (RULES: no wet-stone reflections while snowing) [weather-modifier].
- The winter walkway glows warm at noon and under overcast, and the footprint trail is a stamped glyph strip
  (19, 23) [season-modifier / time-modifier].
- A white swoosh beside the winter hanging lantern, and a detached snow ribbon on the pavilion roof (19-24)
  [season-modifier].
- Pagoda windows bloom into oversized white glows in winter fog (24), and a green window glows in summer (10, 12)
  [time-modifier / detail-orienter].
- Thick glowing rain-splash bars with no depth scaling (16) [weather-modifier].

## Per render

### 01 spring clear 06:05 — revise (3.5)
- The pale square left of the small pagoda at x270-295 y705-740 is unchanged since run 1. [time-modifier]
- The far ridge behind the right hill (x1180-1350 y590-610) and the mountain's left flank (x240-330 y585-640) have pale,
  ragged matte outlines. They read as cut-outs against the dawn sky. [detail-orienter]
- Otherwise this is a believable dawn: lanterns are lit, the horizon glows, and the falling petals are sparse.

### 02 spring partly_cloudy 13:00 — revise (2.5)
- The clouds are Gaussian-blurred white masses (x0-280 y100-350, x820-1560 y30-430) with no painted edge or internal
  shading. They are the softest thing in the frame, which reads as a Photoshop airbrush pasted over the painting.
  [time-modifier]
- Light residue at noon: a warm glow pool on the walkway at x1100-1300 y790-860, a yellow glow inside the pavilion, the
  pale square at x270-295 y705-740, and orange smears on the lake's right end at x1150-1280 y700-740. [time-modifier]
- The grade is over-sharpened and HDR, with a cyan rim on the mountain flank and hills. The pagoda windows have a pale
  green cast. [time-modifier]

### 03 spring clear 19:10 — revise (3.0)
- The lanterns are now lit, which is correct. The sky is still a flat two-stop blue-to-peach gradient with no glow
  structure at the sunset point. [time-modifier]
- The mountain keeps a teal cast under warm low sun. [time-modifier]
- The pale square at x270-295 y705-740 persists. [time-modifier]

### 04 spring clear 22:00 — revise (3.5)
- A lighter band with a ragged top hugs the far ridge at x800-1300 y590-635, and a pale notch sits on the mountain's
  left flank at x240-330 y590-640. Both read as cut-out mattes against the night sky. [detail-orienter]
- A small moon-like glint stays on the lake at x470-500 y770-780 with no source (moonless night). [time-modifier]
- The sky itself is now good: no scribble clouds, and the stars are sparse and varied.

### 05 spring rain 13:00 — revise (3.0)
- The cloud deck and mist are much better. The foreground town, though, is still crisp, saturated blue and HDR, with
  bright cherry blossom, under a heavy rain sky. Rain light is flat and desaturated, so the light here is inconsistent.
  [time-modifier]
- The rain streaks are concentrated in the sky. Over the town and walkway they are sparse, and the lake is uniform
  speckle with no ring ripples. [weather-modifier]
- There is a teal smear on the pagoda's left at x230-270 y600-680, and the pale square at x270-295 y705-740.
  [detail-orienter / time-modifier]

### 06 spring storm 21:00 — revise (3.0)
- The low mist band has a ruler-straight top edge at y~615 across x330-1250 (confirmed in crops). The lightning bolt
  ends exactly on it. Real storm cloud would hide the base in ragged, uneven layers. [weather-modifier]
- The bolt (x820-1010 y50-615) is huge, centred, pure white and evenly branched like a stock brush, so it is the
  loudest element in the frame. A real bolt this close would light the clouds and roofs. Otherwise it should be smaller
  and further off. [weather-modifier]
- The lake is now smooth and calm, so the RULES requirement for choppy water is not met. A blue matte haze patch sits
  left of the pagoda at x225-265 y560-640. [weather-modifier / detail-orienter]

### 07 spring fog 07:00 — revise (3.5)
- Depth falloff and lantern halos now work. The pagoda (x50-270) stays much crisper and more contrasty than the small
  pagoda next to it, so it looks pasted in front of the fog. [weather-modifier]
- The hidden far shore shows as a row of evenly spaced soft white orbs at x560-1000 y690-710. The spacing is too
  regular for town lights seen through fog. [weather-modifier]
- A teal fringe remains on the pagoda's left at x235-265 y610-650. [detail-orienter]

### 08 summer clear 13:00 — revise (2.5)
- The leaves (x830-1672 y0-370) are large clip-art maple stickers: the same size, evenly spaced, outlined and
  haloed, with a flat two-tone fill (confirmed in crops). They clash with the painting's fine foliage. They should be
  smaller and overlapping, shaded in the same brushwork as the pagoda's trees. [season-modifier]
- The hanging lantern's roof has turned into a black spiky flag at x1295-1345 y480-505. [season-modifier]
- Day-plate residue: black smoke beside the small pagoda at x270-300 y680-725, brown-orange smears along the far
  shore at x380-1300 y680-720, and a warm glow pool on the walkway at noon. The mountain texture looks melted in crops.
  [time-modifier]

### 09 summer partly_cloudy 19:50 — revise (2.5)
- Lanterns lit, which is correct. The leaves stay bright yellow-green, ungraded by the low warm sun, so they look
  pasted on. [season-modifier / time-modifier]
- The clouds are blurred blobs. Next to the mountain, one has a straight vertical edge at x~1010 y570-630.
  [time-modifier]
- The same lantern cap, smoke columns and far-shore smears as 08. [season-modifier / time-modifier]

### 10 summer clear 22:30 — revise (2.5)
- There are no fireflies anywhere (confirmed in crops), which is a RULES failure for a summer night. [season-modifier]
- The lantern cap is broken (x1295-1345 y480-505), and a pagoda window glows green at (160,655).
  [season-modifier / detail-orienter]
- A ridge matte band runs at x1010-1300 y595-635 and ends in a pale rectangle at x1000-1030 y620-635. A dark-blue
  smear sits on the hill at x1340-1400 y595-610. [detail-orienter]

### 11 summer storm 16:00 — revise (3.0)
- The cloud deck, mountain mist and blown green leaves all work. The lightning ends in mid-air on the straight mist edge
  at y~625-630 (x1000-1250). [weather-modifier]
- The tree's leaves stay pale bright green-grey with outlines, glowing against a dark storm sky. [season-modifier]
- The lake shows no chop, there is smoke beside the small pagoda, and the lantern cap is broken.
  [weather-modifier / time-modifier / season-modifier]

### 12 summer rain 22:00 — revise (3.5)
- The best summer frame: wet path reflections, drips around the hanging lantern, and a dark, believable sky.
- At intensity 0.4 the rain streaks are nearly invisible over most of the frame, and the lake has no visible ripples.
  [weather-modifier]
- The lantern cap is broken and the pagoda window at (160,655) is green. [season-modifier / detail-orienter]

### 13 autumn clear 09:00 — revise (2.5)
- Misalignment artifacts, all confirmed in crops:
  - sky-coloured bites in the foliage at x240-300 y640-760
  - a white fringe on the pavilion roof crest at x1250-1420 y300-345
  - a yellow straight-topped band on the hill crest at x1170-1340 y600-640
  - a doubled pale far shore in the lake at x300-1250 y660-700
  - a pale walkway streak at x1210-1240 y820-941

  [template-creator]
- The pagoda and town windows glow bright yellow at 09:00. [time-modifier]
- The sun disc sits exactly on the spire with a big bloom (x110-210 y330-420), which looks staged. The frame is
  over-sharpened and over-saturated, with blown yellow on the walkway. [time-modifier]

### 14 autumn partly_cloudy 17:45 — revise (3.0)
- Lanterns lit, which is correct. The large cloud at x0-780 y0-540 is motion-smeared airbrush, as if a blur filter
  were dragged diagonally, not painted cloud. [time-modifier]
- The same misalignment set as 13: bites at x240-300 y640-760, the roof-crest fringe, the hill band, and the doubled
  far shore at x300-1250 y660-700. [template-creator]
- The crescent moon at (1180,420) is plausible.

### 15 autumn clear 22:00 — revise (2.5)
- The blocky reflections are fixed. The lake now reads as a pasted pane, though: a straight top edge at y~668 and a
  straight bottom edge at y~785 (x300-1250), with a grey smear at x290-420 y660-700 (confirmed in crops).
  [template-creator]
- The right hill (x1170-1480 y570-690) stays yellow-olive and looks lit at 22:00, with a straight crest band. A yellow
  sun/cloud leftover glows left of the pagoda at x55-110 y535-565. [template-creator / time-modifier]
- The roof crest has a grey fringe (x1250-1420 y300-345), and there are grey bites beside the pagoda at x270-300
  y640-760. [template-creator]

### 16 autumn rain 18:20 — revise (3.5)
- The mist now softens the mountain base properly. The mountain is a jagged twin peak, unlike the cone in every other
  season. [template-creator]
- The rain splashes are thick, glowing vertical bars at x850-1300 y650-900. The far ones over the lake are as big as
  the near ones, and they read as light poles. [weather-modifier]
- An orange blob glows left of the pagoda at x55-110 y535-575. [template-creator]

### 17 autumn fog 13:00 — revise (3.5)
- The fog depth is now right: the mountain is hidden, the shore is gone and the near scene is crisp.
- Ghost pagoda tier stubs stick out at x225-270 y610-640, there is a yellow blob at x60-100 y540-560, a white
  roof-crest fringe, and a pale walkway streak at x1210-1240 (all confirmed in crops). [template-creator]
- Town windows are lit at 13:00 (x400-520 y820-880). [time-modifier]

### 18 autumn snow 13:00 (Nov 20) — reject (2.0)
- Flakes now fall, but nothing is snowed on: the walkway is bare and glossy-wet, and the roofs and lantern caps are
  bare. RULES for snowing require a fresh blanket and caps. The flakes are identical soft round discs, mostly in the
  sky. [weather-modifier]
- On Nov 20 the tree should be mostly bare, yet it is in full red and gold foliage. [season-modifier]
- The foreground stays warm and sunlit under a flat grey snow sky. There is a doubled pale far shore in the lake at
  x300-1250 y660-700. [time-modifier / template-creator]

### 19 winter clear 13:00 — revise (3.0)
- The walkway (x700-1400 y820-941) is a flat, featureless cream sheet that glows warm at noon. There are no drifts and
  no stone relief. The footprint trail is a scribbled glyph stamp (confirmed in crops). The left foreground roof at
  x0-330 y740-941 is a blank white plane. [season-modifier / time-modifier]
- There is no near-shore ice. A white swoosh sits beside the hanging lantern at x1320-1345 y500-560, and the roof snow
  is a detached ribbon at x1240-1400 y320-345. [season-modifier]
- Black smoke beside the small pagoda (x270-300 y680-730) and brown smears on the far shore (x950-1250 y680-720).
  The sun has a large CG bloom. [time-modifier]

### 20 winter clear 16:45 — revise (3.5)
- The best winter frame: the dusk sky, lit lanterns, snow-capped pagoda and bare branch are all convincing.
- There is no ice along the near shore. The lake is liquid and mirror-clear in January (RULES). [season-modifier]
- The walkway and the left foreground roof are still flat sheets with no drifts at the railing or lantern bases.
  [season-modifier]

### 21 winter clear 22:00 — revise (3.5)
- The same flat walkway, glyph footprints and missing ice as 20. [season-modifier]
- A pale ridge halo band runs at x1210-1480 y570-630 behind the right hill. [detail-orienter]

### 22 winter snow 22:00 — revise (3.0)
- Mirror reflections of the stone lanterns sit on the snow at x900-960 y890-941 and x1250-1290 y840-875 (confirmed in
  crops). RULES forbid wet-stone reflections while snowing, and here the walkway reads as ice or a wet road.
  [weather-modifier]
- The snowfall is too sparse and fine for "fresh, thick snow". The far-shore lights stay crisp, so low visibility is
  not delivered. The mountain haze is good. [weather-modifier]
- The walkway is a smooth grey sheet with no drifts at the railing or lantern bases, and there is no shore ice.
  [season-modifier]

### 23 winter overcast 11:00 — revise (2.5)
- The sky is a uniform diagonal streak texture across the whole frame. It reads as scratched or wind-brushed noise,
  not a cloud deck. Overcast should be soft and even, with a faint brighter patch toward the sun. [time-modifier]
- The walkway and pavilion underside glow warm cream as if in direct sun. The mountain keeps full sunny contrast.
  Under overcast, everything should be flat and cool. [time-modifier]
- Smoke beside the small pagoda, smears on the far shore, the lantern swoosh, and no ice.
  [time-modifier / season-modifier]

### 24 winter fog 08:00 — revise (3.5)
- Good: the mountain is hidden, there are halos on the lanterns, and the near-to-far falloff is right.
- The pagoda windows bloom into oversized white glows (x100-260 y500-830) that are stronger than the lanterns, so the
  pagoda looks backlit. [time-modifier / weather-modifier]
- A teal blob sits on the pagoda's left at x235-265 y610-650. The walkway is the same flat sheet with glyph footprints.
  [detail-orienter / season-modifier]
