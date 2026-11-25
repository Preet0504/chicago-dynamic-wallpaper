"""Stage 3 - big work: image generation of the season templates, with review loop A.

For every season phase we need two plates in the base image's exact geometry: a DAY plate (lamps off) and a
NIGHT plate (lamps lit). The renderer blends between them by sun altitude and adds sky/sun/moon/clouds/weather.

  reference pair:  the base itself is one of them (night or day, whatever it shows); the other is a relight edit.
  other phases:    day_p   = season edit of the day reference
                   night_p = night relight of day_p            (so day and night of a phase show the same foliage)
  snow (optional): day/night like a phase, triggered at runtime by real snow depth.

Every generation is aligned to the base (align.align) and static structure is locked to the base (align.lock).
Loop A: deterministic checks + VLM panel per plate; failing plates are regenerated with a new seed and the panel's
confirmed issues appended to the prompt; the best-scoring candidate is kept. Output: 03_plates/plates.json.
"""
import os
import shutil
import zlib

import cv2
import numpy as np

from . import align, config, imagegen, llm, review
from .common import Timer, read_json, write_json

STAGE = "03_plates"
KEEP = "Do not add, remove, move or resize anything: same composition, same objects, same framing and camera, same {style}."


def load_masks(job):
    z = np.load(job.path("01_perception", "masks.npz"))
    return {k: z[k].astype(np.float32) for k in z.files}


def masks_static_change(masks):
    static = np.clip(sum(masks.get(k, 0) for k in ("structure", "person", "vehicle", "object", "light_source", "window")), 0, 1)
    change = np.clip(sum(masks.get(k, 0) for k in ("vegetation", "terrain", "ground", "roof", "water")), 0, 1)
    return static.astype(np.float32), change.astype(np.float32)


def affected_names(scene, effects):
    names = sorted({o["label"] for o in scene["objects"] if set(o["affected_by"]) & set(effects)})
    return ", ".join(names[:14]) or "the vegetation and ground"


def prompts(scene, plan):
    style = scene["style"] or "painting style"
    keep = KEEP.format(style=style)
    has_lights = any(o["category"] in ("light_source", "window") and "lights_on_off" in o["affected_by"] for o in scene["objects"])
    lights_off = "All lamps, lanterns and windows are switched off (unlit)." if has_lights else ""
    lights_on = "The street lamps, lanterns and windows glow with warm light." if has_lights else ""
    season_objs = affected_names(scene, ["season_foliage", "snow_cover"])
    to_day = ("Change only the lighting to a bright clear day with soft natural daylight and a plain blue sky. %s "
              "Keep the season exactly as it is. %s" % (lights_off, keep))
    to_night = ("Change only the lighting to a clear night after dusk: deep blue night sky, moonlit soft light on the "
                "scene. %s Keep the season exactly as it is. %s" % (lights_on, keep))

    def season(p, snow=False):
        what = plan["snow_visual"] if snow else p["visual_changes"]
        return ("Repaint only %s for this season: %s. Daytime with soft natural light and a plain sky. %s %s"
                % (season_objs, what, lights_off, keep))
    return to_day, to_night, season


def plate_conditions(plan, key, scene):
    phase, tod = key.rsplit("_", 1)
    if phase == "snow":
        desc = "snow lying on the ground (%s)" % plan["snow_visual"][:160]
    else:
        p = next(x for x in plan["phases"] if x["id"] == phase)
        desc = "%s - %s" % (p["name"], p["ground_and_foliage"])
    light = "daytime, lamps and windows unlit" if tod == "day" else "night, lamps and windows lit"
    return "%s; %s. The sky will be replaced later, so judge the landscape more than the sky." % (desc, light)


def run(job, scene, plan, log=None, only=None, rounds=None):
    """only: restrict to these plate keys (the fast preview); results land in the shared state.json so the full run
    later skips what the preview already accepted. The stage is marked done only by a full (only=None) run."""
    log = log or job.log
    d = job.stage_dir(STAGE)
    rounds = rounds or config.PLATE_MAX_ROUNDS
    if job.done(STAGE):
        return read_json(os.path.join(d, "plates.json"))
    gen_dir = os.path.join(d, "gen")
    os.makedirs(gen_dir, exist_ok=True)
    with Timer(job, STAGE + ("_preview" if only else "")):
        base = job.base()
        masks = load_masks(job)
        static, change = masks_static_change(masks)
        gate = 1 - np.clip(masks.get("sky", np.zeros(base.shape[:2], np.float32)), 0, 1)
        to_day, to_night, season = prompts(scene, plan)
        base_is_night = scene["base_time_of_day"] in ("night", "twilight")
        phases = [p["id"] for p in plan["phases"]]
        bp = plan["base_phase_id"]
        keys = [ph + "_" + t for ph in phases for t in ("day", "night")]
        if plan["snow_cover_template"]:
            keys += ["snow_day", "snow_night"]
        all_keys = keys
        if only:
            keys = [k for k in keys if k in only]
        state = read_json(os.path.join(d, "state.json"), {}) or {}
        state.setdefault("plates", {})

        def post(raw, out):
            aligned, q = align.align(base, cv2.imread(raw), gate)
            locked = align.lock(base, aligned, static, change, lights_off="_day_" in os.path.basename(out))
            cv2.imwrite(out, locked)
            return q

        def spec_for(key, attempt, fix=""):
            ph, tod = key.rsplit("_", 1)
            seed = 101 + 17 * attempt + zlib.crc32(key.encode()) % 1000
            raw = os.path.join(gen_dir, "%s_a%d_raw.png" % (key, attempt))
            if tod == "day":
                src = ref_day
                prompt = to_day if (ph == bp and base_is_night) else season(next((p for p in plan["phases"] if p["id"] == ph), None),
                                                                            snow=(ph == "snow"))
            else:
                src = os.path.join(d, ph + "_day.png") if ph != bp else job.path("input", "base.png")
                prompt = to_night
            if fix:
                prompt += " Fix these problems from the last attempt: " + fix
            return dict(images=[src], prompt=prompt, seed=seed, out=raw)

        # --- reference pair
        ref_day = job.path("input", "base.png")
        fixed = {}
        if base_is_night:
            fixed[bp + "_night"] = job.path("input", "base.png")
        else:
            fixed[bp + "_day"] = job.path("input", "base.png")
        for k, src in fixed.items():
            shutil.copy(src, os.path.join(d, k + ".png"))
            state["plates"][k] = dict(status="base", file=k + ".png", score=None)
        if base_is_night:
            ref_key = bp + "_day"
            if not os.path.exists(os.path.join(d, ref_key + ".png")):
                sp = spec_for(ref_key, 0)
                sp["images"] = [job.path("input", "base.png")]
                sp["prompt"] = to_day
                imagegen.edit_batch([sp], gen_dir, log)
                cand = sp["out"].replace("_raw.png", ".png")
                q = post(sp["out"], cand)
                shutil.copy(cand, os.path.join(d, ref_key + ".png"))
                state["plates"][ref_key] = dict(status="generated", attempts=[dict(raw=sp["out"], align=q,
                                                                                  file=os.path.relpath(cand, d))])
            ref_day = os.path.join(d, ref_key + ".png")

        # --- loop A
        todo = [k for k in keys if state["plates"].get(k, {}).get("status") not in ("base", "accepted", "kept_best")]
        fixes = {}
        for rnd in range(rounds):
            if not todo:
                break
            log("  loop A round %d: %d plates to make/review" % (rnd + 1, len(todo)))
            for tod in ("day", "night"):        # nights are derived from days, so days first
                batch = []
                for k in todo:
                    if not k.endswith("_" + tod):
                        continue
                    st = state["plates"].setdefault(k, dict(attempts=[]))
                    if k == bp + "_day" and base_is_night and rnd == 0 and os.path.exists(os.path.join(d, k + ".png")):
                        continue        # reference day plate made above, review it as attempt 0
                    last = (st.get("attempts") or [None])[-1]
                    if last and "scores" not in last and os.path.exists(os.path.join(d, last.get("file", "-"))):
                        continue        # generated before an interruption but never reviewed: review it now
                    fx = fixes.get(k) or " ".join(i["what"] for i in (last or {}).get("issues", []) if i.get("confirmed"))[:500]
                    sp = spec_for(k, len(st.get("attempts", [])), fx)
                    if k == bp + "_day" and base_is_night:
                        sp["images"], sp["prompt"] = [job.path("input", "base.png")], to_day + (
                            " Fix these problems from the last attempt: " + fixes[k] if fixes.get(k) else "")
                    batch.append((k, sp))
                imagegen.edit_batch([sp for _, sp in batch], gen_dir, log)
                for k, sp in batch:
                    cand = sp["out"].replace("_raw.png", ".png")
                    q = post(sp["out"], cand)
                    st = state["plates"][k]
                    st.setdefault("attempts", []).append(dict(raw=sp["out"], file=os.path.relpath(cand, d), align=q))
                    shutil.copy(cand, os.path.join(d, k + ".png"))  # current candidate (night derives from it)
            # review every plate made this round
            llm.unload_all()
            failed = []
            for k in todo:
                st = state["plates"][k]
                att = st["attempts"][-1]
                img = cv2.imread(os.path.join(d, att["file"]))
                cond = plate_conditions(plan, k, scene)
                m, chk = review.deterministic(img, base, masks, dict(is_night=k.endswith("_night"),
                                                                     sun_alt=30 if k.endswith("_day") else -20))
                clusters, agg, ok, info = review.review_frame(img, base, cond, chk, notes=scene["summary"][:300], log=log)
                att.update(metrics=m, scores=agg, issues=review.summarize(clusters), passed=ok, review=info)
                log("    %-22s mean %.2f min %.2f %s [%s %.0fs]  %s" % (k, agg["mean"], agg["min_metric"],
                                                                     "PASS" if ok else "fail", info["tier"], info["seconds"],
                                                           "; ".join("%s(%s)" % (c["defect_type"], c["support"])
                                                                     for c in clusters[:3] if c["confirmed"])))
                # keep the best attempt as the plate
                best = max(st["attempts"], key=lambda a: (a.get("passed", False), a.get("scores", {}).get("mean", 0)))
                if "file" in best:
                    shutil.copy(os.path.join(d, best["file"]), os.path.join(d, k + ".png"))
                st["best"] = best.get("file")
                st["score"] = best.get("scores", {}).get("mean")
                if ok:
                    st["status"] = "accepted"
                else:
                    prev = st["attempts"][-2]["scores"]["mean"] if len(st["attempts"]) > 1 and "scores" in st["attempts"][-2] else None
                    if prev is not None and agg["mean"] - prev < config.PLATEAU_EPS and rnd > 0:
                        st["status"] = "kept_best"      # plateau: stop spending on this plate
                    else:
                        st["status"] = "retry"
                        failed.append(k)
                        fixes[k] = " ".join(c["descriptions"][0] for c in clusters if c["confirmed"])[:500] or \
                            " ".join(c["descriptions"][0] for c in clusters[:2])[:400]
                write_json(os.path.join(d, "state.json"), state)
            # a regenerated day invalidates its night
            for k in list(failed):
                if k.endswith("_day"):
                    n = k[:-4] + "_night"
                    if n in keys and n not in failed and state["plates"].get(n, {}).get("status") != "base":
                        failed.append(n)
                        state["plates"][n]["status"] = "retry"
            todo = failed
        for k in todo:
            state["plates"][k]["status"] = "kept_best"
        write_json(os.path.join(d, "state.json"), state)
        out = dict(keys=keys, base_is_night=base_is_night, base_phase=bp, all_keys=all_keys,
                   plates={k: dict(file=k + ".png", status=state["plates"][k].get("status"),
                                   score=state["plates"][k].get("score")) for k in keys})
        llm.unload_all()
        if not only:
            write_json(os.path.join(d, "plates.json"), out)
            job.mark_done(STAGE)
    return out


def redo(job, scene, plan, key, fix, log=None):
    """Loop B routed a defect to this plate: one more generation with the fix in the prompt, reviewed like loop A;
    it replaces the plate (and its package copy) only if it scores better. Returns True if replaced."""
    log = log or job.log
    d = job.path(STAGE)
    state = read_json(os.path.join(d, "state.json"), {}) or {}
    st = state.get("plates", {}).get(key)
    if not st or st.get("status") == "base":
        log("  plate %s is the user's own image; not regenerating" % key)
        return False
    base = job.base()
    masks = load_masks(job)
    static, change = masks_static_change(masks)
    gate = 1 - np.clip(masks.get("sky", np.zeros(base.shape[:2], np.float32)), 0, 1)
    to_day, to_night, season = prompts(scene, plan)
    bp = plan["base_phase_id"]
    base_is_night = scene["base_time_of_day"] in ("night", "twilight")
    ph, tod = key.rsplit("_", 1)
    attempt = len(st.get("attempts", []))
    if tod == "day":
        if ph == bp and base_is_night:
            src, prompt = job.path("input", "base.png"), to_day
        else:
            src = os.path.join(d, bp + "_day.png")
            prompt = season(next((p for p in plan["phases"] if p["id"] == ph), None), snow=(ph == "snow"))
    else:
        src = os.path.join(d, ph + "_day.png") if ph != bp else job.path("input", "base.png")
        prompt = to_night
    prompt += " Fix these problems from the last attempt: " + fix
    raw = os.path.join(d, "gen", "%s_a%d_raw.png" % (key, attempt))
    imagegen.edit_batch([dict(images=[src], prompt=prompt, seed=101 + 17 * attempt + zlib.crc32(key.encode()) % 1000,
                              out=raw)], os.path.join(d, "gen"), log)
    aligned, q = align.align(base, cv2.imread(raw), gate)
    cand = raw.replace("_raw.png", ".png")
    cv2.imwrite(cand, align.lock(base, aligned, static, change, lights_off=(tod == "day")))
    img = cv2.imread(cand)
    m, chk = review.deterministic(img, base, masks, dict(is_night=tod == "night", sun_alt=30 if tod == "day" else -20))
    clusters, agg, ok, info = review.review_frame(img, base, plate_conditions(plan, key, scene), chk,
                                                  notes=scene["summary"][:300], log=log)
    st.setdefault("attempts", []).append(dict(raw=raw, file=os.path.relpath(cand, d), align=q, metrics=m, scores=agg,
                                              issues=review.summarize(clusters), passed=ok, review=info,
                                              fix=fix, from_loop="B"))
    better = agg["mean"] > (st.get("score") or 0)
    log("  plate %s redo: %.2f vs %.2f -> %s" % (key, agg["mean"], st.get("score") or 0, "replaced" if better else "kept"))
    if better:
        shutil.copy(cand, os.path.join(d, key + ".png"))
        st.update(score=agg["mean"], best=os.path.relpath(cand, d))
        pk = job.path("04_package", "plates", key + ".png")
        if os.path.exists(pk):
            shutil.copy(cand, pk)
            from . import package
            package.refresh_sky(job, key)
    write_json(os.path.join(d, "state.json"), state)
    return better
