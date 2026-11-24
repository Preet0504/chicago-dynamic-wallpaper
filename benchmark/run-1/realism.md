# Realism review — run 1 (baseline)

Coordinates are base px (1672x941). Multiply by 1.531 for output px.
Verdict key: accept / revise / reject. Score = 1-5 realism ("would a viewer believe this is the same painting at that moment").

## Top 5 systemic issues

1. **Winter template is unusable** [season-modifier] (19-24). Snow is a lumpy "popcorn / cotton-wool" texture.
   It is pasted on vertical surfaces too: pavilion walls and posts x1480-1672 y380-720, and the pagoda's mid tiers,
   which have grey smeared patches. Shrubs are piles of identical white balls. The walkway is a flat beige sheet with
   no stone, drift or footprint structure, which repeats the rejected "frosted glass" look. There is no ice on the near
   shore, and white popcorn columns drip into the lake at x700-1000 y700-790. The top-right tree branch is gone. What
   remains is dotted contrail-like dashes at x1050-1672 y0-100, ghost blossom silhouettes in the sky (22), or fully
   white-recoloured blossoms (23, the exact rejected failure). Snow should lie on top surfaces only, with thickness,
   a soft rounded edge and a slight overhang. The branch should be bare, dark and tapering.
2. **Summer template keeps spring and adds clip-art leaves** [season-modifier] (08-12). The branch foliage is flat,
   saturated green "crumpled polygon" tiles at x800-1672 y0-190. No bark or twigs are visible, so the clusters float.
   The fill is denser and harsher than the painting's brushwork. Pink cherry blossom stays on every left tree, on the
   shrubs right of the walkway and in the bottom-right corner. White petals still fall in the sky. RULES: summer means
   full green leaves and no petals, plus fireflies at night (missing in 10 and 12).
3. **Daytime light-off state is wrong** [time-modifier] (02, 03, 05, 07, 08, 09, 11, 13, 14, 17, 18, 19, 23, 24).
   Unlit lanterns are translucent grey "ghost boxes" with a soft halo, which repeats a rejected defect: hanging
   lantern ~(1280-1340, 480-570), stone lanterns (890-960, 790-900) and (1245-1290, 752-840). The far-shore town lights
   and the pagoda and house windows stay lit at 09:00-13:00. The lake keeps vertical streak reflections of those lights
   at x550-1200 y700-790. Where lights were removed, white mist blobs remain on the lake: 02, and especially 13/18 at
   x1000-1200 y750-790. A real daytime lantern is opaque, with wood frame and paper reading solid and matte. Day
   windows are dark or reflect sky, and there are no point-light reflections.
4. **Sky elements look procedural** [time-modifier] (04, 10, 15, 21; 02, 09, 14; 18, 23). The night "clouds" are
   scattered white scribble fragments in diagonal bands. At wallpaper size they read as bird flocks or blowing snow,
   not clouds. The star field is uniform, too dense and the same brightness everywhere, with one cross-sparkle star at
   (760,120) in every night frame. The partly-cloudy clouds are fractal flecks with hard cut-out edges and the same
   layout in 02, 09 and 14. The overcast/snow daytime frames (18, 23) show stars and a hard moon disc at (446,127) in a
   grey daytime sky. Night sky needs fewer, varied stars and soft cloud masses. Overcast day needs one even cloud deck
   with at most a diffuse bright patch where the sun is.
5. **Weather effects are filters, not weather** [weather-modifier]. Storm "choppy water" is a tiled scallop/fish-scale
   stamp across the whole lake x400-1250 y700-790 (06, 11). Real chop is short, irregular, broken highlights that shrink
   with distance. Mist on the mountain is a flat grey band with a straight top edge cutting the cone (05, 06, 11, 12, 16).
   Fog (07, 17, 24) is one flat, evenly opaque beige sheet with no depth falloff and no halos. Snow weather (18, 22)
   is recolour-only: no flakes, no fresh blanket, no mountain haze. Rain-lake ripples are uniform speckle noise (05, 16).

Recurring local artifacts [detail-orienter]:
- A grey rectangle behind the pagoda's upper tiers at x185-210 y300-600 in every spring/summer frame. It shows most
  clearly in 01, 06 and 12.
- A translucent box with straight edges around the small far pagoda at x260-400 y690-790 (01, 19, 20).
- A white/pale-blue matte fringe along the pavilion roof crest at x1250-1420 y300-345 in every autumn frame.
- A white rim on the right-hand hill crest at x1180-1330 y600-640 (13, 18).
- Two dark ghost-figure streaks on the autumn walkway at x1200-1265 y790-900 (13, 14, 17, 18).
- A cyan halo on the pagoda's left silhouette at x230-270 y600-700 (05, 07, 11, 17).

## Scores (one line per render)

| # | render | score | verdict |
|---|---|---|---|
| 01 | spring clear 06:05 | 3.0 | revise |
| 02 | spring partly_cloudy 13:00 | 2.0 | revise |
| 03 | spring clear 19:10 | 2.5 | revise |
| 04 | spring clear 22:00 | 2.0 | revise |
| 05 | spring rain 13:00 | 2.5 | revise |
| 06 | spring storm 21:00 | 2.5 | revise |
| 07 | spring fog 07:00 | 2.5 | revise |
| 08 | summer clear 13:00 | 1.5 | reject |
| 09 | summer partly_cloudy 19:50 | 1.5 | reject |
| 10 | summer clear 22:30 | 1.5 | reject |
| 11 | summer storm 16:00 | 1.5 | reject |
| 12 | summer rain 22:00 | 2.0 | reject |
| 13 | autumn clear 09:00 | 2.5 | revise |
| 14 | autumn partly_cloudy 17:45 | 3.0 | revise |
| 15 | autumn clear 22:00 | 2.0 | reject |
| 16 | autumn rain 18:20 | 3.5 | revise |
| 17 | autumn fog 13:00 | 2.5 | revise |
| 18 | autumn snow 13:00 (Nov 20) | 1.0 | reject |
| 19 | winter clear 13:00 | 1.5 | reject |
| 20 | winter clear 16:45 | 2.0 | reject |
| 21 | winter clear 22:00 | 1.5 | reject |
| 22 | winter snow 22:00 | 1.0 | reject |
| 23 | winter overcast 11:00 | 1.0 | reject |
| 24 | winter fog 08:00 | 1.5 | reject |

Mean: 2.0. Verdicts: 0 accept, 11 revise, 13 reject.

## Per render

### 01 spring clear 06:05 — revise (3.0)
- The grey rectangle behind the pagoda spire at x185-210 y300-600 reads as a pasted patch against the dawn gradient.
  The sky should run continuously behind the spire. [detail-orienter]
- There is a pale smudge box around the small pagoda at x270-300 y690-740, and the hanging lantern has a square haze
  blob around it. Light from a small lantern is a tight warm falloff, not a grey square. [time-modifier]
- The dawn glow sits low-left. Check against the astro.py azimuth that the glow is on the sunrise side. Otherwise this
  is the most believable frame. [time-modifier]

### 02 spring partly_cloudy 13:00 — revise (2.0)
- Ghost lanterns: hanging and stone lanterns are see-through grey with halos. Far-shore lights and their vertical lake
  streaks stay on at noon, and white mist columns remain on the lake at x830-950 y740-790. [time-modifier]
- The day plate is over-sharpened and over-saturated, with a crunchy HDR look. There is a cyan rim on the mountain's
  left flank and on the hills. Blossoms are de-pinked to near-white, so with the white falling petals the scene reads
  close to snow. [time-modifier]
- The clouds are fragmented fractal flecks with hard edges (x0-520 y0-500, x780-1250 y280-560). They are denser and
  noisier than the painting's own soft cloud strokes. [time-modifier]

### 03 spring clear 19:10 — revise (2.5)
- The sun is at +3°, but the lanterns are ghost-grey boxes. RULES: dusk/dawn means lanterns on. They should be lit,
  or at minimum opaque. [time-modifier]
- The sky is a flat CG two-stop gradient (blue to peach) with no cloud or sun glow structure near the horizon. The
  mountain has a teal cast that doesn't match warm low sun. [time-modifier]
- The pagoda rectangle and the smudge left of the small pagoda (x285 y700-740) persist. [detail-orienter]

### 04 spring clear 22:00 — revise (2.0)
- The diagonal bands of white scribble "clouds" (x0-1300 y60-560) read as bird flocks or snow, not cloud. This is the
  single most fake element in the night set. [time-modifier]
- The stars are uniform and too dense, with no variation in brightness or size, and there is a lone cross-sparkle at
  (760,120). There is no moon (correct for the 2026-04-15 phase), but a bright moon-like glint stays on the lake at
  x460-500 y760-780 with no source. [time-modifier]
- The hanging lantern's glow is a square haze. [time-modifier]

### 05 spring rain 13:00 — revise (2.5)
- The rain streaks sit mostly in the sky band. Over the foreground (walkway, pavilion, railing) they are sparse to
  absent, so rain does not read as in front of the scene. Lake "ripples" are uniform speckle noise across the whole
  lake. [weather-modifier]
- The mist band across the mountain has a flat horizontal top edge at y~540. Low cloud should have a ragged edge and
  thin out with height. [weather-modifier]
- Ghost lanterns, plus a cyan halo on the pagoda's left edge at x230 y640. Blossoms are washed to grey-white.
  [time-modifier]

### 06 spring storm 21:00 — revise (2.5)
- Lake chop is a tiled fish-scale stamp of white scallops at x400-1250 y700-790. It looks like a cobbled texture, not
  water. [weather-modifier]
- The lightning does not light anything: sky, mountain and lake stay uniformly dark at the moment of a strike. Either
  lift the clouds near the bolt and add a cool rim on the mountain and roofs, or draw the bolt fainter and more distant.
  [weather-modifier]
- The blown petals are dark brown-red blobs and read as dead leaves or blood specks, not cherry petals. The pagoda
  rectangle is visible against the black sky at x185-210 y460-600. [weather-modifier / detail-orienter]

### 07 spring fog 07:00 — revise (2.5)
- The fog is one flat beige-grey sheet with no depth gradient. The near town, the far town and the sky all get the same
  milkiness. Real fog falls off with distance: near roofs crisp, mid town soft, far shore gone. [weather-modifier]
- Vertical light-streak reflections still show through the fog on the lake at x550-1200 y710-760. With far lights
  hidden, these should be gone. [time-modifier]
- There is a teal fringe on the pagoda's left silhouette at x240-270 y610-700, and the lanterns are ghost boxes with no
  fog halo. RULES asks for halos around lights; at 07:00 the lanterns could stay on in fog. [detail-orienter / time-modifier]

### 08 summer clear 13:00 — reject (1.5)
- The leaves are clip-art green polygon tiles with no branch or twigs (x800-1672 y0-190, confirmed in crops). Their
  style is foreign to the painting. [season-modifier]
- Cherry blossom remains everywhere (left trees, right shrubs, bottom-right corner), and white petals fall in the sky.
  This is spring with a green sticker. [season-modifier]
- Ghost lanterns, far-shore lights lit at noon, and streak reflections on the lake. [time-modifier]

### 09 summer partly_cloudy 19:50 — reject (1.5)
- Same template failures as 08: polygon leaves, pink blossoms, falling petals. [season-modifier]
- The pink-lit flecked clouds have the same layout as 02 and 14. The sun is at +4.8°, yet the lanterns are ghost-grey
  boxes. [time-modifier]

### 10 summer clear 22:30 — reject (1.5)
- No fireflies (RULES: summer night). Blossoms are still present and turned violet. [season-modifier]
- The leaves render as dark polygon confetti against the stars. [season-modifier]
- The night sky has the scribble-cloud flocks and a uniform star field. [time-modifier]

### 11 summer storm 16:00 — reject (1.5)
- The season content is wrong (pink blossoms, polygon leaves). [season-modifier]
- Lake chop is the same tiled scallop stamp as 06, and here it is bright white across the whole lake. [weather-modifier]
- A daytime storm with ghost lanterns. A dark storm afternoon is exactly when lanterns should be lit. The mist band on
  the mountain has a straight edge. [time-modifier / weather-modifier]

### 12 summer rain 22:00 — reject (2.0)
- The rain mood works (wet path reflections under the lanterns are good), but the season reads as spring: violet
  blossoms and polygon leaves. [season-modifier]
- A flat grey mist stripe with straight top and bottom edges (y~545-600) cuts the mountain in half.
  [weather-modifier]
- At intensity 0.4 the rain streaks are almost invisible, and the lake shows no rain ripples. [weather-modifier]

### 13 autumn clear 09:00 — revise (2.5)
- Every pagoda and house window glows warm at 09:00, the far-shore lights are lit, and ghost lanterns again. White
  mist blobs on the lake at x1000-1200 y750-790 (where lights were removed) repeat a rejected defect. [time-modifier]
- A white matte fringe runs along the pavilion roof crest (x1250-1420 y300-345), and a white rim sits on the right
  hill (x1180-1330 y600-640). Two dark ghost-figure streaks stand on the walkway at x1200-1265 y790-900.
  [detail-orienter]
- The whole frame is over-sharpened with blown yellow highlights on the walkway. The sun disc sits exactly behind the
  pagoda spire with a large bloom, which looks staged. [time-modifier]

### 14 autumn partly_cloudy 17:45 — revise (3.0)
- The lake has blocky rectangular reflection ghosts at x830-1100 y700-770. [time-modifier]
- The sun is at +3.8° with the lanterns off as ghost boxes. A golden-hour frame should have them lit or at least
  opaque. [time-modifier]
- Same flecked cloud layout as 02 and 09. The crescent moon is plausible; check that the lit limb faces the sun.
  [time-modifier]

### 15 autumn clear 22:00 — reject (2.0)
- The lake reflections are blocky orange rectangles at x830-1230 y690-770, confirmed in crops. This is the exact "blocky
  light reflections" the user rejected. Real reflections are thin, broken vertical streaks directly under each light.
  [time-modifier]
- The autumn leaves' warm highlights survive the night grade as glowing orange specks, at the tree top and across the
  town. They read as embers or fairy lights. [time-modifier]
- Scribble-cloud flocks in the night sky, and the pavilion roof-crest fringe now shows as a pale blue band.
  [time-modifier / detail-orienter]

### 16 autumn rain 18:20 — revise (3.5)
- The best weather frame. Remaining: a mist band with a hard top edge cuts the mountain at y~545-560. The peak floats
  above it like a separate cut-out, and its jagged twin-peak shape differs from the cone in the other seasons. Either
  cover more of it or soften the band. [weather-modifier]
- The orange leaf specks glow at dusk (x1100-1300 y60-180 and the town) — same grading problem as 15. [time-modifier]
- The lake rain texture is uniform speckle. Ripples should be concentric and denser near the shore.
  [weather-modifier]

### 17 autumn fog 13:00 — revise (2.5)
- The fog is a flat even grey sheet, and the trees and pavilion in the foreground are too saturated and sharp for a
  scene in fog this thick. With no aerial-perspective gradient, it looks like a paste-over. [weather-modifier]
- Town windows are lit at 13:00, the lanterns are ghost boxes with no halos, and the walkway ghost streaks are at
  x1200-1265 y790-900. [time-modifier / detail-orienter]
- A cyan blob sits on the pagoda's left at x240-270 y610-650. [detail-orienter]

### 18 autumn snow 13:00 (Nov 20) — reject (1.0)
- Recolour-only: no snow on the ground, roofs or lanterns, and no flakes. Under RULES, snowing requires a fresh
  blanket, caps and flakes. [weather-modifier]
- Late November should be mostly bare, but the tree is in full red/gold foliage, and white petals fall. [season-modifier]
- A grey sky with stars and a hard moon disc at (446,127) at 13:00. The foreground stays sunlit and saturated under a
  grey sky, so the light is inconsistent. [time-modifier]

### 19 winter clear 13:00 — reject (1.5)
- Popcorn snow on walls, posts and shrubs. Lake drips at x700-1000 y700-790. No shore ice. The flat walkway sheet has
  an orange lantern-light blob at noon. [season-modifier]
- The tree branch is missing; only dotted dash marks remain at x1050-1672 y0-100. The snow cap on the hanging lantern
  is offset right, with a stray white curve at x1320-1360 y520-545. [season-modifier / detail-orienter]
- Ghost lanterns. The sun is a large flat disc with a big bloom, which is acceptable but CG-looking. [time-modifier]

### 20 winter clear 16:45 — reject (2.0)
- The dusk sky and the lit lanterns are right. The snow structure is the same popcorn failure as 19, and the
  walkway is a flat sheet with no drifts at the railing or lantern bases. [season-modifier]
- A translucent box with straight edges sits around the small pagoda and lake at x260-400 y690-790. [detail-orienter]
- There is no ice along the near shore: the lake reflects liquid-clear at -10 °C January dusk. [season-modifier]

### 21 winter clear 22:00 — reject (1.5)
- Popcorn snow, no ice, and the tree branch is missing. Ghost blossom outlines sit in the sky at x1050-1672
  y0-200. [season-modifier]
- Scribble-cloud flocks across the whole sky. [time-modifier]

### 22 winter snow 22:00 — reject (1.0)
- No falling snow (known), and the mountain is crisp with no haze. Under RULES, snowing requires low visibility.
  The frame is identical to 21 minus stars, so it is a recolour. [weather-modifier]
- Dark cherry-blossom silhouettes show in the sky at x820-1672 y0-200 (confirmed in crops). Winter must have no
  blossoms. [season-modifier]
- The "lantern light pool on snow" is a few orange splotches at x960-1000 y900-935, not a warm falloff around the
  lantern bases. [time-modifier]

### 23 winter overcast 11:00 — reject (1.0)
- The full blossom branch is recoloured white/grey, with falling petals. This is literally the previously rejected
  "white blossoms read as flowers". [season-modifier]
- Daytime overcast with visible stars, a hard moon disc at (446,127) and discrete flecked clouds. Overcast means an
  even deck with no stars or disc. [time-modifier]
- Popcorn snow and ghost lanterns. [season-modifier / time-modifier]

### 24 winter fog 08:00 — reject (1.5)
- Popcorn snow stays crisp and bright in front of the fog. On the pavilion walls it is the most legible element in
  the frame, so the snow looks pasted on top of the fog. [season-modifier]
- The fog is a flat beige sheet. Under RULES, fog needs halos around lights, yet the lanterns are ghost boxes at 08:00
  in fog, where they would plausibly be on. [weather-modifier / time-modifier]
- Dash marks at the top edge (x1050-1672 y0-20) are leftovers of the missing branch. [season-modifier]
