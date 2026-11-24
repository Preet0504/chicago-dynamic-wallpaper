# Chicago Dynamic Wallpaper

A painted Japanese lakeside scene that is re-rendered every 30 minutes to match **Chicago right now**:
the real sun and moon (position and phase), cloud cover, rain/storm/fog/snowfall, the season, and whether
there is actually snow on the ground. Output is a native **3840×2160** frame set on every display.

Everything is free and local. The live wallpaper uses **no AI at all**. AI is used once, at build time, to
paint the season templates and upscale them to 4K, and it runs offline on this Mac.

---

## How an image is made

```
templates/<scene>.png (painted, 1672×941)        templates/4k/<scene>.png (AI-upscaled master)
        │                                                   │
        ▼                                                   │
 render/timeofday.py  ── astro.py: real sun/moon alt-az + moon phase for Chicago
        │   • day plate   (night painting → white-balanced daylight, lanterns switched off)
        │   • night plate (golden painting → day-for-night grade, lanterns kept on)
        │   • blend by sun altitude, rebuild the sky (gradient, painted-style clouds, stars, sun, moon)
        │   • lake reflects the new sky, lanterns on from dusk to dawn, fireflies on summer nights
        │   • 4K: fine detail from the AI master is added back on top of the graded plate  ◄──┘
        ▼
 render/effects/{rain,fog,snow}.py   (only when it's actually raining / foggy / snowing / storming)
        ▼
 frame 3840×2160  →  bin/setwallpaper (all displays)
```

### Scene (template) selection — `dynamic_wallpaper.py`
| Condition | Scene |
|---|---|
| Open-Meteo `snow_depth` ≥ 2 cm (any month) | `winter` (snow lying everywhere) |
| Dec–Feb, no snow on the ground | `winterbare` (bare trees, dormant grass) |
| Nov 15–30 | `autumnlate` (mostly bare, rust leaves, litter) |
| Sep–Nov 14 | `autumn` |
| Jun–Aug | `summer` |
| Mar–May | `spring` (the original painting) |

Weather comes from the WMO code (drizzle → light rain … downpour, flurries … heavy snow, fog, thunderstorm);
cloud cover drives clear / partly cloudy / overcast. Rules every image must satisfy are in [RULES.md](RULES.md).

### Where the templates come from
| Template | Source |
|---|---|
| `spring_clear_night.png` | the original painting (by the user) |
| `autumn_clear_golden.png` | a second painting of the same scene, non-rigidly warped onto the spring geometry by `render/align_autumn.py` (raw copy in `templates/originals/`) |
| `winter_clear_night.png`, `summer_clear_night.png`, `autumnlate_clear_night.png`, `winterbare_clear_night.png` | derived from the spring painting by `render/season_<scene>.py`: a procedural "guide" (blossoms removed, roofs/ground prepared) is cut into overlapping tiles and run through **FLUX.2-klein-4B** img2img (strength 0.4); only regions that should change are composited back, everything else stays pixel-identical |
| `templates/4k/*.png` | **SeedVR2** AI upscale of each template (`tools/upscale_templates.sh`) |
| later targeted fixes | **Qwen-Image-Edit 2.1** region edits (`tools/ai_region_edit.py`), logged in `templates/ai/edits.jsonl` |

All AI outputs that a template depends on are saved in `templates/ai/` with their prompts, so every
template rebuilds byte-identically without re-running the AI.

---

## Reproduce from scratch

Requirements: Apple-silicon Mac (16 GB works; 32 GB+ recommended for 4K and the local critic), Python 3, Xcode CLT (`swiftc`).

```sh
cd ~/Documents/wallpapers
python3 -m venv .venv && .venv/bin/pip install numpy opencv-python-headless scipy

# 1. scene analysis (masks, depth) — automatic on first render, or explicitly:
.venv/bin/python render/masks.py /tmp/masks_vis.png
.venv/bin/python render/depth.py /tmp/depth_vis.png

# 2. season templates — rebuild from the saved AI outputs (no AI needed):
.venv/bin/python render/align_autumn.py
.venv/bin/python render/season_winter.py
.venv/bin/python render/season_summer.py
.venv/bin/python render/season_autumnlate.py
.venv/bin/python render/season_winterbare.py

# 3. 4K masters (local AI upscaler, ~1-2 min each on an M5 Max):
uv tool install mflux            # provides mflux-* commands in ~/.local/bin
tools/upscale_templates.sh

# 4. preview any moment, then install the live wallpaper
.venv/bin/python render/preview.py winter snow "2026-01-15 22:00" /tmp/w   # writes /tmp/w_full.png + _crops.png
./install.sh                     # LaunchAgent: renders at login and every :00 / :30
./install.sh uninstall           # removes it
```

To regenerate the AI parts themselves instead of reusing saved outputs, each `render/season_*.py`
docstring lists the exact `mflux` command, model, seed and prompt file; `--tiles DIR` writes the guide tiles.

Try a moment by hand (also sets it as the wallpaper until the next update):
```sh
.venv/bin/python dynamic_wallpaper.py --at "2026-07-15 21:30" --cover 0.2          # summer night, fireflies
.venv/bin/python dynamic_wallpaper.py --scene winter --weather snow                # force snowfall
```

---

## Quality loop (how it is improved)

- **Benchmark**: `render/benchmark.py` renders the same 24 conditions (every season, weather and light) into
  `benchmark/run-N/`. `--summary` compares runs.
- **Local critic (free)**: `tools/critic.py benchmark/run-N` scores each frame on an 8-point rubric and lists
  defects using a vision model in Ollama (`qwen3.5:122b` or `inkling-2-mini`). Its scores track the Claude
  checker closely (e.g. 4.12 vs 4.12, 3.25 vs 3.12 on the same frames).
- **Agents** (`.claude/agents/`): season / weather / time modifiers, template-creator, detail-orienter and
  checker run on Haiku with Opus as advisor (`advisorModel` in `.claude/settings.json`); realism-critic is
  Opus for final sign-off. Rules and the loop protocol live in `.claude/skills/wallpaper-painter/`.
- **Hooks**: any edit that breaks a Python file under `render/` or `tools/` is blocked; agent start/stop is
  logged to `benchmark/agent_log.jsonl`.
- **Cost**: `tools/cost.py --since <ISO time>` gives token usage and API-equivalent cost per agent.

Results so far (checker / realism critic, out of 5): baseline 3.16 / 2.0 → run 2 3.79 / 3.0 → run 3 3.84 / 3.1.

---

## Files
| Path | What |
|---|---|
| `dynamic_wallpaper.py` | runtime: weather + snow depth → scene → render → set |
| `render/timeofday.py`, `render/tod_plates.py`, `render/astro.py` | time-of-day engine, plates, sun/moon |
| `render/effects/` | rain + storm, fog, snowfall |
| `render/masks.py`, `render/depth.py` | scene masks and depth map (shared geometry) |
| `render/season_*.py`, `render/align_autumn.py` | template generators |
| `render/preview.py`, `render/benchmark.py` | previews and the benchmark matrix |
| `templates/` | season templates, `_sky.png` exact sky masks, `4k/` masters, `ai/` saved AI outputs |
| `tools/` | `critic.py`, `ai_region_edit.py`, `upscale_templates.sh`, `cost.py` |
| `setwallpaper.swift`, `install.sh` | sets the desktop picture on all displays; LaunchAgent installer |
| `benchmark/` | every run's renders, scores, reviews, costs |

Runtime copy lives in `~/Library/Application Support/DynamicWallpaper` (launchd can't read ~/Documents).
Log: `~/Library/Application Support/DynamicWallpaper/logs/wallpaper.log`.
