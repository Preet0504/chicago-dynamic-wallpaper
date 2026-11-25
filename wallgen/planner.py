"""Stage 2 - which seasonal looks does THIS place go through, and when?

Geocodes the location, summarises 3 years of daily climate into monthly normals, and asks a local LLM to split the
year into visual phases for the things perception found (e.g. Chicago: bare/bloom/full green/turning/peak/late;
Mumbai: dry/pre-monsoon/monsoon/post-monsoon). Also decides whether a snow-cover template is needed (only where
snow actually lies) and writes the selection rules the runtime uses. Output: 02_plan/plan.json.
"""
import os
import re

from . import config, geo, llm
from .common import Timer, read_json, write_json

STAGE = "02_plan"

PLAN_SCHEMA = {"type": "object", "properties": {
    "phases": {"type": "array", "items": {"type": "object", "properties": {
        "id": {"type": "string", "description": "snake_case"},
        "name": {"type": "string"},
        "start_mmdd": {"type": "string", "description": "MM-DD, first day of the phase"},
        "visual_changes": {"type": "string", "description": "what the affected objects look like in this phase"},
        "ground_and_foliage": {"type": "string"}},
        "required": ["id", "name", "start_mmdd", "visual_changes", "ground_and_foliage"]}},
    "base_phase_id": {"type": "string"},
    "snow_cover_template": {"type": "boolean"},
    "snow_visual": {"type": "string"},
    "snow_min_depth_cm": {"type": "number"},
    "lights_on_below_sun_alt": {"type": "number"},
    "reasoning": {"type": "string"}},
    "required": ["phases", "base_phase_id", "snow_cover_template", "snow_visual", "snow_min_depth_cm",
                 "lights_on_below_sun_alt", "reasoning"]}

PROMPT = """You plan the seasonal looks of a living wallpaper. A picture of a real-world-style scene will be re-painted
for each visual phase of the year at this location, then lit procedurally for every time of day and weather.

Location: {loc} (lat {lat:.2f}, lon {lon:.2f}, {hemi} hemisphere, elevation {elev} m)
Monthly climate normals (from the last 3 years of daily data):
{climate}

The picture currently shows: {season} season, {tod}, weather "{weather}", style "{style}".
Things in the picture that change with season/weather/time (category: labels -> effects):
{objects}

Split the year into {min_p}-{max_p} visual phases that a person living there would actually see on these objects
(foliage states, blossom, dry/wet season, snow-capped peaks, dormant grass...). Phases must be contiguous: each starts
the day after the previous one ends, the last wraps into the first. Use start dates that fit THIS climate (e.g. leaf
colour peaks later in warmer places; tropical places change with rain, not temperature).
Use the monthly mean temperatures to time foliage: deciduous trees leaf out when the monthly mean passes ~12 C,
blossom shortly before, colour peaks when it falls to ~10 C and they are bare below ~5 C; grass browns when dry/hot
or dormant when cold. In tropical/arid places time the phases by rainfall instead.
For each phase write `visual_changes` (max 60 words) describing ONLY the seasonal look of the vegetation, grass,
ground surface (dry/damp/leaf litter, NOT lying snow), mountain snow line and water (ice) that are in the picture.
Never mention the sky, sun, moon, lighting, lamps, windows or buildings - those are handled separately - and never
add objects that are not in the picture. This text goes to an image editor. `ground_and_foliage`: one short phrase.
`base_phase_id`: the phase the picture already shows.
Snow lying on the ground is NOT a calendar phase: set snow_cover_template=true only if snow cover days occur
(snow_cover_days > 0 in some month), and describe in snow_visual how snow lies on the objects. snow_min_depth_cm is
the depth from which the snow template is used (2 is typical).
lights_on_below_sun_alt: sun altitude (degrees) below which lamps/windows switch on (typically 3 to 8).
Explain briefly in `reasoning`."""


def run(job, scene, log=None):
    log = log or job.log
    d = job.stage_dir(STAGE)
    if job.done(STAGE):
        return read_json(os.path.join(d, "plan.json"))
    with Timer(job, STAGE):
        loc = geo.geocode(job.meta()["location"])
        log("  location: %s  (%.3f, %.3f) %s" % (loc["name"], loc["lat"], loc["lon"], loc["timezone"]))
        clim = geo.climate_normals(loc["lat"], loc["lon"])
        write_json(os.path.join(d, "geo.json"), loc)
        write_json(os.path.join(d, "climate.json"), clim)
        objs = {}
        for o in scene["objects"]:
            if o["affected_by"]:
                objs.setdefault(o["category"], set()).add("%s (%s)" % (o["label"], "/".join(o["affected_by"])))
        obj_txt = "\n".join("- %s: %s" % (k, "; ".join(sorted(v))[:400]) for k, v in objs.items())
        clim_txt = "\n".join("month %2d: mean %s C, min %s C, rain/snow %s mm, snowfall %s cm, snow-cover days %s, daylight %s h"
                             % (c["month"], c["temp_mean_c"], c["temp_min_c"], c["precip_mm"], c["snowfall_cm"],
                                c["snow_cover_days"], c["daylight_h"]) for c in clim)
        has_veg = "vegetation" in objs
        prompt = PROMPT.format(loc=loc["name"], lat=loc["lat"], lon=loc["lon"], hemi="northern" if loc["lat"] >= 0 else "southern",
                               elev=loc.get("elevation"), climate=clim_txt, season=scene["base_season"],
                               tod=scene["base_time_of_day"], weather=scene["base_weather"], style=scene["style"],
                               objects=obj_txt or "(none)", min_p=4 if has_veg else 2, max_p=7 if has_veg else 4)
        plan, secs = llm.chat_json(config.LLM_PLANNER, prompt, PLAN_SCHEMA, think="medium", num_ctx=16384, log=log)
        log("  planner (%s): %.0fs, %d phases" % (config.LLM_PLANNER, secs, len(plan["phases"])))
        plan = validate(plan, clim)
        strip_lying_snow(plan, log)
        plan["location"] = loc
        for p in plan["phases"]:
            log("    %s  from %s: %s" % (p["id"], p["start_mmdd"], p["ground_and_foliage"]))
        log("  base phase: %s; snow template: %s" % (plan["base_phase_id"], plan["snow_cover_template"]))
        write_json(os.path.join(d, "plan.json"), plan)
        llm.unload(config.LLM_PLANNER)
        job.mark_done(STAGE)
    return plan


SNOWY = re.compile(r"snow|powder|drift|blanket", re.I)
HIGH = re.compile(r"mountain|peak|ridge|summit|slope|cap", re.I)


def strip_lying_snow(plan, log):
    """Lying snow comes from real snow depth at runtime (snow template), never from the calendar: drop every clause
    that puts snow anywhere but on high mountains (deterministic, so it can't be talked around)."""
    for p in plan["phases"]:
        for key, sep in (("visual_changes", r"(?<=[.;])\s+"), ("ground_and_foliage", r",\s*")):
            parts = re.split(sep, p[key])
            keep = [c for c in parts if not SNOWY.search(c) or HIGH.search(c)]
            if len(keep) != len(parts):
                log("    %s: dropped lying-snow clause(s) from %s" % (p["id"], key))
                p[key] = (" " if key == "visual_changes" else ", ").join(keep) or "dormant"


def validate(plan, clim):
    ph = []
    seen = set()
    for p in plan["phases"]:
        raw_id = p["id"] if not re.fullmatch(r"phase_?\d*", p["id"].lower()) else p["name"]
        pid = "".join(ch if ch.isalnum() else "_" for ch in raw_id.lower())
        pid = re.sub("_+", "_", pid).strip("_")[:24] or "phase"
        if pid == "snow":
            pid = "snow_season"          # 'snow' is reserved for the snow-cover template
        if p["id"] == plan["base_phase_id"]:
            plan["base_phase_id"] = pid
        while pid in seen:
            pid += "_b"
        seen.add(pid)
        p["id"] = pid
        mm, dd = _mmdd(p["start_mmdd"])
        p["start_mmdd"] = "%02d-%02d" % (mm, dd)
        ph.append(p)
    ph.sort(key=lambda p: p["start_mmdd"])
    plan["phases"] = ph
    if plan["base_phase_id"] not in seen:
        plan["base_phase_id"] = min(seen, key=lambda s: _dist(s, plan["base_phase_id"]))
    if not any(c["snow_cover_days"] > 0 for c in clim):
        plan["snow_cover_template"] = False
    plan["snow_min_depth_cm"] = float(plan.get("snow_min_depth_cm") or 2)
    plan["lights_on_below_sun_alt"] = float(min(10, max(0, plan.get("lights_on_below_sun_alt", 5))))
    return plan


def _mmdd(s):
    try:
        mm, dd = [int(v) for v in s.replace("/", "-").split("-")[-2:]]
        return min(12, max(1, mm)), min(28 if mm == 2 else 30, max(1, dd))
    except Exception:
        return 1, 1


def _dist(a, b):
    import difflib
    return 1 - difflib.SequenceMatcher(None, a, b).ratio()


def phase_for(plan, when):
    """Which phase a date falls in (phases sorted by start; the last one wraps around New Year)."""
    key = when.strftime("%m-%d")
    cur = plan["phases"][-1]
    for p in plan["phases"]:
        if p["start_mmdd"] <= key:
            cur = p
    return cur
