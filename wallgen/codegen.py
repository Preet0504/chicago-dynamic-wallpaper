"""Stage 5 - small work: a local code model writes scene_renderer.py for this scene, with review loop B.

The model gets the scene facts (has sky? water? lamps? horizon, camera, phases), the scenekit API and the reference
composition, and writes a module with CAMERA, CONFIG and render(F). The code is statically checked (imports and
builtins allow-list), then run in a separate process under the runtime Python with no network and a timeout, on a
stratified set of moments (dawn, noon, golden hour, dusk, night, overcast, rain, storm, fog, snow, other phases).
Frames go through deterministic checks + the VLM panel; confirmed issues are routed: code issues go back to the
code model as a revision request, plate issues regenerate that plate. Best-scoring version wins.
"""
import ast
import datetime as dt
import inspect
import json
import os
import re
import shutil
import subprocess
import sys
from zoneinfo import ZoneInfo

import cv2
import numpy as np

from . import config, llm, review
from .common import Timer, read_json, write_json
from .scenekit import astro, kit

STAGE = "05_renderer"
RUNTIME_PY = os.path.join(config.ROOT, ".venv", "bin", "python")     # the same interpreter the live wallpaper uses
HARNESS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenekit", "harness.py")
ALLOWED_IMPORTS = {"numpy", "cv2", "math", "scenekit", "scenekit.kit"}
BANNED_NAMES = {"open", "exec", "eval", "compile", "__import__", "globals", "locals", "getattr", "setattr", "input",
                "breakpoint", "os", "sys", "subprocess", "socket", "shutil", "pathlib"}

API = """scenekit.kit API (import as `from scenekit import kit`). Images: float32 BGR in [0,1], shape (kit.OUT_H, kit.OUT_W, 3).
Masks: float32 (OUT_H, OUT_W) in [0,1]. Colours: kit.C(r, g, b) -> BGR array.
  F (kit.Frame): F.scene, F.when (aware datetime), F.st (sun_alt, sun_az, moon_alt, moon_az, moon_illum,
     moon_phase_angle), F.sun_alt, F.cover (cloud cover 0..1), F.weather (None|'rain'|'storm'|'fog'|'snow'),
     F.intensity (0..1), F.phase (plate phase id, e.g. 'spring_full' or 'snow')
  F.scene.plate(key) -> image for key '<phase>_day' or '<phase>_night'
  F.scene.layer(name) -> mask: sky, water, ground, roof, vegetation, terrain, structure, lights, depth (0 near..1 far)
  F.scene.cam -> dict(view_az, hfov, horizon)   F.scene.m -> manifest dict
  F.scene.sky_mask(F, wday) -> sky matte for this frame's plates (use this, not layer('sky'), when composing the sky)
  kit.layers_for(scene) -> dict of all layers (keys above)
  kit.sky(F, cam, cover, stars=True, sun_disk=True, moon=True, cloud=True, moon_size=1.0) -> (sky_img, sun_xy)
  kit.day_night(F, day, night) -> (img, wday)   blend plates by sun altitude with light tint/exposure
  kit.overcast(img, F, cover, strength=0.7) -> img      kit.low_sun(img, F, sun_xy, cover, strength=0.35) -> img
  kit.haze(img, F, depth, sky_img, cover, amount=0.18, horizon=cam['horizon']) -> img
  kit.lights_on(F, threshold_deg) -> 0..1             kit.light_glow(img, night, light_mask, on, glow=1.0) -> img
  kit.water(img, F, water_mask, sky_img, sun_xy, cover, plate=None, strength=0.9, light_mask=None, night=None, on=0.0)
  kit.compose_sky(img, sky_img, sky_mask) -> img      kit.sun_bloom(out, F, sun_xy, cover, strength=0.35) -> img
  kit.rain(img, F, L, intensity, storm=False)   kit.fog(img, F, L, intensity, light_mask, on, night)
  kit.snowfall(img, F, L, intensity, settle=True)
  helpers: kit.mix(a,b,t), kit.screen(a,b), kit.lum(img), kit.smooth(x,e0,e1), kit.lerp_keys(keys,x), kit.feather(m,s)
  kit.default_render(F, P) is the reference composition (source below)."""

SYSTEM = ("You are a careful graphics programmer. You write small, deterministic Python modules that render a "
          "painted wallpaper scene for a given moment and weather using a provided library. Output ONLY one "
          "```python code block containing the complete module.")

TASK = """Write `scene_renderer.py` for this scene.

SCENE FACTS
{facts}

{api}

REFERENCE COMPOSITION (kit.default_render and its DEFAULTS):
```python
{ref}
```

REQUIREMENTS
- Module-level `CAMERA = dict(view_az=..., hfov=..., horizon=...)` (degrees / fraction of height); start from the
  scene facts and keep the horizon unless you have a reason.
- Module-level `CONFIG = dict(...)` holding every tunable number you use.
- `def render(F):` returns the frame (float32, (kit.OUT_H, kit.OUT_W, 3), values in [0,1]).
- Adapt the composition to THIS scene: skip sky composition if it has no sky (the sky still drives the light),
  skip water if there is none, use the lamp threshold from the facts, keep effects subtle and painterly.
- Allowed imports: numpy, cv2, math, `from scenekit import kit`. No file, network or OS access. Deterministic.
- Keep it under ~150 lines. Prefer calling kit functions over re-implementing them.
- Call ONLY these kit functions, with exactly these parameters (anything else fails the build):
{sigs}"""

REVISE = """Your scene_renderer.py was rendered for {n} test moments and reviewed by a panel of vision models.

CURRENT CODE:
```python
{code}
```

{errors}
PANEL SCORES (1-5, mean over frames): {scores}
ISSUES TO FIX IN THE CODE (confirmed by several reviewers or by automatic checks, most important first):
{issues}

Revise the module to fix these issues without breaking what works. Keep the same structure (CAMERA, CONFIG,
render). Change numbers in CONFIG or the composition as needed. Return the COMPLETE module."""


# ------------------------------------------------------------------------------------------ code safety
def static_check(code):
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return "SyntaxError: %s (line %s)" % (e.msg, e.lineno)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name not in ALLOWED_IMPORTS:
                    return "import of '%s' is not allowed" % a.name
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "") not in ALLOWED_IMPORTS:
                return "import from '%s' is not allowed" % node.module
        elif isinstance(node, ast.Name) and node.id in BANNED_NAMES:
            return "use of '%s' is not allowed" % node.id
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__") and node.attr not in ("__init__",):
            return "dunder attribute access '%s' is not allowed" % node.attr
    names = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    if "render" not in names:
        return "no top-level function render(F)"
    return api_check(tree)


class _Short:
    def __repr__(self):
        return "<default>"


def kit_signatures():
    """Exact signatures of the public kit functions (the coder used to invent helpers and keyword arguments)."""
    out = []
    for name in sorted(dir(kit)):
        fn = getattr(kit, name)
        if name.startswith("_") or not inspect.isfunction(fn) or fn.__module__ != kit.__name__:
            continue
        try:
            sig = inspect.signature(fn)
        except (TypeError, ValueError):
            continue
        ps = [p.replace(default=_Short()) if p.default is not p.empty and len(repr(p.default)) > 30 else p
              for p in sig.parameters.values()]
        out.append("kit.%s%s" % (name, sig.replace(parameters=ps)))
    return "\n".join(out)


def api_check(tree):
    """Every kit.X must exist and every call must fit its real signature - caught here instead of after a render."""
    aliases = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "scenekit":
            aliases |= {a.asname or a.name for a in node.names if a.name == "kit"}
        elif isinstance(node, ast.ImportFrom) and node.module == "scenekit.kit":
            for a in node.names:
                if not hasattr(kit, a.name):
                    return "scenekit.kit has no '%s'. Real API:\n%s" % (a.name, kit_signatures())
        elif isinstance(node, ast.Import):
            aliases |= {a.asname for a in node.names if a.name == "scenekit.kit" and a.asname}
    errs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in aliases:
            if not hasattr(kit, node.attr):
                errs.append("kit.%s does not exist" % node.attr)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and \
                isinstance(node.func.value, ast.Name) and node.func.value.id in aliases:
            fn = getattr(kit, node.func.attr, None)
            if not inspect.isfunction(fn):
                continue
            ps = inspect.signature(fn).parameters
            kinds = {p.kind for p in ps.values()}
            if inspect.Parameter.VAR_KEYWORD not in kinds:
                for kw in node.keywords:
                    if kw.arg and kw.arg not in ps:
                        errs.append("kit.%s%s has no argument '%s'" % (node.func.attr, inspect.signature(fn), kw.arg))
            npos = sum(p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD) for p in ps.values())
            if inspect.Parameter.VAR_POSITIONAL not in kinds and not any(isinstance(a, ast.Starred) for a in node.args) \
                    and len(node.args) > npos:
                errs.append("kit.%s%s takes at most %d positional arguments, got %d"
                            % (node.func.attr, inspect.signature(fn), npos, len(node.args)))
    if errs:
        return "; ".join(sorted(set(errs))[:8]) + ". Real API:\n" + kit_signatures()
    return None


def extract_code(text):
    m = re.findall(r"```(?:python)?\s*\n(.*?)```", text, re.S)
    return max(m, key=len).strip() + "\n" if m else text.strip() + "\n"


def run_cases(pkg, code_path, cases, out_dir, timeout=900):
    """Render cases in a separate, network-less process with the runtime interpreter."""
    os.makedirs(out_dir, exist_ok=True)
    cp = os.path.join(out_dir, "cases.json")
    write_json(cp, cases)
    cmd = [RUNTIME_PY, HARNESS, pkg, code_path, cp, out_dir]
    if os.path.exists("/usr/bin/sandbox-exec"):
        cmd = ["/usr/bin/sandbox-exec", "-p", "(version 1)(allow default)(deny network*)"] + cmd
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=out_dir)
    except subprocess.TimeoutExpired:
        return [dict(id=c["id"], ok=False, error="timed out after %ds" % timeout) for c in cases]
    res = {}
    for line in p.stdout.splitlines():
        if line.startswith("{"):
            r = json.loads(line)
            res[r["id"]] = r
    out = []
    for c in cases:
        out.append(res.get(c["id"], dict(id=c["id"], ok=False, error="crashed: " + p.stderr[-800:])))
    return out


# --------------------------------------------------------------------------------------------- test moments
def find_time(day, lat, lon, tz, target, rising):
    best = None
    for m in range(0, 24 * 60, 5):
        t = dt.datetime(day.year, day.month, day.day, m // 60, m % 60, tzinfo=tz)
        a = astro.sky_state(t, lat, lon)["sun_alt"]
        t2 = t + dt.timedelta(minutes=5)
        b = astro.sky_state(t2, lat, lon)["sun_alt"]
        if (a <= target <= b and rising) or (a >= target >= b and not rising):
            return t
        if best is None or abs(a - target) < best[0]:
            best = (abs(a - target), t)
    return best[1]


def make_cases(manifest):
    tz = ZoneInfo(manifest["location"]["timezone"])
    lat, lon = manifest["location"]["lat"], manifest["location"]["lon"]
    phases = manifest["phases"]
    year = dt.date.today().year

    def mid(pid):
        i = next(i for i, p in enumerate(phases) if p["id"] == pid)
        s = dt.date(year, *map(int, phases[i]["start_mmdd"].split("-")))
        e = dt.date(year + (1 if i == len(phases) - 1 else 0), *map(int, phases[(i + 1) % len(phases)]["start_mmdd"].split("-")))
        return s + (e - s) // 2

    def pick(words, avoid=()):
        for w in words:
            for p in phases:
                if w in p["id"] and p["id"] not in avoid:
                    return p["id"]
        return None
    bp = manifest["base_phase"]
    summer = pick(["summer"], [bp]) or phases[(phases.index(next(p for p in phases if p["id"] == bp)) + 1) % len(phases)]["id"]
    autumn = pick(["autumn", "fall", "peak", "monsoon"], [bp, summer]) or phases[-2]["id"]
    winter = pick(["winter", "dormant", "dry"], [bp, summer, autumn]) or phases[0]["id"]
    d0 = mid(bp)
    f = lambda t: t.strftime("%Y-%m-%d %H:%M")
    at = lambda day, h, m=0: dt.datetime(day.year, day.month, day.day, h, m, tzinfo=tz)
    c = [
        dict(id="c01_night", when=f(at(d0, 23)), cover=0.1, phase=bp, series=0),
        dict(id="c02_dawn", when=f(find_time(d0, lat, lon, tz, 1.0, True)), cover=0.15, phase=bp, series=2),
        dict(id="c03_morning", when=f(find_time(d0, lat, lon, tz, 20.0, True)), cover=0.4, phase=bp),
        dict(id="c04_noon", when=f(at(d0, 13)), cover=0.05, phase=bp, series=4),
        dict(id="c05_golden", when=f(find_time(d0, lat, lon, tz, 4.0, False)), cover=0.1, phase=bp, series=3),
        dict(id="c06_dusk", when=f(find_time(d0, lat, lon, tz, -5.0, False)), cover=0.1, phase=bp, series=1),
        dict(id="c07_overcast", when=f(at(d0, 11)), cover=0.97, phase=bp),
        dict(id="c08_rain", when=f(at(d0, 16)), cover=1.0, weather="rain", intensity=0.7, phase=bp),
        dict(id="c09_storm", when=f(at(mid(summer), 14)), cover=1.0, weather="storm", intensity=1.0, phase=summer),
        dict(id="c10_fog", when=f(find_time(mid(autumn), lat, lon, tz, 8.0, True)), cover=0.6, weather="fog",
             intensity=0.8, phase=autumn),
        dict(id="c12_winter_day", when=f(at(mid(winter), 12)), cover=0.3, phase=winter),
    ]
    if manifest.get("snow_template"):
        c.append(dict(id="c11_snow_night", when=f(at(mid(winter), 21)), cover=1.0, weather="snow", intensity=0.6,
                      phase="snow"))
    return c


def describe(case, manifest, sun_alt):
    names = {p["id"]: p["name"] for p in manifest["phases"]}
    names["snow"] = "snow lying on the ground"
    t = case["when"][11:]
    if case.get("weather"):
        wx = {"rain": "raining", "storm": "thunderstorm with heavy rain", "fog": "foggy", "snow": "snowing"}[case["weather"]]
    else:
        cv = case.get("cover", 0.3)
        wx = "clear sky" if cv < 0.2 else "partly cloudy" if cv < 0.7 else "overcast"
    when = ("night" if sun_alt < -12 else "dusk/dawn twilight" if sun_alt < -1 else "sunrise/sunset"
            if sun_alt < 6 else "daytime")
    lamps = "lamps lit" if sun_alt < manifest["lights_on_below_sun_alt"] else "lamps off"
    return "%s season (%s), %s local time, %s (sun %.0f deg), %s, %s" % (
        names.get(case["phase"], case["phase"]), case["when"][:10], t, when, sun_alt, wx, lamps)


def facts(manifest):
    return json.dumps(dict(has_sky=manifest["has_sky"], has_water=manifest["has_water"], has_lights=manifest["has_lights"],
                           camera=manifest["camera"], lights_on_below_sun_alt=manifest["lights_on_below_sun_alt"],
                           phases=[p["id"] for p in manifest["phases"]], snow_template=manifest["snow_template"],
                           location=manifest["location"]["name"], style=manifest["style"],
                           description=manifest["summary"][:600]), indent=1)


def reference_source():
    return inspect.getsource(kit.default_render) + "\nDEFAULTS = " + json.dumps(kit.DEFAULTS, indent=1)


# ------------------------------------------------------------------------------------------------ stage
def ask_coder(prompt, log):
    txt, secs = llm.chat_text(config.LLM_CODER, prompt, system=SYSTEM, temperature=0.2, think="medium", num_ctx=32768)
    log("  coder (%s): %.0fs" % (config.LLM_CODER, secs))
    return extract_code(txt)


def series_check(results, frames):
    """Brightness must rise from night -> dusk -> sunrise -> golden -> noon (same day, clear)."""
    order = sorted([(c["series"], c["id"]) for c in results if "series" in c and c["id"] in frames])
    lums = [(cid, float(cv2.cvtColor(frames[cid], cv2.COLOR_BGR2GRAY).mean())) for _, cid in order]
    issues = []
    for (a, la), (b, lb) in zip(lums, lums[1:]):
        if lb < la - 2:
            issues.append(dict(box_0_1000=[0, 0, 1000, 1000], defect_type="too_dark_or_bright", severity=3,
                               description="%s (mean %.0f) is darker than %s (mean %.0f) although the sun is higher"
                               % (b, lb, a, la), source="check"))
    return lums, issues


def evaluate(job, pkg, code_path, cases, out_dir, manifest, masks, log):
    res = run_cases(pkg, code_path, cases, out_dir)
    errors = [r for r in res if not r["ok"]]
    if errors:
        return None, errors
    base = job.base()
    frames = {r["id"]: cv2.imread(r["file"]) for r in res}
    lums, series_issues = series_check([dict(c, **r) for c, r in zip(cases, res)], frames)
    per = []
    small_masks = {k: cv2.resize(v, (base.shape[1], base.shape[0]), interpolation=cv2.INTER_AREA) for k, v in masks.items()}
    for c, r in zip(cases, res):
        fr = cv2.resize(frames[c["id"]], (base.shape[1], base.shape[0]), interpolation=cv2.INTER_AREA)
        cond = describe(c, manifest, r["sun_alt"])
        m, chk = review.deterministic(fr, base, small_masks, dict(is_night=r["sun_alt"] < -6, sun_alt=r["sun_alt"],
                                                                  weather=c.get("weather")))
        if c["id"] == "c04_noon" or (series_issues and c["id"] == series_issues[0]["description"].split()[0]):
            chk += series_issues
        clusters, agg, ok, info = review.review_frame(frames[c["id"]], base, cond, chk,
                                                      notes=manifest["summary"][:300], log=log)
        per.append(dict(id=c["id"], cond=cond, sun_alt=r["sun_alt"], seconds=r["seconds"], metrics=m, scores=agg,
                        clusters=clusters, passed=ok, file=r["file"], review=info))
        log("    %-16s %.2f %s [%s %.0fs] %s" % (c["id"], agg["mean"], "PASS" if ok else "fail", info["tier"], info["seconds"],
                                     "; ".join("%s(%d)" % (k["defect_type"], k["support"]) for k in clusters[:3] if k["confirmed"])))
    mean = round(float(np.mean([p["scores"]["mean"] for p in per])), 3)
    metric_means = {k: round(float(np.mean([p["scores"]["per_metric"][k] for p in per])), 2) for k in config.RUBRIC}
    return dict(frames=per, mean=mean, per_metric=metric_means, all_passed=all(p["passed"] for p in per),
                render_seconds=round(float(np.mean([p["seconds"] for p in per])), 2), lums=lums), None


def select_cases(cases, fast):
    if not fast:
        return cases
    keep = [c for c in cases if c["id"] in config.FAST_CASES]
    if len(keep) > config.FAST_MAX_CASES and any(c["id"] == "c11_snow_night" for c in keep):
        keep = [c for c in keep if c["id"] != "c12_winter_day"]
    return keep[:config.FAST_MAX_CASES]


def run(job, manifest, scene, plan, log=None, redo_plate=None, fast=False):
    log = log or job.log
    d = job.stage_dir(STAGE)
    pkg = job.path("04_package")
    final = os.path.join(pkg, "scene_renderer.py")
    if job.done(STAGE):
        return read_json(os.path.join(d, "result.json"))
    with Timer(job, STAGE):
        cases = select_cases(make_cases(manifest), fast)
        max_rounds = config.FAST_RENDER_ROUNDS if fast else config.RENDER_MAX_ROUNDS
        write_json(os.path.join(d, "cases.json"), cases)
        z = np.load(os.path.join(pkg, "layers.npz"))
        masks = {k: z[k].astype(np.float32) for k in z.files}
        masks["light_source"] = masks.get("lights")
        hist = read_json(os.path.join(d, "history.json"), []) or []
        prompt = TASK.format(facts=facts(manifest), api=API, ref=reference_source(), sigs=kit_signatures())
        code = None
        best = max(hist, key=lambda h: h.get("mean", 0)) if hist else None
        if hist:
            code = open(os.path.join(d, "v%d.py" % hist[-1]["version"])).read()
        for rnd in range(len(hist), max_rounds):
            v = rnd + 1
            # --- write (or revise) and make it run
            if code is None and os.path.exists(os.path.join(d, "v1.py")) and not hist:
                code = open(os.path.join(d, "v1.py")).read()      # resume: keep the coder's first version
                log("  reusing v1.py from an interrupted run")
            elif code is None:
                code = ask_coder(prompt, log)
            elif hist:
                last = hist[-1]
                code = ask_coder(REVISE.format(n=len(cases), code=code, errors="", scores=json.dumps(last["per_metric"]),
                                               issues=last["code_feedback"] or "(none - polish overall realism)"), log)
            ev = None
            for fix in range(3):
                bad = static_check(code)
                vp = os.path.join(d, "v%d.py" % v)
                open(vp, "w").write(code)
                if bad:
                    log("  v%d rejected by static check: %s" % (v, bad))
                    code = ask_coder("This module was rejected: %s\n```python\n%s```\nReturn the corrected COMPLETE "
                                     "module (allowed imports: numpy, cv2, math, `from scenekit import kit`)." % (bad, code), log)
                    continue
                llm.unload_all()
                log("  v%d: rendering %d test moments…" % (v, len(cases)))
                ev, errors = evaluate(job, pkg, vp, cases, os.path.join(d, "v%d" % v), manifest, masks, log)
                if ev:
                    break
                msg = "\n".join("%s: %s\n%s" % (e["id"], e["error"], e.get("traceback", "")[-600:]) for e in errors[:3])
                log("  v%d failed to run: %s" % (v, errors[0]["error"][:200]))
                code = ask_coder("Your module failed when run:\n%s\n```python\n%s```\nFix it and return the COMPLETE "
                                 "module." % (msg, code), log)
            if not ev:
                log("  v%d never ran; stopping loop B" % v)
                break
            # --- route the confirmed issues
            code_fb, plate_fb = [], {}
            for fr in ev["frames"]:
                for c in [k for k in fr["clusters"] if k["confirmed"]][:3]:
                    case = next(x for x in cases if x["id"] == fr["id"])
                    plate_key = case["phase"] + ("_day" if fr["sun_alt"] > 3 else "_night")
                    plate = cv2.imread(os.path.join(pkg, "plates", plate_key + ".png"))
                    owner = review.route(c, cv2.imread(fr["file"]), plate, log)
                    c["owner"] = owner
                    line = "- [%s, sev %d, %d reviewers] %s at %s: %s" % (fr["id"], c["severity"], c["support"],
                                                                          c["defect_type"], c["box_0_1000"], c["descriptions"][0][:220])
                    if owner == "code":
                        code_fb.append(line)
                    else:
                        plate_fb.setdefault(plate_key, []).append(c["descriptions"][0][:200])
            entry = dict(version=v, mean=ev["mean"], per_metric=ev["per_metric"], all_passed=ev["all_passed"],
                         render_seconds=ev["render_seconds"], code_feedback="\n".join(code_fb[:12]),
                         plate_feedback=plate_fb, frames=[dict(id=f["id"], cond=f["cond"], mean=f["scores"]["mean"],
                                                                passed=f["passed"], issues=review.summarize(f["clusters"], 5))
                                                           for f in ev["frames"]])
            hist.append(entry)
            write_json(os.path.join(d, "history.json"), hist)
            log("  v%d: mean %.2f, %d/%d frames pass, %d code issues, %d plates flagged" % (
                v, ev["mean"], sum(f["passed"] for f in ev["frames"]), len(ev["frames"]), len(code_fb), len(plate_fb)))
            if best is None or ev["mean"] > best["mean"]:
                best = entry
            # plates flagged by the routing get regenerated now (they are shared by every later version)
            if plate_fb and redo_plate:
                for key, fixes in list(plate_fb.items())[:3]:
                    redo_plate(key, " ".join(fixes)[:500])
            if ev["all_passed"]:
                log("  all frames pass -> done")
                break
            if not code_fb:
                log("  no confirmed issues owned by the code -> done")
                break
            if len(hist) > 1 and ev["mean"] - hist[-2]["mean"] < config.PLATEAU_EPS and not plate_fb:
                log("  plateau (%.2f -> %.2f) -> done" % (hist[-2]["mean"], ev["mean"]))
                break
        if best is None:      # the coder never produced runnable code: fall back to the reference composition
            log("  falling back to kit.default_render")
            open(final, "w").write("from scenekit import kit\nCAMERA = None\nCONFIG = {}\n\n\ndef render(F):\n"
                                   "    return kit.default_render(F, CONFIG)\n")
            result = dict(version=0, fallback=True)
        else:
            shutil.copy(os.path.join(d, "v%d.py" % best["version"]), final)
            result = dict(version=best["version"], mean=best["mean"], per_metric=best["per_metric"],
                          all_passed=best["all_passed"], rounds=len(hist), fallback=False)
        write_json(os.path.join(d, "result.json"), result)
        llm.unload_all()
        job.mark_done(STAGE)
    return result
