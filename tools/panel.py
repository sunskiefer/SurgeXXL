#!/usr/bin/env python3
"""SurgeXXL's pages: where every control sits on MPC's plugin screen (1280 x 628), and how it looks.

    python3 tools/panel.py --write     (writes layout.conf from this file and qlinks.json)
    python3 tools/panel.py --check     (fails when layout.conf is stale)

The look is InterzoneXXL's (Valley's sliders and Rogan knobs, VCV's switches, white section frames with their titles in
a white tab, Titillium Web lettering on #282828), with LXRXXL BAZZLINE's mixer faders and lit keys, as in the page
mockups. layout.conf only carries the tabs, one framework widget per control (so mpc-vst-plugins builds the skin's
skeleton: tabs, Q-Links, popups, readouts) and the Q-Links; tools/panel_art.py then draws every page and control from
the descriptions here. Coordinates are page pixels (x 0..1280, y 0..628); layout.conf's are Force Shadow pixels
(y + 86).

Q-Links come from qlinks.json, the file the SurgeXXL Q-Link Map saves (format "qlink-map 1", as BAZZLINE's): per page,
knob n = Q-Link page (n-1)//8 + 1, knob (n-1)%8 + 1. A page missing from it gets the default order (DEFAULT_QLINKS).
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Y0 = 86
W, H = 1280, 628
BG = (0x28, 0x28, 0x28)
QLINK_FILE = os.path.join(ROOT, "qlinks.json")

TABS = ["OSC", "MIXER", "FILTER", "ENV / LFO", "STEP SEQ", "MOD", "FX", "PATCH"]
PAGE_IDS = ["osc", "mixer", "filter", "envlfo", "stepseq", "mod", "fx", "patch"]

PARAMS = json.load(open(os.path.join(ROOT, "params.json")))["params"]
P = {p["key"]: p for p in PARAMS}
FACTS = json.load(open(os.path.join(ROOT, "tools", "surge_facts.json")))


def options(key):
    return P[key]["options"]


# ---------------------------------------------------------------------------------------------------- control helpers
# Every control: {"tab", "kind", "key", ...geometry...}. Kinds:
#   slider  Valley slider: x, y (top-left of its background), k (Valley px -> page px), handle colour, label (or
#           labels_by: a per-option label strip drawn by panel_art, see LABEL_STRIPS), value text under it
#   knob    Valley's orange Rogan knob: cx, cy, s (diameter), label; detents=True for an option list (one frame each)
#   ckss    VCV's CKSS switch (an Off/On option): x, y, k
#   fader   BAZZLINE's mixer fader: x, y, s (scale of its 40 x 182 px box)
#   lit     BAZZLINE's lit key (an Off/On option): x, y, size
#   seg     option buttons: rects [(x, y, w, h)] one per option, texts, font size
#   button  a trigger: x, y, w, h, text, style (dark / orange / red)
#   popup   a field that opens the option list (mpc-vst-plugins popup): x, y, w, h
#   readout live text: x, y, w, h, size, colour, align
C = []


def add(tab, kind, key, **kw):
    d = {"tab": tab, "kind": kind, "key": key}
    d.update(kw)
    assert key in P, key
    C.append(d)
    return d


def slider(tab, key, x, y, k, label="", colour="orange", fs=17, value=True, **kw):
    return add(tab, "slider", key, x=x, y=y, k=k, label=label, colour=colour, fs=fs, value=value, **kw)


def knob(tab, key, cx, cy, s, label="", fs=17, detents=False, value=True, **kw):
    return add(tab, "knob", key, cx=cx, cy=cy, s=s, label=label, fs=fs, detents=detents, value=value, **kw)


def seg(tab, key, rects, texts=None, fs=15):
    texts = texts or options(key)
    assert len(rects) == len(options(key)) == len(texts), key
    return add(tab, "seg", key, rects=rects, texts=texts, fs=fs)


def grid(x, y, w, h, cols, n, gx=6, gy=6):
    return [(x + (i % cols) * (w + gx), y + (i // cols) * (h + gy), w, h) for i in range(n)]


def button(tab, key, x, y, w, h, text, style="dark", fs=16):
    return add(tab, "button", key, x=x, y=y, w=w, h=h, text=text, style=style, fs=fs)


def readout(tab, key, x, y, w, h, size=20, colour="fb9013", align="left"):
    return add(tab, "readout", key, x=x, y=y, w=w, h=h, size=size, colour=colour, align=align)


def popup(tab, key, x, y, w, h):
    return add(tab, "popup", key, x=x, y=y, w=w, h=h)


# Baked (static) artwork: frames with a title tab, sub-headers, text, LCD windows, lines.
ART = {t: [] for t in range(len(TABS))}


def frame(tab, x, y, w, h, title):
    ART[tab].append(("frame", x, y, w, h, title))


def header(tab, x, y, w, text):
    ART[tab].append(("header", x, y, w, text))


def text(tab, x, y, w, s, size=16, colour=(255, 255, 255), align="center"):
    ART[tab].append(("text", x, y, w, s, size, colour, align))


def lcd(tab, x, y, w, h):
    ART[tab].append(("lcd", x, y, w, h))


def line(tab, x, y, w, h, colour=(0x3e, 0x3e, 0x3e)):
    ART[tab].append(("line", x, y, w, h, colour))


# ------------------------------------------------------------------------------------------------------ sizes (0.3.0)
# One size system, so every page reads the same on the 7" screen: FS for names, values and buttons, FS_S the smallest
# lettering anywhere (never below 18), FS_L for the big readouts. Knobs are at most KNOB px across (a 128-frame strip of
# 96 px frames is the largest MPC animates right, docs/NOTES.md), and the lists (wavetable, patch, routing) are data
# wheels of that size.
FS, FS_S, FS_L = 20, 18, 26
KNOB, KNOB_S, WHEEL = 96, 76, 96
SL = 2.6              # Valley slider scale: 59 x 227 px


def wheel(tab, key, cx, cy, label="", **kw):
    """a data wheel (a long list stepped one entry per click): a ribbed grey wheel, no value arc"""
    kw.setdefault("value", False)
    return add(tab, "wheel", key, cx=cx, cy=cy, s=WHEEL, label=label, fs=FS, **kw)


def tbtn(tab, key, x, y, w, h, text, fs=FS):
    """an Off/On option as one button with its name inside (dark off, orange on)"""
    return add(tab, "tbtn", key, x=x, y=y, w=w, h=h, text=text, fs=fs)


# ---------------------------------------------------------------------------------------------------------- 0 OSC
T = 0
frame(T, 12, 26, 1256, 590, "OSCILLATORS")
line(T, 268, 52, 2, 540)
line(T, 946, 52, 2, 540)
header(T, 36, 50, 210, "OSC")
seg(T, "osc_sel", grid(36, 86, 66, 50, 3, 3), fs=26)
header(T, 36, 150, 210, "TYPE")
seg(T, "osc_type", grid(36, 186, 102, 38, 2, 12), fs=FS)
tbtn(T, "osc_keytrack", 36, 474, 102, 48, "KEY\nTRACK", fs=FS_S)
tbtn(T, "osc_retrig", 144, 474, 102, 48, "RETRIG", fs=FS_S)
# the wavetable: name and folder, its picture (wider), browsing
lcd(T, 292, 52, 636, 140)
readout(T, "wt_name", 304, 58, 300, 44, size=30)
readout(T, "wt_folder", 304, 108, 300, 28, size=FS, colour="c97a1c")
add(T, "picture", "wt_pic", x=612, y=58, w=308, h=128)
button(T, "wt_prev", 292, 202, 58, 44, "<", fs=24)
button(T, "wt_next", 356, 202, 58, 44, ">", fs=24)
button(T, "wt_cat_prev", 420, 202, 130, 44, "< FOLDER", fs=FS)
button(T, "wt_cat_next", 556, 202, 130, 44, "FOLDER >", fs=FS)
button(T, "wt_rescan", 692, 202, 120, 44, "RESCAN", fs=FS)
wheel(T, "wt", 880, 230)
text(T, 820, 282, 120, "TABLE", FS_S, (0xcf, 0xcf, 0xcf))
# the type's seven parameters (their names per type: LABEL_STRIPS)
for i in range(7):
    slider(T, "osc_p%d" % (i + 1), 300 + i * 90, 300, SL, labels_by="osc_type", fs=FS)
knob(T, "osc_pitch", 1107, 150, KNOB, "PITCH", fs=FS)
header(T, 955, 292, 304, "OCTAVE")
seg(T, "osc_octave", grid(955, 328, 40, 44, 7, 7, gx=4), fs=FS)

# ---------------------------------------------------------------------------------------------------------- 1 MIXER
T = 1
frame(T, 12, 26, 896, 590, "MIXER")
frame(T, 924, 26, 344, 590, "SCENE")
CH = [("o1", "OSC 1"), ("o2", "OSC 2"), ("o3", "OSC 3"), ("r12", "RING 1x2"), ("r23", "RING 2x3"), ("noise", "NOISE"),
      ("pfg", "PRE-FILTER")]
for i, (k, name) in enumerate(CH):
    x0 = 30 + i * 124
    if i:
        line(T, x0 - 7, 52, 2, 546, (0x3a, 0x3a, 0x3a))
    text(T, x0, 50, 112, name, FS)
    slider(T, "mix_%s" % k, x0 + 25, 80, 2.75, "", fs=FS, value=True, vw=110)   # Valley's slider, as every page
    if k == "pfg":
        text(T, x0, 364, 112, "GAIN", FS_S, (0xcf, 0xcf, 0xcf))
        continue
    tbtn(T, "solo_%s" % k, x0 + 6, 362, 100, 44, "SOLO")
    tbtn(T, "mute_%s" % k, x0 + 6, 412, 100, 44, "MUTE")
    text(T, x0, 466, 112, "ROUTE", FS_S, (0xcf, 0xcf, 0xcf))
    seg(T, "route_%s" % k, [(x0, 490, 112, 36), (x0, 528, 112, 36), (x0, 566, 112, 36)], ["FILTER 1", "BOTH", "FILTER 2"], fs=FS_S)
header(T, 944, 50, 304, "FM ROUTING")
seg(T, "fm_routing", grid(944, 86, 150, 40, 2, 4), fs=FS)
for i, (k, lab) in enumerate((("fm_depth", "FM Depth"), ("noise_color", "Noise Color"), ("osc_drift", "Osc Drift"))):
    knob(T, k, 990 + i * 106, 226, KNOB_S, lab, fs=FS_S)
header(T, 944, 318, 304, "OUTPUT")
slider(T, "sc_volume", 968, 350, 2.4, "VOLUME", fs=FS, vw=120)
knob(T, "sc_pan", 1160, 400, KNOB_S, "Pan", fs=FS)
knob(T, "sc_width", 1160, 520, KNOB_S, "Width", fs=FS)

# ---------------------------------------------------------------------------------------------------------- 2 FILTER
T = 2
frame(T, 12, 26, 860, 116, "CONFIG")
frame(T, 888, 26, 380, 116, "WAVESHAPER")
frame(T, 12, 176, 470, 440, "FILTER 1")
frame(T, 498, 176, 284, 440, "BLOCK")
frame(T, 798, 176, 470, 440, "FILTER 2")
seg(T, "fb_config", grid(30, 62, 98, 56, 8, 8), fs=FS)
popup(T, "ws_type", 906, 62, 230, 52)
knob(T, "ws_drive", 1200, 82, 70, "", value=False)
text(T, 1150, 118, 100, "DRIVE", FS_S, (0xcf, 0xcf, 0xcf))
for n, x0 in ((1, 12), (2, 798)):
    popup(T, "f%d_type" % n, x0 + 18, 198, 290, 50)
    text(T, x0 + 330, 184, 120, "SUBTYPE", FS_S, (0xcf, 0xcf, 0xcf))
    knob(T, "f%d_subtype" % n, x0 + 412, 230, 64, "", value=True, vw=140)
    for i, (k, lab) in enumerate((("cutoff", "Cutoff"), ("res", "Resonance"), ("env", "FEG Amt"), ("ktrk", "Keytrack"))):
        slider(T, "f%d_%s" % (n, k), x0 + 34 + i * 108, 290, SL, lab, fs=FS)
tbtn(T, "f2_linkres", 818, 568, 190, 42, "LINK RESONANCE", fs=FS_S)
tbtn(T, "f2_offset", 1030, 568, 220, 42, "FILTER 2 OFFSET", fs=FS_S)
for i, (k, lab) in enumerate((("feedback", "Feedback"), ("f_balance", "Balance"), ("highpass", "Highpass"))):
    slider(T, k, 514 + i * 88, 290, SL, lab, colour="yellow", fs=FS)

# ---------------------------------------------------------------------------------------------------------- 3 ENV / LFO
T = 3
frame(T, 12, 26, 616, 590, "ENVELOPES")
frame(T, 644, 26, 624, 590, "LFO")
for gi, (pre, title, col) in enumerate((("aeg", "AMP EG", "red"), ("feg", "FILTER EG", "yellow"))):
    x0 = 30 + gi * 298
    header(T, x0, 50, 284, title)
    for i, k in enumerate("adsr"):
        slider(T, "%s_%s" % (pre, k), x0 + 4 + i * 72, 92, SL, k.upper(), colour=col, fs=22)
    seg(T, "%s_mode" % pre, [(x0 + 6, 384, 134, 40), (x0 + 144, 384, 134, 40)], ["DIGITAL", "ANALOG"], fs=FS)
    for i, (k, lab) in enumerate((("ash", "ATK SHAPE"), ("dsh", "DEC SHAPE"), ("rsh", "REL SHAPE"))):
        text(T, x0 + i * 96, 436, 92, lab, FS_S, (0xcf, 0xcf, 0xcf))
        knob(T, "%s_%s" % (pre, k), x0 + 46 + i * 96, 494, 64, "", detents=True, value=True, vw=94)
seg(T, "lfo_sel", grid(660, 52, 94, 44, 6, 6, gx=5), fs=FS)
seg(T, "lfo_shape", grid(660, 104, 113, 38, 5, 10), fs=FS_S)
for i, (k, lab) in enumerate((("lfo_rate", "Rate"), ("lfo_phase", "Phase"), ("lfo_amp", "Amplitude"),
                              ("lfo_deform", "Deform"))):
    knob(T, k, 712 + i * 144, 240, KNOB_S, lab, fs=FS)
text(T, 660, 346, 90, "TRIGGER", FS_S, (0xcf, 0xcf, 0xcf), align="left")
seg(T, "lfo_trig", [(746, 336, 110, 40), (860, 336, 124, 40), (988, 336, 104, 40)], fs=FS_S)
tbtn(T, "lfo_uni", 1110, 336, 140, 40, "UNIPOLAR", fs=FS_S)
header(T, 660, 392, 590, "LFO EG")
for i, k in enumerate(("delay", "attack", "hold", "decay", "sustain", "release")):
    slider(T, "lfo_%s" % k, 672 + i * 98, 426, 1.5, k.capitalize(), fs=FS_S)

# ---------------------------------------------------------------------------------------------------------- 4 STEP SEQ
T = 4
frame(T, 12, 26, 1256, 590, "STEP SEQUENCER")
readout(T, "seq_info", 30, 54, 610, 36, size=FS, colour="cfcfcf")
seg(T, "lfo_sel", grid(650, 50, 94, 44, 6, 6, gx=5), fs=FS)
for i in range(16):
    slider(T, "seq_%d" % (i + 1), 34 + i * 76, 108, 3.2, str(i + 1), colour="orange", fs=FS, bipolar=True)
button(T, "seq_on", 34, 500, 230, 56, "STEP SEQ ON", style="orange", fs=22)
button(T, "mod_learn", 280, 500, 170, 56, "ROUTE", style="dark", fs=22)
text(T, 466, 500, 230, "ROUTE, then touch the", FS_S, (0xcf, 0xcf, 0xcf), align="left")
text(T, 466, 524, 230, "control the steps should move", FS_S, (0xcf, 0xcf, 0xcf), align="left")
knob(T, "seq_start", 800, 520, KNOB_S, "LOOP START", fs=FS)
knob(T, "seq_end", 1000, 520, KNOB_S, "LOOP END", fs=FS)

# ---------------------------------------------------------------------------------------------------------- 5 MOD
T = 5
frame(T, 12, 26, 1256, 590, "MODULATION")
header(T, 30, 50, 240, "SCENE")
seg(T, "scene", [(30, 86, 110, 44), (146, 86, 110, 44)], fs=22)
header(T, 300, 50, 400, "ROUTING")
wheel(T, "mod_slot", 350, 128, value=True, vrect=(410, 106, 300, 40), value_size=FS_L, value_colour="fffb9013")
text(T, 410, 148, 300, "Turn: next routing; past the last: NEW", FS_S, (0xcf, 0xcf, 0xcf), align="left")
header(T, 30, 184, 1220, "SOURCE")
popup(T, "mod_src", 30, 220, 300, 50)
header(T, 30, 296, 1220, "TARGET")
lcd(T, 30, 332, 900, 70)
readout(T, "mod_target", 44, 340, 870, 54, size=28)
button(T, "mod_learn", 950, 332, 150, 70, "LEARN", style="orange", fs=24)
button(T, "mod_clear", 1110, 332, 140, 70, "CLEAR", style="red", fs=22)
readout(T, "mod_info", 30, 408, 900, 30, size=FS, colour="cfcfcf")
header(T, 30, 448, 1220, "DEPTH")
knob(T, "mod_depth", 120, 536, KNOB, "", value=True, vw=140)
text(T, 220, 506, 1000, "LEARN, then touch or turn a control on any page: it becomes the target of the routing "
     "shown", FS_S, (0xcf, 0xcf, 0xcf), align="left")
text(T, 220, 530, 1000, "(or of a NEW one from the source above).", FS_S, (0xcf, 0xcf, 0xcf), align="left")

# ---------------------------------------------------------------------------------------------------------- 6 FX
T = 6
frame(T, 12, 26, 452, 590, "FX SLOTS")
frame(T, 480, 26, 788, 590, "EFFECT")
for r, name in enumerate(("A INSERT", "B INSERT", "SEND", "GLOBAL")):
    text(T, 26, 72 + r * 86, 92, name, FS_S, (0xcf, 0xcf, 0xcf), align="left")
seg(T, "fx_sel", grid(120, 52, 78, 64, 4, 16, gx=6, gy=22), fs=22)
header(T, 28, 392, 420, "SENDS (SCENE)")
for i in range(4):
    knob(T, "send_%d" % (i + 1), 80 + i * 104, 450, 56, "Send %d" % (i + 1), fs=FS_S, value=False)
header(T, 28, 506, 420, "RETURNS")
for i in range(4):
    knob(T, "ret_%d" % (i + 1), 80 + i * 104, 562, 56, "Return %d" % (i + 1), fs=FS_S, value=False)
popup(T, "fx_type", 500, 54, 320, 58)
tbtn(T, "fx_on", 960, 61, 110, 44, "ON")
for i in range(12):
    knob(T, "fx_p%d" % (i + 1), 560 + (i % 6) * 128, 196 + (i // 6) * 190, 80, "", labels_by="fx_type", value=True)
text(T, 500, 538, 200, "FX CHAIN", FS_S, (0xcf, 0xcf, 0xcf), align="left")
seg(T, "fx_bypass", grid(500, 562, 180, 40, 4, 4, gx=6), fs=FS_S)

# ---------------------------------------------------------------------------------------------------------- 7 PATCH
T = 7
frame(T, 12, 26, 760, 590, "PATCH")
frame(T, 788, 26, 480, 590, "VOICE")
lcd(T, 30, 54, 724, 100)
readout(T, "patch_browse", 44, 58, 696, 56, size=40)
readout(T, "patch_cat", 44, 114, 696, 34, size=22, colour="c97a1c")
button(T, "patch_prev", 30, 170, 70, 56, "<", fs=28)
button(T, "patch_next", 106, 170, 70, 56, ">", fs=28)
button(T, "cat_prev", 182, 170, 112, 56, "< CAT", fs=FS_S)
button(T, "cat_next", 300, 170, 112, 56, "CAT >", fs=FS_S)
wheel(T, "patch", 470, 198)
button(T, "patch_load", 536, 170, 104, 56, "LOAD", style="orange", fs=22)
button(T, "patch_save", 646, 170, 104, 56, "SAVE", fs=22)
text(T, 30, 256, 120, "LOADED", FS_S, (0xcf, 0xcf, 0xcf), align="left")
readout(T, "patch_name", 116, 250, 636, 34, size=FS_L, colour="ffffff")
header(T, 30, 296, 724, "MACROS")
for i in range(8):
    cx = 74 + i * 90
    knob(T, "macro_%d" % (i + 1), cx, 364, 72, "", value=True, vw=88)
    readout(T, "macro_%d_name" % (i + 1), cx - 44, 432, 88, 26, size=FS_S, colour="ffffff", align="center")
header(T, 806, 50, 120, "SCENE")
seg(T, "scene", [(806, 86, 60, 44), (872, 86, 60, 44)], fs=22)
header(T, 960, 50, 290, "SCENE MODE")
seg(T, "scene_mode", grid(960, 86, 142, 40, 2, 4), ["Single", "Key Split", "Dual", "Ch. Split"], fs=FS_S)
header(T, 806, 176, 444, "PLAY MODE")
seg(T, "play_mode", grid(806, 212, 143, 40, 3, 6), fs=FS_S)
for i, (k, lab) in enumerate((("poly_limit", "Poly Limit"), ("portamento", "Portamento"), ("bend_up", "Bend Up"))):
    knob(T, k, 872 + i * 156, 350, 72, lab, fs=FS_S)
for i, (k, lab) in enumerate((("volume", "Volume"), ("bend_dn", "Bend Down"), ("split_key", "Split Point"))):
    knob(T, k, 872 + i * 156, 472, 72, lab, fs=FS_S)
button(T, "panic", 1010, 572, 220, 40, "PANIC", style="red", fs=22)

# ---------------------------------------------------------------------------------------------------------- Q-Links
# The first order of each page's knobs (8 per Q-Link page); qlinks.json (the Q-Link Map) replaces it. "-": empty knob.
DEFAULT_QLINKS = {
    "osc": ["osc_p1", "osc_p2", "osc_p3", "osc_p4", "osc_p5", "osc_p6", "osc_p7", "osc_pitch",
            "wt", "osc_octave", "osc_type", "osc_sel", "osc_keytrack", "osc_retrig"],
    "mixer": ["mix_o1", "mix_o2", "mix_o3", "mix_noise", "mix_r12", "mix_r23", "mix_pfg", "sc_volume",
              "fm_depth", "noise_color", "osc_drift", "sc_pan", "sc_width", "fm_routing", "route_o1", "route_o2",
              "mute_o1", "mute_o2", "mute_o3", "mute_noise", "solo_o1", "solo_o2", "solo_o3", "solo_noise"],
    "filter": ["f1_cutoff", "f1_res", "f1_env", "f1_ktrk", "f2_cutoff", "f2_res", "f2_env", "f2_ktrk",
               "feedback", "f_balance", "highpass", "ws_drive", "f1_type", "f2_type", "ws_type", "fb_config",
               "f1_subtype", "f2_subtype"],
    "envlfo": ["aeg_a", "aeg_d", "aeg_s", "aeg_r", "feg_a", "feg_d", "feg_s", "feg_r",
               "lfo_rate", "lfo_phase", "lfo_amp", "lfo_deform", "lfo_shape", "lfo_sel", "lfo_trig", "lfo_uni",
               "lfo_delay", "lfo_attack", "lfo_hold", "lfo_decay", "lfo_sustain", "lfo_release", "aeg_mode",
               "feg_mode"],
    "stepseq": ["seq_%d" % (i + 1) for i in range(16)] + ["seq_start", "seq_end", "lfo_sel"],
    "mod": ["mod_depth", "mod_slot", "mod_src", "scene"],
    "fx": ["fx_p1", "fx_p2", "fx_p3", "fx_p4", "fx_p5", "fx_p6", "fx_p7", "fx_p8",
           "fx_p9", "fx_p10", "fx_p11", "fx_p12", "fx_type", "fx_sel", "fx_on", "fx_bypass",
           "send_1", "send_2", "send_3", "send_4", "ret_1", "ret_2", "ret_3", "ret_4"],
    "patch": ["macro_%d" % (i + 1) for i in range(8)] + ["patch", "volume", "poly_limit", "portamento", "bend_up",
                                                         "bend_dn", "play_mode", "scene", "scene_mode", "split_key"],
}


def default_qlinks(tab):
    keys = DEFAULT_QLINKS[PAGE_IDS[tab]]
    have = set(c["key"] for c in controls(tab))
    for k in keys:
        assert k == "-" or k in have, "DEFAULT_QLINKS: %s is not on %s" % (k, TABS[tab])
    return list(keys)


def qlink_map_json():
    """qlinks.json as the Q-Link Map saves it (format "qlink-map 1"), from the present order of every page"""
    names = {}
    for c in C:
        names.setdefault(c["key"], P[c["key"]]["name"])
    out = {"plugin": "SurgeXXL", "format": "qlink-map 1", "pages": {}}
    for t, pid in enumerate(PAGE_IDS):
        order = qlink_order(t)
        out["pages"][pid] = {"name": TABS[t], "knobs": [
            {"n": i + 1, "qlinkPage": i // 8 + 1, "knob": i % 8 + 1, "key": None if k == "-" else k,
             "name": None if k == "-" else names[k]} for i, k in enumerate(order)]}
    return out


def controls(tab):
    return [c for c in C if c["tab"] == tab]


def qlink_order(tab):
    """the page's knob order (keys, "-" for an empty knob): qlinks.json, else the default"""
    allowed = set(c["key"] for c in controls(tab) if c["kind"] not in ("readout", "picture", "button"))

    if os.path.exists(QLINK_FILE):
        data = json.load(open(QLINK_FILE))
        pg = data.get("pages", {}).get(PAGE_IDS[tab])
        if pg:
            slots = []
            for k in sorted(pg["knobs"], key=lambda k: k["n"]):
                while len(slots) < k["n"] - 1:
                    slots.append("-")
                key = k.get("key") or "-"
                if key != "-" and key not in allowed:
                    raise SystemExit("qlinks.json: %s is not a control of %s" % (key, TABS[tab]))
                if key != "-" and key in slots:
                    raise SystemExit("qlinks.json: %s is on two knobs of %s" % (key, TABS[tab]))
                slots.append(key)
            while slots and slots[-1] == "-":
                slots.pop()
            return slots
    return default_qlinks(tab)


def qlink_pages(tab):
    """the page's Q-Link pages: 8 knobs each (the Force's eight Q-Link knobs), as BAZZLINE; "-" keeps a knob empty"""
    order = qlink_order(tab)
    pages = [order[i:i + 8] for i in range(0, len(order), 8)]
    return [p for p in pages if any(k != "-" for k in p)] or [[]]


def qlink_names(tab):
    n = len(qlink_pages(tab))
    return [TABS[tab] if n == 1 else "%s %d" % (TABS[tab], i + 1) for i in range(n)]


# ---------------------------------------------------------------------------------------------------------- layout.conf
def touch_box(c):
    """the control's touch area on the page (x, y, w, h)"""
    k = c["kind"]
    if k == "slider":
        bw, bh = 22.8 * c["k"], 87.5 * c["k"]
        return (int(c["x"]), int(c["y"]), int(bw), int(bh))
    if k in ("knob", "wheel"):
        s = c["s"]
        return (int(c["cx"] - s / 2), int(c["cy"] - s / 2), s, s)
    if k == "fader":
        return (c["x"], c["y"], int(40 * c["s"]), int(182 * c["s"]))
    if k == "ckss":
        return (c["x"], c["y"], int(14 * c["k"]), int(20.64 * c["k"]))
    if k == "lit":
        return (c["x"], c["y"], c["size"], c["size"])
    if k in ("button", "popup", "readout", "picture", "tbtn"):
        return (c["x"], c["y"], c["w"], c["h"])
    raise SystemExit("touch_box: %s" % k)


def layout_lines():
    L = ["# SurgeXXL -- page layout (mpc-vst-plugins layout.conf syntax: tools/shadow_skin.py, docs/SKIN_STUDIO.md).",
         "# GENERATED by tools/panel.py from its pages and qlinks.json: edit those, then run `python3 tools/panel.py --write`.",
         "# tools/panel_art.py then draws every page and control. Coordinates are Force Shadow pixels (y 86..714).",
         "scale_names=1", "label_scale=1.0",
         "theme_bg=282828", "theme_panel=282828", "theme_line=ffffff", "theme_ink=ffffff", "theme_ink_dim=cfcfcf",
         "theme_ink_faint=6a6a6a", "theme_accent=f29a2e", "theme_accent_hi=ffffff", "theme_knob_face=1c1c1c",
         "theme_knob_ring=f29a2e", "theme_knob_dot=ffffff", "theme_bar=282828", "theme_seg_active=f29a2e",
         "theme_seg_inactive=1c1c1c", "theme_seg_active_tx=111111", "theme_btn_text=ffffff", "theme_tab_on=ffffff",
         "theme_tab_on_tx=111111", "theme_lcd=1c1c1c", "theme_box=1c1c1c", ""]
    for t, name in enumerate(TABS):
        L.append("[tab %s]" % name)
        for c in controls(t):
            k = c["kind"]
            if k == "picture":
                continue
            if k == "seg":
                xs = [r[0] for r in c["rects"]]
                ys = [r[1] for r in c["rects"]]
                x0, y0 = min(xs), min(ys)
                x1 = max(r[0] + r[2] for r in c["rects"])
                y1 = max(r[1] + r[3] for r in c["rects"])
                L.append('enum_h cx=%d cy=%d w=%d h=%d label="" key=%s' % ((x0 + x1) // 2, (y0 + y1) // 2 + Y0,
                                                                         x1 - x0, y1 - y0, c["key"]))
                continue
            x, y, w, h = touch_box(c)
            cx, cy = x + w // 2, y + h // 2 + Y0
            if k == "slider" or k == "fader":
                L.append('slider_v cx=%d cy=%d w=%d h=%d label="" key=%s ns=0 bw=%d' % (cx, cy, w, h, c["key"], w))
            elif k in ("knob", "wheel"):
                L.append('knob cx=%d cy=%d r=%d label="" key=%s ns=0 bw=%d' % (cx, cy, max(8, w // 2), c["key"], w))
            elif k in ("ckss", "lit", "tbtn"):
                L.append('toggle cx=%d cy=%d label="" key=%s ns=0 bw=%d' % (cx, cy, c["key"], w))
            elif k == "button":
                L.append('button cx=%d cy=%d label="%s" key=%s' % (cx, cy, c["text"], c["key"]))
            elif k == "popup":
                L.append('popup cx=%d cy=%d w=%d h=%d key=%s' % (cx, cy, w, h, c["key"]))
            elif k == "readout":
                L.append('readout cx=%d cy=%d w=%d h=%d key=%s' % (cx, cy, w, h, c["key"]))
        for name_, keys in zip(qlink_names(t), qlink_pages(t)):
            L.append('qlinks "%s" = %s' % (name_, ",".join(keys)))
        L.append("")
    return L


def main():
    if "--qlinks-json" in sys.argv:       # write qlinks.json from the present order (first time, or to reset it)
        json.dump(qlink_map_json(), open(QLINK_FILE, "w"), indent=1)
        print("panel: qlinks.json written")
        return
    out = "\n".join(layout_lines()) + "\n"
    path = os.path.join(ROOT, "layout.conf")
    if "--check" in sys.argv:
        if not os.path.exists(path) or open(path).read() != out:
            raise SystemExit("layout.conf is stale: run python3 tools/panel.py --write")
        return
    open(path, "w").write(out)
    print("panel: %d controls on %d pages -> layout.conf" % (len(C), len(TABS)))


if __name__ == "__main__":
    main()
