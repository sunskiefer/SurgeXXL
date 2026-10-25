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
import theme  # noqa: E402

ROOT = panel.ROOT
SS = 2                      # draw this many times larger, then scale down
MAX_STRIP = 12288
FONT = os.path.join(ROOT, "art", "fonts", "TitilliumWeb-SemiBold.ttf")
TH = theme.T
BG = TH["bg"]
ORANGE = TH["accent"]
SEG_OFF = TH["seg_off"]
INK = TH["ink"]
INK_DIM = TH["ink_dim"]
VALUE_COLOUR = TH["value"]
BTN_OFF_INK = TH["seg_off_ink"]
ACCENT_INK = TH["accent_ink"]
BTN_ON = TH["btn_on"]            # a lit button / the selected option
BTN_ON_INK = TH["btn_on_ink"]
VALUE_SIZE = 20             # live value text (0.3.0: the same size as every name)
HEADER_SIZE = 20
STRIP_SIZE = 20             # the per-type parameter names under sliders / knobs
KNOB_MAX = 96               # 128 frames of 96 px: the largest knob strip MPC animates right (docs/NOTES.md)
LCD_FILL = TH["screen_fill"]
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


def gold_fill(img, box, radius, vertical=True):
    """paint a rounded box with the theme's gold: lighter along the top, darker towards the foot, and a thin lit edge"""
    x0, y0, x1, y1 = [int(v) for v in box]
    w, h = max(1, x1 - x0), max(1, y1 - y0)
    hi, mid, lo = TH["gold_hi"], TH["btn_on"], TH["gold_lo"]
    g = Image.new("RGBA", (w, h))
    gd = ImageDraw.Draw(g)
    for i in range(h):
        t = i / max(1, h - 1)
        if t < 0.45:
            u = t / 0.45
            c = tuple(int(hi[k] + (mid[k] - hi[k]) * u) for k in range(3))
        else:
            u = (t - 0.45) / 0.55
            c = tuple(int(mid[k] + (lo[k] - mid[k]) * u) for k in range(3))
        gd.line((0, i, w, i), fill=c + (255,))
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=255)
    img.paste(g, (x0, y0), m)


def screen_hex(h):
    """lettering on a dark screen: the dark skin's orange becomes this theme's screen inks (8-digit AARRGGBB or 6-digit)"""
    t = h.lower()
    a, c = (t[:2], t[2:]) if len(t) == 8 else ("", t)
    ink, dim = TH["screen_ink"], TH["screen_dim"]
    c = {"fb9013": "%02x%02x%02x" % ink, "c97a1c": "%02x%02x%02x" % dim}.get(c, c)
    return a + c


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
        d.rectangle((x * SS, y * SS, (x + w) * SS - 1, (y + h) * SS - 1), outline=TH["frame_line"], width=(2 if TH["bevel"] else 3) * SS)
        f = font(24 * SS)
        tw = d.textlength(title, font=f) / SS
        tx = x + (w - tw) / 2 - 22
        d.rectangle((tx * SS, (y - 18) * SS, (tx + tw + 44) * SS, (y + 18) * SS), fill=TH["tab_fill"], outline=TH["frame_line"] if TH["bevel"] else None, width=SS)
        d.text(((x + w / 2) * SS, y * SS), title, font=f, fill=TH["tab_text"], anchor="mm")
    elif kind == "header":
        _, x, y, w, s = item
        text_at(d, x, y, w, s, HEADER_SIZE, INK, "left")
        d.rectangle((x * SS, (y + 28) * SS, (x + w) * SS, (y + 29) * SS - 1), fill=TH["header_line"])
    elif kind == "text":
        _, x, y, w, s, size, colour, align = item
        text_at(d, x, y, w, s, size, (TH["bg_text"] or {}).get(tuple(colour), colour), align)
    elif kind == "lcd":
        _, x, y, w, h = item
        d.rounded_rectangle((x * SS, y * SS, (x + w) * SS, (y + h) * SS), radius=4 * SS, fill=LCD_FILL,
                            outline=(0x0a, 0x0a, 0x0a), width=2 * SS)
    elif kind == "line":
        _, x, y, w, h, colour = item
        if tuple(colour) == (0x3e, 0x3e, 0x3e):
            colour = TH["line"]
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
    if TH["style"] == "hive":      # HIVE 2: a slim dark track the cap runs on, no ticks
        cx = x + hx + hw / 2
        top, bot = y + (TRAVEL[0] + hh / (2 * k)) * k, y + (TRAVEL[1] + hh / (2 * k)) * k
        d.rounded_rectangle(((cx - 5.5) * SS, (top - 8) * SS, (cx + 5.5) * SS, (bot + 8) * SS), radius=5.5 * SS, fill=TH["track"])
        return
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


CAP_COLOURS = {"orange": ORANGE, "red": (0xd2, 0x3a, 0x2a), "yellow": (0xf2, 0xc8, 0x2e), "green": (0x4c, 0xc2, 0x5a),
               "blue": (0x3a, 0x7c, 0xe0)}


def hive_cap(hw, hh, colour):
    """a HIVE-style fader cap: a thin flat bar a little wider than the track"""
    w, h = int(hw * 1.45 * SS), int(hh * 0.12 * SS)
    cap = Image.new("RGBA", (int(hw * SS), int(hh * SS)), (0, 0, 0, 0))
    d = ImageDraw.Draw(cap)
    x0, y0 = (cap.size[0] - w) // 2, (cap.size[1] - h) // 2
    d.rounded_rectangle((x0, y0, x0 + w, y0 + h), radius=2 * SS, fill=TH["cap"])
    return cap


def slider_frames(page_img, c):
    bw, bh, hw, hh, hx = slider_geom(c)
    box = (c["x"], c["y"], bw, bh)
    base = crop(page_img, box)
    n = max(2, min(128, MAX_STRIP // int(bh)))
    handle = svg(art("valley", HANDLE[c["colour"]]), hw * SS, hh * SS)
    if TH["style"] == "hive":
        handle = hive_cap(hw, hh, c["colour"])
    frames = []
    for i in range(n):
        v = i / float(n - 1)
        cell = base.copy()
        top = (TRAVEL[1] + (TRAVEL[0] - TRAVEL[1]) * v) * c["k"]
        if TH["style"] == "hive":     # the lit part of the track, from the foot up to the cap
            cxs = (hx + hw / 2) * SS
            mid = (top + hh / 2) * SS
            foot = (TRAVEL[1] * c["k"] + hh / 2 + 8) * SS
            fc = CAP_COLOURS[c["colour"]] if c["colour"] in ("red", "yellow", "green", "blue") and not TH.get("mono_fill") else TH["fill"]
            if TH.get("mono_fill"):
                gold_fill(cell, (cxs - 5.5 * SS, mid, cxs + 5.5 * SS, foot), 5.5 * SS)
            else:
                ImageDraw.Draw(cell).rounded_rectangle((cxs - 5.5 * SS, mid, cxs + 5.5 * SS, foot), radius=5.5 * SS, fill=fc)
        paste(cell, handle, hx * SS, top * SS)
        frames.append(down(cell, bw, bh))
    return box, frames


def hive_knob(s, v):
    """a flat black knob (HIVE / Serum): a thin ring with the value arc, a cap, and a light pointer (drawn at SS; the Serum
    look adds a bevel: a light edge on the cap's top, a dark one underneath)"""
    L = TH["knob_look"]
    img = Image.new("RGBA", (s * SS, s * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = s * SS / 2
    a0, a1 = -90 - math.degrees(ROGAN_SWEEP), -90 + math.degrees(ROGAN_SWEEP)
    ring = (2.5 * SS, 2.5 * SS, s * SS - 2.5 * SS, s * SS - 2.5 * SS)
    d.arc(ring, a0, a1, fill=L["ring"], width=int(2.4 * SS))
    if L.get("dot"):               # Serum: one short lit mark on the ring where the pointer is, not an arc
        am = a0 + (a1 - a0) * v
        d.arc(ring, am - 3.5, am + 3.5, fill=L["arc"], width=int(4.2 * SS))
    elif v > 0.004:
        d.arc(ring, a0, a0 + (a1 - a0) * v, fill=L["arc"], width=int(2.4 * SS))
    rb = r * L["rb"]
    d.ellipse((r - rb, r - rb, r + rb, r + rb), fill=L["cap_o"])
    d.ellipse((r - rb * 0.93, r - rb * 0.93, r + rb * 0.93, r + rb * 0.93), fill=L["cap_i"])
    if TH["bevel"]:
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(lay)
        box = (r - rb * 0.93, r - rb * 0.93, r + rb * 0.93, r + rb * 0.93)
        ld.arc(box, 200, 340, fill=(255, 255, 255, 70), width=int(1.6 * SS))
        ld.arc(box, 20, 160, fill=(0, 0, 0, 150), width=int(1.6 * SS))
        ld.ellipse((r - rb * 0.55, r - rb * 0.55, r + rb * 0.55, r + rb * 0.55), outline=(255, 255, 255, 16), width=SS)
        img.alpha_composite(lay)
        d = ImageDraw.Draw(img)
    ang = -ROGAN_SWEEP + 2 * ROGAN_SWEEP * v
    px, py = math.sin(ang), -math.cos(ang)
    d.line((r + px * rb * L["p0"], r + py * rb * L["p0"], r + px * rb * L["p1"], r + py * rb * L["p1"]), fill=L["tick"], width=int(3.2 * SS))
    return img


def tint(layer):
    """the knob cap in this theme's colours (the shading kept, the alpha kept)"""
    lo, hi = TH["knob_tint"]
    grey = ImageOps.autocontrast(layer.convert("L"))
    out = ImageOps.colorize(grey, black=lo, white=hi).convert("RGBA")
    out.putalpha(layer.getchannel("A"))
    return out


def knob_frames(page_img, c, nopts):
    """128 square frames (numFrames 127), the device-checked knob strip; an option knob snaps each frame to the
    nearest option's angle, so it turns like a switch and the strip is still the verified shape"""
    s = c["s"]
    assert s <= KNOB_MAX, "%s: a %d px knob makes a strip MPC cannot animate (max %d)" % (c["key"], s, KNOB_MAX)
    box = (c["cx"] - s / 2, c["cy"] - s / 2, s, s)
    base = crop(page_img, box)
    layers = [svg(art("valley", p), s * SS, s * SS) for p in KNOB]
    n = 128
    frames = []
    for i in range(n):
        v = i / float(n - 1)
        if c.get("detents") and nopts > 1:
            v = round(v * (nopts - 1)) / float(nopts - 1)
        cell = base.copy()
        angle = -ROGAN_SWEEP + 2 * ROGAN_SWEEP * v
        if TH["knob"] in ("hive", "serum"):
            paste(cell, hive_knob(s, v), 0, 0)
            frames.append(down(cell, s, s))
            continue
        paste(cell, layers[0], 0, 0)
        paste(cell, layers[1].rotate(-math.degrees(angle), resample=Image.BICUBIC), 0, 0)
        paste(cell, layers[2], 0, 0)
        frames.append(down(cell, s, s))
    return box, frames


def wheel_image(s):
    """a data wheel: a dark ribbed disc with a lighter rim and one marker dot (drawn at SS)"""
    img = Image.new("RGBA", (s * SS, s * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = s * SS / 2
    if TH["knob"] in ("hive", "serum"):      # the same black cap, ring and white tick as the knobs; it turns a full revolution
        L = TH["knob_look"]
        d.ellipse((2.5 * SS, 2.5 * SS, s * SS - 2.5 * SS, s * SS - 2.5 * SS), fill=L["ring"])
        d.ellipse((5 * SS, 5 * SS, s * SS - 5 * SS, s * SS - 5 * SS), fill=L["cap_o"])
        d.ellipse((8 * SS, 8 * SS, s * SS - 8 * SS, s * SS - 8 * SS), fill=L["cap_i"])
        d.line((r, 11 * SS, r, 26 * SS), fill=L["tick"], width=int(3.6 * SS))
        return img
    d.ellipse((0, 0, s * SS - 1, s * SS - 1), fill=(0x16, 0x16, 0x16))
    d.ellipse((3 * SS, 3 * SS, s * SS - 3 * SS, s * SS - 3 * SS), fill=(0x3a, 0x3a, 0x3a))
    d.ellipse((8 * SS, 8 * SS, s * SS - 8 * SS, s * SS - 8 * SS), fill=(0x24, 0x24, 0x24))
    for i in range(24):                       # the ribs on the rim
        a = i * 2 * math.pi / 24
        x0, y0 = r + (r - 8 * SS) * math.sin(a), r - (r - 8 * SS) * math.cos(a)
        x1, y1 = r + (r - 3.5 * SS) * math.sin(a), r - (r - 3.5 * SS) * math.cos(a)
        d.line((x0, y0, x1, y1), fill=(0x18, 0x18, 0x18), width=int(1.6 * SS))
    d.ellipse((14 * SS, 14 * SS, s * SS - 14 * SS, s * SS - 14 * SS), fill=(0x2c, 0x2c, 0x2c), outline=(0x1a, 0x1a, 0x1a), width=SS)
    m = 4 * SS
    d.ellipse((r - m, 16 * SS, r + m, 16 * SS + 2 * m), fill=ORANGE)   # the marker, at 12 o'clock in frame 0
    return img


def wheel_frames(page_img, c):
    """a data wheel turns one full revolution over its list (128 frames); its text says where it is"""
    s = c["s"]
    box = (c["cx"] - s / 2, c["cy"] - s / 2, s, s)
    base = crop(page_img, box)
    disc = wheel_image(s)
    frames = []
    for i in range(128):
        cell = base.copy()
        paste(cell, disc.rotate(-i * 360.0 / 128, resample=Image.BICUBIC), 0, 0)
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
    if TH["bevel"] and tuple(fill) == tuple(BTN_ON):
        gold_fill(img, (0, 0, w * SS, h * SS), radius * SS)
        d = ImageDraw.Draw(img)
    if TH["bevel"]:               # a lit top edge, a darker foot and a faint sheen (the Serum look)
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(lay)
        for y in range(h * SS // 2):
            ld.line((SS, y, w * SS - SS, y), fill=(255, 255, 255, int(20 * (1 - y / (h * SS / 2)))))
        ld.rounded_rectangle((0, 0, w * SS - 1, h * SS - 1), radius=radius * SS, outline=(255, 255, 255, 46), width=SS)
        ld.line((radius * SS, h * SS - SS, w * SS - radius * SS, h * SS - SS), fill=(0, 0, 0, 170), width=SS)
        lay2 = Image.new("RGBA", img.size, (0, 0, 0, 0))
        m = Image.new("L", img.size, 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, w * SS - 1, h * SS - 1), radius=radius * SS, fill=255)
        lay2.paste(lay, (0, 0), m)
        img.alpha_composite(lay2)
        d = ImageDraw.Draw(img)
    lines = s.split("\n")
    lh = fs * 1.15
    for i, ln in enumerate(lines):
        y = h / 2 + (i - (len(lines) - 1) / 2) * lh
        d.text((w / 2 * SS, y * SS), ln, font=font(fs * SS), fill=ink, anchor="mm")
    return down(img, w, h)


STYLES = {"dark": (SEG_OFF, BTN_OFF_INK, (0x3a, 0x3a, 0x3a), INK), "orange": (BTN_ON, BTN_ON_INK, (255, 196, 120), BTN_ON_INK),
          "red": ((210, 58, 42), (255, 255, 255), (240, 96, 80), (255, 255, 255))}
if TH["bevel"]:                    # no flat red on a Serum page: the panic key is a dark key with gold lettering
    STYLES["red"] = (SEG_OFF, TH["gold_hi"], BTN_ON, BTN_ON_INK)


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
def depth(page, t):
    """the Serum look's depth: a faint light sheen falling from the top of every panel, a lit inner edge and a dark one,
    and a shadow inside the top of every screen (all low-alpha, over the flat colours)"""
    lay = Image.new("RGBA", page.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for item in panel.ART[t]:
        if item[0] == "frame":
            _, x, y, w, h, _title = item
            x0, y0, x1, y1 = (x + 2) * SS, (y + 2) * SS, (x + w - 2) * SS, (y + h - 2) * SS
            span = int(min(h * SS, 160 * SS))
            for i in range(span):
                d.line((x0, y0 + i, x1, y0 + i), fill=(255, 255, 255, int(11 * (1 - i / span) ** 1.5)))
            d.line((x0 + SS, y0 + SS, x1 - SS, y0 + SS), fill=(255, 255, 255, 34), width=SS)
            d.line((x0 + SS, y0 + SS, x0 + SS, y1 - SS), fill=(255, 255, 255, 18), width=SS)
            d.line((x0 + SS, y1 - SS, x1 - SS, y1 - SS), fill=(0, 0, 0, 120), width=SS)
            d.line((x1 - SS, y0 + SS, x1 - SS, y1 - SS), fill=(0, 0, 0, 90), width=SS)
        elif item[0] == "lcd":
            _, x, y, w, h = item
            for i in range(14 * SS):
                d.line(((x + 2) * SS, (y + 2) * SS + i, (x + w - 2) * SS, (y + 2) * SS + i),
                       fill=(0, 0, 0, int(120 * (1 - i / (14 * SS)) ** 1.6)))
            d.line(((x + 4) * SS, (y + h - 1) * SS, (x + w - 4) * SS, (y + h - 1) * SS), fill=(255, 255, 255, 26), width=SS)
    page.alpha_composite(lay)


def build_page(sk, t):
    cs = panel.controls(t)
    page = Image.new("RGBA", (panel.W * SS, panel.H * SS), BG + (255,))
    d = ImageDraw.Draw(page)
    for item in panel.ART[t]:
        if item[0] in ("frame", "lcd", "line"):
            draw_art(d, item)
    if TH["bevel"]:
        depth(page, t)
        d = ImageDraw.Draw(page)
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
                      fill=TH["screen_ink"])
    for item in panel.ART[t]:
        if item[0] in ("header", "text"):
            draw_art(d, item)
    # static names under sliders and knobs
    for c in cs:
        if c["kind"] == "slider" and c.get("label"):
            bw, bh, _, _, _ = slider_geom(c)
            text_at(d, c["x"] - 30, c["y"] + bh + 6, bw + 60, c["label"], c["fs"], INK)
        elif c["kind"] in ("knob", "wheel") and c.get("label"):
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
            if o is c or o["kind"] not in ("slider", "knob", "wheel") or not o.get("value", True):
                continue
            if abs(row_y(o) - row_y(c)) < 40:
                best = min(best, abs(centre_x(o) - cx))
        return best - 4

    def value_rect(c, box):
        """where the value text goes (page px), or None"""
        if not c.get("value", True):
            return None
        if c.get("vrect"):
            return c["vrect"]
        x, y, w, h = box
        vh = c.get("value_size", VALUE_SIZE) + 6
        if c["kind"] == "slider":
            vw = min(c.get("vw", w + 50), room(c))
            ly = y + h + (6 + c["fs"] + 4 if c.get("label") or c.get("labels_by") else 6)
            return (x + w / 2 - vw / 2, ly + c.get("value_dy", 0), vw, vh)
        if c["kind"] in ("knob", "wheel"):
            vw = min(c.get("vw", w + 30), room(c))
            ly = y + h + (4 + c["fs"] + 4 if c.get("label") or c.get("labels_by") else 2)
            return (x + w / 2 - vw / 2, ly + c.get("value_dy", 0), vw, vh)
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
            colour = screen_hex(c.get("value_colour", VALUE_COLOUR))
            comps.append(label_comp("Value", vr[0] - ox0, vr[1] - oy0, vr[2], vr[3], colour, c.get("value_size", VALUE_SIZE)))
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
            place_film(c, box, frames, len(frames) - 1, value_rect(c, box))
        elif k == "wheel":
            box, frames = wheel_frames(page, c)
            place_film(c, box, frames, len(frames) - 1, value_rect(c, box))
        elif k == "tbtn":
            fill, ink, fill_on, ink_on = STYLES["dark"][0], STYLES["dark"][1], BTN_ON, BTN_ON_INK
            off = button_image(c["w"], c["h"], c["text"], c["fs"], fill, ink)
            on = button_image(c["w"], c["h"], c["text"], c["fs"], fill_on, ink_on)
            placed[c["key"]] = ("switch", (sk.save(off, "sx_%d_%s_off.png" % (t, c["key"])),
                                           sk.save(on, "sx_%d_%s_on.png" % (t, c["key"]))), (c["x"], c["y"], c["w"], c["h"]))
        elif k == "fader":
            box, frames = fader_frames(page, c)
            vr = None
            if c.get("lcd"):
                vr = c["lcd"]
                c["value_colour"], c["value_size"] = screen_hex("fffb9013"), 19
            place_film(c, box, frames, len(frames), vr)
        elif k in ("ckss", "lit"):
            box, (off, on) = ckss_images(page, c) if k == "ckss" else lit_images(page, c)
            placed[c["key"]] = ("switch", (sk.save(off, "sx_%d_%s_off.png" % (t, c["key"])),
                                           sk.save(on, "sx_%d_%s_on.png" % (t, c["key"]))), box)
        elif k == "seg":
            imgs = []
            for r, s in zip(c["rects"], c["texts"]):
                imgs.append((button_image(r[2], r[3], s, c["fs"], SEG_OFF, BTN_OFF_INK),
                             button_image(r[2], r[3], s, c["fs"], BTN_ON, BTN_ON_INK)))
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
                cx, ly, maxw = c["x"] + bw / 2, c["y"] + bh + 6, 88
            else:
                cx, ly, maxw = c["cx"], c["cy"] + c["s"] / 2 + 4, 120
            rows.setdefault(ly, []).append((i, cx, maxw))
        n = len(names)
        pidx = sk.index[by]
        for o in range(n):
            for ly, items in rows.items():
                xs = [cx for _, cx, _ in items]
                rect = (min(xs) - 64, ly, max(xs) - min(xs) + 128, 26)
                img = label_strip(page, rect, [(cx, names[o][i] if i < len(names[o]) else "", maxw)
                                               for i, cx, maxw in items], STRIP_SIZE)
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
                col = screen_hex(c["colour"].lower())
                if TH["bg_text"] and col in TH["bg_text"]:      # a light theme: lettering on the page (not on a dark display)
                    cx_, cy_ = c["x"] + c["w"] / 2, c["y"] + c["h"] / 2
                    over_lcd = any(i[0] == "lcd" and i[1] <= cx_ <= i[1] + i[3] and i[2] <= cy_ <= i[2] + i[4]
                                   for i in panel.ART[t])
                    if not over_lcd:
                        col = TH["bg_text"][col]
                ts["colour"] = "ff" + col
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
            data["offImage"] = sk.save(button_image(w, h, label, 20, SEG_OFF, BTN_OFF_INK),
                                       "sx_po_%s_%s_%s_off.png" % (tab, pkey, i))
            data["onImage"] = sk.save(button_image(w, h, label, 20, BTN_ON, BTN_ON_INK),
                                      "sx_po_%s_%s_%s_on.png" % (tab, pkey, i))
            n += 1
        elif key.startswith("shPopPanel_"):
            img = find_sub(d, "Image")
            w, h = [int(v) for v in img["bounds"]["bounds"].split()[2:]]
            pnl = Image.new("RGB", (w, h), (0x24, 0x24, 0x24))
            ImageDraw.Draw(pnl).rectangle((0, 0, w - 1, h - 1), outline=TH["pop_rim"], width=2)
            img["componentData"]["data"]["image"] = sk.save(pnl, "sx_pp_%s.png" % key[len("shPopPanel_"):])
        elif key.startswith("shPopField_"):
            lab = find_sub(d, "Label")
            if lab:
                ts = lab["componentData"]["data"]["textStyle"]
                ts["colour"], ts["font"]["height"] = screen_hex("fffb9013"), 26.0
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
