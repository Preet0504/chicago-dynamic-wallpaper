#!/usr/bin/env python3
"""Generates docs/architecture.excalidraw - the wallgen system design as an editable Excalidraw diagram - plus an
SVG preview of the same shapes (docs/architecture.svg) and, if Google Chrome is installed, docs/architecture.png.

  python3 tools/make_architecture.py

Open the .excalidraw at https://excalidraw.com (File > Open) or with the VS Code Excalidraw extension.
Layout is a 3 x 3 grid of lanes; edit coordinates below and re-run rather than hand-editing the JSON.
"""
import json
import os
import random
import shutil
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "architecture")
random.seed(11)
E = []
# fills by role
C = dict(input="#d3f9d8", vision="#d0ebff", ai="#e5dbff", data="#ffe8cc", review="#fff3bf", ok="#b2f2bb",
         stop="#ffc9c9", star="#ffd8a8", mac="#c3fae8", note="#ffffff")
LANE = dict(a="#f8f9fa", b="#f3f0ff", c="#fff9db", d="#ebfbee", e="#e7f5ff")
INK, MUTE = "#1e1e1e", "#495057"


def _base(t, x, y, w, h, **kw):
    e = dict(id="e%d" % len(E), type=t, x=x, y=y, width=w, height=h, angle=0, strokeColor=INK,
             backgroundColor="transparent", fillStyle="solid", strokeWidth=2, strokeStyle="solid",
             roughness=1, opacity=100, groupIds=[], frameId=None, roundness=None,
             seed=random.randint(1, 2 ** 30), version=1, versionNonce=random.randint(1, 2 ** 30),
             isDeleted=False, boundElements=[], updated=1, link=None, locked=False)
    e.update(kw)
    E.append(e)
    return e


def text(x, y, s, size=16, w=None, align="left", color=INK, container=None, h=None):
    lines = s.split("\n")
    w = w or max(len(l) for l in lines) * size * 0.56
    h = h or len(lines) * size * 1.25
    return _base("text", x, y, w, h, text=s, originalText=s, fontSize=size, fontFamily=1, textAlign=align,
                 verticalAlign="middle", containerId=container, lineHeight=1.25, autoResize=True, strokeColor=color)


def box(x, y, w, h, label, fill, size=17, shape="rectangle", dashed=False, stroke=INK):
    b = _base(shape, x, y, w, h, backgroundColor=fill, strokeColor=stroke,
              roundness={"type": 3} if shape == "rectangle" else ({"type": 2} if shape == "diamond" else None),
              strokeStyle="dashed" if dashed else "solid")
    pad = 0.22 if shape in ("ellipse", "diamond") else 0.04
    t = text(x + w * pad, y + h * pad, label, size=size, w=w * (1 - 2 * pad), align="center", container=b["id"],
             h=h * (1 - 2 * pad))
    b["boundElements"].append({"type": "text", "id": t["id"]})
    return b


def frame(x, y, w, h, label=None, color=MUTE):
    f = _base("rectangle", x, y, w, h, strokeStyle="dashed", strokeWidth=1, roundness={"type": 3}, strokeColor=color)
    if label:
        text(x + 10, y + 6, label, size=14, color=color)
    return f


def lane(x, y, w, h, title, fill):
    _base("rectangle", x, y, w, h, backgroundColor=fill, strokeStyle="dashed", strokeWidth=1,
          roundness={"type": 3}, strokeColor="#868e96")
    text(x + 18, y + 12, title, size=24)


def _pt(e, s):
    return {"r": (e["x"] + e["width"], e["y"] + e["height"] / 2), "l": (e["x"], e["y"] + e["height"] / 2),
            "b": (e["x"] + e["width"] / 2, e["y"] + e["height"]), "t": (e["x"] + e["width"] / 2, e["y"])}[s]


def link(a, b, side=("r", "l"), via=(), label=None, lxy=None, dashed=False, color=INK, width=2):
    """Arrow from side of a to side of b, optionally through intermediate points (orthogonal routing)."""
    pts = [_pt(a, side[0])] + list(via) + [_pt(b, side[1])]
    x0, y0 = pts[0]
    rel = [[px - x0, py - y0] for px, py in pts]
    xs, ys = [q[0] for q in rel], [q[1] for q in rel]
    ar = _base("arrow", x0, y0, max(xs) - min(xs), max(ys) - min(ys), points=rel,
               startBinding={"elementId": a["id"], "focus": 0, "gap": 4},
               endBinding={"elementId": b["id"], "focus": 0, "gap": 4},
               startArrowhead=None, endArrowhead="arrow", lastCommittedPoint=None, roundness=None,
               strokeStyle="dashed" if dashed else "solid", strokeColor=color, strokeWidth=width)
    a["boundElements"].append({"type": "arrow", "id": ar["id"]})
    b["boundElements"].append({"type": "arrow", "id": ar["id"]})
    if label:
        if lxy is None:
            (x1, y1), (x2, y2) = pts[0], pts[1]
            lxy = ((x1 + x2) / 2 - len(label) * 3.8, (y1 + y2) / 2 - 24)
        text(lxy[0], lxy[1], label, size=14, color=color if color != INK else MUTE)
    return ar


# ============================================================================================ layout
text(0, -110, "wallgen · any picture + a place → a living wallpaper", size=40)
text(0, -55, "every model runs locally on the Mac · no cloud AI · the live wallpaper itself uses no AI", size=18,
     color=MUTE)

# ---------------------------------------------------------------- row 1: upload · perception · plan
lane(0, 0, 660, 540, "① Upload", LANE["d"])
user = box(40, 90, 160, 90, "👤\nYou", C["input"], shape="ellipse")
web = box(250, 90, 170, 90, "🌐 Web app", C["input"])
queue = box(460, 90, 160, 90, "📥 Job queue", C["data"])
progress = box(250, 300, 170, 100, "📊 Live\nprogress", C["input"])
store = box(460, 300, 160, 100, "🗄 jobs/<id>\nresumable", C["data"])
link(user, web, label="picture + place", lxy=(178, 64))
link(web, queue)
link(queue, store, side=("b", "t"))
link(store, progress, side=("l", "r"), dashed=True)

lane(720, 0, 1340, 540, "② What changes with weather & time?", LANE["e"])
vis = frame(750, 70, 500, 140, "path A · vision models")
seg = box(765, 100, 150, 90, "🧩 Segment", C["vision"])
det = box(930, 100, 150, 90, "🎯 Detect\n+ mask", C["vision"])
dep = box(1095, 100, 140, 90, "📏 Depth", C["vision"])
llm = box(1290, 95, 160, 100, "🧠 LLM\nreasons", C["ai"])
vlm = box(1000, 290, 190, 100, "👁 Vision LLM\nlooks", C["ai"])
text(780, 325, "path B", size=14, color=MUTE)
agree = box(1470, 150, 160, 140, "Agree?", C["review"], shape="diamond")
tie = box(1475, 380, 150, 90, "⚖ Tie-break", C["ai"])
union = box(1660, 175, 150, 90, "∪ Union\n+ masks", C["data"])
anyc = box(1850, 150, 180, 140, "Anything\nchanges?", C["review"], shape="diamond", size=16)
nothing = box(1855, 400, 170, 100, "💬 'Nothing\nto animate'", C["stop"])
link(queue, vis)
link(queue, vlm, side=("r", "l"), via=[(705, 135), (705, 340)])
link(vis, llm)
link(llm, agree, side=("r", "t"), via=[(1550, 145)])
link(vlm, agree, side=("r", "b"), via=[(1550, 340)])
link(agree, union, label="yes", lxy=(1628, 192))
link(agree, tie, side=("r", "r"), via=[(1645, 220), (1645, 425)], label="no", lxy=(1652, 300))
link(tie, union, side=("t", "b"), via=[(1550, 360), (1735, 360)])
link(union, anyc)
link(anyc, nothing, side=("b", "t"), label="no", lxy=(1950, 330))

lane(2120, 0, 760, 540, "③ Season plan", LANE["a"])
geo = box(2160, 90, 170, 90, "📍 Find the\nplace", C["data"])
clim = box(2160, 260, 170, 100, "📊 3 years\nof weather", C["data"])
plan = box(2390, 170, 190, 110, "🗓 Planner\nLLM", C["ai"])
phases = frame(2625, 60, 230, 410, "season phases")
ph = [box(2645, 95 + i * 72, 190, 56, s, f, size=16) for i, (s, f) in enumerate(
    [("🌸 spring", "#ffdeeb"), ("☀️ summer", "#d3f9d8"), ("🍂 autumn", "#ffe8cc"), ("🌨 winter", "#e7f5ff"),
     ("⛄ snow on ground", "#f1f3f5")])]
link(anyc, geo, side=("r", "l"), via=[(2090, 220), (2090, 135)], label="yes", lxy=(2040, 192))
link(geo, clim, side=("b", "t"))
link(clim, plan, side=("r", "l"), via=[(2360, 310), (2360, 225)])
link(plan, phases)

# ---------------------------------------------------------------- row 2: preview · templates · review
lane(0, 620, 660, 560, "④ First wallpaper, fast", LANE["d"])
today = box(400, 700, 230, 80, "📅 Today's\nseason only", C["data"])
quick_edit = box(400, 810, 230, 80, "🎨 2-3 edits", C["ai"])
quick_rev = box(400, 920, 230, 80, "⚡ Quick review", C["review"])
wall = box(40, 880, 260, 140, "🖼 Wallpaper\nin ~4 min", C["star"], shape="ellipse", size=20)
later = box(40, 1065, 590, 80, "↻ rest of the year keeps building in the background", C["note"], size=15, dashed=True)
link(phases, today, side=("b", "t"), via=[(2740, 585), (515, 585)], label="today first", lxy=(1250, 558),
     color="#e8590c", width=3)
link(today, quick_edit, side=("b", "t"))
link(quick_edit, quick_rev, side=("b", "t"))
link(quick_rev, wall, side=("l", "r"), via=[(350, 960), (350, 950)])
link(wall, progress, side=("l", "l"), via=[(-30, 950), (-30, 350)], label="shown + set", lxy=(-150, 640),
     color="#2b8a3e", dashed=True)

lane(720, 620, 1340, 560, "⑤ Big work · season templates", LANE["b"])
edit = box(770, 720, 180, 100, "🎨 Image\nmodel edits", C["ai"])
align = box(990, 720, 160, 100, "📐 Line up\nwith original", C["vision"])
lock = box(1190, 720, 160, 100, "🔒 Keep\nbuildings", C["vision"])
rev_a = box(1390, 720, 150, 100, "🔎 Review", C["review"])
pass_a = box(1580, 700, 150, 140, "Pass?", C["review"], shape="diamond")
for i in (2, 1):       # a little stack: one day + night plate per phase
    _base("rectangle", 1790 + 8 * i, 730 + 8 * i, 200, 90, backgroundColor=C["ok"], roundness={"type": 3})
tmpl = box(1790, 730, 200, 90, "✅ Templates\nday + night", C["ok"])
link(edit, align)
link(align, lock)
link(lock, rev_a)
link(rev_a, pass_a)
link(pass_a, tmpl, label="yes", lxy=(1735, 745))
link(pass_a, edit, side=("b", "b"), via=[(1655, 960), (860, 960)], label="no → retry with the reviewers' fixes",
     lxy=(1000, 970), color="#7048e8")
text(770, 1060, "max 2 rounds · best attempt wins", size=15, color=MUTE)

lane(2120, 620, 760, 560, "🧑‍⚖️ Review · both loops", LANE["c"])
checks = box(2150, 730, 170, 90, "🤖 Auto\nchecks", C["vision"])
screen = box(2360, 730, 170, 90, "⚡ Quick\nscreen", C["ai"])
good = box(2565, 705, 150, 140, "Clearly\ngood?", C["review"], shape="diamond", size=16)
accept = box(2745, 735, 115, 80, "✅", C["ok"], size=24)
panel = frame(2340, 885, 380, 125, "full panel · in parallel")
m1 = box(2355, 915, 170, 80, "👁 Model 1", C["ai"])
m2 = box(2535, 915, 170, 80, "👁 Model 2", C["ai"])
merge = box(2150, 1060, 190, 90, "∪ Merge +\nconfirm", C["review"])
router = box(2390, 1060, 170, 90, "🧭 Who\nfixes it?", C["review"])
to_img = box(2610, 1040, 240, 55, "🎨 → image model", C["ai"], size=15)
to_code = box(2610, 1105, 240, 55, "💻 → code model", C["vision"], size=15)
link(checks, screen)
link(screen, good)
link(good, accept, label="yes", lxy=(2712, 742))
link(good, panel, side=("b", "t"), label="no", lxy=(2650, 850))
link(panel, merge, side=("l", "t"), via=[(2245, 947)])
link(merge, router)
link(router, to_img, side=("r", "l"), via=[(2585, 1105), (2585, 1067)])
link(router, to_code, side=("r", "l"), via=[(2585, 1105), (2585, 1132)])
link(rev_a, checks, side=("t", "t"), via=[(1465, 680), (2235, 680)], dashed=True, color="#e67700")

# ---------------------------------------------------------------- row 3: renderer code · on your Mac
lane(0, 1240, 2060, 560, "⑥ Small work · renderer code", LANE["e"])
pkg = box(40, 1340, 190, 100, "📦 Scene\npackage", C["data"])
coder = box(290, 1340, 180, 100, "💻 Code\nmodel", C["ai"])
safe = box(530, 1340, 170, 100, "🛡 Safety +\nAPI check", C["vision"])
sand = box(760, 1340, 170, 100, "🧪 Sandbox\nrender", C["vision"])
for i, s in enumerate(["🌙", "🌅", "☀️", "🌧", "🌫", "❄️"]):
    box(760 + i * 29, 1455, 26, 30, s, "#ffffff", size=13)
rev_b = box(990, 1340, 150, 100, "🔎 Review", C["review"])
pass_b = box(1180, 1320, 150, 140, "Pass?", C["review"], shape="diamond")
rend = box(1390, 1345, 170, 90, "✅ Renderer", C["ok"])
up = box(1610, 1345, 170, 90, "🔍 4K\nupscale", C["ai"])
ready = box(1830, 1330, 190, 120, "🎁 Ready", C["star"], shape="ellipse", size=20)
link(tmpl, pkg, side=("b", "l"), via=[(1890, 1205), (-30, 1205), (-30, 1390)], color="#2b8a3e", width=3)
link(pkg, coder)
link(coder, safe)
link(safe, coder, side=("t", "t"), via=[(615, 1295), (380, 1295)], label="reject", lxy=(455, 1270), color="#c92a2a")
link(safe, sand)
link(sand, rev_b)
link(rev_b, pass_b)
link(pass_b, rend, label="yes", lxy=(1335, 1350))
link(pass_b, coder, side=("b", "b"), via=[(1255, 1580), (380, 1580)], label="no → revise the code",
     lxy=(620, 1590), color="#1971c2")
link(rend, up)
link(up, ready)
link(rev_b, checks, side=("t", "l"), via=[(1065, 1222), (2133, 1222), (2133, 775)], dashed=True, color="#e67700")
text(40, 1700, "the code runs with no network, a time limit and an import allow-list", size=15, color=MUTE)

lane(2120, 1240, 760, 560, "⑦ On your Mac · no AI", LANE["d"])
tick = box(2160, 1340, 170, 90, "⏰ Every 30 min\n+ on wake", C["mac"], size=16)
wx = box(2380, 1340, 170, 90, "☁️ Live\nweather", C["mac"])
astro = box(2380, 1480, 170, 90, "🌞🌙 Sun +\nmoon", C["mac"])
draw = box(2600, 1340, 170, 90, "🎞 Render\n~1 s", C["mac"])
desk = box(2160, 1630, 280, 120, "🖥 Every\ndesktop", C["star"], shape="ellipse", size=18)
link(ready, tick, label="package", lxy=(2040, 1350))
link(tick, wx)
link(wx, draw)
link(astro, draw, side=("r", "b"), via=[(2685, 1525)])
link(draw, desk, side=("r", "r"), via=[(2850, 1385), (2850, 1690)])

# legend
for i, (s, f) in enumerate([("AI model (local)", C["ai"]), ("vision / checks", C["vision"]), ("review / decision", C["review"]),
                            ("data", C["data"]), ("runs on your Mac", C["mac"]), ("result", C["star"])]):
    box(i * 300, 1850, 270, 50, s, f, size=15)


# ============================================================================================ write
def write_excalidraw():
    doc = dict(type="excalidraw", version=2, source="tools/make_architecture.py", elements=E,
               appState=dict(viewBackgroundColor="#ffffff", gridSize=None), files={})
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT + ".excalidraw", "w") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def write_svg():
    """Plain preview of the same elements (clean shapes, not Excalidraw's hand-drawn look)."""
    xs, ys = [], []
    for e in E:
        pts = [(e["x"] + px, e["y"] + py) for px, py in e["points"]] if e["type"] == "arrow" else \
            [(e["x"], e["y"]), (e["x"] + e["width"], e["y"] + e["height"])]
        xs += [p[0] for p in pts]
        ys += [p[1] for p in pts]
    x0, y0, x1, y1 = min(xs) - 40, min(ys) - 40, max(xs) + 40, max(ys) + 40
    byid = {e["id"]: e for e in E}
    out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="%d %d %d %d" width="%d" height="%d">'
           % (x0, y0, x1 - x0, y1 - y0, x1 - x0, y1 - y0),
           '<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
           'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="context-stroke"/></marker></defs>',
           '<rect x="%d" y="%d" width="%d" height="%d" fill="#ffffff"/>' % (x0, y0, x1 - x0, y1 - y0),
           '<style>text{font-family:"Comic Sans MS","Segoe Print","Chalkboard SE",sans-serif}</style>']
    for e in E:
        st = 'stroke="%s" stroke-width="%s" fill="%s"%s' % (
            e["strokeColor"], e["strokeWidth"], "none" if e["backgroundColor"] == "transparent" else e["backgroundColor"],
            ' stroke-dasharray="8 6"' if e["strokeStyle"] == "dashed" else "")
        x, y, w, h = e["x"], e["y"], e["width"], e["height"]
        if e["type"] == "rectangle":
            out.append('<rect x="%g" y="%g" width="%g" height="%g" rx="%d" %s/>' % (x, y, w, h, 14 if e["roundness"] else 0, st))
        elif e["type"] == "ellipse":
            out.append('<ellipse cx="%g" cy="%g" rx="%g" ry="%g" %s/>' % (x + w / 2, y + h / 2, w / 2, h / 2, st))
        elif e["type"] == "diamond":
            out.append('<polygon points="%g,%g %g,%g %g,%g %g,%g" %s/>' % (x + w / 2, y, x + w, y + h / 2, x + w / 2, y + h,
                                                                          x, y + h / 2, st))
        elif e["type"] == "arrow":
            pts = " ".join("%g,%g" % (x + px, y + py) for px, py in e["points"])
            out.append('<polyline points="%s" stroke="%s" stroke-width="%s" fill="none" marker-end="url(#ah)"%s/>'
                       % (pts, e["strokeColor"], e["strokeWidth"], ' stroke-dasharray="8 6"' if e["strokeStyle"] == "dashed" else ""))
    for e in E:
        if e["type"] != "text":
            continue
        lines = e["text"].split("\n")
        lh = e["fontSize"] * 1.25
        if e["containerId"]:
            c = byid[e["containerId"]]
            cx, cy = c["x"] + c["width"] / 2, c["y"] + c["height"] / 2
            anchor, top = "middle", cy - lh * len(lines) / 2
        else:
            cx, top, anchor = e["x"], e["y"], "start"
        for i, l in enumerate(lines):
            out.append('<text x="%g" y="%g" font-size="%d" fill="%s" text-anchor="%s" dominant-baseline="central">%s</text>'
                       % (cx, top + lh * (i + 0.5), e["fontSize"], e["strokeColor"], anchor, _esc(l)))
    out.append("</svg>")
    with open(OUT + ".svg", "w") as f:
        f.write("\n".join(out))
    return x1 - x0, y1 - y0


def write_png(w, h):
    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if not os.path.exists(chrome):
        return False
    html = OUT + ".preview.html"
    with open(html, "w") as f:
        f.write('<html><body style="margin:0"><img src="architecture.svg" width="%d" height="%d"></body></html>' % (w, h))
    subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                    "--screenshot=" + OUT + ".png", "--window-size=%d,%d" % (w, h), "file://" + html],
                   capture_output=True, timeout=120)
    os.remove(html)
    if os.path.exists(OUT + ".png"):       # headless Chrome can pad the window; crop to the drawing
        subprocess.run(["sips", "--cropToHeightWidth", str(int(h)), str(int(w)), "--cropOffset", "0", "0",
                        OUT + ".png"], capture_output=True)
    return os.path.exists(OUT + ".png")


if __name__ == "__main__":
    write_excalidraw()
    w, h = write_svg()
    png = write_png(w, h)
    print("wrote %s.excalidraw (%d elements), .svg%s" % (os.path.relpath(OUT, ROOT), len(E), ", .png" if png else ""))
