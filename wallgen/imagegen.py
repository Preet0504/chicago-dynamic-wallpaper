"""Image generation front-end: batches edit requests to the mflux worker (one model load per batch), and
SeedVR2 upscaling for accepted plates. Ollama models are unloaded first so nothing swaps."""
import json
import os
import subprocess

import cv2

from . import config, llm
from .common import write_json

HERE = os.path.dirname(os.path.abspath(__file__))


def model_dims(w, h, long_side=1664):
    s = long_side / max(w, h)
    return int(round(w * s / 16)) * 16, int(round(h * s / 16)) * 16


def edit_batch(items, workdir, log=print):
    """items: list of dict(images=[...], prompt, seed, out, [width, height, steps]). Runs them in one worker."""
    if not items:
        return []
    llm.unload_all()
    for it in items:
        if "width" not in it:
            h, w = cv2.imread(it["images"][0]).shape[:2]
            it["width"], it["height"] = model_dims(w, h)
        it.setdefault("steps", config.EDIT_STEPS)
    spec = os.path.join(workdir, "mflux_batch_%d.json" % (abs(hash(json.dumps(items, sort_keys=True))) % 10 ** 8))
    write_json(spec, dict(model=config.EDIT_MODEL, quantize=config.EDIT_QUANT, items=items))
    pending = [it for it in items if not os.path.exists(it["out"])]
    log("  image-gen: %d edits (%d cached) with %s" % (len(pending), len(items) - len(pending), config.EDIT_MODEL))
    p = subprocess.Popen([config.MFLUX_PY, os.path.join(HERE, "mflux_worker.py"), spec], stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True)
    for line in p.stdout:
        line = line.strip()
        if line.startswith("{"):
            ev = json.loads(line)
            if ev.get("status") == "done":
                log("    %s (%.0fs)" % (os.path.basename(ev["out"]), ev["seconds"]))
            elif ev.get("status") == "loaded":
                log("    model loaded in %.0fs" % ev["seconds"])
    err = p.stderr.read()
    if p.wait() != 0:
        raise RuntimeError("mflux worker failed: %s" % err[-1500:])
    return [it["out"] for it in items]


def upscale(src, out, height=2160, log=print):
    """SeedVR2 4K master of an accepted plate (same tool the original templates used)."""
    if os.path.exists(out) and os.path.getmtime(out) > os.path.getmtime(src):
        return out
    llm.unload_all()
    tmp = out + ".part.png"
    subprocess.run([config.MFLUX_UPSCALE, "--image-path", src, "--resolution", str(height), "--seed", "1",
                    "--output", tmp], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    im = cv2.imread(tmp)
    im = cv2.resize(im, (config.OUT_W, config.OUT_H), interpolation=cv2.INTER_AREA)
    cv2.imwrite(out, im)
    os.remove(tmp)
    log("    upscaled %s" % os.path.basename(out))
    return out
