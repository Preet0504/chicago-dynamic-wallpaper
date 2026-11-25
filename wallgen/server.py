"""Local web app: upload a picture + location, watch the pipeline, inspect every stage, preview any moment.

    .venv-gen/bin/python -m wallgen.server          # http://127.0.0.1:8765
Jobs run one at a time in a background worker (the models need the whole GPU).
"""
import io
import os
import queue
import re
import tempfile
import threading
import time

import cv2
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response

from . import codegen, config, pipeline
from .common import Job, read_json

app = FastAPI(title="Dynamic wallpaper generator")
WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
Q = queue.Queue()
SAFE = re.compile(r"^[A-Za-z0-9._-]+$")


def worker():
    while True:
        jid = Q.get()
        try:
            pipeline.run(Job(jid))
        except Exception as e:      # recorded in job.json by pipeline.run
            print("job %s failed: %r" % (jid, e))
        Q.task_done()


threading.Thread(target=worker, daemon=True).start()


@app.get("/", response_class=HTMLResponse)
def index():
    return open(os.path.join(WEB, "index.html")).read()


@app.post("/api/jobs")
async def create(image: UploadFile = File(...), location: str = Form(...)):
    if not location.strip():
        raise HTTPException(400, "location is required")
    data = await image.read()
    if len(data) > 60 * 1024 * 1024:
        raise HTTPException(413, "image too large")
    suffix = os.path.splitext(image.filename or "x.png")[1].lower() or ".png"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(data)
    try:
        job = Job.create(f.name, location.strip())
    except ValueError as e:
        raise HTTPException(400, str(e))
    finally:
        os.unlink(f.name)
    Q.put(job.id)
    return {"id": job.id}


@app.post("/api/jobs/{jid}/resume")
def resume(jid: str):
    _job(jid)
    Q.put(jid)
    return {"ok": True}


def _job(jid):
    if not SAFE.match(jid) or not os.path.isdir(os.path.join(config.JOBS, jid)):
        raise HTTPException(404, "no such job")
    return Job(jid)


@app.get("/api/jobs")
def jobs():
    out = []
    if os.path.isdir(config.JOBS):
        for jid in sorted(os.listdir(config.JOBS), reverse=True):
            if os.path.isdir(os.path.join(config.JOBS, jid)) and SAFE.match(jid):
                m = Job(jid).meta()
                out.append(dict(id=jid, location=m.get("location"), status=m.get("status"), created=m.get("created")))
    return out


@app.get("/api/jobs/{jid}")
def job(jid: str):
    j = _job(jid)
    m = j.meta()
    scene = read_json(j.path("01_perception", "scene.json"))
    plan = read_json(j.path("02_plan", "plan.json"))
    pstate = read_json(j.path("03_plates", "state.json"), {}) or {}
    hist = read_json(j.path("05_renderer", "history.json"), [])
    return dict(
        id=jid, meta=m, queue_position=list(Q.queue).index(jid) + 1 if jid in list(Q.queue) else None,
        perception=None if not scene else dict(agreement=scene["agreement"], summary=scene["summary"],
                                               affectable=scene["affectable"], message=scene["message"],
                                               base=dict(time=scene["base_time_of_day"], season=scene["base_season"],
                                                         style=scene["style"]),
                                               objects=[dict(label=o["label"], category=o["category"],
                                                             effects=o["affected_by"], sources=o["sources"])
                                                        for o in scene["objects"]]),
        plan=None if not plan else dict(phases=plan["phases"], base=plan["base_phase_id"], snow=plan["snow_cover_template"],
                                        reasoning=plan["reasoning"], location=plan.get("location")),
        plates={k: dict(status=v.get("status"), score=v.get("score"), attempts=len(v.get("attempts", [])),
                        issues=(v.get("attempts") or [{}])[-1].get("issues", [])[:3])
                for k, v in pstate.get("plates", {}).items()},
        renderer=[dict(version=h["version"], mean=h["mean"], per_metric=h["per_metric"], all_passed=h["all_passed"],
                       frames=h["frames"]) for h in hist],
        result=read_json(j.path("05_renderer", "result.json")),
        report=read_json(j.path("06_finalize", "report.json")))


@app.get("/api/jobs/{jid}/log")
def log(jid: str, tail: int = 200):
    j = _job(jid)
    try:
        lines = open(j.path("log.txt")).read().splitlines()[-tail:]
    except FileNotFoundError:
        lines = []
    return {"lines": lines}


@app.get("/files/{jid}/{path:path}")
def files(jid: str, path: str):
    j = _job(jid)
    full = os.path.realpath(os.path.join(j.dir, path))
    if not full.startswith(os.path.realpath(j.dir) + os.sep) or not os.path.isfile(full):
        raise HTTPException(404)
    return FileResponse(full)


@app.get("/api/jobs/{jid}/render")
def render(jid: str, when: str, cover: float = 0.3, weather: str = "", intensity: float = 0.8, snow: float = 0.0):
    j = _job(jid)
    pkg = j.path("04_package")
    rp = os.path.join(pkg, "scene_renderer.py")
    if not os.path.exists(rp):
        raise HTTPException(409, "renderer not built yet")
    if not re.match(r"^\d{4}-\d\d-\d\d \d\d:\d\d$", when):
        raise HTTPException(400, "when must be YYYY-MM-DD HH:MM")
    case = dict(id="preview_%d" % int(time.time() * 1000), when=when, cover=max(0.0, min(1.0, cover)),
                weather=weather if weather in ("rain", "storm", "fog", "snow") else None,
                intensity=max(0.1, min(1.0, intensity)), snow_depth_m=max(0.0, snow))
    out = codegen.run_cases(pkg, rp, [case], os.path.join(j.dir, "previews"), timeout=120)[0]
    if not out["ok"]:
        raise HTTPException(500, out.get("error", "render failed"))
    im = cv2.imread(out["file"])
    os.remove(out["file"])
    ok, buf = cv2.imencode(".jpg", cv2.resize(im, (1920, 1080), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 90])
    return Response(buf.tobytes(), media_type="image/jpeg", headers={"X-Phase": str(out.get("phase")),
                                                                      "X-Sun-Alt": str(out.get("sun_alt"))})


def main():
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")


if __name__ == "__main__":
    main()
