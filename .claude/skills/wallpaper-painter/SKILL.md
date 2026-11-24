---
name: wallpaper-painter
description: How to create or modify images for the Chicago dynamic wallpaper (season templates, weather effects, time-of-day lighting) to a detailed, realistic standard, and how to review them. Load before touching anything under templates/ or render/.
---

# Wallpaper painter

The wallpaper is ONE painted scene (Japanese lakeside town, five-tier pagoda left, snow-capped
volcano centre, lake, wooden pavilion with hanging lantern right, stone walkway with two stone
lanterns, wooden railing, a tree branch across the top right). Every image must keep this exact
composition. We change season, weather and time of day — never the layout.

Build-time tools: code (numpy / OpenCV) on the painted templates, plus LOCAL AI image editing via mflux
(FLUX.2 klein 4B, free/offline on this Mac: `~/.local/bin/mflux-generate-flux2-edit`, `mflux-generate-fill`,
`mflux-upscale-seedvr2`) for structural edits a filter can't do. The live wallpaper itself never uses AI.
Python: always `/Users/preetpatel/Documents/wallpapers/.venv/bin/python`.
Agents: `.claude/agents/*.md`. Iteration protocol: `LOOP.md` next to this file.

## Pipeline (who does what)

1. **Season templates** — `templates/<season>_clear_<time>.png`, 1672x941, same composition.
   `spring_clear_night.png` (original painting) and `autumn_clear_golden.png` (painted, real)
   exist. Summer/winter are derived from spring by the season painters.
2. **Time of day** — `render/timeofday.py` turns a template into any moment: real sun/moon
   (`render/astro.py`), sky gradient, painted clouds, lanterns on/off, lake reflection.
   Night-lit templates get a colour-recovered day plate; golden templates get a day-for-night grade.
3. **Weather** — `render/effects/<module>.py`, `apply(img, ctx) -> img`, runs on the finished
   frame (see `render/effects/__init__.py` for the ctx contract). `rain`, `storm`, `fog`, `snow`.
4. **Runtime** — `dynamic_wallpaper.py` renders the current Chicago moment every 30 min.

## Coordinates

- Templates are 1672x941 ("base px"). Output is 3840x2160 (env WALLPAPER_W/H); `SX = 3840/1672 ≈ 2.297`. 4K masters: templates/4k/.
- Hand-placed geometry (base px) lives in: `render/masks.py` (HORIZON, PAGODA, PAVILION, MOON),
  `render/timeofday.py` (LAKE), `render/tod_plates.py` + `render/season_winter.py` (walkway, railing, lantern geometry).

- Key spots: moon painted at (446,127) r56; hanging lantern ~(1280-1340, 475-570);
  stone lanterns ~(890-960, 790-900) and (1245-1290, 752-840); lake far shore y≈700, near
  shore y≈785-792 between x≈262 and 1268; walkway bottom-right below the railing; tree branch
  zone y<345, x>740; shrubs at far left (x<70, y 520-760), right of walkway (1290-1480, 640-830),
  bottom-right corner.
- `render/depth.npy` (base px, 0 near .. 1 sky) — `A.depth` at output size.

## Realism rules

Read `RULES.md` in the project root. Every image must satisfy every rule for its condition.

## Quality bar (be detail-specific)

- **Match the painting.** Keep the painted anime-illustration look: crisp edges, painterly
  texture, saturated but controlled colour. Never blur a region to hide a problem. New
  elements must have the same sharpness, outline weight and shading style as nearby paint.
- **Structure before colour.** Recolouring alone is not enough (white-recoloured blossoms read
  as white flowers, not snow; pink-to-green blossoms read as green flowers). Change *shapes*
  where the real thing has a different shape (bare twigs, leaf clusters, snow lying on top
  surfaces with thickness and overhang).
- **Everything connects.** Twigs connect to branches, branches taper, snow sits on top of
  surfaces, reflections sit directly below their source, rain streaks are in front of what
  they cover. No floating fragments.
- **Light is consistent.** One light state per frame: moon/sky light + lantern light at night,
  sun at day. Lit surfaces near lanterns are warm; snow and wet stone pick up lantern colour.
- **No hard mask edges, no rectangles, no straight cut lines.** Feather 1-3 px at output res,
  follow real object outlines. Any visible polygon edge is a failure.
- **Scale with depth.** Particles, texture, contrast and detail shrink/soften with distance
  (use `A.depth`).

### What the user rejected before (don't repeat)

- Snowy winter attempt: blossoms turned white still looked like flowers; procedural twigs were a
  radial "starburst" and floating segments; walkway snow was a flat grey/white sheet that read
  as a wall or frosted glass with stone pattern showing through; hard polygon edge on the path;
  lake ice as a straight grey stripe; pink tint left on shrubs.
- Daytime: unlit lanterns look like ghostly translucent grey boxes; blocky light reflections
  on the lake; mist smudges where lights were removed.

## Review loop (mandatory, at least 3 rounds)

1. Render with `render/preview.py SEASON WEATHER "YYYY-MM-DD HH:MM" PREFIX` into your own
   scratch folder. Check at least: a day time (13:00), golden/dusk, and night (22:00).
   Season → month: winter Jan, spring Apr, summer Jul, autumn Oct.
2. **Read both** `PREFIX_full.png` and `PREFIX_crops.png`. Crops are full resolution — that's
   where problems show.
3. Write down every defect against the quality bar and RULES.md, fix, re-render. Stop only
   when a round finds nothing you'd be embarrassed to show the user.
4. Report: what you changed, the preview paths of your final round, remaining known issues.

## Benchmark rubric (checker scores 1-5 each)

style match · composition intact · realism rules satisfied · structure (not just recolour) ·
light consistency · edges/artifacts · depth/scale · overall "would set as wallpaper".

## Ground rules for agents

- Only edit files you own (your prompt lists them). Never edit `render/timeofday.py`,
  `render/effects/__init__.py`, `render/preview.py`, `render/masks.py` unless you own them.
- Never run `install.sh`, never change the user's wallpaper, never touch `~/Library`.
- Scratch output goes in your own folder under the scratchpad given in your prompt.
- Keep files importable at all times (other agents render concurrently).
