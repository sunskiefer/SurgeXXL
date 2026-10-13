#!/usr/bin/env python3
"""Draw SurgeXXL's skin over the skeleton mpc-vst-plugins built from layout.conf.

    python3 tools/panel_art.py "<skin dir>/Plugin Skins"

For every page of tools/panel.py:
  - the background: #282828 with the white section frames and their title tabs, headers, lettering (Titillium Web
    SemiBold), the LCD windows, Valley's slider slots with their tick marks and BAZZLINE's fader boxes;
  - every control gets images of its own, drawn over exactly the part of the background it covers, and a definition of
    its own in TUI.json (per page, so a control shown on two pages can sit differently on each):
      Valley sliders (a filmstrip of the handle along its travel), Valley's orange Rogan knobs (VCV's sweep; one frame
      per option for an option knob), VCV's CKSS switch, BAZZLINE's fader (its white cap along the box) and lit keys,
      option buttons and trigger buttons with their lettering, live text (readouts, values) in place;
  - per-option pictures (MPC's IndexedEnabling, as BAZZLINE's display): the names of the selected oscillator type's
    seven parameters under its sliders, the selected FX type's parameter names under its twelve knobs, and the picture
    of the selected oscillator's wavetable (tools/wt_art.py).
Images nothing uses any more are deleted. Needs Pillow and cairosvg.

Filmstrips follow mpc-vst-plugins' device-checked layouts (docs/NOTES.md), as InterzoneXXL: a knob is square frames
with numFrames = frames - 1; a slider is frames of its own w x h, numFrames = their count, at most 12288 px tall.
"""
import copy
import io
import json
import math
import os
import sys

import cairosvg
from PIL import Image, ImageDraw, ImageFont, ImageOps

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import panel  # noqa: E402

ROOT = panel.ROOT
SS = 2                      # draw this many times larger, then scale down
MAX_STRIP = 12288
FONT = os.path.join(ROOT, "art", "fonts", "TitilliumWeb-SemiBold.ttf")
BG = panel.BG
ORANGE = (0xf2, 0x9a, 0x2e)
SEG_OFF = (0x1c, 0x1c, 0x1c)
INK = (255, 255, 255)
INK_DIM = (0xcf, 0xcf, 0xcf)
VALUE_COLOUR = "ffcfcfcf"
LCD_FILL = (0x12, 0x12, 0x12)
ROGAN_SWEEP = 0.83 * math.pi
WT_PICTURES = os.environ.get("SXXL_WT_PICTURES", "1") != "0"

# Valley's widgets (InterzoneXXL tools/panel.py), sizes in Valley's panel px
SLIDER = {"bg": "valleySliderBackground.svg", "bg_size": (22.8, 87.5), "handle_size": (12.0, 29.9)}
HANDLE = {"orange": "sliderOrange.svg", "green": "sliderGreen.svg", "red": "sliderRed.svg",
          "yellow": "sliderYellow.svg", "blue": "sliderBlue.svg"}
TRAVEL = (1.5, 61.5)        # the handle's top: Valley's slider, top .. bottom
KNOB = ("v2/Med/Rogan1PSMed-bg.svg", "v2/Med/Rogan1PSOrangeMed.svg", "v2/Med/Rogan1PSOrangeMed-fg.svg")
CKSS = ("CKSS_0.svg", "CKSS_1.svg")
FADER_BOX = (40, 182)       # BAZZLINE's LEVEL slider box (art/bazzline/fader_box.png) and its channel inside it
FADER_CHANNEL = (13, 16, 12, 151)
THUMB = (14, 25)


def art(*p):
    return os.path.join(ROOT, "art", *p)


_svg = {}


def svg(path, w, h):
    w, h = max(1, int(round(w))), max(1, int(round(h)))
    k = (path, w, h)
    if k not in _svg:
        _svg[k] = Image.open(io.BytesIO(cairosvg.svg2png(url=path, output_width=w, output_height=h))).convert("RGBA")
    return _svg[k]


_fonts = {}


def font(px):
    px = int(round(px))
    if px not in _fonts:
        _fonts[px] = ImageFont.truetype(FONT, px)
    return _fonts[px]


def paste(img, layer, x, y):
    xi, yi = int(round(x)), int(round(y))
    sx0, sy0 = max(0, -xi), max(0, -yi)
    sx1, sy1 = min(layer.size[0], img.size[0] - xi), min(layer.size[1], img.size[1] - yi)
    if sx1 > sx0 and sy1 > sy0:
        img.alpha_composite(layer.crop((sx0, sy0, sx1, sy1)), (xi + sx0, yi + sy0))


def text_at(d, x, y, w, s, size, colour, align="center"):
    """lettering in page px (x, y top-left of its line box, w wide), drawn at SS"""
    f = font(size * SS)
    if align == "center":
        d.text(((x + w / 2) * SS, (y + size * 0.65) * SS), s, font=f, fill=colour, anchor="mm")
    elif align == "right":
        d.text(((x + w) * SS, (y + size * 0.65) * SS), s, font=f, fill=colour, anchor="rm")
    else:
        d.text((x * SS, (y + size * 0.65) * SS), s, font=f, fill=colour, anchor="lm")


# ------------------------------------------------------------------------------------------------ page backgrounds
def draw_art(d, item):
    kind = item[0]
    if kind == "frame":
        _, x, y, w, h, title = item
        d.rectangle((x * SS, y * SS, (x + w) * SS - 1, (y + h) * SS - 1), outline=INK, width=3 * SS)
        f = font(24 * SS)
        tw = d.textlength(title, font=f) / SS
        tx = x + (w - tw) / 2 - 22
        d.rectangle((tx * SS, (y - 18) * SS, (tx + tw + 44) * SS, (y + 18) * SS), fill=INK)
        d.text(((x + w / 2) * SS, y * SS), title, font=f, fill=(0x11, 0x11, 0x11), anchor="mm")
    elif kind == "header":
        _, x, y, w, s = item
        text_at(d, x, y, w, s, 17, INK, "left")
        d.rectangle((x * SS, (y + 26) * SS, (x + w) * SS, (y + 27) * SS - 1), fill=INK)
    elif kind == "text":
        _, x, y, w, s, size, colour, align = item
        text_at(d, x, y, w, s, size, colour, align)
    elif kind == "lcd":
        _, x, y, w, h = item
        d.rounded_rectangle((x * SS, y * SS, (x + w) * SS, (y + h) * SS), radius=4 * SS, fill=LCD_FILL,
                            outline=(0x0a, 0x0a, 0x0a), width=2 * SS)
    elif kind == "line":
        _, x, y, w, h, colour = item
        d.rectangle((x * SS, y * SS, (x + w) * SS - 1, (y + h) * SS - 1), fill=colour)


def slider_geom(c):
    k = c["k"]
    bw, bh = SLIDER["bg_size"][0] * k, SLIDER["bg_size"][1] * k
    hw, hh = SLIDER["handle_size"][0] * k, SLIDER["handle_size"][1] * k
    hx = 5.4 * k
    return bw, bh, hw, hh, hx


def draw_slider_slot(img, c):
    """the static part: the dark slab, the tick marks either side, Valley's slider background"""
    d = ImageDraw.Draw(img)
    k = c["k"]
    bw, bh, hw, hh, hx = slider_geom(c)
    x, y = c["x"], c["y"]
    d.rounded_rectangle(((x + hx - 4) * SS, y * SS, (x + hx + hw + 4) * SS, (y + bh) * SS), radius=4 * SS,
                        fill=(0x1b, 0x1b, 0x1b))
    t0, t1 = (TRAVEL[0] + 14.95) * k, (TRAVEL[1] + 14.95) * k
    tl, g = 3.4 * k, 1.6 * k
    for i in range(11):
        ty = y + t0 + (t1 - t0) * i / 10
        long_ = i in (0, 5, 10) or c.get("bipolar") and i == 5
        ext = tl * (1.5 if long_ else 1.0)
        for x0 in (x + hx - 4 - g - ext, x + hx + hw + 4 + g):
            d.rectangle((x0 * SS, (ty - 1.5) * SS, (x0 + ext) * SS, (ty + 1.5) * SS), fill=INK)
    paste(img, svg(art("valley", SLIDER["bg"]), bw * SS, bh * SS), x * SS, y * SS)


def draw_fader_box(img, c):
    s = c["s"]
    box = Image.open(art("bazzline", "fader_box.png")).convert("RGBA")
    box = box.resize((int(FADER_BOX[0] * s * SS), int(FADER_BOX[1] * s * SS)), Image.LANCZOS)
    paste(img, box, c["x"] * SS, c["y"] * SS)
    if c.get("lcd"):
        x, y, w, h = c["lcd"]
        ImageDraw.Draw(img).rounded_rectangle((x * SS, y * SS, (x + w) * SS, (y + h) * SS), radius=4 * SS,
                                              fill=LCD_FILL, outline=(0x0a, 0x0a, 0x0a), width=2 * SS)


# ------------------------------------------------------------------------------------------------ control images
def crop(page_img, box):
    x, y, w, h = box
    return page_img.crop((int(x * SS), int(y * SS), int((x + w) * SS), int((y + h) * SS)))


def down(img, w, h):
    return img.resize((int(w), int(h)), Image.LANCZOS).convert("RGB")


def strip(frames):
    w, h = frames[0].size
    out = Image.new("RGB", (w, h * len(frames)))
    for i, f in enumerate(frames):
        out.paste(f, (0, i * h))
    return out


def slider_frames(page_img, c):
    bw, bh, hw, hh, hx = slider_geom(c)
    box = (c["x"], c["y"], bw, bh)
    base = crop(page_img, box)
    n = max(2, min(128, MAX_STRIP // int(bh)))
    handle = svg(art("valley", HANDLE[c["colour"]]), hw * SS, hh * SS)
    frames = []
    for i in range(n):
        v = i / float(n - 1)
        cell = base.copy()
        top = (TRAVEL[1] + (TRAVEL[0] - TRAVEL[1]) * v) * c["k"]
        paste(cell, handle, hx * SS, top * SS)
        frames.append(down(cell, bw, bh))
    return box, frames


def knob_frames(page_img, c, nopts):
    s = c["s"]
    box = (c["cx"] - s / 2, c["cy"] - s / 2, s, s)
    base = crop(page_img, box)
    layers = [svg(art("valley", p), s * SS, s * SS) for p in KNOB]
    if c.get("detents"):
        values = [i / float(nopts - 1) for i in range(nopts)]
    else:
        n = max(16, min(128, MAX_STRIP // int(s)))
        values = [i / float(n - 1) for i in range(n)]
    frames = []
    for v in values:
        cell = base.copy()
        angle = -ROGAN_SWEEP + 2 * ROGAN_SWEEP * v
        paste(cell, layers[0], 0, 0)
        paste(cell, layers[1].rotate(-math.degrees(angle), resample=Image.BICUBIC), 0, 0)
        paste(cell, layers[2], 0, 0)
        frames.append(down(cell, s, s))
    return box, frames


def fader_frames(page_img, c):
    s = c["s"]
    w, h = FADER_BOX[0] * s, FADER_BOX[1] * s
    box = (c["x"], c["y"], w, h)
    base = crop(page_img, box)
    thumb = Image.open(art("bazzline", "thumb_v.png")).convert("RGBA")
    thumb = thumb.resize((int(THUMB[0] * s * SS), int(THUMB[1] * s * SS)), Image.LANCZOS)
    n = max(2, min(128, MAX_STRIP // int(h)))
    cx, cy, cw, ch = FADER_CHANNEL
    frames = []
    for i in range(n):
        v = i / float(n - 1)
        cell = base.copy()
        centre = (cy + ch * (1 - v)) * s
        paste(cell, thumb, (cx + cw / 2.0 - THUMB[0] / 2.0) * s * SS, (centre - THUMB[1] * s / 2.0) * SS)
        frames.append(down(cell, w, h))
    return box, frames


def ckss_images(page_img, c):
    k = c["k"]
    w, h = 14 * k, 20.64 * k
    box = (c["x"], c["y"], w, h)
    out = []
    for f in CKSS:
        cell = crop(page_img, box)
        paste(cell, svg(art("vcv", f), w * SS, h * SS), 0, 0)
        out.append(down(cell, w, h))
    return box, out


def lit_images(page_img, c):
    sz = c["size"]
    box = (c["x"], c["y"], sz, sz)
    key = Image.open(art("bazzline", "btn_lit_small.png")).convert("RGBA").resize((sz * SS, sz * SS), Image.LANCZOS)
    grey = ImageOps.grayscale(key)
    alpha = key.split()[3]
    off = ImageOps.colorize(grey, black=(18, 18, 18), white=(215, 215, 215)).convert("RGBA")
    on = ImageOps.colorize(grey, black=(60, 22, 0), white=(255, 214, 150)).convert("RGBA")
    out = []
    for layer in (off, on):
        layer.putalpha(alpha)
        cell = crop(page_img, box)
        cell.alpha_composite(layer)
        out.append(down(cell, sz, sz))
    return box, out


def button_image(w, h, s, fs, fill, ink, radius=3):
    img = Image.new("RGBA", (w * SS, h * SS), BG + (255,))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w * SS - 1, h * SS - 1), radius=radius * SS, fill=fill)
    lines = s.split("\n")
    lh = fs * 1.15
    for i, ln in enumerate(lines):
        y = h / 2 + (i - (len(lines) - 1) / 2) * lh
        d.text((w / 2 * SS, y * SS), ln, font=font(fs * SS), fill=ink, anchor="mm")
    return down(img, w, h)


STYLES = {"dark": (SEG_OFF, INK_DIM, (0x3a, 0x3a, 0x3a), INK), "orange": (ORANGE, (17, 17, 17), (255, 196, 120), (17, 17, 17)),
          "red": ((210, 58, 42), INK, (240, 96, 80), INK)}


# ------------------------------------------------------------------------------------------------ label strips
def osc_labels():
    """per oscillator type (option index), the names of its seven parameters (Surge's own; "" where unused)"""
    out = []
    for t in panel.FACTS["osc_types"]:
        out.append([p["name"] if p["ct"] else "" for p in t["params"]])
    return out


def fx_labels():
    """per fx_type option (Surge type, SurgeXXL's order), the names of its twelve parameters"""
    by_type = {t["type"]: t for t in panel.FACTS["fx_types"]}
    import gen_params
    out = []
    for surge_type, _ in gen_params.FX_TYPES:
        t = by_type[surge_type]
        names = [p["name"] if p["ct"] else "" for p in t["params"]]
        if surge_type == 14:   # Airwindows: Surge names the parameters after the chosen effect, live; here by number
            names = ["Effect"] + ["Param %d" % i for i in range(1, len(names))]
        out.append(names)
    return out


ABBREV = [("Unison ", "Uni "), ("Horizontal", "H"), ("Vertical", "V"), ("Frequency", "Freq"), ("Feedback", "Fdbk")]


def short(name, max_px, size):
    f = font(size)
    for a, b in ABBREV:
        if f.getlength(name) > max_px:
            name = name.replace(a, b)
    while f.getlength(name) > max_px and len(name) > 3:
        name = name[:-1]
    return name


def label_strip(page_img, rect, items, size):
    """an opaque strip of the page (rect) with each (cx, text) lettered on it"""
    x, y, w, h = rect
    cell = crop(page_img, rect)
    d = ImageDraw.Draw(cell)
    for cx, s, maxw in items:
        s = short(s, maxw, size)
        d.text(((cx - x) * SS, h / 2 * SS), s, font=font(size * SS), fill=INK, anchor="mm")
    return down(cell, w, h)


# ------------------------------------------------------------------------------------------------ TUI.json
def defs_list(tui):
    return tui["pageData"]["componentDefinitions"]["localComponentDefinitions"]


def child_param(child):
    for m in child.get("handle remapping", {}).get("map", []):
        if m.get("key") == "Data" and str(m.get("value", "")).startswith("Parameter "):
            return int(m["value"].split()[1])
    return None


def bstr(x, y, w, h):
    return "%d %d %d %d" % (int(round(x)), int(round(y)), int(round(w)), int(round(h)))


def sub_bounds(comp, x, y, w, h):
    comp["bounds"]["bounds"] = bstr(x, y, w, h)


def label_comp(name, x, y, w, h, colour, size, just="horizontallyCentred verticallyCentred"):
    return {"version": 2, "componentData": {"version": 1, "name": name, "type": "Label", "data": {
        "version": 1, "textStyle": {"version": 1, "font": {"version": 1, "name": "Titillium Web", "style": "SemiBold",
                                                          "height": float(size)},
                                    "colour": colour, "justification": just, "case": "Original"},
        "type": "Value", "handleName": "Data"}},
        "handle remapping": {"version": 1, "map": []},
        "bounds": {"version": 2, "acceptsHWFocus": "No", "showWhenDataModelInvalid": "Show", "whenVisible": "Always",
                   "boundsType": "Absolute", "bounds": bstr(x, y, w, h), "additionalInvalidatingHandles": []}}


def image_comp(img, x, y, w, h, handles=None):
    return {"version": 2, "componentData": {"version": 1, "name": "Picture", "type": "Image", "data": {
        "version": 2, "imageType": "Regular", "colour": "0", "image": img}},
        "handle remapping": {"version": 1, "map": []},
        "bounds": {"version": 2, "acceptsHWFocus": "No", "showWhenDataModelInvalid": "Show", "whenVisible": "Always",
                   "boundsType": "Absolute", "bounds": bstr(x, y, w, h),
                   "additionalInvalidatingHandles": handles or []}}


class Skin:
    def __init__(self, skin):
        self.skin = skin
        self.tui = json.load(open(os.path.join(skin, "TUI.json")))
        self.defs = {d["key"]: d for d in defs_list(self.tui)}
        self.order = [p["key"] for p in panel.PARAMS]
        self.index = {k: i for i, k in enumerate(self.order)}
        self.new_defs = []
        self.written = set()

    def save(self, img, name):
        img.save(os.path.join(self.skin, name), optimize=True)
        self.written.add(name)
        return name

    def tabs_of(self, t):
        """the sub-page components of page t (one per Q-Link page)"""
        out = []
        for tab in self.tui["pageData"]["tabs"]:
            if tab["componentName"].split("|")[0] == panel.TABS[t]:
                out.append(self.defs[tab["componentName"]])
        return out

    def add_def(self, key, comps, actions_from):
        d = copy.deepcopy(actions_from)
        d["key"] = key
        d["value"]["componentsData"] = comps
        self.new_defs.append(d)
        self.defs[key] = d
        return d


def find_sub(defn, ctype, name=None):
    for comp in defn["value"]["componentsData"]:
        cd = comp["componentData"]
        if cd["type"] == ctype and (name is None or cd["name"] == name):
            return comp
    return None


# ------------------------------------------------------------------------------------------------ main
def build_page(sk, t):
    cs = panel.controls(t)
    page = Image.new("RGBA", (panel.W * SS, panel.H * SS), BG + (255,))
    d = ImageDraw.Draw(page)
    for item in panel.ART[t]:
        if item[0] in ("frame", "lcd", "line"):
            draw_art(d, item)
    for c in cs:
        if c["kind"] == "slider":
            draw_slider_slot(page, c)
        elif c["kind"] == "fader":
            draw_fader_box(page, c)
        elif c["kind"] == "popup":
            x, y, w, h = c["x"], c["y"], c["w"], c["h"]
            d.rounded_rectangle((x * SS, y * SS, (x + w) * SS, (y + h) * SS), radius=4 * SS, fill=LCD_FILL,
                                outline=(0x5a, 0x5a, 0x5a), width=2 * SS)
            mx, my = x + w - 20, y + h / 2
            d.polygon([((mx - 7) * SS, (my - 4) * SS), ((mx + 7) * SS, (my - 4) * SS), (mx * SS, (my + 5) * SS)],
                      fill=ORANGE)
    for item in panel.ART[t]:
        if item[0] in ("header", "text"):
            draw_art(d, item)
    # static names under sliders and knobs
    for c in cs:
        if c["kind"] == "slider" and c.get("label"):
            bw, bh, _, _, _ = slider_geom(c)
            text_at(d, c["x"] - 30, c["y"] + bh + 6, bw + 60, c["label"], c["fs"], INK)
        elif c["kind"] == "knob" and c.get("label"):
            text_at(d, c["cx"] - 80, c["cy"] + c["s"] / 2 + 4, 160, c["label"], c["fs"], INK)
    # placements: key -> (defn key, outer bounds)
    placed = {}
    pics = []          # Image components added to every sub-page: (image, x, y, w, h, handles)

    def centre_x(o):
        if o["kind"] == "slider":
            return o["x"] + slider_geom(o)[0] / 2
        return o["cx"]

    def row_y(o):
        return o["y"] if o["kind"] == "slider" else o["cy"] - o["s"] / 2

    def room(c):
        """the value text's width: up to the default, never reaching the next control on the same row"""
        cx, best = centre_x(c), 10000
        for o in cs:
            if o is c or o["kind"] not in ("slider", "knob") or not o.get("value", True):
                continue
            if abs(row_y(o) - row_y(c)) < 40:
                best = min(best, abs(centre_x(o) - cx))
        return best - 4

    def value_rect(c, box):
        """where the value text goes (page px), or None"""
        if not c.get("value", True):
            return None
        x, y, w, h = box
        if c["kind"] == "slider":
            vw = min(c.get("vw", w + 50), room(c))
            ly = y + h + (6 + c["fs"] + 4 if c.get("label") or c.get("labels_by") else 6)
            return (x + w / 2 - vw / 2, ly + c.get("value_dy", 0), vw, 22)
        if c["kind"] == "knob":
            vw = min(c.get("vw", w + 30), room(c))
            ly = y + h + (4 + c["fs"] + 4 if c.get("label") or c.get("labels_by") else 2)
            return (x + w / 2 - vw / 2, ly + c.get("value_dy", 0), vw, 22)
        return None

    def place_film(c, box, frames, numframes, value):
        name = sk.save(strip(frames), "sx_%d_%s.png" % (t, c["key"]))
        x, y, w, h = box
        vr = value
        ox0, oy0 = min(x, vr[0]) if vr else x, min(y, vr[1]) if vr else y
        ox1 = max(x + w, vr[0] + vr[2]) if vr else x + w
        oy1 = max(y + h, vr[1] + vr[3]) if vr else y + h
        tmpl_key = None
        for k2, dd in sk.defs.items():
            if k2.startswith(("shKnob", "shSlider")):
                tmpl_key = k2
                break
        tmpl = sk.defs[tmpl_key]
        comps = [copy.deepcopy(find_sub(tmpl, "Focus"))]
        sub_bounds(comps[0], 0, 0, ox1 - ox0, oy1 - oy0)
        film = copy.deepcopy(find_sub(tmpl, "Knob"))
        film["componentData"]["data"]["filmStrip"] = name
        film["componentData"]["data"]["numFrames"] = numframes
        film["componentData"]["data"]["dragOrientation"] = "Vertical"
        sub_bounds(film, x - ox0, y - oy0, w, h)
        comps.append(film)
        if vr:
            colour = c.get("value_colour", VALUE_COLOUR)
            comps.append(label_comp("Value", vr[0] - ox0, vr[1] - oy0, vr[2], vr[3], colour, c.get("value_size", 17)))
        key = "sx_%d_%s" % (t, c["key"])
        sk.add_def(key, comps, tmpl)
        placed[c["key"]] = (key, (ox0, oy0, ox1 - ox0, oy1 - oy0))

    def place_buttons(c, rects, images):
        """an option list as image buttons, one per option (a radio group on the parameter)"""
        tmpl = None
        for k2, dd in sk.defs.items():
            if k2.startswith("shSeg_"):
                tmpl = dd
                break
        keys = []
        for i, (r, (off, on)) in enumerate(zip(rects, images)):
            noff = sk.save(off, "sx_%d_%s_%d_off.png" % (t, c["key"], i))
            non = sk.save(on, "sx_%d_%s_%d_on.png" % (t, c["key"], i))
            comps = copy.deepcopy(tmpl["value"]["componentsData"])
            b = comps[0]["componentData"]["data"]
            b["onImage"], b["offImage"] = non, noff
            b["buttonId"], b["numButtonsInGroup"] = i, len(rects)
            sub_bounds(comps[0], 0, 0, r[2], r[3])
            key = "sx_%d_%s_%d" % (t, c["key"], i)
            sk.add_def(key, comps, tmpl)
            keys.append((key, r))
        placed[c["key"]] = ("seg", keys)

    for c in cs:
        k = c["kind"]
        p = panel.P[c["key"]]
        nopts = len(p.get("options", [])) or 2
        if k == "slider":
            box, frames = slider_frames(page, c)
            place_film(c, box, frames, len(frames), value_rect(c, box))
        elif k == "knob":
            box, frames = knob_frames(page, c, nopts)
            place_film(c, box, frames, len(frames) - 1 if not c.get("detents") else len(frames), value_rect(c, box))
        elif k == "fader":
            box, frames = fader_frames(page, c)
            vr = None
            if c.get("lcd"):
                vr = c["lcd"]
                c["value_colour"], c["value_size"] = "fffb9013", 19
            place_film(c, box, frames, len(frames), vr)
        elif k in ("ckss", "lit"):
            box, (off, on) = ckss_images(page, c) if k == "ckss" else lit_images(page, c)
            placed[c["key"]] = ("switch", (sk.save(off, "sx_%d_%s_off.png" % (t, c["key"])),
                                           sk.save(on, "sx_%d_%s_on.png" % (t, c["key"]))), box)
        elif k == "seg":
            imgs = []
            for r, s in zip(c["rects"], c["texts"]):
                imgs.append((button_image(r[2], r[3], s, c["fs"], SEG_OFF, INK_DIM),
                             button_image(r[2], r[3], s, c["fs"], ORANGE, (17, 17, 17))))
            place_buttons(c, c["rects"], imgs)
        elif k == "button":
            fill, ink, fill_on, ink_on = STYLES[c["style"]]
            off = button_image(c["w"], c["h"], c["text"], c["fs"], fill, ink)
            on = button_image(c["w"], c["h"], c["text"], c["fs"], fill_on, ink_on)
            placed[c["key"]] = ("trig", (sk.save(off, "sx_%d_%s_off.png" % (t, c["key"])),
                                         sk.save(on, "sx_%d_%s_on.png" % (t, c["key"]))), (c["x"], c["y"], c["w"], c["h"]))
        elif k == "readout":
            placed[c["key"]] = ("readout", c)
        elif k == "popup":
            placed[c["key"]] = ("popup", c)
        elif k == "picture":
            if WT_PICTURES:
                import wt_art
                n = p["max"] + 1
                for i in range(n):
                    img = wt_art.picture(i, c["w"], c["h"])
                    name = sk.save(img, "sx_wt_%d.png" % i)
                    pics.append((name, c["x"], c["y"], c["w"], c["h"],
                                 ["IndexedEnabling/%d/%d/Parameter %d" % (i, n, sk.index[c["key"]])]))
    # per-type name strips
    for by, labels, groups in (("osc_type", osc_labels, None), ("fx_type", fx_labels, None)):
        group = [c for c in cs if c.get("labels_by") == by]
        if not group:
            continue
        names = labels()
        rows = {}
        for i, c in enumerate(group):
            if c["kind"] == "slider":
                bw, bh, _, _, _ = slider_geom(c)
                cx, ly, maxw = c["x"] + bw / 2, c["y"] + bh + 6, 86
            else:
                cx, ly, maxw = c["cx"], c["cy"] + c["s"] / 2 + 4, 120
            rows.setdefault(ly, []).append((i, cx, maxw))
        n = len(names)
        pidx = sk.index[by]
        for o in range(n):
            for ly, items in rows.items():
                xs = [cx for _, cx, _ in items]
                rect = (min(xs) - 64, ly, max(xs) - min(xs) + 128, 22)
                img = label_strip(page, rect, [(cx, names[o][i] if i < len(names[o]) else "", maxw)
                                               for i, cx, maxw in items], 16)
                name = sk.save(img, "sx_%d_%s_lbl_%d_%d.png" % (t, by, o, int(ly)))
                pics.append((name, rect[0], rect[1], rect[2], rect[3],
                             ["IndexedEnabling/%d/%d/Parameter %d" % (o, n, pidx)]))
    bg_name = sk.save(down(page, panel.W, panel.H), "sx_bg_%d.png" % t)
    # rewrite every sub-page of this page
    for tab_def in sk.tabs_of(t):
        comps = tab_def["value"]["componentsData"]
        out = []
        for child in comps:
            cd = child["componentData"]
            if cd["type"] == "Image" and cd["name"] == "Background":
                cd["data"]["image"] = bg_name
                out.append(child)
                continue
            pi = child_param(child)
            key = sk.order[pi] if pi is not None and pi < len(sk.order) else None
            ctype = cd["type"]
            if key is None or key not in placed:
                out.append(child)        # popup panels/options, anything we don't restyle
                continue
            pl = placed[key]
            if pl[0] == "seg":
                if not ctype.startswith("shSeg_"):
                    out.append(child)
                    continue
                i = int(ctype.rsplit("_", 1)[1])
                dk, r = pl[1][i]
                child["componentData"]["type"] = dk
                child["bounds"]["bounds"] = bstr(*r)
                out.append(child)
            elif pl[0] in ("trig", "switch"):
                if not (ctype.startswith("shTrig") or ctype.startswith("shToggle")):
                    out.append(child)
                    continue
                tdef = copy.deepcopy(sk.defs[ctype])
                tdef["key"] = "sx_%d_%s_btn" % (t, key)
                btn = find_sub(tdef, "Button")
                btn["componentData"]["data"]["offImage"], btn["componentData"]["data"]["onImage"] = pl[1]
                x, y, w, h = pl[2]
                for comp in tdef["value"]["componentsData"]:
                    sub_bounds(comp, 0, 0, w, h)
                if tdef["key"] not in sk.defs:
                    sk.new_defs.append(tdef)
                    sk.defs[tdef["key"]] = tdef
                child["componentData"]["type"] = tdef["key"]
                child["bounds"]["bounds"] = bstr(x, y, w, h)
                out.append(child)
            elif pl[0] == "readout":
                c = pl[1]
                rdef = copy.deepcopy(sk.defs[ctype])
                rdef["key"] = "sx_%d_%s_txt" % (t, key)
                lab = find_sub(rdef, "Label")
                ts = lab["componentData"]["data"]["textStyle"]
                ts["font"]["height"] = float(c["size"])
                ts["colour"] = "ff" + c["colour"]
                ts["justification"] = {"left": "centredLeft", "center": "horizontallyCentred verticallyCentred",
                                       "right": "centredRight"}[c["align"]]
                sub_bounds(lab, 0, 0, c["w"], c["h"])
                if rdef["key"] not in sk.defs:
                    sk.new_defs.append(rdef)
                    sk.defs[rdef["key"]] = rdef
                child["componentData"]["type"] = rdef["key"]
                child["bounds"]["bounds"] = bstr(c["x"], c["y"], c["w"], c["h"])
                out.append(child)
            elif pl[0] == "popup":
                out.append(child)
            else:
                dk, rect = pl
                if not (ctype.startswith("shKnob") or ctype.startswith("shSlider")):
                    out.append(child)
                    continue
                child["componentData"]["type"] = dk
                child["bounds"]["bounds"] = bstr(*rect)
                out.append(child)
        # the per-option pictures go right after the background, under the controls
        pic_comps = [image_comp(*p) for p in pics]
        tab_def["value"]["componentsData"] = out[:1] + pic_comps + out[1:]
    return len(cs)


def restyle_popups(sk):
    """the popups' lists: Titillium lettering on the dark buttons, the selected option orange; the open list's panel
    dark with an orange rim; the field's value text orange"""
    n = 0
    for key, d in list(sk.defs.items()):
        if key.startswith("shPopOpt_"):
            rest = key[len("shPopOpt_"):]
            tab, rest = rest.split("_", 1)
            pkey, i = rest.rsplit("_", 1)
            if pkey not in panel.P:
                continue
            label = panel.P[pkey]["options"][int(i)]
            btn = find_sub(d, "Button")
            w, h = [int(v) for v in btn["bounds"]["bounds"].split()[2:]]
            data = btn["componentData"]["data"]
            data["offImage"] = sk.save(button_image(w, h, label, 15, SEG_OFF, INK_DIM),
                                       "sx_po_%s_%s_%s_off.png" % (tab, pkey, i))
            data["onImage"] = sk.save(button_image(w, h, label, 15, ORANGE, (17, 17, 17)),
                                      "sx_po_%s_%s_%s_on.png" % (tab, pkey, i))
            n += 1
        elif key.startswith("shPopPanel_"):
            img = find_sub(d, "Image")
            w, h = [int(v) for v in img["bounds"]["bounds"].split()[2:]]
            pnl = Image.new("RGB", (w, h), (0x24, 0x24, 0x24))
            ImageDraw.Draw(pnl).rectangle((0, 0, w - 1, h - 1), outline=ORANGE, width=2)
            img["componentData"]["data"]["image"] = sk.save(pnl, "sx_pp_%s.png" % key[len("shPopPanel_"):])
        elif key.startswith("shPopField_"):
            lab = find_sub(d, "Label")
            if lab:
                ts = lab["componentData"]["data"]["textStyle"]
                ts["colour"], ts["font"]["height"] = "fffb9013", 22.0
    return n


def prune(sk):
    defs = defs_list(sk.tui) + sk.new_defs
    used_types = set()
    for d in defs:
        for comp in d["value"].get("componentsData", []):
            used_types.add(comp["componentData"]["type"])
    for tab in sk.tui["pageData"]["tabs"]:
        used_types.add(tab["componentName"])
    keep = [d for d in defs if d["key"] in used_types]
    sk.tui["pageData"]["componentDefinitions"]["localComponentDefinitions"] = keep
    text = json.dumps(sk.tui)
    removed = 0
    for name in os.listdir(sk.skin):
        if name.endswith(".png") and ('"%s"' % name) not in text:
            os.remove(os.path.join(sk.skin, name))
            removed += 1
    return removed


def main():
    skin = sys.argv[1]
    sk = Skin(skin)
    n = 0
    for t in range(len(panel.TABS)):
        n += build_page(sk, t)
    restyle_popups(sk)
    removed = prune(sk)
    json.dump(sk.tui, open(os.path.join(skin, "TUI.json"), "w"), indent=1)
    print("panel_art: %d controls on %d pages drawn, %d images written, %d unused removed" %
          (n, len(panel.TABS), len(sk.written), removed))


if __name__ == "__main__":
    main()
