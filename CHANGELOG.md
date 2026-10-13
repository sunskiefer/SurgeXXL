# Changelog

## 0.1.1
- Fixed: LOAD crashed the Force ("Your Force recovered from an internal error"). Surge loads a patch on its own
  thread, and while it ran MPC read every value and value text again (the LOAD press refreshes the pages), played
  notes and moved Q-Links into the half-loaded patch. The plugin now loads on its own thread and nothing else touches
  the synth until it is done: the sound is silent for the moment of the load, the pages keep their last values and
  show "Loading...", and notes and Q-Link moves in that moment are dropped. A new offline test does what MPC does
  during a load (reads every page, plays notes, moves Q-Links) and runs clean under ThreadSanitizer (the old code:
  322 races).

## 0.1.0
- Surge XT 1.3.4's engine (the Surge Synth Team) as an MPC OS VST2 instrument for the Force, built headless for its
  32-bit ARM (Cortex-A17, NEON) with zig; Spring Reverb left out (a patch using it loads with that slot off), MTS-ESP off, Lua formula modulators interpreted (no JIT).
- Eight pages in InterzoneXXL's look (Valley sliders and Rogan knobs, VCV switches) with LXRXXL BAZZLINE's mixer
  faders and lit keys: OSC, MIXER, FILTER, ENV / LFO, STEP SEQ, MOD, FX, PATCH. Pages follow the edited scene and the
  selected oscillator, LFO and FX slot; oscillator and FX parameter names change with the type (Surge's own names).
- Every factory and third-party patch (3008) and wavetable (761); a picture of each shipped wavetable; your own
  patches (SAVE as SurgeXXL NNN) and wavetables (RESCAN) in /sdcard/SurgeXXL, first in the lists.
- Modulation: browse the scene's routings, pick a source, LEARN a target by touching any control, depth, clear.
- The 8 macros with the patch's names; polyphony limit 2-32; RMXXXL's brickwall limiter on the output (-0.3 dBFS).
- The whole sound in the MPC project (Surge's patch, every LFO's steps, the page selections), through mpc-vst-plugins'
  wrapper with a 4 MB state chunk (tools/wrap_chunk.py, offered upstream: docs/UPSTREAM.md).
- Q-Links: 8 knobs per Q-Link page, from qlinks.json (the SurgeXXL Q-Link Map's format, as BAZZLINE's).
- Offline tests: the engine (patches, FX types, wavetables, save, state, learn) and mpc-vst-plugins' host test, on x86
  and as the Force build under qemu-arm. Found and fixed offline: a 32-bit build without 64-bit file offsets lists no
  folders on filesystems with large inode numbers.
