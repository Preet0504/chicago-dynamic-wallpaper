"""Review: deterministic checks first (cheap, objective), then a panel of local vision models.

Each panel model scores the rubric 1-5 and lists issues {box, defect_type, severity, description}. Issues from all
models are clustered (same defect type + overlapping region) and counted: confirmed = >= 2 models, or 1 model plus a
deterministic check of the same type. Unconfirmed issues are kept but ranked last. Routing decides whether a fix
belongs to the image generator (template/plate problem) or the code model (renderer problem).
"""
import concurrent.futures as cf
import json

import cv2
import numpy as np

from . import config, llm
from .common import jpeg_b64, tiles

DEFECTS = ["halo_fringe", "seam_hard_edge", "banding", "smudge_blob", "floating_fragment", "lights_wrong",
           "sky_wrong", "sun_moon_wrong", "reflection_wrong", "season_wrong", "composition_changed",
           "hallucinated_object", "color_cast", "too_dark_or_bright", "ai_overdetail", "other"]
IMAGE_OWNED = {"season_wrong", "composition_changed", "hallucinated_object", "ai_overdetail"}
CODE_OWNED = {"sky_wrong", "sun_moon_wrong", "reflection_wrong", "banding", "too_dark_or_bright"}
# lights_wrong, halos, smudges, seams… are ambiguous: route() checks whether the plate already has the defect

PANEL_SCHEMA = {"type": "object", "properties": {
    "scores": {"type": "object", "properties": {k: {"type": "integer", "minimum": 1, "maximum": 5} for k in config.RUBRIC},
               "required": list(config.RUBRIC)},
    "issues": {"type": "array", "items": {"type": "object", "properties": {
        "box_0_1000": {"type": "array", "items": {"type": "integer"}},
        "defect_type": {"type": "string", "enum": DEFECTS},
        "severity": {"type": "integer", "minimum": 1, "maximum": 3},
        "description": {"type": "string"}}, "required": ["box_0_1000", "defect_type", "severity", "description"]}},
    "verdict": {"type": "string", "enum": ["accept", "revise", "reject"]}},
    "required": ["scores", "issues", "verdict"]}

PANEL_PROMPT = """You are a strict art director reviewing a desktop wallpaper made from a reference picture.
Image 1 is the ORIGINAL reference. Image 2 is the CANDIDATE to judge. Images 3-6 are full-resolution quarters of the
candidate (top-left, top-right, bottom-left, bottom-right) so you can see small defects.
The candidate must show the same place and composition as the original, changed to: {cond}.
Scene notes: {notes}

Score each criterion 1-5 (5 = would ship as-is, 3 = clearly flawed but acceptable at a glance, 1 = broken):
{rubric}
- style_match: same art style and rendering as the original
- composition_intact: same objects in the same places; nothing added, removed or moved
- realism: believable for that place, season, weather and time of day
- light_consistency: light direction/colour, shadows, lamps lit only when dark, reflections agree with the sky
- season_correct: vegetation, ground and sky match the stated season/conditions
- edges_artifacts: no halos, seams, smudges, banding, floating fragments, hard mask edges
- would_set_as_wallpaper: overall

List up to 6 concrete issues, most important first. Give each a box [x0,y0,x1,y1] in 0-1000 coordinates of the
candidate, a defect_type, severity (3 = ruins the image, 2 = noticeable, 1 = minor) and a short description of what
is wrong and where. Do not invent issues: if it is good, return few or none. Reply with JSON only."""


# --------------------------------------------------------------------------------- deterministic checks
def deterministic(img, base, masks, cond, kind="plate"):
    """img/base uint8 BGR same size. masks: dict of float HxW layers. cond: dict(sun_alt, is_night, has_lights...).
    Returns (metrics dict, issues list in the panel's format with source='check')."""
    from .align import edge_recall
    h, w = img.shape[:2]
    issues, m = [], {}
    static = np.clip(sum(masks.get(k, 0) for k in ("structure", "person", "vehicle", "object")), 0, 1)
    obscured = cond.get("weather") in ("fog", "rain", "storm", "snow") or cond.get("sun_alt", 0) < -12
    if np.asarray(static).max() > 0.5 and not obscured:    # fog/rain/deep night legitimately hide edges
        m["edge_recall_static"] = round(edge_recall(base, img, static), 3)
        if m["edge_recall_static"] < config.DRIFT_MIN_EDGE_RECALL:
            issues.append(_iss([0, 0, 1000, 1000], "composition_changed", 3,
                               "static structure moved/changed: only %.0f%% of the original's edges are kept"
                               % (100 * m["edge_recall_static"])))
    lum = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    m["mean_luma"] = round(float(lum.mean()), 3)
    if cond.get("is_night") is not None:
        if cond["is_night"] and m["mean_luma"] > 0.45:
            issues.append(_iss([0, 0, 1000, 1000], "too_dark_or_bright", 2, "night frame is too bright (mean %.2f)" % m["mean_luma"]))
        if not cond["is_night"] and m["mean_luma"] < 0.22:
            issues.append(_iss([0, 0, 1000, 1000], "too_dark_or_bright", 2, "day frame is too dark (mean %.2f)" % m["mean_luma"]))
    # lights lit in daylight: bright warm pixels inside light masks while the sun is up
    lights = np.clip(masks.get("light_source", 0) + masks.get("window", 0), 0, 1)
    if np.asarray(lights).max() > 0.5:
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        warm = ((hsv[..., 0] < 35) & (hsv[..., 1] > 90) & (hsv[..., 2] > 200)).astype(np.float32)
        frac = float((warm * (lights > 0.5)).sum() / ((lights > 0.5).sum() + 1))
        m["lit_fraction_in_lights"] = round(frac, 3)
        if cond.get("sun_alt", -90) > 12 and frac > 0.08:
            issues.append(_iss(_bbox(lights > 0.5, w, h), "lights_wrong", 2, "lamps/windows look lit in daylight"))
    # banding in the sky: few distinct levels across a wide luminance range
    sky = masks.get("sky")
    if sky is not None and np.asarray(sky).mean() > 0.02:
        s = lum[sky > 0.9]
        if s.size > 5000:
            rng = np.percentile(s, 98) - np.percentile(s, 2)
            levels = len(np.unique((s * 255).astype(np.uint8)))
            m["sky_levels_per_range"] = round(levels / max(1.0, rng * 255), 2)
            if rng > 0.12 and m["sky_levels_per_range"] < 0.35:
                issues.append(_iss(_bbox(sky > 0.9, w, h), "banding", 2, "sky gradient shows banding"))
    # hard seams: straight long discontinuities that the base does not have
    gi = cv2.Canny(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 80, 200)
    gb = cv2.dilate(cv2.Canny(cv2.cvtColor(base, cv2.COLOR_BGR2GRAY), 40, 120), np.ones((5, 5), np.uint8))
    new_edges = (gi > 0) & (gb == 0)
    lines = cv2.HoughLinesP(new_edges.astype(np.uint8) * 255, 1, np.pi / 180, 120, minLineLength=int(0.15 * w), maxLineGap=4)
    m["new_straight_lines"] = 0 if lines is None else int(len(lines))
    if lines is not None and len(lines) >= 3:
        x0, y0, x1, y1 = lines[0][0]
        issues.append(_iss([int(1000 * min(x0, x1) / w), int(1000 * min(y0, y1) / h), int(1000 * max(x0, x1) / w) + 5,
                            int(1000 * max(y0, y1) / h) + 5], "seam_hard_edge", 2, "long straight edges not in the original"))
    for i in issues:
        i["source"] = "check"
    return m, issues


def _iss(box, t, sev, desc):
    return dict(box_0_1000=[int(v) for v in box], defect_type=t, severity=sev, description=desc)


def _bbox(mask, w, h):
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return [0, 0, 1000, 1000]
    return [int(1000 * xs.min() / w), int(1000 * ys.min() / h), int(1000 * xs.max() / w), int(1000 * ys.max() / h)]


# ------------------------------------------------------------------------------------------------- panel
def ask_panel_model(model, img, base, cond_text, notes, log=print):
    imgs = [jpeg_b64(base, 1024), jpeg_b64(img, 1536)] + [jpeg_b64(t, 1024) for _, t in tiles(img, 2)]
    prompt = PANEL_PROMPT.format(cond=cond_text, notes=notes, rubric=", ".join(config.RUBRIC))
    out, secs = llm.chat_json(model, prompt, PANEL_SCHEMA, images=imgs, temperature=0.1, num_ctx=24576, log=log,
                              timeout=400, num_predict=3500, retries=1)
    out["model"], out["seconds"] = model, round(secs, 1)
    for i in out["issues"]:
        i["source"] = model
        b = i.get("box_0_1000") or [0, 0, 1000, 1000]
        i["box_0_1000"] = (list(b) + [1000] * 4)[:4]
    return out


def panel(img, base, cond_text, notes="", models=None, log=print):
    """All panel models review the frame (in parallel when they fit on the GPU together). A model that fails or
    times out is skipped for this frame; if every model fails the frame is reported unscored (neutral 3s)."""
    models = models or config.REVIEW_PANEL

    def safe(m):
        try:
            return ask_panel_model(m, img, base, cond_text, notes, log)
        except Exception as e:
            log("    panel model %s skipped: %s" % (m, str(e)[:160]))
            return None
    if config.PANEL_PARALLEL:
        with cf.ThreadPoolExecutor(len(models)) as ex:
            res = list(ex.map(safe, models))
    else:
        res = [safe(m) for m in models]
    res = [r for r in res if r]
    if not res:
        res = [dict(model="none", scores={k: 3 for k in config.RUBRIC}, issues=[], verdict="revise", seconds=0)]
    return res


SCREEN_PROMPT = """You are a strict art director doing a quick first look at a desktop wallpaper.
Image 1 is the ORIGINAL reference. Image 2 is the CANDIDATE, which must show the same place and composition changed
to: {cond}.
Scene notes: {notes}
Check in particular: lamps/windows lit or unlit exactly as stated; no leftovers of another season (flowers, leaves,
snow) where the stated season would not have them; nothing added, removed or moved.
Score 1-5 (5 = ship as-is, 3 = clearly flawed): {rubric}.
List at most 3 real problems (box [x0,y0,x1,y1] in 0-1000 candidate coordinates, defect_type, severity 3 = ruins it,
2 = noticeable, 1 = minor, description under 15 words). verdict "accept" only if you would ship it unchanged.
Reply with JSON only."""


def screen(img, base, cond_text, notes="", model=None, log=print):
    """Tier 1: one model, two downscaled images, short answer. Returns the panel-format result or None on failure."""
    model = model or config.SCREEN_MODEL
    imgs = [jpeg_b64(base, 768), jpeg_b64(img, 1152)]
    prompt = SCREEN_PROMPT.format(cond=cond_text, notes=notes, rubric=", ".join(config.RUBRIC))
    try:
        out, secs = llm.chat_json(model, prompt, PANEL_SCHEMA, images=imgs, temperature=0.1, num_ctx=8192, log=log,
                                  timeout=240, num_predict=900, retries=1)
    except Exception as e:
        log("    screen %s failed: %s" % (model, str(e)[:160]))
        return None
    out["model"], out["seconds"] = model + ":screen", round(secs, 1)
    for i in out["issues"]:
        i["source"] = out["model"]
        b = i.get("box_0_1000") or [0, 0, 1000, 1000]
        i["box_0_1000"] = (list(b) + [1000] * 4)[:4]
    return out


def screen_accepts(s, check_issues):
    """The screen may only accept, and only when it is clearly good and no automatic check fired."""
    if not s:
        return False
    sc = [s["scores"].get(k, 0) for k in config.RUBRIC]
    return (s["verdict"] == "accept" and sum(sc) / len(sc) >= config.SCREEN_ACCEPT_MEAN
            and min(sc) >= config.SCREEN_ACCEPT_FLOOR and not any(i["severity"] >= 2 for i in s["issues"])
            and not any(i["severity"] >= 2 for i in check_issues))


def review_frame(img, base, cond_text, check_issues, notes="", tier=None, log=print):
    """Tiered review. Returns (clusters, agg, passed, info). info = {tier: 'screen'|'panel', seconds}."""
    tier = tier or config.REVIEW_TIER
    s = None
    if tier == "tiered":
        s = screen(img, base, cond_text, notes, log=log)
        if screen_accepts(s, check_issues):
            clusters, agg = merge([s], check_issues)
            return clusters, agg, True, dict(tier="screen", seconds=s["seconds"])
    res = panel(img, base, cond_text, notes=notes, log=log)
    clusters, agg = merge(res, check_issues)
    secs = max(r.get("seconds", 0) for r in res) + (s["seconds"] if s else 0)
    return clusters, agg, passed(agg, clusters), dict(tier="panel", seconds=round(secs, 1),
                                                      screen_mean=_mean(s) if s else None)


def _mean(r):
    sc = [r["scores"].get(k, 0) for k in config.RUBRIC]
    return round(sum(sc) / len(sc), 2)


def merge(panel_results, check_issues):
    """Union of all issues, clustered; returns (clusters sorted by priority, aggregate scores)."""
    allis = [dict(i) for r in panel_results for i in r["issues"]] + [dict(i) for i in check_issues]
    clusters = []
    for i in allis:
        hit = next((c for c in clusters if c["defect_type"] == i["defect_type"] and
                    _ov(c["box_0_1000"], i["box_0_1000"]) > 0.25), None)
        if hit:
            hit["sources"] = sorted(set(hit["sources"]) | {i["source"]})
            hit["severity"] = max(hit["severity"], i["severity"])
            hit["descriptions"].append(i["description"])
            hit["box_0_1000"] = [min(hit["box_0_1000"][0], i["box_0_1000"][0]), min(hit["box_0_1000"][1], i["box_0_1000"][1]),
                                 max(hit["box_0_1000"][2], i["box_0_1000"][2]), max(hit["box_0_1000"][3], i["box_0_1000"][3])]
        else:
            clusters.append(dict(defect_type=i["defect_type"], severity=i["severity"], box_0_1000=list(i["box_0_1000"]),
                                 sources=[i["source"]], descriptions=[i["description"]]))
    for c in clusters:
        models = [s for s in c["sources"] if s != "check"]
        c["support"] = len(models)
        c["confirmed"] = len(models) >= 2 or (len(models) >= 1 and "check" in c["sources"]) or \
            (c["sources"] == ["check"] and c["severity"] >= 3)
    clusters.sort(key=lambda c: (not c["confirmed"], -c["severity"], -c["support"]))
    scores = {}
    for k in config.RUBRIC:
        vals = [r["scores"].get(k, 3) for r in panel_results]
        scores[k] = round(sum(vals) / len(vals), 2) if vals else None
    mean = round(sum(scores.values()) / len(scores), 3) if scores else 0
    return clusters, dict(per_metric=scores, mean=mean, min_metric=min(scores.values()) if scores else 0,
                          verdicts=[r["verdict"] for r in panel_results])


def _ov(a, b):
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    small = min(max(1, (a[2] - a[0]) * (a[3] - a[1])), max(1, (b[2] - b[0]) * (b[3] - b[1])))
    return inter / small


def passed(agg, clusters):
    blocking = [c for c in clusters if c["confirmed"] and c["severity"] >= 3]
    return agg["mean"] >= config.PASS_MEAN and agg["min_metric"] >= config.PASS_FLOOR and not blocking


def route(cluster, frame, plate, log=print):
    """'image' if the defect is already in the plate the frame was rendered from, else 'code'."""
    t = cluster["defect_type"]
    if t in IMAGE_OWNED:
        return "image"
    if t in CODE_OWNED:
        return "code"
    # ambiguous type: look at the same region of the plate and ask whether the defect is there already
    h, w = plate.shape[:2]
    x0, y0, x1, y1 = cluster["box_0_1000"]
    crop = plate[int(y0 * h / 1000):max(int(y0 * h / 1000) + 8, int(y1 * h / 1000)),
                 int(x0 * w / 1000):max(int(x0 * w / 1000) + 8, int(x1 * w / 1000))]
    sch = {"type": "object", "properties": {"defect_present": {"type": "boolean"}, "reason": {"type": "string"}},
           "required": ["defect_present", "reason"]}
    try:
        out, _ = llm.chat_json(config.REVIEW_PANEL[-1], "A reviewer reported this defect in a rendered frame: '%s' (%s). "
                               "This crop is the same region of the source template before rendering. Is the same "
                               "defect already visible here?" % (cluster["descriptions"][0], t), sch,
                               images=[jpeg_b64(crop, 768)], log=log)
        return "image" if out["defect_present"] else "code"
    except Exception:
        return "code"


def summarize(clusters, n=8):
    return [dict(type=c["defect_type"], severity=c["severity"], confirmed=c["confirmed"], support=c["support"],
                 box=c["box_0_1000"], what=c["descriptions"][0][:200]) for c in clusters[:n]]
