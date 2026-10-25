"""Colour themes of SurgeXXL's skin: the layout, knobs, sliders, buttons and every text size are the same in all of
them (tools/panel.py), only these colours change. Pick one with SXXL_SKIN=<name> when building the skin
(./build.sh --skin-only); no name builds "dark", the skin SurgeXXL ships with.

    dark   the shipped skin: charcoal pages, white frames, orange accent
    white  HIVE 2 light: pale grey pages, graphite frames and lettering, dark displays, the same orange accent
"""
import os

THEMES = {
    "dark": dict(
        bg=(0x28, 0x28, 0x28), ink=(255, 255, 255), ink_dim=(0xcf, 0xcf, 0xcf), tab_text=(0x11, 0x11, 0x11),
        seg_off=(0x1c, 0x1c, 0x1c), seg_off_ink=(0xcf, 0xcf, 0xcf), accent=(0xf2, 0x9a, 0x2e),
        accent_ink=(17, 17, 17), value="ffcfcfcf", line=(0x3e, 0x3e, 0x3e), knob_tint=None, bg_text=None, style="valley"),
    "white": dict(
        bg=(0xd9, 0xd9, 0xd9), ink=(0x26, 0x26, 0x26), ink_dim=(0x3a, 0x3a, 0x3a), tab_text=(255, 255, 255),
        seg_off=(0xf3, 0xf3, 0xf3), seg_off_ink=(0x2a, 0x2a, 0x2a), accent=(0xf2, 0x9a, 0x2e),
        accent_ink=(17, 17, 17), value="ff262626", line=(0xb6, 0xb6, 0xb6), knob_tint=None, style="hive",
        # lettering panel.py draws in light ink for a dark page -> this on a light one (not over a dark display)
        bg_text={(255, 255, 255): (0x26, 0x26, 0x26), (0xcf, 0xcf, 0xcf): (0x3a, 0x3a, 0x3a),
                 "ffffff": "262626", "cfcfcf": "3a3a3a"}),
}
NAME = os.environ.get("SXXL_SKIN", "dark")
if NAME not in THEMES:
    raise SystemExit("SXXL_SKIN=%s: known skins are %s" % (NAME, ", ".join(sorted(THEMES))))
T = THEMES[NAME]
