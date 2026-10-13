# Offered upstream to mpc-vst-plugins

## A bigger state chunk (CHUNK_MAX)

`wrapper/vst2_wrap.c` keeps a plugin's state chunk in a fixed `char chunk[8192]`. A Surge sound is the whole patch
(parameters, modulation, the wavetables it uses, step sequences, MSEGs): 35-160 KB, 50-210 KB as the base64 text the
engine's `"state"` key returns. SurgeXXL builds the wrapper with that buffer `CHUNK_MAX` bytes long (4 MB, from vst.json
`"defines"`) through `tools/wrap_chunk.py`, which changes only that line. The upstream change:

```diff
 #include "params.h"
+#ifndef CHUNK_MAX
+#define CHUNK_MAX 8192 /* the state chunk buffer's size (vst.json "defines"); an engine with a big state raises it */
+#endif
 ...
-    char chunk[8192];
+    char chunk[CHUNK_MAX];
```

plus a line in `tools/gen_vst.py`'s docstring (`defines`) and `docs/PORTING.md` ("State saved via chunks"). Every port
that doesn't set it builds exactly as before. Once it is in mpc-vst-plugins, `tools/wrap_chunk.py` passes the file
through unchanged (it checks for `CHUNK_MAX`) and can go.

Not verified on a device yet: how large a chunk MPC keeps in a project. JUCE stores it base64 in the project XML;
MPC OS's own instruments store kilobytes. SurgeXXL's first device test should save and reload a project with a
wavetable patch loaded.
