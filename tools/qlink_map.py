#!/usr/bin/env python3
"""Make the SurgeXXL Q-Link Map page (an artifact): a picture of each page to number the controls on, the knob banks,
and Save as surgexxl-qlinks.json, which the build reads as qlinks.json (tools/panel.py).

    python3 tools/qlink_map.py <preview dir> <out dir>
<preview dir>: mpc-vst-plugins' `tools/studio.py preview` of the built skin (page_<n>.png per Q-Link page).
Writes <out dir>/index.html (from tools/qlink_map_template.html, the BAZZLINE Q-Link Map's page) and p0..p7.jpg."""
import json
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import panel  # noqa: E402


def rect(c):
    if c["kind"] == "seg":
        x0 = min(r[0] for r in c["rects"])
        y0 = min(r[1] for r in c["rects"])
        x1 = max(r[0] + r[2] for r in c["rects"])
        y1 = max(r[1] + r[3] for r in c["rects"])
        return x0, y0, x1 - x0, y1 - y0
    return panel.touch_box(c)


def main():
    prev, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    pages, pics, sub = [], [], 0
    for t, pid in enumerate(panel.PAGE_IDS):
        controls, seen = [], set()
        for c in panel.controls(t):
            if c["kind"] in ("readout", "picture", "button") or c["key"] in seen:
                continue
            seen.add(c["key"])
            x, y, w, h = rect(c)
            controls.append({"key": c["key"], "name": panel.P[c["key"]]["name"].upper(), "x": int(x), "y": int(y),
                             "w": int(w), "h": int(h)})
        pages.append({"id": pid, "name": panel.TABS[t], "controls": controls,
                      "current": [k if k != "-" else "" for k in panel.qlink_order(t)]})
        Image.open(os.path.join(prev, "page_%d.png" % sub)).convert("RGB").save(os.path.join(out, "p%d.jpg" % t),
                                                                                quality=85)
        pics.append("p%d.jpg" % t)
        sub += len(panel.qlink_pages(t))
    html = open(os.path.join(panel.ROOT, "tools", "qlink_map_template.html")).read()
    html = html.replace("/*DATA*/null", json.dumps({"pages": pages})).replace("/*PICS*/null", json.dumps(pics))
    open(os.path.join(out, "index.html"), "w").write(html)
    print("qlink_map: %d pages -> %s" % (len(pages), out))


if __name__ == "__main__":
    main()
