"""Job folders, logging, small image helpers shared by every stage."""
import datetime as dt
import json
import os
import time

import cv2
import numpy as np

from . import config


class Job:
    """jobs/<id>/ holds every artifact; each stage writes into its own folder plus a done-marker so a crashed
    or interrupted run resumes where it stopped."""

    def __init__(self, job_id):
        self.id = job_id
        self.dir = os.path.join(config.JOBS, job_id)
        os.makedirs(self.dir, exist_ok=True)
        self.meta_path = os.path.join(self.dir, "job.json")

    @classmethod
    def create(cls, image_path, location, job_id=None):
        job_id = job_id or dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        j = cls(job_id)
        os.makedirs(j.path("input"), exist_ok=True)
        im = cv2.imread(image_path, cv2.IMREAD_COLOR)
        if im is None:
            raise ValueError("could not read image %s" % image_path)
        h, w = im.shape[:2]
        s = config.WORK_LONG / max(h, w)
        if abs(s - 1) > 1e-3:
            im = cv2.resize(im, (int(round(w * s)), int(round(h * s))),
                            interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LANCZOS4)
        cv2.imwrite(j.path("input", "base.png"), im)
        j.update(location=location, created=now(), status="queued", stages={}, source=os.path.abspath(image_path))
        return j

    def path(self, *parts):
        return os.path.join(self.dir, *parts)

    def stage_dir(self, name):
        p = self.path(name)
        os.makedirs(p, exist_ok=True)
        return p

    def meta(self):
        try:
            with open(self.meta_path) as f:
                return json.load(f)
        except Exception:
            return {}

    def update(self, **kw):
        m = self.meta()
        m.update(kw)
        write_json(self.meta_path, m)
        return m

    def stage_state(self, name, **kw):
        m = self.meta()
        st = m.setdefault("stages", {}).setdefault(name, {})
        st.update(kw)
        write_json(self.meta_path, m)

    def done(self, name):
        return os.path.exists(self.path(name, "DONE"))

    def mark_done(self, name, **info):
        write_json(self.path(name, "DONE"), dict(at=now(), **info))

    def log(self, msg):
        line = "%s  %s" % (dt.datetime.now().strftime("%H:%M:%S"), msg)
        print(line, flush=True)
        with open(self.path("log.txt"), "a") as f:
            f.write(line + "\n")

    def base(self):
        return cv2.imread(self.path("input", "base.png"))


def now():
    return dt.datetime.now().isoformat(timespec="seconds")


def write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=2, default=_jsonable)
    os.replace(tmp, path)


def read_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def _jsonable(o):
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


class Timer:
    def __init__(self, job, stage):
        self.job, self.stage = job, stage

    def __enter__(self):
        self.t0 = time.time()
        self.job.stage_state(self.stage, status="running", started=now())
        self.job.log("== %s ==" % self.stage)
        return self

    def __exit__(self, et, ev, tb):
        secs = round(time.time() - self.t0, 1)
        self.job.stage_state(self.stage, status="failed" if et else "done", seconds=secs,
                             error=repr(ev) if ev else None)
        self.job.log("== %s %s in %.0fs ==" % (self.stage, "FAILED" if et else "done", secs))
        return False


# ---------------------------------------------------------------------------------------------- images
def jpeg_b64(img, long_side=1600, quality=90):
    import base64
    h, w = img.shape[:2]
    s = long_side / max(h, w)
    if s < 1:
        img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    return base64.b64encode(cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])[1]).decode()


def to_u8(img):
    if img.dtype == np.uint8:
        return img
    return (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)


def tiles(img, n=2, overlap=0.1):
    """n x n overlapping crops at full resolution, for reviewers that downsample whole frames."""
    h, w = img.shape[:2]
    th, tw = int(h / n * (1 + overlap)), int(w / n * (1 + overlap))
    out = []
    for i in range(n):
        for j in range(n):
            y = min(h - th, int(i * h / n - (th - h / n) / 2)) if i else 0
            x = min(w - tw, int(j * w / n - (tw - w / n) / 2)) if j else 0
            y, x = max(0, y), max(0, x)
            out.append(((x, y, tw, th), img[y:y + th, x:x + tw]))
    return out


def overlay_masks(img, masks, labels):
    rng = np.random.default_rng(3)
    out = img.astype(np.float32).copy()
    spots = []
    for m, lab in zip(masks, labels):
        c = rng.integers(40, 255, 3).astype(np.float32)
        a = (m > 0.5)[..., None] * 0.45
        out = out * (1 - a) + c * a
        ys, xs = np.nonzero(m > 0.5)
        if len(xs):
            spots.append((lab, int(xs.mean()) - 30, int(ys.mean())))
    out = np.clip(out, 0, 255).astype(np.uint8)
    for lab, x, y in spots:
        cv2.putText(out, lab, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
    return out
