#!/usr/bin/env python3
"""Pictures of Surge's factory and third-party wavetables, for the OSC page (tools/panel_art.py).

picture(i, w, h): i = the wt_pic value (src/wt_pictures.inc order, 1-based; 0 = a user table or no wavetable). The
picture is the table drawn as Surge draws it in 3D: some of its frames, front to back, each a line in the display's
orange, on the LCD's black. It is a still of the table, not of the morph position (the skin can't draw live).

Reads Surge's two formats: .wt ("vawt": frame size, frame count, flags; int16 or float32 samples) and .wav (PCM or
float; the frame size from Surge's "clm " or "srge" chunk, else one frame if the file is a power of two up to 4096
samples, else 2048 per frame, as Surge's loader decides).
"""
import math
import os
import struct
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_params  # noqa: E402

ROOT = gen_params.ROOT
DATA = os.path.join(ROOT, "third_party", "surge", "resources", "data")
CACHE = os.path.join(ROOT, "build", "wt_art")
FONT = os.path.join(ROOT, "art", "fonts", "TitilliumWeb-SemiBold.ttf")
SS = 3
LCD = (0x12, 0x12, 0x12)
ORANGE = (0xfb, 0x90, 0x13)
_list = None


def files():
    global _list
    if _list is None:
        _list = gen_params.wt_pictures()
    return _list


def read_wt(path):
    """-> list of frames (lists of floats -1..1)"""
    raw = open(path, "rb").read()
    if raw[:4] == b"vawt":
        size, count, flags = struct.unpack("<IHH", raw[4:12])
        body = raw[12:]
        if flags & 4:        # int16
            n = size * count
            vals = struct.unpack("<%dh" % n, body[:2 * n])
            vals = [v / 32768.0 for v in vals]
        else:
            n = size * count
            vals = list(struct.unpack("<%df" % n, body[:4 * n]))
        return [vals[i * size:(i + 1) * size] for i in range(count)]
    if raw[:4] == b"RIFF":
        pos, fmt, data, frame = 12, None, None, None
        while pos + 8 <= len(raw):
            cid, clen = raw[pos:pos + 4], struct.unpack("<I", raw[pos + 4:pos + 8])[0]
            body = raw[pos + 8:pos + 8 + clen]
            if cid == b"fmt ":
                fmt = struct.unpack("<HHIIHH", body[:16])
            elif cid == b"data":
                data = body
            elif cid == b"clm ":
                txt = body.decode("latin1")
                if txt.startswith("<!>"):
                    try:
                        frame = int(txt[3:].split()[0])
                    except ValueError:
                        pass
            elif cid == b"srge":
                frame = struct.unpack("<ii", body[:8])[1]
            pos += 8 + clen + (clen & 1)
        if not fmt or data is None:
            return []
        tag, ch, _, _, _, bits = fmt
        step = bits // 8 * ch
        n = len(data) // step
        vals = []
        for i in range(n):
            o = i * step
            if tag == 3 and bits == 32:
                v = struct.unpack("<f", data[o:o + 4])[0]
            elif bits == 16:
                v = struct.unpack("<h", data[o:o + 2])[0] / 32768.0
            elif bits == 24:
                b = data[o:o + 3]
                v = int.from_bytes(b, "little", signed=True) / 8388608.0
            elif bits == 32:
                v = struct.unpack("<i", data[o:o + 4])[0] / 2147483648.0
            elif bits == 8:
                v = (data[o] - 128) / 128.0
            else:
                v = 0.0
            vals.append(v)
        if frame is None:
            frame = n if n <= 4096 and n & (n - 1) == 0 else 2048
        frame = max(1, frame)
        return [vals[i * frame:(i + 1) * frame] for i in range(max(1, n // frame))]
    return []


def draw(frames, w, h):
    img = Image.new("RGB", (w * SS, h * SS), LCD)
    d = ImageDraw.Draw(img)
    if not frames:
        return img
    shown = min(len(frames), 24)
    idx = [round(i * (len(frames) - 1) / max(1, shown - 1)) for i in range(shown)] if shown > 1 else [0]
    peak = max(1e-6, max(max(abs(v) for v in f) for f in frames if f))
    pad = 8 * SS
    depth_x, depth_y = 0.28 * w * SS, 0.32 * h * SS        # back frames shift up and right
    fw = w * SS - 2 * pad - depth_x
    amp = (h * SS - 2 * pad - depth_y) / 2.2
    for k, fi in reversed(list(enumerate(idx))):            # the back first
        f = frames[fi]
        if not f:
            continue
        z = k / max(1, shown - 1)
        ox, oy = pad + depth_x * z, h * SS - pad - amp * 1.1 - depth_y * z
        step = max(1, len(f) // 256)
        pts = [(ox + fw * i / (len(f) - 1 or 1), oy - f[i] / peak * amp) for i in range(0, len(f), step)]
        fade = 1.0 - 0.7 * z
        col = tuple(int(LCD[j] + (ORANGE[j] - LCD[j]) * fade) for j in range(3))
        d.line(pts, fill=col, width=max(1, int((2.2 - 1.2 * z) * SS / 2)), joint="curve")
    return img


def generic(w, h):
    img = Image.new("RGB", (w * SS, h * SS), LCD)
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, 15 * SS)
    d.line([(10 * SS, h * SS / 2), ((w - 10) * SS, h * SS / 2)], fill=(0x55, 0x33, 0x0c), width=2 * SS)
    d.text((w * SS / 2, h * SS / 2 - 16 * SS), "NO PICTURE", font=f, fill=(0x80, 0x4c, 0x10), anchor="mm")
    d.text((w * SS / 2, h * SS / 2 + 16 * SS), "user table / no wavetable", font=ImageFont.truetype(FONT, 11 * SS),
           fill=(0x80, 0x4c, 0x10), anchor="mm")
    return img


def picture(i, w, h):
    os.makedirs(CACHE, exist_ok=True)
    cached = os.path.join(CACHE, "%d_%dx%d.png" % (i, w, h))
    if os.path.exists(cached):
        return Image.open(cached).convert("RGB")
    if i == 0:
        img = generic(w, h)
    else:
        try:
            img = draw(read_wt(os.path.join(DATA, files()[i - 1])), w, h)
        except Exception as e:     # an unreadable table gets the plain picture, never a failed build
            print("wt_art: %s: %s" % (files()[i - 1], e))
            img = generic(w, h)
    img = img.resize((w, h), Image.LANCZOS)
    img.save(cached, optimize=True)
    return img


if __name__ == "__main__":
    # python3 tools/wt_art.py <i> [out.png]: one picture, to look at
    i = int(sys.argv[1])
    picture(i, 200, 128).save(sys.argv[2] if len(sys.argv) > 2 else "/tmp/wt_%d.png" % i)
