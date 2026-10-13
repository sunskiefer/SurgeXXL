#!/usr/bin/env python3
"""Copy mpc-vst-plugins' wrapper/vst2_wrap.c into the build with a bigger state chunk.

    python3 tools/wrap_chunk.py <mpc-vst-plugins dir> <out file>

The framework's wrapper keeps the plugin's state chunk in a fixed 8192-byte buffer. A Surge sound is far bigger (the
whole patch: parameters, modulation, the wavetables it uses, step sequences, MSEGs: 35-160 KB, as base64 text 50-210 KB),
so SurgeXXL builds the wrapper with that buffer CHUNK_MAX bytes long (vst.json "defines"). Only that one line changes;
everything else is the framework's file as it is. The same change, a CHUNK_MAX define defaulting to 8192, is offered
upstream (docs/UPSTREAM.md); once mpc-vst-plugins has it, this script goes.
"""
import os
import sys

OLD = "    char chunk[8192];"
NEW = "    char chunk[CHUNK_MAX];   /* SurgeXXL (tools/wrap_chunk.py): the state chunk's buffer, from vst.json */"
GUARD = ("#ifndef CHUNK_MAX\n#define CHUNK_MAX 8192 /* SurgeXXL (tools/wrap_chunk.py): the state chunk buffer's size */\n"
         "#endif\n")


def main():
    src = os.path.join(sys.argv[1], "wrapper", "vst2_wrap.c")
    out = sys.argv[2]
    text = open(src).read()
    if "CHUNK_MAX" in text:          # upstream has it already: use the file as it is
        open(out, "w").write(text)
        return
    if text.count(OLD) != 1 or text.count('#include "params.h"\n') != 1:
        sys.exit("wrap_chunk: mpc-vst-plugins' vst2_wrap.c changed; update tools/wrap_chunk.py")
    text = text.replace(OLD, NEW).replace('#include "params.h"\n', '#include "params.h"\n' + GUARD)
    open(out, "w").write(text)


if __name__ == "__main__":
    main()
