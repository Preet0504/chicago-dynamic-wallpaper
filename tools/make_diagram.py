#!/usr/bin/env python3
"""Generates docs/workflow.excalidraw — the project workflow as an editable Excalidraw diagram.
Open it at https://excalidraw.com (File > Open) or with the VS Code Excalidraw extension.

  python3 tools/make_diagram.py
"""
import json, os, random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
random.seed(7)
E = []
C = {"build": "#d0ebff", "run": "#d3f9d8", "loop": "#fff3bf", "ai": "#e5dbff", "data": "#ffe8cc",
     "out": "#ffc9c9", "lane": "#f8f9fa"}


def _base(t, x, y, w, h, **kw):
    e = dict(id="e%d" % len(E), type=t, x=x, y=y, width=w, height=h, angle=0, strokeColor="#1e1e1e",
             backgroundColor="transparent", fillStyle="solid", strokeWidth=2, strokeStyle="solid",
             roughness=1, opacity=100, groupIds=[], frameId=None, roundness=None,
             seed=random.randint(1, 2**30), version=1, versionNonce=random.randint(1, 2**30),
             isDeleted=False, boundElements=[], updated=1, link=None, locked=False)
    e.update(kw)
    E.append(e)
    return e


def text(x, y, s, size=16, w=None, align="left", color="#1e1e1e", container=None, h=None):
    lines = s.split("\n")
    w = w or max(len(l) for l in lines) * size * 0.55
    h = h or len(lines) * size * 1.25
    return _base("text", x, y, w, h, text=s, originalText=s, fontSize=size, fontFamily=1,
                 textAlign=align, verticalAlign="middle", containerId=container, lineHeight=1.25,
                 autoResize=True, strokeColor=color)


def box(x, y, w, h, label, fill, size=15, dashed=False):
    b = _base("rectangle", x, y, w, h, backgroundColor=fill, roundness={"type": 3},
              strokeStyle="dashed" if dashed else "solid")
    t = text(x + 6, y + 6, label, size=size, w=w - 12, align="center", container=b["id"], h=h - 12)
    b["boundElements"].append({"type": "text", "id": t["id"]})
    return b


def lane(x, y, w, h, title, sub):
    _base("rectangle", x, y, w, h, backgroundColor=C["lane"], strokeStyle="dashed", strokeWidth=1,
          roundness={"type": 3}, strokeColor="#868e96")
    text(x + 16, y + 10, title, size=26)
    text(x + 16, y + 46, sub, size=15, color="#495057")


def arrow(a, b, label=None, side=("r", "l"), dashed=False, color="#1e1e1e"):
    def pt(e, s):
        return {"r": (e["x"] + e["width"], e["y"] + e["height"] / 2), "l": (e["x"], e["y"] + e["height"] / 2),
                "b": (e["x"] + e["width"] / 2, e["y"] + e["height"]), "t": (e["x"] + e["width"] / 2, e["y"])}[s]
    (x1, y1), (x2, y2) = pt(a, side[0]), pt(b, side[1])
    ar = _base("arrow", x1, y1, x2 - x1, y2 - y1, points=[[0, 0], [x2 - x1, y2 - y1]],
               startBinding={"elementId": a["id"], "focus": 0, "gap": 4},
               endBinding={"elementId": b["id"], "focus": 0, "gap": 4},
               startArrowhead=None, endArrowhead="arrow", lastCommittedPoint=None,
               roundness={"type": 2}, strokeStyle="dashed" if dashed else "solid", strokeColor=color)
    a["boundElements"].append({"type": "arrow", "id": ar["id"]})
    b["boundElements"].append({"type": "arrow", "id": ar["id"]})
    if label:
        text((x1 + x2) / 2 - len(label) * 3.6, (y1 + y2) / 2 - 22, label, size=13, color="#495057")
    return ar


def path(a, b, pts, label=None, lxy=None, dashed=False, color="#1e1e1e"):
    x0, y0 = pts[0]
    rel = [[px - x0, py - y0] for px, py in pts]
    xs, ys = [q[0] for q in rel], [q[1] for q in rel]
    ar = _base("arrow", x0, y0, max(xs) - min(xs), max(ys) - min(ys), points=rel,
               startBinding={"elementId": a["id"], "focus": 0, "gap": 4},
               endBinding={"elementId": b["id"], "focus": 0, "gap": 4},
               startArrowhead=None, endArrowhead="arrow", lastCommittedPoint=None, roundness=None,
               strokeStyle="dashed" if dashed else "solid", strokeColor=color)
    a["boundElements"].append({"type": "arrow", "id": ar["id"]})
    b["boundElements"].append({"type": "arrow", "id": ar["id"]})
    if label:
        text(lxy[0], lxy[1], label, size=13, color=color)
    return ar


text(40, 10, "Chicago Dynamic Wallpaper — how the images are made", size=34)
text(40, 58, "Build time = local AI, once (free, offline)  ·  Runtime = no AI, every 30 min  ·  "
     "Quality loop = agents + benchmarks", size=17, color="#495057")

# ---------------- lane 1: build time
lane(20, 110, 1900, 400, "1  Build time — season templates (one-time, local AI)",
     "everything outside an edited region stays pixel-identical to the painting")
p1 = box(50, 190, 230, 90, "Original painting\nspring_clear_night\n(user)", C["data"])
p2 = box(50, 300, 230, 90, "Autumn painting\n(user)", C["data"])
al = box(330, 300, 230, 90, "align_autumn.py\nnon-rigid warp onto\nspring geometry", C["build"])
mk = box(330, 190, 230, 90, "masks.py + depth.py\nsky · lake · lights ·\ndepth map", C["build"])
gd = box(610, 190, 250, 100, "season_<scene>.py\nprocedural guide\n(blossoms off, roofs, ground)", C["build"])
fx = box(910, 190, 250, 100, "FLUX.2-klein-4B\nimg2img on 2× tiles\n(mflux, strength 0.4)", C["ai"])
cp = box(1210, 190, 240, 100, "composite changed\nregions only +\nexact _sky.png", C["build"])
tp = box(1500, 190, 390, 100, "6 season templates (1672×941)\nspring · summer · autumn · autumnlate\nwinterbare · winter (snow)", C["out"])
up = box(1500, 400, 390, 80, "SeedVR2 AI upscale → templates/4k/\n3840×2160 masters", C["ai"])
re = box(610, 320, 420, 150, "tools/ai_region_edit.py\nQwen-Image-Edit 2.1 repaints ONE region at 4K\nseveral seeds → local critic keeps the best\n→ written to template + 4K master\n(logged in templates/ai/edits.jsonl)", C["ai"])
arrow(p1, mk); arrow(p2, al); arrow(mk, gd); arrow(gd, fx); arrow(fx, cp); arrow(cp, tp)
path(al, tp, [(560, 345), (585, 345), (585, 305), (1470, 305), (1470, 270), (1500, 270)])
arrow(tp, up, side=("b", "t"))
path(re, tp, [(1030, 370), (1560, 370), (1560, 290)], "targeted fixes", (1240, 348), dashed=True, color="#7048e8")

# ---------------- lane 2: runtime
lane(20, 540, 1900, 380, "2  Runtime — every 30 minutes (no AI)",
     "launchd LaunchAgent → ~/Library/Application Support/DynamicWallpaper")
ld = box(50, 620, 200, 80, "launchd\n:00 / :30 + login", C["run"])
om = box(50, 730, 200, 110, "Open-Meteo API\nweather code · clouds\nsnow depth · temp", C["data"])
dw = box(300, 620, 240, 110, "dynamic_wallpaper.py\npick scene:\nsnow ≥ 2 cm → winter\nDec–Feb bare · Nov 15+ late", C["run"])
asx = box(300, 760, 240, 80, "astro.py\nreal sun + moon\nalt/az + phase", C["run"])
td = box(590, 620, 330, 220, "timeofday.py + tod_plates.py\n• day plate / night plate, blend by sun\n• sky: gradient, painted clouds,\n  stars, sun, moon (real phase)\n• lanterns on dusk→dawn\n• lake reflects the sky\n• fireflies on summer nights\n• + 4K detail from AI master", C["run"])
ef = box(970, 640, 270, 180, "render/effects/\nrain · storm (lightning)\nfog · snowfall\n(depth-aware, only when\nthe weather says so)", C["run"])
fr = box(1290, 670, 230, 110, "frame\n3840 × 2160", C["out"])
sw = box(1570, 670, 300, 110, "setwallpaper (Swift)\nall displays", C["out"])
arrow(ld, dw); path(om, dw, [(250, 770), (275, 770), (275, 705), (300, 705)]); arrow(dw, td); arrow(asx, td, side=("r", "l"))
arrow(td, ef); arrow(ef, fr); arrow(fr, sw)
path(up, td, [(1695, 480), (1695, 525), (755, 525), (755, 620)], "templates + 4K masters", (1100, 503), dashed=True, color="#1971c2")

# ---------------- lane 3: quality loop
lane(20, 950, 1900, 400, "3  Quality loop — agents, benchmarks, critics",
     "agents on Haiku with Opus as advisor · hooks block broken Python · tools/cost.py tracks spend")
mo = box(50, 1030, 300, 150, "Modifier agents\nseason · weather · time\ntemplate-creator · detail-orienter\n(edit templates + engine)", C["loop"])
bm = box(410, 1030, 260, 150, "render/benchmark.py\n24 fixed conditions\n(every season, weather,\nlight state)", C["loop"])
lc = box(730, 1010, 300, 100, "LOCAL critic (free)\ntools/critic.py · Ollama\nqwen3.5:122b / inkling-2-mini", C["ai"])
cc = box(730, 1130, 300, 100, "Claude checker (Haiku/Sonnet)\n+ realism-critic (Opus)\nfinal sign-off", C["loop"])
pl = box(1090, 1030, 280, 150, "scores.json\npunchlist.md\nrealism.md\nfeedback/<agent>.md", C["data"])
st = box(1430, 1030, 440, 150, "stop when score ≥ 4.2, no rejects,\nor improvement < 0.1 (plateau)\n\nbaseline 3.16 → 3.79 → 3.84\nthen 4K + AI region fixes", C["out"])
arrow(mo, bm); arrow(bm, lc); arrow(bm, cc, side=("r", "l")); arrow(lc, pl); arrow(cc, pl, side=("r", "l"))
arrow(pl, st)
path(pl, mo, [(1230, 1180), (1230, 1290), (200, 1290), (200, 1180)],
     "feedback → the same agents (SendMessage keeps their context)", (520, 1268), dashed=True, color="#e03131")

doc = {"type": "excalidraw", "version": 2, "source": "https://excalidraw.com", "elements": E,
       "appState": {"viewBackgroundColor": "#ffffff", "gridSize": None}, "files": {}}
os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
out = os.path.join(ROOT, "docs", "workflow.excalidraw")
json.dump(doc, open(out, "w"), indent=1)
print("wrote", out, len(E), "elements")
