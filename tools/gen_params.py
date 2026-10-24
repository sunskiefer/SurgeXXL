#!/usr/bin/env python3
"""The single source of SurgeXXL's parameter list: writes params.json (for mpc-vst-plugins' gen_vst.py),
src/param_table.inc (how the engine binds each key to Surge) and src/param_ids.h (P_<KEY> index constants).

    python3 tools/gen_params.py

MPC stores automation and saved values by parameter INDEX, so this list is append-only: never reorder, rename a key or
remove a parameter that has shipped, and never change the number of options of a shipped option list.

Most controls are Surge's own parameters for what the pages are showing: the edited scene (A/B, Surge's own "Active
Scene"), the selected oscillator, LFO and FX slot. Their option lists and labels come from Surge itself
(tools/surge_facts.json, dumped from the vendored engine by test/dump_facts.cpp), so a value means here what it means
in Surge XT. Binding patterns (src/engine.cpp, resolve()):
    %s  the edited scene's letter (a/b)      %o  the selected oscillator (1-3)
    %l  the selected LFO's Surge index (0-2 voice LFOs 1-3, 6-8 scene LFOs 1-3)
    %x  the selected FX slot's Surge storage number (fx1..fx16, in Surge's slot order)
"""
import json
import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
FACTS = json.load(open(os.path.join(ROOT, "tools", "surge_facts.json")))
SURGE = {p["storage"]: p for p in FACTS["scene"] + FACTS["global"] if "storage" in p}

# FX types SurgeXXL leaves out: Spring Reverb (Surge's own CMake flags it as not working in 32-bit Linux builds). A
# patch that uses it loads with that slot off. Surge's own type numbers (fx_type_names in SurgeStorage.h).
REMOVED_FX = {"Spring Reverb": 27}
FX_TYPES = [(i, t["name"]) for i, t in enumerate(FACTS["fx_types"]) if i not in REMOVED_FX.values()]
FX_SLOT_NAMES = ["A1", "A2", "A3", "A4", "B1", "B2", "B3", "B4", "S1", "S2", "S3", "S4", "G1", "G2", "G3", "G4"]
LFO_NAMES = ["LFO 1", "LFO 2", "LFO 3", "S-LFO 1", "S-LFO 2", "S-LFO 3"]
MIX_CHANNELS = [("o1", "Osc 1"), ("o2", "Osc 2"), ("o3", "Osc 3"), ("r12", "Ring 1x2"), ("r23", "Ring 2x3"),
                ("noise", "Noise")]
MIX_SURGE = {"o1": "o1", "o2": "o2", "o3": "o3", "r12": "ring12", "r23": "ring23", "noise": "noise"}
PLAY_MODES = ["Poly", "Mono", "Mono ST", "Mono FP", "Mono ST+FP", "Latch"]   # Surge's 6, short for the buttons
MOD_SOURCES = FACTS["mod_sources"][1:]          # Surge's modsources after "Off" (index = Surge's number - 1)


def factory_patches():
    data = os.path.join(ROOT, "third_party", "surge", "resources", "data")
    n = 0
    for top in ("patches_factory", "patches_3rdparty"):
        for _, _, files in os.walk(os.path.join(data, top)):
            n += sum(1 for f in files if f.lower().endswith(".fxp"))
    return n


# The browse lists' ranges: exactly the shipped patches and wavetables, so every value of the knob is a real entry
# (mpc-vst-plugins' stepping of a long list assumes that). The user's own come FIRST in the browse order
# (src/engine.cpp), so the knob always reaches them; with user files added, the last shipped entries are reached with
# the < > / FOLDER / CAT buttons.
MAX_PATCHES = None
MAX_WT = None


def wt_pictures():
    """the factory and third-party wavetables that get a picture (tools/wt_art.py draws them in this order)"""
    data = os.path.join(ROOT, "third_party", "surge", "resources", "data")
    out = []
    for top in ("wavetables", "wavetables_3rdparty"):
        for d, _, files in os.walk(os.path.join(data, top)):
            for f in files:
                if f.lower().endswith((".wt", ".wav")):
                    out.append(os.path.relpath(os.path.join(d, f), data).replace(os.sep, "/"))
    return sorted(out, key=lambda s: s.lower())


def surge(storage):
    p = SURGE[storage]
    return p


def cont(key, name, pattern, **kw):
    """a continuous Surge parameter, 0..1 as Surge's own normalised value; the value text is Surge's"""
    p = {"key": key, "name": name, "min": 0.0, "max": 1.0, "default": 0.0, "dynamic_display": True,
         "bind": ["cont", pattern]}
    p.update(kw)
    return p


def opt(key, name, pattern, labels=None, values=None, **kw):
    """a Surge int parameter as an option list: option i sets Surge's value values[i]"""
    sp = surge(pattern.replace("%s", "a").replace("%o", "1").replace("%l", "0").replace("%x", "1"))
    if values is None:
        values = list(range(sp["min"], sp["max"] + 1))
    if labels is None:
        labels = [sp["opts"][v - sp["min"]] for v in values]
    assert len(labels) == len(values)
    p = {"key": key, "name": name, "options": labels, "default": values.index(sp["def"]) if sp["def"] in values else 0,
         "bind": ["int", pattern, values]}
    p.update(kw)
    return p


def onoff(key, name, pattern, **kw):
    p = {"key": key, "name": name, "options": ["Off", "On"], "default": 0, "bind": ["bool", pattern]}
    p.update(kw)
    return p


def intrange(key, name, pattern, lo, hi, **kw):
    """a Surge int parameter as a whole number lo..hi (the value text is Surge's)"""
    p = {"key": key, "name": name, "min": lo, "max": hi, "default": lo, "display": "int", "dynamic_display": True,
         "bind": ["intr", pattern]}
    p.update(kw)
    return p


def eng_opts(key, name, options, default=0, **kw):
    p = {"key": key, "name": name, "options": options, "default": default, "bind": ["engine"]}
    p.update(kw)
    return p


def eng_num(key, name, lo, hi, default, **kw):
    p = {"key": key, "name": name, "min": lo, "max": hi, "default": default, "dynamic_display": True,
         "bind": ["engine"]}
    p.update(kw)
    return p


def trigger(key, name):
    return {"key": key, "name": name, "min": 0.0, "max": 1.0, "momentary": True, "type": "trigger", "default": 0.0,
            "bind": ["engine"]}


def readout(key, name):
    return {"key": key, "name": name, "min": 0.0, "max": 1.0, "default": 0.0, "display": "string", "type": "readout",
            "bind": ["engine"]}


P = []
# ---- 0.1.0 -----------------------------------------------------------------------------------------------------------
# what the pages show
P += [
    opt("scene", "Edit Scene", "scene_active", ["A", "B"]),
    eng_opts("osc_sel", "Oscillator", ["1", "2", "3"]),
    eng_opts("lfo_sel", "LFO", LFO_NAMES),
    eng_opts("fx_sel", "FX Slot", FX_SLOT_NAMES),
]
# STEP SEQ (the selected LFO's step sequencer)
P += [eng_num("seq_%d" % (i + 1), "Step %d" % (i + 1), -1.0, 1.0, 0.0) for i in range(16)]
P += [eng_num("seq_start", "Loop Start", 1, 16, 1, display="int"), eng_num("seq_end", "Loop End", 1, 16, 16,
                                                                            display="int")]
# OSC
P += [opt("osc_type", "Osc Type", "%s_osc%o_type")]
P += [cont("osc_p%d" % (i + 1), "Osc Param %d" % (i + 1), "%%s_osc%%o_param%d" % i) for i in range(7)]
P += [
    opt("osc_octave", "Osc Octave", "%s_osc%o_octave", ["-3", "-2", "-1", "0", "+1", "+2", "+3"]),
    cont("osc_pitch", "Osc Pitch", "%s_osc%o_pitch"),
    onoff("osc_keytrack", "Osc Keytrack", "%s_osc%o_keytrack"),
    onoff("osc_retrig", "Osc Retrigger", "%s_osc%o_retrigger"),
    eng_num("wt", "Wavetable", 0, len(wt_pictures()) - 1, 0, display="int", nudge_pct=10, poll=False),
    trigger("wt_prev", "Wavetable Prev"), trigger("wt_next", "Wavetable Next"),
    trigger("wt_cat_prev", "WT Folder Prev"), trigger("wt_cat_next", "WT Folder Next"),
    trigger("wt_rescan", "WT Rescan"),
    readout("wt_name", "Wavetable Name"), readout("wt_folder", "Wavetable Folder"),
    eng_num("wt_pic", "Wavetable Picture", 0, len(wt_pictures()), 0, display="int", poll=False),
]
# MIXER
P += [cont("mix_%s" % k, "%s Level" % n, "%%s_level_%s" % MIX_SURGE[k]) for k, n in MIX_CHANNELS]
P += [cont("mix_pfg", "Pre-Filter Gain", "%s_level_pfg")]
P += [onoff("mute_%s" % k, "%s Mute" % n, "%%s_mute_%s" % MIX_SURGE[k]) for k, n in MIX_CHANNELS]
P += [onoff("solo_%s" % k, "%s Solo" % n, "%%s_solo_%s" % MIX_SURGE[k]) for k, n in MIX_CHANNELS]
P += [opt("route_%s" % k, "%s Route" % n, "%%s_route_%s" % MIX_SURGE[k], ["F1", "BOTH", "F2"]) for k, n in MIX_CHANNELS]
P += [
    opt("fm_routing", "FM Routing", "%s_fm_switch"),
    cont("fm_depth", "FM Depth", "%s_fm_depth"),
    cont("noise_color", "Noise Color", "%s_noisecol"),
    cont("osc_drift", "Osc Drift", "%s_drift"),
    cont("sc_volume", "Scene Volume", "%s_volume"),
    cont("sc_pan", "Scene Pan", "%s_pan"),
    cont("sc_width", "Scene Width", "%s_pan2"),
]
# FILTER
P += [opt("fb_config", "Filter Config", "%s_fb_config")]
for n in (1, 2):
    P += [
        opt("f%d_type" % n, "Filter %d Type" % n, "%%s_filter%d_type" % n),
        intrange("f%d_subtype" % n, "Filter %d Subtype" % n, "%%s_filter%d_subtype" % n, 0, 7),
        cont("f%d_cutoff" % n, "Filter %d Cutoff" % n, "%%s_filter%d_cutoff" % n),
        cont("f%d_res" % n, "Filter %d Resonance" % n, "%%s_filter%d_resonance" % n),
        cont("f%d_env" % n, "Filter %d FEG Amount" % n, "%%s_filter%d_envmod" % n),
        cont("f%d_ktrk" % n, "Filter %d Keytrack" % n, "%%s_filter%d_keytrack" % n),
    ]
P += [
    onoff("f2_offset", "Filter 2 Offset Mode", "%s_f2_cf_is_offset"),
    onoff("f2_linkres", "Link Resonance", "%s_f2_link_resonance"),
    cont("feedback", "Feedback", "%s_feedback"),
    cont("f_balance", "Filter Balance", "%s_f_balance"),
    cont("highpass", "Highpass", "%s_lowcut"),
    opt("ws_type", "Waveshaper Type", "%s_ws_type"),
    cont("ws_drive", "Waveshaper Drive", "%s_ws_drive"),
]
# ENVELOPES (Surge: env1 = Amp EG, env2 = Filter EG)
for pre, n, nm in (("aeg", 1, "Amp EG"), ("feg", 2, "Filter EG")):
    P += [
        cont("%s_a" % pre, "%s Attack" % nm, "%%s_env%d_attack" % n),
        cont("%s_d" % pre, "%s Decay" % nm, "%%s_env%d_decay" % n),
        cont("%s_s" % pre, "%s Sustain" % nm, "%%s_env%d_sustain" % n),
        cont("%s_r" % pre, "%s Release" % nm, "%%s_env%d_release" % n),
        opt("%s_ash" % pre, "%s Attack Shape" % nm, "%%s_env%d_attack_shape" % n),
        opt("%s_dsh" % pre, "%s Decay Shape" % nm, "%%s_env%d_decay_shape" % n),
        opt("%s_rsh" % pre, "%s Release Shape" % nm, "%%s_env%d_release_shape" % n),
        opt("%s_mode" % pre, "%s Mode" % nm, "%%s_env%d_mode" % n),
    ]
# LFO (the selected one)
P += [
    opt("lfo_shape", "LFO Shape", "%s_lfo%l_shape", ["Sine", "Triangle", "Square", "Sawtooth", "Noise", "S&H",
                                                     "Envelope", "Step Seq", "MSEG", "Formula"]),
    cont("lfo_rate", "LFO Rate", "%s_lfo%l_rate"),
    cont("lfo_phase", "LFO Phase", "%s_lfo%l_phase"),
    cont("lfo_amp", "LFO Amplitude", "%s_lfo%l_magnitude"),
    cont("lfo_deform", "LFO Deform", "%s_lfo%l_deform"),
    opt("lfo_trig", "LFO Trigger", "%s_lfo%l_trigmode"),
    onoff("lfo_uni", "LFO Unipolar", "%s_lfo%l_unipolar"),
    cont("lfo_delay", "LFO EG Delay", "%s_lfo%l_delay"),
    cont("lfo_attack", "LFO EG Attack", "%s_lfo%l_attack"),
    cont("lfo_hold", "LFO EG Hold", "%s_lfo%l_hold"),
    cont("lfo_decay", "LFO EG Decay", "%s_lfo%l_decay"),
    cont("lfo_sustain", "LFO EG Sustain", "%s_lfo%l_sustain"),
    cont("lfo_release", "LFO EG Release", "%s_lfo%l_release"),
]
# MOD (the edited scene's modulation routings, and the global ones)
P += [
    eng_num("mod_slot", "Mod Slot", 1, 64, 1, display="int"),
    eng_opts("mod_src", "Mod Source", MOD_SOURCES, 0),
    eng_num("mod_depth", "Mod Depth", -1.0, 1.0, 0.0),
    trigger("mod_learn", "Mod Learn"), trigger("mod_clear", "Mod Clear"),
    readout("mod_target", "Mod Target"), readout("mod_info", "Mod Info"),
]
# FX (the selected slot)
P += [
    {"key": "fx_type", "name": "FX Type", "options": [n for _, n in FX_TYPES], "default": 0,
     "bind": ["int", "fx%x_type", [i for i, _ in FX_TYPES]]},
]
P += [cont("fx_p%d" % (i + 1), "FX Param %d" % (i + 1), "fx%%x_p%d" % i) for i in range(12)]
P += [eng_opts("fx_on", "FX On", ["Off", "On"], 1)]
P += [cont("send_%d" % (i + 1), "Send %d" % (i + 1), "%%s_send_fx_%d" % (i + 1)) for i in range(4)]
P += [cont("ret_%d" % (i + 1), "Return %d" % (i + 1), "volume_FX%d" % (i + 1)) for i in range(4)]
P += [opt("fx_bypass", "FX Chain", "fx_bypass", ["All FX", "No Send", "No Send/Glb", "All Off"])]
# PATCH / VOICE
P += [
    eng_num("patch", "Patch", 0, factory_patches() - 1, 0, display="int", nudge_pct=10, poll=False),
    trigger("patch_prev", "Patch Prev"), trigger("patch_next", "Patch Next"),
    trigger("cat_prev", "Category Prev"), trigger("cat_next", "Category Next"),
    trigger("patch_load", "Load Patch"), trigger("patch_save", "Save Patch"),
    readout("patch_name", "Loaded Patch"), readout("patch_browse", "Browse"), readout("patch_cat", "Category"),
    opt("play_mode", "Play Mode", "%s_polymode", PLAY_MODES),
    intrange("poly_limit", "Poly Limit", "polylimit", 2, 32, default=16, qlink_ticks=1),
    cont("portamento", "Portamento", "%s_portamento"),
    intrange("bend_up", "Bend Up", "%s_pbrange_up", 0, 24, default=2),
    intrange("bend_dn", "Bend Down", "%s_pbrange_dn", 0, 24, default=2),
    opt("scene_mode", "Scene Mode", "scenemode"),
    intrange("split_key", "Split Point", "splitkey", 0, 127, default=60),
    cont("volume", "Volume", "volume"),
    trigger("panic", "Panic"),
]
# MACROS (Surge's 8 macro controls, with the patch's own names)
P += [eng_num("macro_%d" % (i + 1), "Macro %d" % (i + 1), 0.0, 1.0, 0.0) for i in range(8)]
P += [readout("macro_%d_name" % (i + 1), "Macro %d Name" % (i + 1)) for i in range(8)]
# ---- 0.3.0 (appended: params.lock keeps the order of the keys above) -----------------------------------------------
# STEP SEQ: one button makes the selected LFO play the steps (its shape becomes Step Seq), and a line says what it
# does and whether it is routed anywhere (an LFO modulates nothing until it is)
P += [eng_opts("seq_on", "Step Seq On", ["Off", "On"], 0), readout("seq_info", "Step Seq Info"),
       trigger("cat_factory", "Jump Factory"), trigger("cat_3rd", "Jump 3rd Party"), trigger("cat_user", "Jump User"),
       eng_opts("route_on", "Route", ["Off", "On"], 0)]

# ---- checks --------------------------------------------------------------------------------------------------------
keys = [p["key"] for p in P]
assert len(keys) == len(set(keys)), "duplicate key"
for p in P:
    assert "__" not in p["key"]

# ---- write ---------------------------------------------------------------------------------------------------------
KIND = {"cont": "B_CONT", "int": "B_INT", "bool": "B_BOOL", "intr": "B_INTR", "engine": "B_ENGINE"}


def main():
    out = [dict((k, v) for k, v in p.items() if k != "bind") for p in P]
    json.dump({"name": "SurgeXXL", "params": out}, open(os.path.join(ROOT, "params.json"), "w"), indent=1)
    with open(os.path.join(ROOT, "src", "param_ids.h"), "w") as f:
        f.write("// GENERATED by tools/gen_params.py -- do not edit. VST parameter indices (append-only).\n#pragma once\n")
        for i, k in enumerate(keys):
            f.write("#define P_%s %d\n" % (k.upper(), i))
        f.write("#define P_COUNT %d\n" % len(keys))
    with open(os.path.join(ROOT, "src", "param_table.inc"), "w") as f:
        f.write("// GENERATED by tools/gen_params.py -- do not edit. {key, binding, Surge storage-name pattern, option\n"
                "// count, the Surge value of each option (B_INT), min, max (VST units)}\n")
        for p in P:
            b = p["bind"]
            pat = b[1] if len(b) > 1 else ""
            vals = b[2] if b[0] == "int" else []
            nopt = len(p.get("options", []))
            lo, hi = (0.0, float(max(nopt - 1, 1))) if p.get("options") else (float(p["min"]), float(p["max"]))
            f.write('{"%s", %s, "%s", %d, {%s}, %sf, %sf},\n' % (p["key"], KIND[b[0]], pat, len(vals),
                                                                ", ".join(str(v) for v in vals), repr(lo), repr(hi)))
    with open(os.path.join(ROOT, "src", "wt_pictures.inc"), "w") as f:
        f.write("// GENERATED by tools/gen_params.py -- do not edit. Factory and third-party wavetables with a picture\n"
                "// (index + 1 = the wt_pic value that shows it; tools/wt_art.py draws them).\n")
        for rel in wt_pictures():
            f.write('"%s",\n' % rel.replace("\\", "\\\\").replace('"', '\\"'))
    print("gen_params: %d parameters, %d wavetable pictures" % (len(P), len(wt_pictures())))


if __name__ == "__main__":
    main()
