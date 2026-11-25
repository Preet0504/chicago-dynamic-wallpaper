#!/usr/bin/env python3
"""Generates docs/architecture.excalidraw - how wallgen turns a picture into a living wallpaper, as an editable
Excalidraw diagram - plus a plain SVG preview (docs/architecture.svg) and, if Google Chrome is installed,
docs/architecture.png.

  python3 tools/make_architecture.py                        # uses the thumbnails in docs/img/
  python3 tools/make_architecture.py --thumbs-from jobs/<id>   # refresh docs/img/ from a finished job first

Open the .excalidraw at https://excalidraw.com (File > Open) or with the VS Code Excalidraw extension.
The diagram reads top to bottom: one row per step, each with a plain-English heading, the boxes that do the work,
and on the right the real result from the Chicago test job. Edit coordinates here and re-run rather than
hand-editing the JSON.
"""
import base64
import hashlib
import json
import os
import random
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "architecture")
IMG = os.path.join(ROOT, "docs", "img")
random.seed(11)
E, FILES = [], {}

# one colour per kind of box, explained in the legend at the bottom
K = dict(you=("#d3f9d8", "#2b8a3e"), ai=("#e5dbff", "#6741d9"), code=("#d0ebff", "#1971c2"),
         check=("#fff3bf", "#e67700"), result=("#ffe8cc", "#d9480f"), stop=("#ffc9c9", "#c92a2a"),
         note=("#ffffff", "#868e96"))
INK, MUTE = "#1e1e1e", "#495057"
FONT = 2            # Excalidraw "Normal" (Helvetica): easier to read than the hand-drawn font
X0, XR, W = 110, 2220, 2700   # blocks start at X0, results column starts at XR, rows are W wide


def _base(t, x, y, w, h, **kw):
    e = dict(id="e%d" % len(E), type=t, x=x, y=y, width=w, height=h, angle=0, strokeColor=INK,
             backgroundColor="transparent", fillStyle="solid", strokeWidth=2, strokeStyle="solid",
             roughness=0, opacity=100, groupIds=[], frameId=None, roundness=None,
             seed=random.randint(1, 2 ** 30), version=1, versionNonce=random.randint(1, 2 ** 30),
             isDeleted=False, boundElements=[], updated=1, link=None, locked=False)
    e.update(kw)
    E.append(e)
    return e


def text(x, y, s, size=16, w=None, align="left", color=INK, group=None, container=None, h=None):
    lines = s.split("\n")
    fixed = w is not None
    w = w or max(len(l) for l in lines) * size * 0.56
    h = h or len(lines) * size * 1.25
    return _base("text", x, y, w, h, text=s, originalText=s, fontSize=size, fontFamily=FONT, textAlign=align,
                 verticalAlign="middle" if container else "top", containerId=container, lineHeight=1.25,
                 autoResize=not fixed, strokeColor=color, groupIds=[group] if group else [])


def card(x, y, w, h, title, detail="", kind="code", model=None, dashed=False):
    """A block: bold-ish title, one or two plain lines saying what it does, and the model it uses (if any)."""
    fill, accent = K[kind]
    g = "g%d" % len(E)
    r = _base("rectangle", x, y, w, h, backgroundColor=fill, strokeColor=accent, roundness={"type": 3},
              strokeStyle="dashed" if dashed else "solid", groupIds=[g])
    text(x + 10, y + 14, title, size=20, w=w - 20, align="center", group=g)
    if detail:
        text(x + 10, y + 46, detail, size=15, w=w - 20, align="center", color=MUTE, group=g)
    if model:
        text(x + 10, y + h - 24, model, size=13, w=w - 20, align="center", color=accent, group=g)
    return r


def diamond(x, y, w, h, label):
    fill, accent = K["check"]
    d = _base("diamond", x, y, w, h, backgroundColor=fill, strokeColor=accent, roundness={"type": 2})
    t = text(x + w * 0.2, y + h * 0.2, label, size=17, w=w * 0.6, h=h * 0.6, align="center", container=d["id"])
    d["boundElements"].append({"type": "text", "id": t["id"]})
    return d


def image(x, y, w, h, name, caption=None):
    path = os.path.join(IMG, name + ".jpg")
    data = open(path, "rb").read()
    fid = hashlib.sha1(data).hexdigest()
    FILES[fid] = dict(mimeType="image/jpeg", id=fid, created=1, lastRetrieved=1,
                      dataURL="data:image/jpeg;base64," + base64.b64encode(data).decode())
    im = _base("image", x, y, w, h, fileId=fid, status="saved", scale=[1, 1], strokeColor="transparent")
    _base("rectangle", x, y, w, h, strokeColor="#adb5bd", strokeWidth=1)
    if caption:
        text(x, y + h + 8, caption, size=14, w=w, align="center", color=MUTE)
    return im


def row(y, h, n, heading, explain, fill="#f8f9fa"):
    _base("rectangle", 0, y, W, h, backgroundColor=fill, strokeColor="#dee2e6", strokeWidth=1, roundness={"type": 3})
    c = None
    if n:
        c = _base("ellipse", 30, y + 22, 56, 56, backgroundColor=INK, strokeColor=INK)
        t = text(38, y + 30, str(n), size=28, w=40, h=40, align="center", color="#ffffff", container=c["id"])
        c["boundElements"].append({"type": "text", "id": t["id"]})
    text(X0, y + 24, heading, size=30)
    text(X0, y + 66, explain, size=18, color=MUTE)
    return c


def _pt(e, s):
    return {"r": (e["x"] + e["width"], e["y"] + e["height"] / 2), "l": (e["x"], e["y"] + e["height"] / 2),
            "b": (e["x"] + e["width"] / 2, e["y"] + e["height"]), "t": (e["x"] + e["width"] / 2, e["y"])}[s]


def link(a, b, side=("r", "l"), via=(), label=None, lxy=None, dashed=False, color=INK, width=2):
    """Arrow from one side of a to one side of b, optionally through corner points (orthogonal routing)."""
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
        text(lxy[0], lxy[1], label, size=15, color=color if color != INK else MUTE)
    return ar


# ============================================================================================ layout
text(0, -230, "wallgen: how a picture becomes a living wallpaper", size=44)
text(0, -170, "Read it top to bottom. Every AI model runs on the Mac itself, nothing is sent to the cloud. "
              "Pictures are real results from the Chicago test.", size=20, color=MUTE)

# ---------------------------------------------------------------- timeline
text(X0, -110, "How long you wait", size=22)
bar0 = _base("ellipse", X0, -40, 16, 16, backgroundColor=INK)
bar1 = _base("ellipse", 2644, -40, 16, 16, backgroundColor=INK)
link(bar0, bar1, color="#868e96", width=3)
for x, top, bottom in [(X0, "0 min", "you upload"), (760, "about 2.5 min", "it knows what changes and the seasons"),
                       (1440, "about 4 min", "first wallpaper is on your screen"),
                       (2100, "about 25 min", "every season finished, swapped in quietly")]:
    _base("ellipse", x, -40, 16, 16, backgroundColor="#d9480f" if top == "about 4 min" else INK)
    text(x, -75, top, size=18)
    text(x, -10, bottom, size=15, color=MUTE)

# ---------------------------------------------------------------- 1. upload
Y = 60
n1 = row(Y, 330, 1, "You give it a picture and a place",
         "Through the web app or the command line. Paintings and photos both work.")
pic = image(X0, Y + 120, 300, 169, "input", "your picture")
place = card(470, Y + 228, 240, 92, "A place", "typed in, e.g.\n\"Chicago, US\"", "you")
web = card(800, Y + 140, 260, 130, "Web app", "upload page that shows\nlive progress", "code")
job = card(1150, Y + 140, 330, 130, "A job folder", "every step saves its output,\nso a crash resumes where it stopped",
           "code")
link(pic, web)
link(place, web, via=[(755, Y + 274), (755, Y + 205)])
link(web, job)

# ---------------------------------------------------------------- 2. what changes
Y = 430
n2 = row(Y, 520, 2, "It finds what in the picture can change with weather and time",
         "Two separate checkers look at the picture. Using two catches what one alone would miss.")
text(X0, Y + 112, "Checker A", size=16, color=K["ai"][1])
a1 = card(X0, Y + 140, 310, 160, "Vision models", "outline every object (sky,\ntrees, water, lamps) and\nmeasure distance",
          "ai", "Mask2Former, Grounding DINO, SAM, Depth")
a2 = card(480, Y + 140, 270, 160, "Text model", "decides which objects\nreact to weather and time", "ai", "qwen3:8b")
text(X0, Y + 322, "Checker B", size=16, color=K["ai"][1])
b1 = card(X0, Y + 350, 640, 120, "Vision-language model", "looks at the picture itself and lists what changes",
          "ai", "qwen3.5:122b")
cmp_ = card(830, Y + 250, 230, 120, "Compare", "do both lists name\nthe same things?", "code")
agree = diamond(1110, Y + 230, 180, 160, "Agree?")
keep = card(1350, Y + 140, 250, 120, "Keep both lists", "everything either\nchecker found", "code")
tie = card(1350, Y + 360, 250, 130, "Third model", "settles what they\ndisagree on", "ai", "inkling-2-mini")
anyc = diamond(1660, Y + 120, 200, 160, "Anything that\ncan change?")
stop = card(1660, Y + 350, 200, 110, "Stop", "tells you: nothing\nto animate", "stop")
ov = image(XR, Y + 76, 440, 248, "overlay",
           "Result: a map of the parts that change\n(sky, trees, lake, lanterns, mountain snow...)")
link(a1, a2)
link(a2, cmp_, via=[(790, Y + 220), (790, Y + 310)])
link(b1, cmp_, via=[(790, Y + 410), (790, Y + 310)])
link(cmp_, agree)
link(agree, keep, side=("t", "l"), via=[(1200, Y + 200)], label="yes", lxy=(1210, Y + 178))
link(agree, tie, side=("b", "l"), via=[(1200, Y + 425)], label="no", lxy=(1210, Y + 400))
link(tie, keep, side=("t", "b"))
link(keep, anyc)
link(anyc, stop, side=("b", "t"), label="no", lxy=(1770, Y + 300))
link(anyc, ov, label="yes", lxy=(1890, Y + 172))

# ---------------------------------------------------------------- 3. seasons
Y = 1010
n3 = row(Y, 340, 3, "It works out the seasons for that place",
         "Seasons look different in Chicago than in Tokyo, so they come from real local weather, not a fixed calendar.")
geo = card(X0, Y + 140, 260, 140, "Find the place", "turn the name into\nmap coordinates", "code", "Open-Meteo")
clim = card(450, Y + 140, 290, 140, "3 years of weather", "daily temperature, rain\nand snow on the ground", "code",
            "Open-Meteo")
planr = card(820, Y + 140, 290, 140, "Planning model", "splits the year into the\nlooks this place really has", "ai",
             "gpt-oss:120b")
link(geo, clim)
link(clim, planr)
text(1190, Y + 112, "Result for Chicago:", size=16, color=K["result"][1])
phases = [("early spring", "from 1 Mar", "#ffdeeb"), ("full spring", "from 15 Apr", "#d3f9d8"),
          ("summer", "from 15 Jun", "#b2f2bb"), ("autumn", "from 15 Sep", "#ffd8a8"),
          ("winter", "from 1 Dec", "#e7f5ff"), ("snow", "only on days with\n2 cm+ snow lying", "#f1f3f5")]
first = None
for i, (nm, when, fill) in enumerate(phases):
    p = _base("rectangle", 1190 + i * 248, Y + 140, 230, 140, backgroundColor=fill, strokeColor=K["result"][1],
              roundness={"type": 3}, strokeStyle="dashed" if nm == "snow" else "solid")
    text(1190 + i * 248, Y + 165, nm, size=22, w=230, align="center")
    text(1190 + i * 248, Y + 205, when, size=15, w=230, align="center", color=MUTE)
    first = first or p
link(planr, first)

# ---------------------------------------------------------------- 4. paint the seasons
Y = 1410
n4 = row(Y, 460, 4, "It paints the picture again for every season, by day and by night",
         "Today's season is painted first, so a wallpaper is ready in about 4 minutes. "
         "The other seasons follow in the background.")
paint = card(X0, Y + 140, 290, 150, "Image model repaints", "same scene, asked for\ne.g. \"autumn, daytime\"",
             "ai", "FLUX.2-klein")
align = card(470, Y + 140, 270, 150, "Line it up", "shift and scale it to sit\nexactly on the original",
             "code")
lock = card(810, Y + 140, 300, 150, "Put the buildings back", "copy the original's buildings\nso nothing moves",
            "code")
chk4 = card(1180, Y + 140, 240, 150, "Check it", "see \"How checking\nworks\" at the bottom", "check")
ok4 = diamond(1490, Y + 135, 180, 160, "Good\nenough?")
link(paint, align)
link(align, lock)
link(lock, chk4)
link(chk4, ok4)
link(ok4, paint, side=("b", "b"), via=[(1580, Y + 360), (X0 + 145, Y + 360)], color=K["ai"][1],
     label="no: paint it again using the reviewers' notes (2 tries at most, the best one is kept)",
     lxy=(X0 + 200, Y + 370))
grid = [("summer_day", "summer day"), ("autumn_day", "autumn day"), ("winter_night", "winter night"),
        ("snow_day", "snow day")]
ims = [image(XR + (i % 2) * 225, Y + 110 + (i // 2) * 140, 215, 121, nm) for i, (nm, _) in enumerate(grid)]
text(XR, Y + 392, "Result: 12 season pictures\n(above: summer day, autumn day, winter night, snow day)", size=14,
     w=440, align="center", color=MUTE)
link(ok4, ims[0], via=[(1950, Y + 215), (1950, Y + 170)], label="yes", lxy=(1700, Y + 188))

# ---------------------------------------------------------------- 5. write the drawing code
Y = 1930
n5 = row(Y, 460, 5, "It writes the program that draws sky, light and weather",
         "A coding model writes a small Python program. Later, that program (not an AI) draws every wallpaper.")
coder = card(X0, Y + 140, 300, 160, "Coding model writes it", "sky, sun and moon, clouds,\nlamps, reflections,\n"
             "rain, fog, snow", "ai", "gpt-oss:120b")
safe = card(490, Y + 140, 260, 160, "Safety check", "only allowed imports,\nonly functions that exist,\nno network",
            "code")
test = card(830, Y + 140, 270, 160, "Test-draw 6 moments", "night, noon, dusk,\nrain, fog, snow", "code")
chk5 = card(1180, Y + 140, 240, 160, "Check it", "see \"How checking\nworks\" at the bottom", "check")
ok5 = diamond(1490, Y + 140, 180, 160, "Good\nenough?")
up = card(1740, Y + 140, 260, 160, "Make 4K versions", "sharpen the season\npictures to 3840 x 2160", "ai",
          "SeedVR2")
link(coder, safe)
link(safe, coder, side=("t", "t"), via=[(620, Y + 112), (X0 + 150, Y + 112)], color=K["stop"][1],
     label="rejected", lxy=(330, Y + 88))
link(safe, test)
link(test, chk5)
link(chk5, ok5)
link(ok5, up, label="yes", lxy=(1680, Y + 190))
link(ok5, coder, side=("b", "b"), via=[(1580, Y + 360), (X0 + 150, Y + 360)], color=K["code"][1],
     label="no: fix the program using the reviewers' notes (2 tries at most, the best one is kept)",
     lxy=(X0 + 200, Y + 370))
tests = [image(XR + (i % 2) * 225, Y + 110 + (i // 2) * 140, 215, 121, nm)
         for i, nm in enumerate(["c01_night", "c06_dusk", "c08_rain", "c10_fog"])]
text(XR, Y + 392, "Result: the scene package (season pictures\n+ the program). Above: its test drawings.", size=14,
     w=440, align="center", color=MUTE)
link(up, tests[0], via=[(2110, Y + 220), (2110, Y + 170)])

# ---------------------------------------------------------------- 6. on your Mac
Y = 2450
n6 = row(Y, 760, 6, "On your Mac, every 30 minutes: no AI from here on",
         "A tiny program redraws the wallpaper for the real time and weather. It takes about 1 second, "
         "so it's fine on battery.", fill="#ebfbee")
tick = card(X0, Y + 180, 240, 130, "Timer", "every 30 minutes and\nwhen the Mac wakes up", "you")
ins = [card(450, Y + 110 + i * 100, 320, 88, t, d, "code") for i, (t, d) in enumerate(
    [("Pick the season", "from today's date"), ("Sun and moon", "position and phase, right now"),
     ("Live weather", "clouds, rain, fog, snow")])]
draw = card(870, Y + 170, 300, 150, "Draw the wallpaper", "season picture, then sky, light,\nlamps and weather "
            "on top\n(about 1 second)", "code")
desk = card(1260, Y + 180, 260, 130, "Set as wallpaper", "on every screen\nand every desktop", "you")
for b in ins:
    link(tick, b, via=[(410, Y + 245), (410, b["y"] + 44)])
    link(b, draw, via=[(820, b["y"] + 44), (820, Y + 245)])
link(draw, desk)
now = image(XR, Y + 121, 440, 248, "now", "Result: Chicago this evening\n(autumn, overcast)")
link(desk, now)
text(X0, Y + 430, "One day of the finished wallpaper, every 2 hours from midnight to 10 pm:", size=16, color=MUTE)
image(X0, Y + 460, 1360, 255, "strip")

# ---------------------------------------------------------------- how checking works
Y = 3270
row(Y, 560, None, "How checking works (used in steps 4 and 5)",
    "A quick check lets clear passes through fast. Only the full panel of two bigger models can fail a picture.",
    fill="#fff9db")
auto = card(X0, Y + 140, 320, 150, "Automatic checks", "did buildings move? too dark?\nlamps lit at night?\n"
            "colour banding?", "code")
quick = card(500, Y + 150, 260, 130, "Quick check", "one model looks,\nabout 7 seconds", "ai", "qwen3.5:122b")
clear = diamond(820, Y + 135, 190, 160, "Clearly\nfine?")
acc = card(1080, Y + 160, 180, 110, "Accept", "keep this\npicture", "result")
panel = _base("rectangle", 700, Y + 360, 430, 160, strokeColor=K["ai"][1], strokeStyle="dashed", strokeWidth=1,
              roundness={"type": 3})
text(712, Y + 368, "full panel: both judges at the same time", size=14, color=K["ai"][1])
j1 = card(715, Y + 395, 195, 110, "Judge 1", "scores it, lists\nproblems", "ai", "qwen3.5:122b")
j2 = card(920, Y + 395, 195, 110, "Judge 2", "scores it, lists\nproblems", "ai", "inkling-2-mini")
merge = card(1200, Y + 380, 320, 120, "Count only agreed problems", "2 judges agree, or a judge\n"
             "and an automatic check agree", "code")
who = diamond(1590, Y + 360, 200, 160, "Who can\nfix it?")
fix_img = card(1870, Y + 290, 300, 110, "Image model", "wrong season, invented\nor moved objects", "ai")
fix_code = card(1870, Y + 440, 300, 110, "Coding model", "sky, sun and moon,\nreflections, brightness", "ai")
rule = card(XR, Y + 130, 440, 150, "Passing score", "average 3.6 out of 5 or better,\nnothing below 2.5, and no "
            "serious\nproblem that two judges agree on", "note", dashed=True)
link(auto, quick)
link(quick, clear)
link(clear, acc, label="yes", lxy=(1025, Y + 188))
link(clear, panel, side=("b", "t"), label="no, or not sure", lxy=(925, Y + 315))
link(panel, merge)
link(merge, who)
link(who, fix_img, side=("t", "l"), via=[(1690, Y + 345)])
link(who, fix_code, side=("b", "l"), via=[(1690, Y + 495)])

# ---------------------------------------------------------------- spine + legend
for a, b in [(n1, n2), (n2, n3), (n3, n4), (n4, n5), (n5, n6)]:
    link(a, b, side=("b", "t"), color="#868e96", width=3)
text(0, 3880, "Colours:", size=18)
for i, (s, k) in enumerate([("you / your Mac", "you"), ("AI model (runs on the Mac)", "ai"),
                            ("ordinary code, no AI", "code"), ("a check or decision", "check"),
                            ("result", "result")]):
    fill, accent = K[k]
    _base("rectangle", 110 + i * 420, 3870, 46, 36, backgroundColor=fill, strokeColor=accent, roundness={"type": 3})
    text(170 + i * 420, 3877, s, size=18)


# ============================================================================================ write
def write_excalidraw():
    doc = dict(type="excalidraw", version=2, source="tools/make_architecture.py", elements=E,
               appState=dict(viewBackgroundColor="#ffffff", gridSize=None), files=FILES)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT + ".excalidraw", "w") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def write_svg():
    """Plain preview of the same elements."""
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
           '<style>text{font-family:"Helvetica Neue",Helvetica,Arial,sans-serif}</style>']
    for e in E:
        st = 'stroke="%s" stroke-width="%s" fill="%s"%s' % (
            "none" if e["strokeColor"] == "transparent" else e["strokeColor"], e["strokeWidth"],
            "none" if e["backgroundColor"] == "transparent" else e["backgroundColor"],
            ' stroke-dasharray="8 6"' if e["strokeStyle"] == "dashed" else "")
        x, y, w, h = e["x"], e["y"], e["width"], e["height"]
        if e["type"] == "rectangle":
            out.append('<rect x="%g" y="%g" width="%g" height="%g" rx="%d" %s/>'
                       % (x, y, w, h, 12 if e["roundness"] else 0, st))
        elif e["type"] == "ellipse":
            out.append('<ellipse cx="%g" cy="%g" rx="%g" ry="%g" %s/>' % (x + w / 2, y + h / 2, w / 2, h / 2, st))
        elif e["type"] == "diamond":
            out.append('<polygon points="%g,%g %g,%g %g,%g %g,%g" %s/>'
                       % (x + w / 2, y, x + w, y + h / 2, x + w / 2, y + h, x, y + h / 2, st))
        elif e["type"] == "image":
            out.append('<image x="%g" y="%g" width="%g" height="%g" preserveAspectRatio="none" href="%s"/>'
                       % (x, y, w, h, FILES[e["fileId"]]["dataURL"]))
        elif e["type"] == "arrow":
            pts = " ".join("%g,%g" % (x + px, y + py) for px, py in e["points"])
            out.append('<polyline points="%s" stroke="%s" stroke-width="%s" fill="none" marker-end="url(#ah)"%s/>'
                       % (pts, e["strokeColor"], e["strokeWidth"],
                          ' stroke-dasharray="8 6"' if e["strokeStyle"] == "dashed" else ""))
    for e in E:
        if e["type"] != "text":
            continue
        lines = e["text"].split("\n")
        lh = e["fontSize"] * 1.25
        if e["containerId"]:
            c = byid[e["containerId"]]
            cx, top, anchor = c["x"] + c["width"] / 2, c["y"] + c["height"] / 2 - lh * len(lines) / 2, "middle"
        elif e["textAlign"] == "center":
            cx, top, anchor = e["x"] + e["width"] / 2, e["y"], "middle"
        else:
            cx, top, anchor = e["x"], e["y"], "start"
        for i, l in enumerate(lines):
            out.append('<text x="%g" y="%g" font-size="%d" fill="%s" text-anchor="%s" dominant-baseline="central">'
                       '%s</text>' % (cx, top + lh * (i + 0.5), e["fontSize"], e["strokeColor"], anchor, _esc(l)))
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


def refresh_thumbs(job):
    """Re-make docs/img/*.jpg from a finished job (small JPEGs so the diagram stays light)."""
    src = {"input": ("input/base.png", 600), "overlay": ("01_perception/overlay.jpg", 600),
           "now": ("03p_preview/now.jpg", 600), "strip": ("06_finalize/day_strip.jpg", 1440)}
    src.update({p: ("04_package/plates/%s.png" % p, 320) for p in ("summer_day", "autumn_day", "winter_night",
                                                                    "snow_day")})
    src.update({c: ("05_renderer/v1/%s.png" % c, 320) for c in ("c01_night", "c06_dusk", "c08_rain", "c10_fog")})
    os.makedirs(IMG, exist_ok=True)
    for name, (rel, width) in src.items():
        height = 270 if name == "strip" else width * 9 // 16
        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "72", "--resampleHeightWidth",
                        str(height), str(width), os.path.join(job, rel), "--out", os.path.join(IMG, name + ".jpg")],
                       check=True, capture_output=True)


if __name__ == "__main__":
    if "--thumbs-from" in sys.argv:
        refresh_thumbs(sys.argv[sys.argv.index("--thumbs-from") + 1])
    write_excalidraw()
    w, h = write_svg()
    png = write_png(w, h)
    print("wrote %s.excalidraw (%d elements), .svg%s" % (os.path.relpath(OUT, ROOT), len(E), ", .png" if png else ""))
