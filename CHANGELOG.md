# Changelog

## 0.2.0
- **Fixed: SurgeXXL loaded nothing (or took MPC down when a track switched to it) on every Force.** MPC's service runs
  with no `HOME` variable, and Surge's start-up asked for the home folder before anything else, so no instance could
  ever be made: the crash log said `create: exception The environment variable HOME is unset or empty`. Surge now never
  looks there (the plugin has its own user folder, `/sdcard/SurgeXXL`). Every offline test (x86, and the Force binary
  under an ARM emulator) now runs with no HOME as MPC does; the old code fails it with the Force's exact log line.
- Built with mpc-vst-plugins at sunskiefer 3845bea: the Q-Link / automation UpdateDisplay fix (#486-#489) and the
  installer's escaped L'Cronx name.
- The whole library stays in (every factory and third-party patch and wavetable). The package is big (about 450 MB
  unpacked): install it on its own, not in a batch with other plugins (see the release notes).

## 0.1.3
- Packed under **L'Cronx**: the plugin folder is now `L'Cronx - VST - SurgeXXL` and MPC lists the maker as L'Cronx. Nothing else
  changed from 0.1.2. If you installed 0.1.2, run its `uninstall.sh` first (copy out anything you saved inside the plugin
  folder), then install 0.1.3. The installer handles the ' in the folder name.

## 0.1.2
- Q-Links in the order of your SurgeXXL Q-Link Map (qlinks.json): MIXER's mute, solo and route rows on their own
  Q-Link pages with Ring 1x2 / 2x3 included, FILTER's types and subtypes beside their filter, the envelope shapes on
  ENV / LFO 4, FX On and Type first on FX, the patch browser off PATCH's Q-Links (touch only).
- Still crashing on LOAD on a Force after 0.1.1, so this version brings its own crash log: `/sdcard/SurgeXXL/surgexxl.log`
  gets a line per instance, LOAD (and how long it took) and state restore, and, if MPC is about to go down, the
  signal, where in the plugin it happened and the plugin's return addresses on the stack. The library keeps its symbol
  table (no debug info) so those addresses name functions.
- Hardening around LOAD: the load thread has an 8 MB stack and its own signal stack; no exception can leave the
  plugin (each entry point and the load catch, log and carry on).

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
