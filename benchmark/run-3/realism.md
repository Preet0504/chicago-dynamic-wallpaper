# Realism review — run 3

Coordinates are base px (1672x941; the run-3 full frames are already at base size).
Verdict key: accept / revise / reject. Score = 1-5 realism ("would a viewer believe this is the same painting at that moment").
Same scale as runs 1-2. Accept needs >= 4 with no RULES violation.
Read every *_full.png once. Crop sheets used to confirm: 06, 10, 13, 15, 18, 19, 22, 23.
Note for the finalizer: in every crop sheet the top-row tiles (tree top, walkway, lake) are cut to about 180-250 px
tall, with black filler below. They still show enough to confirm, but the sheet layout is broken.

## Top 5 systemic issues

1. **The winter ground is still a slab, and it now buries things** [season-modifier] (19, 20, 21, 22, 24).
   - The walkway snow at x700-1390 y825-941 is one flat plane with a hard top edge along the railing line. It covers the
     bases of the railing posts and cuts off the near stone lantern at about y~880. It reads as a white wall or a raised
     platform, not snow lying on stone.
   - The "footprints" are now brown-grey holes at x1010-1170 y895-941 that show the cobbles through the snow. They read
     as stains or melt holes (confirmed in the 19 crops).
   - The left foreground roof at x0-400 y730-941 is still a blank white plane with no tile ridges.
   - The hanging lantern's snow cap is a mushroom dome with a translucent rim, plus the white crescent swoosh at
     x1320-1345 y500-560 (19). At night (21, 22) the dome glows blue-white, so the lantern reads as a jellyfish.
   - Real snow would follow the cobbles in soft undulations, drift against the post bases and the lantern plinths, and
     leave a trodden, darker, compacted line of prints. The posts and lanterns must always sit on top of the snow.
2. **Matte halos around silhouettes where the sky is composited** [time-modifier] (13, 15, 17; also 02, 05, 07).
   - Autumn (confirmed in the 13 and 15 crops): every maple cluster, falling leaf and pavilion roof edge, the pagoda
     outline, the spire tip and the mountain ridge carry a 3-6 px pale halo. The halo is white by day (13, 17) and
     blue-grey at night (15). At 22:00 it makes the whole tree look cut out with scissors.
   - Spring: a green-white vertical glare sits on the pavilion's right edge at x1600-1672 y590-700 (02, 05, 07), and a
     teal blob sits on the pagoda's left at x225-270 y600-680 (05, 07).
   - Fix the sky/foreground alpha instead of painting over it. A painted sky meets foliage with no rim at all.
3. **Day-plate residue still not cleaned** [time-modifier] (02, 08, 09, 11, 18, 19, 23).
   - A dark smoke column stands beside the small pagoda at x260-310 y685-750 (08, 11, 18, 19, 23; confirmed in the 18
     and 19 crops).
   - Brown-orange smears run along the far shore at x380-1300 y680-720 (02, 08, 18, 19, 23).
   - The pavilion underside glows warm cream at 11:00 and 13:00 (19, 23).
   - The grade is over-sharpened HDR: crunchy edges, a cyan rim on the hills, and saturated blue roofs under a grey sky
     (02, 08, 13, 23).
4. **Weather and sky effects draw attention to themselves** [weather-modifier / time-modifier].
   - Storm mist is still an opaque flat grey sheet with a ruler-straight top at y~600-640 from the mountain's right flank
     to x1300. Both bolts end exactly on it (06, 11; confirmed in the 06 crops). [weather-modifier]
   - New: anamorphic glints. Long vertical white flare streaks sit on the stone lanterns, the pagoda and the pavilion post
     (06, 16; confirmed in the 06 crops). They read as camera lens artifacts, which a painting does not have.
     [weather-modifier]
   - Partly cloudy clouds are still airbrush and motion-smeared (02, 09, 14). Low clouds still have straight vertical
     sides at x940-1010 y580-630 (09) and x1180-1240 y590-640 (14). [time-modifier]
5. **New templates fall back to recolour** [season-modifier] (18, 23, 08-12).
   - The shrubs at x1290-1480 y600-830 and the left-edge tree at x0-80 y560-740 are the spring blossom masses tinted tan,
     with the same flower-cluster shapes (18, 23; confirmed in crops). On Nov 20 they should be thin and mostly bare, and
     in January bare twigs.
   - In 18 the whole town (x0-1250 y700-941), walls included, is desaturated grey-white, as if a filter had been
     applied. The walkway next to it has only a dusting. Snow should lie on roof tops only, at the same depth as on the
     walkway.
   - Summer leaves are still uniform 40-55 px outlined clip-art shapes with sky between them. They are now heart-shaped
     instead of maple-shaped.
   - Spring petal specks are left on the lake in summer and winter (08, 23; red dots at x480-900 y720-790).

Recurring local artifacts [detail-orienter]:
- The green pagoda window at (160,655) (10, 12, confirmed in the 10 crops).
- The teal blob on the pagoda's left at x225-270 y600-680 (05, 07).
- Dark floating flecks around the summer twig tips at x940-1180 y300-400 (08-12).
- Blue/cyan rectangular glitch fragments in the autumn foliage at x760-850 y0-70 (17).
- Orange "fire" blobs on the near-shore lake edge at x1050-1100 y795-805 (15), and a lit yellow-green band on the far
  right shore at x1180-1260 y640-665 at 22:00 (15).

## Scores (one line per render)

| # | render | run 2 | run 3 | verdict |
|---|---|---|---|---|
| 01 | spring clear 06:05 | 3.5 | 4.0 | accept |
| 02 | spring partly_cloudy 13:00 | 2.5 | 2.5 | revise |
| 03 | spring clear 19:10 | 3.0 | 3.5 | revise |
| 04 | spring clear 22:00 | 3.5 | 4.0 | accept |
| 05 | spring rain 13:00 | 3.0 | 3.0 | revise |
| 06 | spring storm 21:00 | 3.0 | 3.0 | revise |
| 07 | spring fog 07:00 | 3.5 | 3.5 | revise |
| 08 | summer clear 13:00 | 2.5 | 2.5 | revise |
| 09 | summer partly_cloudy 19:50 | 2.5 | 2.5 | revise |
| 10 | summer clear 22:30 | 2.5 | 3.5 | revise |
| 11 | summer storm 16:00 | 3.0 | 3.0 | revise |
| 12 | summer rain 22:00 | 3.5 | 3.5 | revise |
| 13 | autumn clear 09:00 | 2.5 | 2.5 | revise |
| 14 | autumn partly_cloudy 17:45 | 3.0 | 3.0 | revise |
| 15 | autumn clear 22:00 | 2.5 | 2.0 | revise |
| 16 | autumn rain 18:20 | 3.5 | 3.5 | revise |
| 17 | autumn fog 13:00 | 3.5 | 3.5 | revise |
| 18 | autumnlate snow 13:00 (Nov 20) | 2.0 | 3.0 | revise |
| 19 | winter clear 13:00 | 3.0 | 2.5 | revise |
| 20 | winter clear 16:45 | 3.5 | 3.5 | revise |
| 21 | winter clear 22:00 | 3.5 | 3.5 | revise |
| 22 | winter snow 22:00 | 3.0 | 3.0 | revise |
| 23 | winterbare overcast 11:00 | 2.5 | 3.0 | revise |
| 24 | winter fog 08:00 | 3.5 | 3.0 | revise |

Mean: 3.1 (run 2: 3.0, run 1: 2.0). Verdicts: 2 accept, 22 revise, 0 reject (run 2: 0 / 23 / 1).
Plateau warning: the mean moved by only +0.1. Fixes in one place (lantern cap, fireflies, bare late-autumn branch)
were offset by regressions in others (autumn halos, winter slab, glints).

**Would accept as a desktop wallpaper today: 01 (spring dawn) and 04 (spring night). Nothing else.**
Next closest: 10, 12, 16, 20 and 21 (each is one or two local fixes away).

## Fixed since run 2

- The summer hanging-lantern roof is no longer a black spiky flag (08-12).
- Summer night has fireflies: small, sparse and warm, around the tree and hill (10, confirmed in crops). The summer
  leaves are graded dark at night.
- The storm lake has chop again (06, 11). The summer storm bolt is smaller and off-centre (11).
- The autumn mountain in rain is a cone again (16). The autumn sky bites beside the pagoda and the ghost tier stubs are
  no longer visible (13-17).
- The autumn pagoda and town windows are off by day (13, 17).
- The overcast sky is no longer a diagonal streak texture (23). It is now a flat grey deck with faint cloud masses.
- The lantern mirror reflections on snow are gone (22).
- Late November now has a bare, tapering branch with a few rust leaves (18). January without snow cover has a bare
  branch and no lying snow (23), which matches the updated RULES.
- The spring dusk sky now has a warm horizon glow on the right (03).

## New problems introduced

- Pale and blue-grey matte halos around all the autumn foliage, the roof, the spire and the mountain (13, 15, 17)
  [time-modifier].
- The winter snow slab now buries the railing post bases and the near stone lantern base, and the footprints became
  brown melt holes (19-21, 24) [season-modifier].
- At night the hanging-lantern snow cap glows blue-white like a jellyfish (21, 22) [season-modifier].
- Anamorphic vertical flare streaks on the lanterns, the pagoda and the pavilion post in storm and rain (06, 16)
  [weather-modifier].
- A green-white vertical glare on the pavilion's right edge in spring day frames (02, 05, 07) [time-modifier].
- The whole autumnlate town is greyscaled, and its shrubs are tan-tinted blossom masses (18). The winterbare shrubs are
  sepia-tinted blossom masses (23) [season-modifier].
- At noon on a clear summer day the walkway looks wet and glossy, with reflections at x1180-1300 y800-900 (08)
  [time-modifier].

## Per render

### 01 spring clear 06:05 — accept (4.0)
- A believable dawn: lanterns lit, a warm horizon glow behind the pagoda, sparse petals, and the lake catching
  far-shore lights.
- Minor: a pale cut-out cloud shape sits behind the right hill at x1240-1350 y565-610, and a faint lighter matte runs
  along the mountain's left flank at x240-330 y590-615. [detail-orienter]

### 02 spring partly_cloudy 13:00 — revise (2.5)
- The clouds are still airbrush. The big right-hand mass at x810-1520 y30-450 has soft smeared edges and no painted
  shading. It is the softest thing in a frame where everything else is over-sharpened. [time-modifier]
- A green-white vertical glare sits on the pavilion's right edge at x1600-1672 y640-700. Brown smears run along the far
  shore at x1060-1290 y680-720. Red petal specks lie flat on the lake at x840-900 y740-790. [time-modifier]
- The HDR grade is crunchy: a cyan rim on the mountain and hills, and green-tinted pagoda windows. [time-modifier]

### 03 spring clear 19:10 — revise (3.5)
- The horizon glow at x1300-1500 y450-640 is an improvement. The mountain is still teal-green under a 3° warm sun, when
  it should pick up peach on its west face. [time-modifier]
- Dark vertical drip marks on the lake at x800-900 y740-790 read as stains, not reflections. [time-modifier]

### 04 spring clear 22:00 — accept (4.0)
- A convincing night: sparse varied stars, lit windows and lanterns, warm pools on the walkway, and town lights
  reflected in the lake.
- Minor: a small pale cloud blob on the right hill crest at x1290-1350 y565-585 looks like a leftover matte.
  [detail-orienter]

### 05 spring rain 13:00 — revise (3.0)
- The teal blob on the pagoda's left at x225-270 y600-680 persists, and the green-white pavilion edge glare at
  x1640-1672 y600-680. [detail-orienter / time-modifier]
- The rain streaks are dense in the sky and thin out over the town and walkway, which is backwards: near streaks
  should be bigger and more visible. The lake is uniform speckle with no ring ripples. [weather-modifier]
- The blossoms and roofs stay bright and saturated under a heavy grey deck. [time-modifier]

### 06 spring storm 21:00 — revise (3.0)
- The mist is an opaque flat grey sheet with a straight top from the mountain's right flank across to x1300
  (y600-640). It erases the lower mountain and the right ridges, and the bolt (x770-920 y150-610) ends exactly on it
  (confirmed in crops). Real cloud would sit in ragged, uneven layers. [weather-modifier]
- Long vertical white flare streaks sit on both stone lanterns (x900-950 y830-920, x1250-1270 y780-920), across the
  pagoda (x120-200 y590-760) and on the pavilion post. They read as lens glints and pull the eye more than the bolt.
  Remove them, or make them short, faint rain catching lantern light. [weather-modifier]
- The bolt is still big, pure white and centred, and it lights nothing: the clouds and roofs around it stay dark.
  [weather-modifier]

### 07 spring fog 07:00 — revise (3.5)
- The fog depth is good. The pagoda (x50-270) is still far crisper and more contrasty than the small pagoda right next
  to it, and it has a teal fringe on its left at x225-270 y600-700. It looks pasted in front of the fog.
  [weather-modifier / detail-orienter]
- A row of evenly spaced soft orbs runs at x570-1000 y700-710. A bright vertical glare sits on the pavilion edge at
  x1600-1650 y620-700. [weather-modifier / time-modifier]

### 08 summer clear 13:00 — revise (2.5)
- The leaves at x830-1672 y0-400 are sparse, outlined, uniform 40-55 px heart shapes with sky between them. This is
  vector ivy clip-art, not a summer canopy. A real summer canopy is dense and overlapping, and the leaves get smaller and
  darker toward the interior. Dark flecks float off the twig tips at x940-1180 y300-400. [season-modifier /
  detail-orienter]
- Residue: a smoke column beside the small pagoda, brown smears on the far shore, and red petal specks on the lake.
  The walkway is glossy and wet-looking at x1180-1300 y800-900 under a clear noon sky.
  [time-modifier / season-modifier]
- The lantern cap is fixed and the shrubs right of the walkway are properly green.

### 09 summer partly_cloudy 19:50 — revise (2.5)
- Low clouds by the mountain have rectangular vertical sides at x940-1010 y580-630. The big pink masses at x0-180 and
  x1030-1500 are smeared airbrush. [time-modifier]
- At a 4.8° sun the leaves stay flat bright yellow-green and ungraded. The flecks around the twig tips persist.
  [season-modifier / time-modifier]

### 10 summer clear 22:30 — revise (3.5)
- Fireflies are now present, which is a RULES pass. They are so small and few that at full frame they are nearly
  invisible. A few slightly larger, warmer ones low over the shrubs (x1300-1480 y640-830) would read.
  [season-modifier]
- The green pagoda window at (160,655) is confirmed. [detail-orienter]
- The leaves are graded dark, the lantern is fixed, and the sky is good.

### 11 summer storm 16:00 — revise (3.0)
- The bolt is smaller and off-centre (better). It still ends in mid-air on a straight bright mist line at y~625-635
  (x1010-1250). [weather-modifier]
- The leaves stay pale grey-green with dark outlines and glow against the storm sky. [season-modifier]
- The smoke column beside the small pagoda at x260-310 y690-720 remains. The lake chop is back (good).
  [time-modifier]

### 12 summer rain 22:00 — revise (3.5)
- Still the best summer frame: a dark sky, a wet walkway with lantern reflections, and drips under the hanging lantern.
- At intensity 0.4 the rain is close to invisible over the town and lake, and there are no ripples.
  [weather-modifier]
- The green pagoda window at (160,655). [detail-orienter]

### 13 autumn clear 09:00 — revise (2.5)
- White halos around every maple cluster, falling leaf and roof edge against the sky at x760-1672 y0-360, and a yellow
  rim along the mountain's right flank (confirmed in crops). The leaves look like stickers with a white border.
  [time-modifier]
- The sun disc sits on the spire with a large soft bloom at x110-210 y330-410. The frame is over-saturated HDR, with
  blown yellow on the walkway and a glaring yellow band on the far right shore at x1000-1240 y630-660.
  [time-modifier]
- The windows are now off (fixed).

### 14 autumn partly_cloudy 17:45 — revise (3.0)
- The big cloud at x0-790 y0-540 is still diagonal motion-smeared airbrush. The cloud right of the mountain ends in
  vertical rectangular pillars at x1180-1240 y590-640. [time-modifier]
- The crescent moon at (1180,420), the lit lanterns and the warm light are all plausible.

### 15 autumn clear 22:00 — revise (2.0)
- Blue-grey halos outline the whole tree, every falling leaf, the pavilion roof, the pagoda (with a cyan glow on the
  spire tip) and the mountain ridge, all confirmed in crops. At night this is the dominant feature of the frame.
  [time-modifier]
- The far right shore at x1180-1260 y640-665 is lit yellow-green at 22:00. Orange fire-like blobs sit on the
  near-shore water at x1050-1100 y795-805. [time-modifier / detail-orienter]
- Red ember specks are scattered through the town at x300-360 y740-800. [season-modifier]

### 16 autumn rain 18:20 — revise (3.5)
- The mood, mist and cone mountain are all good.
- The glint streaks remain: bright vertical bars over the pagoda at x130-200 y700-760, over the far lake at
  x1090-1110 y680-720, and at the lantern at x1190-1220 y780-910. The far ones are as big as the near ones.
  [weather-modifier]

### 17 autumn fog 13:00 — revise (3.5)
- The fog is right: the mountain is hidden, the lake is gone, the near scene stays legible, and the windows are off.
- White halo fringes run around the foliage. Blue/cyan rectangular glitch fragments sit in the leaves at x760-850
  y0-70. [time-modifier / detail-orienter]
- The pagoda stays crisp and contrasty in front of the fog, and the pavilion has a vertical glare at x1600-1650
  y620-700. [weather-modifier / time-modifier]

### 18 autumnlate snow 13:00 (Nov 20) — revise (3.0)
- The structure is right now: a bare tapering branch with a few rust leaves, and a light dusting with leaf litter on
  the walkway. That fits the updated RULES for late November at intensity 0.4.
  - The remaining leaves are pale outlined stickers, and two float unattached at x885-910 y360-400 and x925-945
    y310-350. [season-modifier]
- The town (x0-1250 y700-941) is greyscaled wholesale, walls and all. It reads as a pencil sketch, not snow on roofs,
  and it does not match the near walkway's light dusting. The shrubs at x1290-1480 y600-830 and x0-80 y560-740 are
  full tan blossom masses (confirmed in crops). [season-modifier]
- The smoke column beside the small pagoda at x260-310 y690-750 is very visible against the white town (confirmed).
  The flakes are uniform round discs. [time-modifier / weather-modifier]

### 19 winter clear 13:00 — revise (2.5)
- The walkway is a raised white slab with a hard top edge at the railing. It buries the post bases and the near
  lantern base, and the footprints are brown melt holes at x1010-1170 y895-941 (confirmed in crops). The left
  foreground roof is a blank white plane. [season-modifier]
- The sun at (1020,305) has a large CG bloom. The pavilion underside glows orange at noon (x1260-1480 y370-430). The
  smoke column beside the small pagoda is confirmed. [time-modifier]
- The lantern has a mushroom snow cap with the white swoosh at x1320-1345 y500-560 (confirmed). There is no visible
  near-shore ice. [season-modifier]

### 20 winter clear 16:45 — revise (3.5)
- The best snowy frame: dusk glow, lit lanterns, a snow-capped pagoda and a bare branch.
- The same walkway slab and brown footprint holes as 19, and the blank foreground roof. [season-modifier]
- A pale ragged band along the near shore (x430-1250 y770-790) reads as a snowy bank. It does not read as ice.
  [season-modifier]

### 21 winter clear 22:00 — revise (3.5)
- The night sky, lit windows and roof snow work.
- The walkway slab and holes are the same as 19. The hanging lantern's snow dome glows blue-white at x1275-1345
  y478-505 and reads as a jellyfish. Snow on the cap should be dark grey-blue on top with warm light under the rim.
  [season-modifier]

### 22 winter snow 22:00 — revise (3.0)
- Fixed: no mirror reflections on the snow.
- The walkway at x840-1390 y835-941 is now a flat dark grey plane with a hard bright curved edge. It reads as wet
  asphalt, not a fresh blanket. Fresh snow at night under lanterns is pale blue-grey with warm pools, and it drifts
  against the railing. [season-modifier / weather-modifier]
- The snowfall is moderate rather than "thick", and the far-shore lights stay sharp points behind it.
  [weather-modifier]
- The lantern dome is blue as in 21. [season-modifier]

### 23 winterbare overcast 11:00 — revise (3.0)
- A bare branch and no lying snow, which is correct for 0 cm snow depth. The sky is a calm grey deck now.
- The shrubs at x1290-1480 y600-830 and x0-80 y560-740 are the spring blossom clusters tinted sepia (confirmed in
  crops). Dormant shrubs would be a brown tangle of twigs. Red petal specks lie on the lake at x480-900 y720-790.
  [season-modifier]
- The light is wrong for overcast: saturated blue roofs, crisp HDR edges and a warm-lit pavilion underside. Add the
  smoke column beside the small pagoda and the brown far-shore smear. [time-modifier]

### 24 winter fog 08:00 — revise (3.0)
- The fog falloff and the lantern halos are good.
- The pagoda's windows bloom into large white glows on every tier (x100-260 y500-830), brighter than the lanterns.
  A row of evenly spaced orbs runs at x500-1050 y695-705. [time-modifier / weather-modifier]
- The walkway slab has the brown footprint holes at x1010-1170 y900-941, still clearly visible through the fog.
  [season-modifier]
