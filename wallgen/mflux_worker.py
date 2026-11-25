"""Batch image-edit worker. Runs inside mflux's own environment (not .venv-gen):

    ~/.local/share/uv/tools/mflux/bin/python wallgen/mflux_worker.py jobs.json

jobs.json: {"model": "flux2-klein-4b", "quantize": 8, "items": [
              {"images": ["a.png"], "prompt": "...", "seed": 1, "width": 1664, "height": 928, "steps": 4,
               "out": "x.png"}, ...]}
Loads the model once, runs every item, prints one JSON line per finished item. Items whose output exists are skipped.
"""
import json
import os
import sys
import time
from pathlib import Path


def main(spec_path):
    spec = json.load(open(spec_path))
    todo = [it for it in spec["items"] if not os.path.exists(it["out"])]
    if not todo:
        print(json.dumps({"status": "nothing to do"}), flush=True)
        return
    from mflux.models.common.config.model_config import AVAILABLE_MODELS  # noqa: F401
    from mflux.models.common.resolution.config_resolution import ConfigResolution
    from mflux.models.flux2.variants import Flux2KleinEdit
    name = spec.get("model", "flux2-klein-4b")
    t0 = time.time()
    cfg = ConfigResolution.resolve_restricted(name, "flux2-klein-4b", model_path=None, extra_keys=(), base_model=None)
    model = Flux2KleinEdit(model_config=cfg, quantize=spec.get("quantize", 8))
    print(json.dumps({"status": "loaded", "seconds": round(time.time() - t0, 1)}), flush=True)
    for it in todo:
        t1 = time.time()
        img = model.generate_image(seed=int(it["seed"]), prompt=it["prompt"], width=int(it["width"]),
                                   height=int(it["height"]), guidance=1.0,
                                   image_paths=[Path(p) for p in it["images"]],
                                   num_inference_steps=int(it.get("steps", 4)), scheduler="flow_match_euler_discrete")
        os.makedirs(os.path.dirname(it["out"]) or ".", exist_ok=True)
        tmp = it["out"] + ".part.png"
        img.save(path=tmp, export_json_metadata=False)
        os.replace(tmp, it["out"])
        print(json.dumps({"status": "done", "out": it["out"], "seconds": round(time.time() - t1, 1)}), flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
