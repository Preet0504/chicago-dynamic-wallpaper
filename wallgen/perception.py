"""Stage 1 - what is in the picture, and what of it changes with weather and time?

Path A: Mask2Former (ADE20K, 150 classes, every pixel) + Grounding DINO (small things: lamps, lanterns, windows…)
        + SAM masks  ->  object list with confidences  ->  local LLM reasons per object.
Path B: a vision-language model looks at the image itself and lists the same things in the same schema.
Both answer in ONE fixed taxonomy so they can be compared. Agreement = Jaccard of the affectable category sets.
Disagreements go to a third model (different family) that looks at a crop. Result: the union.

Writes 01_perception/scene.json, masks.npz (per-layer + per-object masks), depth.npy, overlay.jpg.
"""
import concurrent.futures as cf
import json
import os

import cv2
import numpy as np

from . import config, llm
from .common import Timer, jpeg_b64, overlay_masks, read_json, write_json

STAGE = "01_perception"

CATEGORIES = ["sky", "water", "vegetation", "terrain", "ground", "structure", "roof", "light_source", "window",
              "vehicle", "person", "object", "indoor_surface"]
EFFECTS = ["time_of_day_light", "lights_on_off", "season_foliage", "snow_cover", "rain_wetness", "cloud_cover",
           "sun_moon_visible", "reflections", "fog_visibility"]
# categories whose pixels can carry a visible weather/time change
AFFECTABLE = {"sky", "water", "vegetation", "terrain", "ground", "roof", "light_source", "window"}

ADE_TO_CAT = {
    "sky": "sky", "water": "water", "sea": "water", "river": "water", "lake": "water", "swimming pool": "water",
    "fountain": "water", "waterfall": "water",
    "tree": "vegetation", "plant": "vegetation", "grass": "vegetation", "flower": "vegetation", "palm": "vegetation",
    "field": "vegetation",
    "mountain": "terrain", "hill": "terrain", "rock": "terrain", "sand": "terrain", "land": "terrain", "earth": "terrain",
    "dirt track": "ground", "road": "ground", "sidewalk": "ground", "path": "ground", "stairs": "ground",
    "stairway": "ground", "step": "ground", "runway": "ground", "floor": "ground",
    "building": "structure", "house": "structure", "skyscraper": "structure", "tower": "structure", "wall": "structure",
    "fence": "structure", "railing": "structure", "bridge": "structure", "pier": "structure", "column": "structure",
    "hovel": "structure", "awning": "structure", "canopy": "structure", "booth": "structure", "tent": "structure",
    "bannister": "structure", "pole": "structure", "grandstand": "structure", "sculpture": "structure",
    "lamp": "light_source", "light": "light_source", "streetlight": "light_source", "chandelier": "light_source",
    "sconce": "light_source", "traffic light": "light_source", "signboard": "light_source",
    "windowpane": "window",
    "car": "vehicle", "bus": "vehicle", "truck": "vehicle", "van": "vehicle", "boat": "vehicle", "ship": "vehicle",
    "bicycle": "vehicle", "minibike": "vehicle", "airplane": "vehicle",
    "person": "person", "animal": "person",
    "ceiling": "indoor_surface", "bed": "indoor_surface", "sofa": "indoor_surface", "cabinet": "indoor_surface",
    "rug": "indoor_surface", "curtain": "indoor_surface", "table": "indoor_surface", "chair": "indoor_surface",
}
DET_PROMPTS = ["lantern", "street lamp", "lamp post", "lit window", "window", "traffic light", "neon sign",
               "sun", "moon", "roof", "snow", "puddle", "chimney"]
DET_TO_CAT = {"lantern": "light_source", "street lamp": "light_source", "lamp post": "light_source",
              "lit window": "window", "window": "window", "traffic light": "light_source", "neon sign": "light_source",
              "sun": "sky", "moon": "sky", "roof": "roof", "snow": "ground", "puddle": "ground", "chimney": "structure"}


# ------------------------------------------------------------------------------------------- vision models
def _device():
    import torch
    return "mps" if torch.backends.mps.is_available() else "cpu"


def segment(img_bgr):
    """ADE20K semantic segmentation: returns (label map HxW, per-class mean prob dict, id2label)."""
    import torch
    from PIL import Image
    from transformers import AutoImageProcessor, Mask2FormerForUniversalSegmentation
    proc = AutoImageProcessor.from_pretrained(config.SEG_MODEL)
    model = Mask2FormerForUniversalSegmentation.from_pretrained(config.SEG_MODEL).eval()
    dev = _device()
    try:
        model.to(dev)
    except Exception:
        dev = "cpu"
    h, w = img_bgr.shape[:2]
    pil = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
    with torch.no_grad():
        inp = proc(images=pil, return_tensors="pt").to(dev)
        out = model(**inp)
        # class probabilities per pixel: softmax over queries' classes weighted by mask probs
        cls = out.class_queries_logits.softmax(-1)[..., :-1]          # B,Q,C
        masks = out.masks_queries_logits.sigmoid()                    # B,Q,h,w
        seg = torch.einsum("bqc,bqhw->bchw", cls, masks)
        seg = torch.nn.functional.interpolate(seg, size=(h, w), mode="bilinear", align_corners=False)[0]
        prob = seg / (seg.sum(0, keepdim=True) + 1e-6)
        conf, lab = prob.max(0)
    lab, conf = lab.cpu().numpy().astype(np.int32), conf.cpu().numpy().astype(np.float32)
    del model
    return lab, conf, model_id2label(config.SEG_MODEL)


def model_id2label(name):
    from transformers import AutoConfig
    return {int(k): v for k, v in AutoConfig.from_pretrained(name).id2label.items()}


def detect(img_bgr, prompts=DET_PROMPTS, box_thr=0.30, text_thr=0.25):
    import torch
    from PIL import Image
    from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor
    proc = AutoProcessor.from_pretrained(config.DET_MODEL)
    model = AutoModelForZeroShotObjectDetection.from_pretrained(config.DET_MODEL).eval()
    pil = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
    text = ". ".join(prompts) + "."
    with torch.no_grad():
        inp = proc(images=pil, text=text, return_tensors="pt")
        out = model(**inp)
    res = proc.post_process_grounded_object_detection(out, inp.input_ids, threshold=box_thr, text_threshold=text_thr,
                                                      target_sizes=[pil.size[::-1]])[0]
    dets = []
    labels = res.get("text_labels", res.get("labels"))
    for box, score, lab in zip(res["boxes"].tolist(), res["scores"].tolist(), labels):
        lab = str(lab).strip()
        lab = next((p for p in prompts if p == lab), next((p for p in prompts if p in lab), lab))
        x0, y0, x1, y1 = box
        area = (x1 - x0) * (y1 - y0) / (pil.size[0] * pil.size[1])
        if area > 0.5:      # "window" boxes covering half the frame are not windows
            continue
        dets.append(dict(label=lab, score=round(score, 3), box=[round(v, 1) for v in box]))
    del model
    return _nms(dets)


def _nms(dets, iou=0.6):
    dets = sorted(dets, key=lambda d: -d["score"])
    keep = []
    for d in dets:
        if all(_iou(d["box"], k["box"]) < iou or d["label"] != k["label"] for k in keep):
            keep.append(d)
    return keep


def _iou(a, b):
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / (ua + 1e-6)


def sam_masks(img_bgr, boxes):
    if not boxes:
        return []
    import torch
    from PIL import Image
    from transformers import SamModel, SamProcessor
    proc = SamProcessor.from_pretrained(config.SAM_MODEL)
    model = SamModel.from_pretrained(config.SAM_MODEL).eval()
    pil = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
    out = []
    for i in range(0, len(boxes), 16):
        chunk = [list(map(float, b)) for b in boxes[i:i + 16]]
        with torch.no_grad():
            inp = proc(images=pil, input_boxes=[chunk], return_tensors="pt")
            o = model(**inp, multimask_output=False)
        ms = proc.image_processor.post_process_masks(o.pred_masks, inp["original_sizes"], inp["reshaped_input_sizes"])[0]
        for m in ms:
            out.append(m[0].numpy().astype(np.float32))
    del model
    return out


def depth(img_bgr):
    import torch
    from PIL import Image
    from transformers import AutoImageProcessor, AutoModelForDepthEstimation
    proc = AutoImageProcessor.from_pretrained(config.DEPTH_MODEL)
    model = AutoModelForDepthEstimation.from_pretrained(config.DEPTH_MODEL).eval()
    pil = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
    with torch.no_grad():
        pred = model(**proc(images=pil, return_tensors="pt")).predicted_depth
    d = torch.nn.functional.interpolate(pred[None], size=img_bgr.shape[:2], mode="bicubic", align_corners=False)[0, 0]
    disp = d.numpy().astype(np.float32)               # relative inverse depth: large = near
    disp = (disp - np.percentile(disp, 1)) / (np.percentile(disp, 99.5) - np.percentile(disp, 1) + 1e-6)
    del model
    return np.clip(1 - disp, 0, 1)                    # 0 = nearest, 1 = farthest


# ----------------------------------------------------------------------------------------------- path A
def objects_from_vision(lab, conf, id2label, dets, det_masks, shape):
    h, w = shape
    objs = []
    for cid in np.unique(lab):
        m = lab == cid
        area = m.mean()
        name = id2label[int(cid)]
        if area < 0.003:
            continue
        ys, xs = np.nonzero(m)
        objs.append(dict(id="seg%d" % cid, label=name, source="mask2former", confidence=round(float(conf[m].mean()), 3),
                         area_pct=round(100 * area, 2), bbox=[int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
                         where=_where(xs.mean() / w, ys.mean() / h), hint=ADE_TO_CAT.get(name, "object")))
    for i, (d, m) in enumerate(zip(dets, det_masks)):
        objs.append(dict(id="det%d" % i, label=d["label"], source="grounding-dino+sam", confidence=d["score"],
                         area_pct=round(100 * float((m > 0.5).mean()), 3), bbox=[int(v) for v in d["box"]],
                         where=_where((d["box"][0] + d["box"][2]) / 2 / w, (d["box"][1] + d["box"][3]) / 2 / h),
                         hint=DET_TO_CAT.get(d["label"], "object")))
    return objs


def _where(fx, fy):
    return ("top" if fy < 0.33 else "middle" if fy < 0.66 else "bottom") + "-" + \
           ("left" if fx < 0.33 else "centre" if fx < 0.66 else "right")


ITEM_SCHEMA = {"type": "object", "properties": {
    "id": {"type": "string"}, "label": {"type": "string"}, "category": {"type": "string", "enum": CATEGORIES},
    "affected_by": {"type": "array", "items": {"type": "string", "enum": EFFECTS}},
    "reason": {"type": "string"}}, "required": ["id", "label", "category", "affected_by", "reason"]}
A_SCHEMA = {"type": "object", "properties": {
    "objects": {"type": "array", "items": ITEM_SCHEMA},
    "scene_is_outdoor_or_shows_outdoors": {"type": "boolean"},
    "anything_changes_with_weather_or_time": {"type": "boolean"}, "summary": {"type": "string"}},
    "required": ["objects", "scene_is_outdoor_or_shows_outdoors", "anything_changes_with_weather_or_time", "summary"]}

TAXONOMY_TEXT = """Categories: %s.
Effects (what can visibly change it): %s.
Rules: every outdoor surface is lit differently by time of day (time_of_day_light). Only things that EMIT light get
lights_on_off. Deciduous trees/grass/flowers get season_foliage; evergreens do not. Snow can lie on ground, roofs,
terrain, vegetation (snow_cover) only if the location gets snow. Water reflects the sky (reflections). The sky gets
cloud_cover and sun_moon_visible. Indoor-only things (ceiling, bed, sofa) are not affected unless lit by a window.""" % (
    ", ".join(CATEGORIES), ", ".join(EFFECTS))


def path_a(objs, location, log):
    slim = [{k: o[k] for k in ("id", "label", "source", "confidence", "area_pct", "where", "hint")} for o in objs]
    prompt = ("A detector and a segmenter found these objects in an image (confidence 0-1, area as % of the frame):\n"
              + json.dumps(slim) + "\n\nLocation of the scene: %s.\n%s\n\n" % (location, TAXONOMY_TEXT)
              + "For EVERY object give its category and which effects can visibly change it, with a one-line reason. "
                "Drop obvious detector mistakes by giving them category 'object' and no effects.")
    out, secs = llm.chat_json(config.LLM_PERCEPTION, prompt, A_SCHEMA, log=log, num_ctx=16384)
    log("  path A (%s over %d detections): %.0fs" % (config.LLM_PERCEPTION, len(objs), secs))
    return out


B_SCHEMA = {"type": "object", "properties": {
    "objects": {"type": "array", "items": {"type": "object", "properties": {
        "label": {"type": "string"}, "category": {"type": "string", "enum": CATEGORIES},
        "affected_by": {"type": "array", "items": {"type": "string", "enum": EFFECTS}},
        "box_0_1000": {"type": "array", "items": {"type": "integer"}}, "reason": {"type": "string"}},
        "required": ["label", "category", "affected_by", "box_0_1000", "reason"]}},
    "scene_is_outdoor_or_shows_outdoors": {"type": "boolean"},
    "anything_changes_with_weather_or_time": {"type": "boolean"},
    "time_of_day_shown": {"type": "string", "enum": ["night", "twilight", "day", "golden_hour", "unclear"]},
    "season_shown": {"type": "string", "enum": ["spring", "summer", "autumn", "winter", "unclear"]},
    "weather_shown": {"type": "string"},
    "style": {"type": "string"}, "has_visible_sky": {"type": "boolean"},
    "horizon_height_0_1000": {"type": "integer"}, "lights_currently_lit": {"type": "boolean"},
    "summary": {"type": "string"}},
    "required": ["objects", "scene_is_outdoor_or_shows_outdoors", "anything_changes_with_weather_or_time",
                 "time_of_day_shown", "season_shown", "weather_shown", "style", "has_visible_sky",
                 "horizon_height_0_1000", "lights_currently_lit", "summary"]}


def path_b(img, location, log):
    prompt = ("Look at this image. List every distinct element that could visibly change with the weather, the "
              "season or the time of day (sky, water, trees, grass, mountains, ground, roofs, street lamps, lanterns, "
              "windows...) and also the main static elements (buildings, railings, vehicles). Give each a box "
              "[x0,y0,x1,y1] in 0-1000 image coordinates. Location of the scene: %s.\n%s\n"
              "Also describe the image as painted: time of day, season, weather, art style, whether sky is visible, "
              "where the horizon is (0 = top, 1000 = bottom), and whether lights are lit." % (location, TAXONOMY_TEXT))
    out, secs = llm.chat_json(config.VLM_PERCEPTION, prompt, B_SCHEMA, images=[jpeg_b64(img, 1536)], log=log)
    log("  path B (%s, looks at the image): %.0fs, %d elements" % (config.VLM_PERCEPTION, secs, len(out["objects"])))
    return out


def tiebreak(img, category, box, log):
    h, w = img.shape[:2]
    x0, y0, x1, y1 = box
    pad = 0.15
    bx0, by0 = max(0, int(x0 - pad * (x1 - x0))), max(0, int(y0 - pad * (y1 - y0)))
    bx1, by1 = min(w, int(x1 + pad * (x1 - x0))), min(h, int(y1 + pad * (y1 - y0)))
    if bx1 - bx0 < 8 or by1 - by0 < 8:
        crop = img
    else:
        crop = img[by0:by1, bx0:bx1]
    sch = {"type": "object", "properties": {"present": {"type": "boolean"}, "changes_with_weather_or_time": {"type": "boolean"},
                                            "reason": {"type": "string"}},
           "required": ["present", "changes_with_weather_or_time", "reason"]}
    out, _ = llm.chat_json(config.VLM_TIEBREAK, "Two systems disagree about this crop of a larger image. Is there a "
                           "'%s' in it, and would it visibly change with weather, season or time of day? Answer "
                           "strictly from what you see." % category, sch, images=[jpeg_b64(crop, 768)], log=log)
    return out


# ------------------------------------------------------------------------------------------------- stage
def run(job, log=None):
    log = log or job.log
    d = job.stage_dir(STAGE)
    if job.done(STAGE):
        return read_json(os.path.join(d, "scene.json"))
    img = job.base()
    h, w = img.shape[:2]
    location = job.meta()["location"]
    with Timer(job, STAGE):
        # --- vision models (path A's eyes); cached so a rerun only repeats the reasoning
        vis_p = os.path.join(d, "vision.npz")
        if os.path.exists(vis_p):
            z = np.load(vis_p, allow_pickle=True)
            lab, conf, dep, det_masks = z["lab"], z["conf"], z["depth"], list(z["det_masks"])
            dets, id2label = read_json(os.path.join(d, "detections.json")), {int(k): v for k, v in
                                                                             read_json(os.path.join(d, "id2label.json")).items()}
        else:
            log("  segmenting (Mask2Former ADE20K)…")
            lab, conf, id2label = segment(img)
            log("  detecting small things (Grounding DINO)…")
            dets = detect(img)
            det_masks = sam_masks(img, [dd["box"] for dd in dets])
            log("  %d detections, masks by SAM; depth (Depth Anything V2)…" % len(dets))
            dep = depth(img)
            np.savez_compressed(vis_p, lab=lab, conf=conf, depth=dep,
                                det_masks=np.array(det_masks if det_masks else np.zeros((0, h, w), np.float32)))
            write_json(os.path.join(d, "detections.json"), dets)
            write_json(os.path.join(d, "id2label.json"), id2label)
            _free_torch()
        objs = objects_from_vision(lab, conf, id2label, dets, det_masks, (h, w))

        # --- the two reasoning paths, in parallel
        A, B = read_json(os.path.join(d, "path_a.json")), read_json(os.path.join(d, "path_b.json"))
        if not (A and B):
            with cf.ThreadPoolExecutor(2) as ex:
                fa = ex.submit(path_a, objs, location, log)
                fb = ex.submit(path_b, img, location, log)
                A, B = fa.result(), fb.result()
            write_json(os.path.join(d, "path_a.json"), A)
            write_json(os.path.join(d, "path_b.json"), B)
        llm.unload(config.VLM_PERCEPTION, config.LLM_PERCEPTION)

        scene = reconcile(img, objs, A, B, lab, id2label, dets, det_masks, dep, d, log)
        write_json(os.path.join(d, "scene.json"), scene)
        llm.unload(config.VLM_TIEBREAK)
        job.mark_done(STAGE, affectable=scene["affectable"])
    return scene


def _free_torch():
    import gc
    gc.collect()
    try:
        import torch
        torch.mps.empty_cache()
    except Exception:
        pass


def reconcile(img, objs, A, B, lab, id2label, dets, det_masks, dep, d, log):
    h, w = img.shape[:2]
    by_id = {o["id"]: o for o in objs}
    a_items = [x for x in A["objects"] if x["id"] in by_id]
    a_aff = [x for x in a_items if x["affected_by"] and x["category"] in AFFECTABLE]
    b_aff = [x for x in B["objects"] if x["affected_by"] and x["category"] in AFFECTABLE]
    ca, cb = {x["category"] for x in a_aff}, {x["category"] for x in b_aff}
    union_c = ca | cb
    jac = len(ca & cb) / len(union_c) if union_c else 1.0
    log("  agreement: A=%s  B=%s  Jaccard %.2f" % (sorted(ca), sorted(cb), jac))

    # per-pixel layer masks start from path A's labelled pixels
    layers = {c: np.zeros((h, w), np.float32) for c in CATEGORIES}
    final = []
    for x in a_items:
        o = by_id[x["id"]]
        if o["source"] == "mask2former":
            cid = int(o["id"][3:])
            m = (lab == cid).astype(np.float32)
        else:
            m = det_masks[int(o["id"][3:])]
        layers[x["category"]] = np.maximum(layers[x["category"]], m)
        final.append(dict(id=x["id"], label=x["label"], category=x["category"], affected_by=x["affected_by"],
                          reason=x["reason"], confidence=o["confidence"], bbox=o["bbox"], sources=["A"]))
    # match B's elements onto A's by category + box overlap; unmatched B elements need their own masks
    b_only = []
    for x in B["objects"]:
        bx = _box_px(x["box_0_1000"], w, h)
        hit = next((f for f in final if f["category"] == x["category"] and _overlap(f["bbox"], bx) > 0.3), None)
        if hit:
            if "B" not in hit["sources"]:
                hit["sources"].append("B")
            hit["affected_by"] = sorted(set(hit["affected_by"]) | set(x["affected_by"]))
        elif x["category"] in AFFECTABLE and x["affected_by"]:
            b_only.append((x, bx))

    # disagreements: a category only one side found -> third model looks at a crop
    disputed = sorted(union_c - (ca & cb))
    verdicts = {}
    for cat in disputed:
        if cat in cb:
            box = next(bx for x, bx in b_only + [(x, _box_px(x["box_0_1000"], w, h)) for x in b_aff] if x["category"] == cat)
        else:
            box = next(f["bbox"] for f in final if f["category"] == cat)
        try:
            v = tiebreak(img, cat, box, log)
        except Exception as e:      # no verdict: keep the union (the side that saw it wins)
            log("  tie-break %s failed (%s) - keeping it (union)" % (cat, str(e)[:120]))
            v = dict(present=True, changes_with_weather_or_time=True, reason="tie-break unavailable; union kept")
        verdicts[cat] = v
        log("  tie-break %s: present=%s changes=%s (%s)" % (cat, v["present"], v["changes_with_weather_or_time"],
                                                          v["reason"][:80]))
    keep_b = [(x, bx) for x, bx in b_only if x["category"] not in verdicts or
              (verdicts[x["category"]]["present"] and verdicts[x["category"]]["changes_with_weather_or_time"])]
    if keep_b:
        from . import perception as P  # SAM for B-only boxes
        ms = P.sam_masks(img, [bx for _, bx in keep_b])
        _free_torch()
        for (x, bx), m in zip(keep_b, ms):
            layers[x["category"]] = np.maximum(layers[x["category"]], m)
            final.append(dict(id="vlm_%s" % x["label"].replace(" ", "_"), label=x["label"], category=x["category"],
                              affected_by=x["affected_by"], reason=x["reason"], confidence=None,
                              bbox=[int(v) for v in bx], sources=["B"]))
    for cat, v in verdicts.items():
        if cat in ca and not (v["present"] and v["changes_with_weather_or_time"]):
            for f in final:
                if f["category"] == cat and f["sources"] == ["A"]:
                    f["affected_by"] = []

    # a painted sun/moon belongs to the sky: the renderer draws the real one for each moment
    for f in final:
        if any(w in f["label"].lower() for w in ("moon", "sun")) and f["category"] in ("object", "sky"):
            x0, y0, x1, y1 = [int(v) for v in f["bbox"]]
            pad = int(0.15 * max(x1 - x0, y1 - y0))
            sub = layers["object"][max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad]
            m = np.zeros((h, w), np.float32)
            cv2.circle(m, ((x0 + x1) // 2, (y0 + y1) // 2), int(0.62 * max(x1 - x0, y1 - y0)), 1.0, -1)
            layers["sky"] = np.maximum(layers["sky"], m)
            layers["object"] = np.where(m > 0, 0, layers["object"])
            f["category"] = "sky"
            del sub
    # sky: soft matte refined against the image itself; everything else hard
    sky = refine_matte(img, layers["sky"])
    layers["sky"] = sky
    aff_objs = [f for f in final if f["affected_by"] and f["category"] in AFFECTABLE]
    affectable = bool(aff_objs) and (A["anything_changes_with_weather_or_time"] or B["anything_changes_with_weather_or_time"])
    agree = jac >= config.AGREE_JACCARD or all(verdicts.get(c, {}).get("present") is not None for c in disputed)
    np.savez_compressed(os.path.join(d, "masks.npz"), **{k: v.astype(np.float16) for k, v in layers.items()})
    np.save(os.path.join(d, "depth.npy"), np.maximum(dep, sky).astype(np.float16))
    show = [layers[c] for c in CATEGORIES if layers[c].max() > 0.5]
    cv2.imwrite(os.path.join(d, "overlay.jpg"), overlay_masks(img, show, [c for c in CATEGORIES if layers[c].max() > 0.5]))
    horizon = B.get("horizon_height_0_1000", 500) / 1000.0
    if sky.max() > 0.5:   # measured horizon: lowest row where the sky still covers a good part of the width
        rows = (sky > 0.5).mean(1)
        idx = np.nonzero(rows > 0.05)[0]
        if len(idx):
            horizon = float(idx.max()) / h
    return dict(
        image=dict(w=w, h=h), location=None, style=B["style"], outdoor=B["scene_is_outdoor_or_shows_outdoors"],
        base_time_of_day=B["time_of_day_shown"], base_season=B["season_shown"], base_weather=B["weather_shown"],
        lights_lit_in_base=B["lights_currently_lit"], has_sky=bool(sky.mean() > 0.01), horizon=round(horizon, 3),
        summary=B["summary"], objects=final,
        layers_present={c: round(float((layers[c] > 0.5).mean()), 4) for c in CATEGORIES if layers[c].max() > 0.5},
        agreement=dict(jaccard=round(jac, 3), A=sorted(ca), B=sorted(cb), disputed=disputed, tiebreak=verdicts,
                       agreed=agree),
        affectable=affectable,
        message=None if affectable else "Nothing in this image visibly changes with weather or time of day.")


def _box_px(b, w, h):
    if not b or len(b) != 4:
        return [0, 0, w, h]
    x0, y0, x1, y1 = [max(0, min(1000, int(v))) for v in b]
    return [x0 * w / 1000, y0 * h / 1000, max(x0 + 1, x1) * w / 1000, max(y0 + 1, y1) * h / 1000]


def _overlap(a, b):
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    return inter / (min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1])) + 1e-6)


def refine_matte(img, m, r=8, eps=1e-3):
    """Guided-filter the hard sky mask against the image so the edge follows painted silhouettes."""
    if m.max() < 0.5:
        return m
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    box = lambda a: cv2.boxFilter(a, -1, (2 * r + 1, 2 * r + 1))
    mi, mp = box(g), box(m)
    a = (box(g * m) - mi * mp) / (box(g * g) - mi * mi + eps)
    b = mp - a * mi
    return np.clip(box(a) * g + box(b), 0, 1).astype(np.float32)
