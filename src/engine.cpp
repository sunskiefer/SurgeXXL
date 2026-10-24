// SPDX-License-Identifier: GPL-3.0-or-later
// SurgeXXL: Surge XT (the Surge Synth Team's open-source hybrid synthesizer) as an MPC OS VST2 instrument for the
// Akai Force. The sound engine is Surge XT 1.3.4's own, vendored and built headless (third_party/surge, see
// src/VENDORED.md), the way Surge's VCV Rack modules build it. This file is the plugin layer: it drives one
// SurgeSynthesizer from MPC through the mpc-vst-plugins engine interface (wrapper/engine.h).
//
// Parameters (tools/gen_params.py, src/param_table.inc): most keys are Surge's own parameters for what the pages are
// showing, the edited scene (Surge's "Active Scene"), the selected oscillator, LFO and FX slot. A continuous one is
// Surge's normalised 0..1 value with Surge's own value text; an option list is a Surge int parameter, option i setting
// the Surge value listed for it. Changing the selection changes what every such key reads, so the engine bumps
// "display_rev" and the wrapper re-reads the values (HAS_DISPLAY_REV).
//
// Patches: the browse list is Surge's own (factory, third party, then the user's folder), in Surge's order; LOAD loads
// the browsed patch on the plugin's own load thread (nothing else touches the synth meanwhile), SAVE writes the sound as "SurgeXXL NNN" to the user folder.
// Wavetables: the selected oscillator's table is picked from Surge's list (factory, third party, the user's
// Wavetables folder); wt_pic tells the skin which picture to show (factory and third-party tables have one).
// The user folder is "SurgeXXL" next to the "Synths" folder the plugin is installed in (/sdcard/SurgeXXL on a Force):
// Patches/ and Wavetables/ there, as Surge's own user folder.
//
// FX: Spring Reverb is not built (tools/gen_params.py REMOVED_FX); a patch that uses it loads with that slot off.
// Output: Surge's stereo out, through RMXXXL's brickwall limiter (-0.3 dBFS), to MPC's int16.
// State: the whole Surge patch (Surge's own saveRaw: parameters, modulation, wavetables, step sequences, MSEGs) as
// base64 text in the plugin chunk, with the page selections in front.
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <algorithm>
#include <atomic>
#include <string>
#include <pthread.h>
#include <chrono>
#include <unordered_map>
#include <vector>

#include "SurgeSynthesizer.h"
#include "SurgeStorage.h"
#include "dsp/Effect.h"

#include "denormals.h"
#include "diag.h"
#include "limiter.h"
#include "param_ids.h"

extern "C" {
#include "engine.h"
}

namespace {

enum Bind { B_CONT, B_INT, B_BOOL, B_INTR, B_ENGINE };
struct KeyDef {
  const char *key;
  Bind bind;
  const char *pat;
  int nvals;
  int vals[64];
  float lo, hi;
};
const KeyDef kKeys[] = {
#include "param_table.inc"
};
const int kNumKeys = sizeof(kKeys) / sizeof(kKeys[0]);
static_assert(sizeof(kKeys) / sizeof(kKeys[0]) == P_COUNT, "param_table.inc and param_ids.h disagree");

const char *kWtPictures[] = {
#include "wt_pictures.inc"
};
const int kNumWtPictures = sizeof(kWtPictures) / sizeof(kWtPictures[0]);

const float kSampleRate = 44100.0f;
const char *const kVersion = "0.2.0";
const uint64_t kGestureFrames = 15435;   // 0.35 s: trigger sets closer than this are one Q-Link turn
const int kRemovedFx[] = {27};           // Spring Reverb (Surge's fx type number)
const char *kSlotNames[n_fx_slots] = {"A1", "A2", "A3", "A4", "B1", "B2", "B3", "B4",
                                      "S1", "S2", "S3", "S4", "G1", "G2", "G3", "G4"};

std::unordered_map<std::string, int> &keyIndex() {
  static std::unordered_map<std::string, int> m;
  if (m.empty())
    for (int i = 0; i < kNumKeys; ++i) m[kKeys[i].key] = i;
  return m;
}

int clampi(int v, int lo, int hi) { return v < lo ? lo : (v > hi ? hi : v); }
float clampf(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }

// ---- base64 (the state chunk is text) ---------------------------------------------------------------------------
const char kB64[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

std::string b64enc(const unsigned char *d, size_t n) {
  std::string o;
  o.reserve((n + 2) / 3 * 4);
  for (size_t i = 0; i < n; i += 3) {
    uint32_t v = d[i] << 16 | (i + 1 < n ? d[i + 1] << 8 : 0) | (i + 2 < n ? d[i + 2] : 0);
    o += kB64[v >> 18 & 63];
    o += kB64[v >> 12 & 63];
    o += i + 1 < n ? kB64[v >> 6 & 63] : '=';
    o += i + 2 < n ? kB64[v & 63] : '=';
  }
  return o;
}

bool b64dec(const char *s, std::vector<unsigned char> &out) {
  int val[256];
  for (int i = 0; i < 256; ++i) val[i] = -1;
  for (int i = 0; i < 64; ++i) val[(unsigned char)kB64[i]] = i;
  uint32_t acc = 0;
  int bits = 0;
  out.clear();
  for (; *s; ++s) {
    if (*s == '=') break;
    int v = val[(unsigned char)*s];
    if (v < 0) return false;
    acc = acc << 6 | v;
    bits += 6;
    if (bits >= 8) {
      bits -= 8;
      out.push_back((unsigned char)(acc >> bits & 0xff));
    }
  }
  return true;
}

// ---- the instance -----------------------------------------------------------------------------------------------
struct ModSlot {
  long ptag;
  int src, srcScene, index;
};

struct Inst : public SurgeSynthesizer::PluginLayer {
  SurgeSynthesizer *synth = nullptr;
  std::unordered_map<std::string, Parameter *> byName;
  std::vector<int> wtPicOf;             // wt_list index -> picture (1-based; 0: none)

  int osc = 0, lfo = 0, fxPos = 0;      // the selected oscillator, LFO (0-5) and FX slot (display position 0-15)
  int browse = 0;                       // patch browse position in patchOrder
  std::vector<int> patchOrder, wtOrder; // Surge's orderings with the user's own first (the knob reaches them)
  std::string loadedPath, loadedName = "Init";
  // LOAD runs Surge's loadPatch on our own thread. While it runs nothing else touches the synth: render() plays
  // silence, set() and MIDI are dropped and get() answers from textCache (the last answer per key). The wrapper
  // serializes every engine call, so `loading` is only read and written under its lock; the loader thread only sets
  // loadDone. (Surge's own patch-load thread let the host's reads, notes and Q-Links run into the half-loaded patch:
  // a Force crashed on LOAD, 2026-10-13; test/engine_test.cpp testLoadWhileHostReads under ThreadSanitizer.)
  bool loading = false;
  pthread_t loader;
  bool loaderRunning = false;
  int loadId = -1;
  std::atomic<bool> loadDone{false};
  std::unordered_map<std::string, std::string> textCache;
  int modSlot = 0;                      // 0-based; == count: a new routing
  int modNewSrc = ms_lfo1;              // the source a new routing gets
  bool learn = false;
  std::string modMsg;

  float outL[BLOCK_SIZE], outR[BLOCK_SIZE];
  int outPos = BLOCK_SIZE;
  std::vector<float> bufL, bufR;
  sxxl::Limiter lim;

  uint64_t frames = 0;
  unsigned rev = 1;
  int revAgain = 0;                     // blocks until a second display_rev bump (Surge applies type changes later)
  float trigLast[P_COUNT];
  uint64_t trigAt[P_COUNT];
  double ppq = -1, bpm = 120;
  int playing = 0;

  std::string userDir;

  void surgeParameterUpdated(const SurgeSynthesizer::ID &, float) override {}
  void surgeMacroUpdated(long, float) override {}

  // ---- Surge parameters ----
  SurgePatch &patch() { return synth->storage.getPatch(); }
  int scene() { return clampi(patch().scene_active.val.i, 0, n_scenes - 1); }
  int lfoIndex() { return lfo < 3 ? lfo : lfo + 3; }      // LFO 1-3 = Surge's lfo0-2, S-LFO 1-3 = lfo6-8
  int fxSlot() { return fxslot_order[clampi(fxPos, 0, n_fx_slots - 1)]; }

  Parameter *resolve(const KeyDef &k) {
    char name[96];
    int o = 0;
    for (const char *s = k.pat; *s && o < (int)sizeof(name) - 4; ++s) {
      if (*s == '%' && s[1]) {
        ++s;
        if (*s == 's') o += snprintf(name + o, sizeof(name) - o, "%c", 'a' + scene());
        else if (*s == 'o') o += snprintf(name + o, sizeof(name) - o, "%d", osc + 1);
        else if (*s == 'l') o += snprintf(name + o, sizeof(name) - o, "%d", lfoIndex());
        else if (*s == 'x') o += snprintf(name + o, sizeof(name) - o, "%d", fxSlot() + 1);
      } else {
        name[o++] = *s;
      }
    }
    name[o] = 0;
    auto it = byName.find(name);
    return it == byName.end() ? nullptr : it->second;
  }

  void setInt(Parameter *p, int v) {
    if (p->valtype == vt_bool) {
      synth->setParameter01(synth->idForParameter(p), v ? 1.f : 0.f, false, true);
      return;
    }
    v = clampi(v, p->val_min.i, p->val_max.i);
    synth->setParameter01(synth->idForParameter(p), Parameter::intScaledToFloat(v, p->val_max.i, p->val_min.i), false, true);
  }

  // ---- create ----
  bool init(const char *dataDir) {
    std::string data = dataDir ? dataDir : "";
    // the user folder: "SurgeXXL" next to the folder the plugin's folder is in (<card>/Synths/<plugin>/data)
    std::string up = data;
    for (int i = 0; i < 3 && !up.empty(); ++i) {
      size_t sl = up.find_last_of('/');
      up = sl == std::string::npos ? "" : up.substr(0, sl);
    }
    userDir = (up.empty() ? std::string(".") : up) + "/SurgeXXL";
    surgeXXLUserDataPath() = userDir;
    sxxl::Diag::get().open(userDir);
    sxxl::Diag::get().install();
    sxxl::Diag::get().log("SurgeXXL %s: new instance, data %s", kVersion, data.c_str());
    synth = new SurgeSynthesizer(this, data);
    synth->setSamplerate(kSampleRate);
    synth->time_data.tempo = 120;
    synth->time_data.ppqPos = 0;
    for (auto *p : patch().param_ptr) byName[p->get_storage_name()] = p;
    mapPictures();
    makeOrders();
    lim.Init();
    for (int i = 0; i < P_COUNT; ++i) trigLast[i] = 0, trigAt[i] = 0;
    sxxl::Diag::get().log("ready: %d patches, %d wavetables", numPatches(), (int)wtOrder.size());
    return true;
  }

  void mapPictures() {
    auto &st = synth->storage;
    std::string data = st.datapath.generic_string();
    if (!data.empty() && data.back() != '/') data += '/';
    std::unordered_map<std::string, int> pic;
    for (int i = 0; i < kNumWtPictures; ++i) pic[kWtPictures[i]] = i + 1;
    wtPicOf.assign(st.wt_list.size(), 0);
    for (size_t i = 0; i < st.wt_list.size(); ++i) {
      std::string p = st.wt_list[i].path.generic_string();
      if (p.compare(0, data.size(), data) == 0) {
        auto it = pic.find(p.substr(data.size()));
        if (it != pic.end()) wtPicOf[i] = it->second;
      }
    }
  }

  ~Inst() {
    if (synth) {
      joinLoader();                             // a load in flight finishes first
      delete synth;
    }
  }

  void bump() { ++rev; revAgain = 3; }

  // ---- patches ----
  void makeOrders() {
    auto &st = synth->storage;
    patchOrder.clear();
    for (int id : st.patchOrdering)
      if (st.patch_list[id].category >= st.firstUserCategory) patchOrder.push_back(id);
    for (int id : st.patchOrdering)
      if (st.patch_list[id].category < st.firstUserCategory) patchOrder.push_back(id);
    wtOrder.clear();
    for (int id : st.wtOrdering)
      if (st.wt_list[id].category >= st.firstUserWTCategory) wtOrder.push_back(id);
    for (int id : st.wtOrdering)
      if (st.wt_list[id].category < st.firstUserWTCategory) wtOrder.push_back(id);
  }
  int numPatches() { return (int)patchOrder.size(); }
  int patchAt(int pos) {
    auto &o = patchOrder;
    if (o.empty()) return -1;
    return o[clampi(pos, 0, (int)o.size() - 1)];
  }
  std::string categoryName(int cat) {
    auto &st = synth->storage;
    if (cat < 0 || cat >= (int)st.patch_category.size()) return "";
    const char *root = cat >= st.firstUserCategory ? "USER" : (cat >= st.firstThirdPartyCategory ? "3RD PARTY" : "FACTORY");
    return std::string(root) + "  " + st.patch_category[cat].name;
  }
  void loadBrowsed() {
    int id = patchAt(browse);
    if (id < 0 || loading) return;
    loadedPath = synth->storage.patch_list[id].path.generic_string();
    loadedName = synth->storage.patch_list[id].name;
    joinLoader();
    loading = true;
    loadDone = false;
    loadId = id;
    sxxl::Diag::get().log("LOAD %d: %s", id, loadedPath.c_str());
    // our own thread with a known 8 MB stack (a host may run with a small default) and its own signal stack
    pthread_attr_t at;
    pthread_attr_init(&at);
    pthread_attr_setstacksize(&at, 8 * 1024 * 1024);
    loaderRunning = pthread_create(&loader, &at, loaderMain, this) == 0;
    pthread_attr_destroy(&at);
    if (!loaderRunning) {
      sxxl::Diag::get().log("LOAD: no thread, loading in place");
      loaderBody();
    }
    bump();
  }
  static void *loaderMain(void *self) {
    sxxl::Diag::altStack();
    ((Inst *)self)->loaderBody();
    return nullptr;
  }
  void loaderBody() {
    auto t0 = std::chrono::steady_clock::now();
    try {
      synth->stopSound();
      synth->loadPatch(loadId);
      synth->storage.getPatch().isDirty = false;
    } catch (const std::exception &e) {
      sxxl::Diag::get().log("LOAD %d: exception %s", loadId, e.what());
    } catch (...) {
      sxxl::Diag::get().log("LOAD %d: unknown exception", loadId);
    }
    long ms = (long)std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - t0).count();
    sxxl::Diag::get().log("LOAD %d: done in %ld ms", loadId, ms);
    loadDone = true;
  }
  void joinLoader() {
    if (loaderRunning) pthread_join(loader, nullptr), loaderRunning = false;
  }
  // called under the wrapper's lock: a finished load hands the synth back
  void finishLoad(bool wait) {
    if (!loading || !(wait || loadDone)) return;
    joinLoader();
    synth->patchChanged = false;
    afterPatchLoad();
  }
  void stepCategory(int dir) {
    int n = numPatches();
    if (n <= 0) return;
    auto &pl = synth->storage.patch_list;
    int cur = pl[patchAt(browse)].category, pos = browse;
    if (dir > 0) {
      while (pos < n - 1 && pl[patchAt(pos)].category == cur) ++pos;
    } else {
      while (pos > 0 && pl[patchAt(pos)].category == cur) --pos;       // into the category before
      int c = pl[patchAt(pos)].category;
      while (pos > 0 && pl[patchAt(pos - 1)].category == c) --pos;     // its first patch
    }
    browse = pos;
    bump();
  }
  // FACTORY / 3RD PARTY / USER: the first patch of that group (a group with no patches leaves the browser where it is)
  void jumpGroup(int g) {
    auto &st = synth->storage;
    for (int pos = 0; pos < numPatches(); ++pos) {
      int c = st.patch_list[patchAt(pos)].category;
      int cg = c >= st.firstUserCategory ? 2 : (c >= st.firstThirdPartyCategory ? 1 : 0);
      if (cg == g) { browse = pos; bump(); return; }
    }
  }
  void savePatch() {
    fs::path dir = fs::path(userDir) / "Patches" / "SurgeXXL";
    std::error_code ec;
    fs::create_directories(dir, ec);
    // "<loaded patch> - SurgeXXL NNN" (no text entry on MPC: the loaded patch's name, Init included, tells the saves
    // apart); NNN counts up to 999 per name. A name that was already a save keeps its base ("Lead - SurgeXXL 002").
    std::string base = loadedName.empty() ? std::string("Init") : loadedName;
    size_t mark = base.rfind(" - SurgeXXL ");
    if (mark != std::string::npos) base.resize(mark);
    for (char &ch : base)
      if (ch == '/' || ch == '\\' || ch == ':' || ch == '*' || ch == '?' || ch == '"' || ch == '<' || ch == '>' || ch == '|') ch = '-';
    if (base.size() > 40) base.resize(40);
    int n = 1;
    char name[96];
    for (; n < 1000; ++n) {
      snprintf(name, sizeof name, "%s - SurgeXXL %03d", base.c_str(), n);
      if (!fs::exists(dir / (std::string(name) + ".fxp"), ec)) break;
    }
    if (n >= 1000) return;                   // 999 saves of this name: nothing is overwritten
    patch().name = name;
    patch().category = "SurgeXXL";
    fs::path file = dir / (std::string(name) + ".fxp");
    synth->savePatchToPath(file, false);   // no patch database (its rescan would parse every patch on the Force)
    synth->storage.refresh_patchlist();
    makeOrders();
    loadedPath = file.generic_string();
    loadedName = name;
    // browse to it in the refreshed list
    auto &st = synth->storage;
    for (int pos = 0; pos < numPatches(); ++pos)
      if (st.patch_list[patchAt(pos)].path.generic_string() == loadedPath) browse = pos;
    bump();
  }

  int removedFx = 0;                    // FX slots the last load turned off (removed types; the offline test counts them)

  void afterPatchLoad() {
    loading = false;
    // removed FX types: their slots off
    removedFx = 0;
    for (int s = 0; s < n_fx_slots; ++s) {
      int t = patch().fx[s].type.val.i;
      for (int r : kRemovedFx)
        if (t == r) setInt(&patch().fx[s].type, fxt_off), ++removedFx;
    }
    modSlot = 0;
    learn = false;
    bump();
  }

  // ---- wavetables ----
  OscillatorStorage &oscData() { return patch().scene[scene()].osc[osc]; }
  int wtCurrent() {
    auto &w = oscData().wt;
    if (w.queue_id >= 0) return w.queue_id;
    auto &list = synth->storage.wt_list;
    if (w.current_id >= 0 && w.current_id < (int)list.size()) return w.current_id;   // (Surge sets it by name on a load)
    const std::string &name = oscData().wavetable_display_name;
    for (size_t i = 0; i < list.size(); ++i)
      if (list[i].name == name) return (int)i;
    return -1;
  }
  int wtPos() {
    int id = wtCurrent();
    auto &o = wtOrder;
    for (size_t i = 0; i < o.size(); ++i)
      if (o[i] == id) return (int)i;
    return 0;
  }
  bool oscUsesWt() {
    int t = oscData().type.val.i;
    return t == ot_wavetable || t == ot_window;
  }
  void wtSelectPos(int pos) {
    auto &o = wtOrder;
    if (o.empty()) return;          // any oscillator keeps a table (Surge loads it whatever the type); it sounds once
                                    // the type is Wavetable or Window
    oscData().wt.queue_id = o[clampi(pos, 0, (int)o.size() - 1)];
    bump();
  }
  void wtStepFolder(int dir) {
    auto &st = synth->storage;
    auto &o = wtOrder;
    if (o.empty()) return;
    int pos = wtPos(), n = (int)o.size();
    int cur = st.wt_list[o[pos]].category;
    if (dir > 0) {
      while (pos < n - 1 && st.wt_list[o[pos]].category == cur) ++pos;
    } else {
      while (pos > 0 && st.wt_list[o[pos]].category == cur) --pos;
      int c = st.wt_list[o[pos]].category;
      while (pos > 0 && st.wt_list[o[pos - 1]].category == c) --pos;
    }
    wtSelectPos(pos);
  }
  std::string wtFolder() {
    auto &st = synth->storage;
    int id = wtCurrent();
    if (id < 0 || id >= (int)st.wt_list.size()) return "";
    int c = st.wt_list[id].category;
    if (c < 0 || c >= (int)st.wt_category.size()) return "";
    const char *root = c >= st.firstUserWTCategory ? "USER" : (c >= st.firstThirdPartyWTCategory ? "3RD PARTY" : "FACTORY");
    return std::string(root) + "  " + st.wt_category[c].name;
  }
  void wtRescan() {
    int id = wtCurrent();
    std::string keep = id >= 0 && id < (int)synth->storage.wt_list.size()
                           ? synth->storage.wt_list[id].path.generic_string() : "";
    synth->storage.refresh_wtlist();
    mapPictures();
    makeOrders();
    // the oscillators keep their tables; the list positions moved, so re-find each current id by its file
    (void)keep;
    bump();
  }

  // ---- step sequencer (the selected LFO's) ----
  LFOStorage &lfoData() { return patch().scene[scene()].lfo[lfoIndex()]; }
  const char *lfoLabel() {
    static const char *names[6] = {"LFO 1", "LFO 2", "LFO 3", "S-LFO 1", "S-LFO 2", "S-LFO 3"};
    return names[clampi(lfo, 0, 5)];
  }
  // STEP SEQ ON: the selected LFO's shape becomes Step Seq (that is what plays the steps)
  void seqOn() {
    setInt(&lfoData().shape, lt_stepseq);
    modNewSrc = ms_lfo1 + lfoIndex();        // a NEW routing made next (LEARN past the last one) comes from this LFO
    modSlot = (int)modSlots().size();        // ... so LEARN on the STEP SEQ page routes the steps, not an old slot
    bump();
  }
  // how many routings use the selected LFO as a source (an LFO that modulates nothing is silent)
  int lfoRoutings() {
    int src = ms_lfo1 + lfoIndex(), n = 0;
    for (const ModSlot &m : modSlots())
      if (m.src == src) ++n;
    return n;
  }
  std::string seqInfo() {
    std::string out = lfoLabel();
    if (lfoData().shape.val.i != lt_stepseq) return out + ": shape is " + lfoData().shape.get_display() + ". Press STEP SEQ ON to play the steps.";
    int n = lfoRoutings();
    if (n == 0) return out + " plays the steps, but modulates nothing yet: ROUTE, then move the control it should drive.";
    char t[64];
    snprintf(t, sizeof t, " plays the steps into %d routing%s.", n, n == 1 ? "" : "s");
    return out + t;
  }

  // ---- modulation ----
  std::vector<ModSlot> modSlots() {
    std::vector<ModSlot> out;
    int sc = scene();
    auto &P = patch();
    for (auto *list : {&P.scene[sc].modulation_voice, &P.scene[sc].modulation_scene})
      for (auto &r : *list) out.push_back({(long)(P.scene_start[sc] + r.destination_id), r.source_id, sc, r.source_index});
    for (auto &r : P.modulation_global)
      if (r.source_scene < 0 || r.source_scene == sc) out.push_back({(long)r.destination_id, r.source_id, r.source_scene < 0 ? sc : r.source_scene, r.source_index});
    return out;
  }
  bool currentMod(ModSlot &m) {
    auto v = modSlots();
    if (modSlot < 0 || modSlot >= (int)v.size()) return false;
    m = v[modSlot];
    return true;
  }
  std::string paramName(long ptag) {
    if (ptag < 0 || ptag >= (long)patch().param_ptr.size()) return "";
    return patch().param_ptr[ptag]->get_full_name();
  }
  void learnTarget(Parameter *p) {
    learn = false;
    ModSlot m;
    int src = currentMod(m) ? m.src : modNewSrc;
    int idx = currentMod(m) ? m.index : 0;
    if (!synth->isValidModulation(p->id, (modsources)src)) {
      modMsg = std::string(modsource_names[src]) + " can't modulate " + p->get_full_name();
      bump();
      return;
    }
    float depth = 0.25f;
    if (currentMod(m)) {          // re-target the routing: its depth moves to the new target
      depth = synth->getModDepth01(m.ptag, (modsources)m.src, m.srcScene, m.index);
      synth->clearModulation(m.ptag, (modsources)m.src, m.srcScene, m.index, true);
    }
    synth->setModDepth01(p->id, (modsources)src, scene(), idx, depth);
    auto v = modSlots();
    for (size_t i = 0; i < v.size(); ++i)
      if (v[i].ptag == p->id && v[i].src == src) modSlot = (int)i;
    modMsg = "";
    bump();
  }

  // ---- triggers ----
  static bool isTrigger(int i) {
    switch (i) {
      case P_WT_PREV: case P_WT_NEXT: case P_WT_CAT_PREV: case P_WT_CAT_NEXT: case P_WT_RESCAN:
      case P_PATCH_PREV: case P_PATCH_NEXT: case P_CAT_PREV: case P_CAT_NEXT: case P_PATCH_LOAD: case P_PATCH_SAVE:
      case P_PANIC: case P_MOD_LEARN: case P_MOD_CLEAR:
      case P_CAT_FACTORY: case P_CAT_3RD: case P_CAT_USER:
        return true;
      default:
        return false;
    }
  }

  bool fires(int i, float v) {
    bool fire = v >= 0.5f && (trigLast[i] < 0.5f || frames - trigAt[i] > kGestureFrames);
    trigLast[i] = v;
    if (fire) trigAt[i] = frames;
    return fire;
  }

  void action(int i) {
    switch (i) {
      case P_WT_PREV: wtSelectPos(wtPos() - 1); break;
      case P_WT_NEXT: wtSelectPos(wtPos() + 1); break;
      case P_WT_CAT_PREV: wtStepFolder(-1); break;
      case P_WT_CAT_NEXT: wtStepFolder(1); break;
      case P_WT_RESCAN: wtRescan(); break;
      case P_PATCH_PREV: browse = clampi(browse - 1, 0, numPatches() - 1); bump(); break;
      case P_PATCH_NEXT: browse = clampi(browse + 1, 0, numPatches() - 1); bump(); break;
      case P_CAT_PREV: stepCategory(-1); break;
      case P_CAT_NEXT: stepCategory(1); break;
      case P_CAT_FACTORY: jumpGroup(0); break;
      case P_CAT_3RD: jumpGroup(1); break;
      case P_CAT_USER: jumpGroup(2); break;
      case P_PATCH_LOAD: loadBrowsed(); break;
      case P_PATCH_SAVE: savePatch(); break;
      case P_PANIC: synth->allNotesOff(); break;
      case P_MOD_LEARN: learn = !learn; modMsg = learn ? "Move a control to modulate" : ""; bump(); break;
      case P_MOD_CLEAR: {
        ModSlot m;
        if (currentMod(m)) synth->clearModulation(m.ptag, (modsources)m.src, m.srcScene, m.index, true);
        bump();
        break;
      }
      default: break;
    }
  }

  // ---- set ----
  void set(const char *key, const char *val) {
    if (!strcmp(key, "state")) {
      finishLoad(true);
      sxxl::Diag::get().log("state: restoring %d bytes", (int)strlen(val));
      setState(val);
      sxxl::Diag::get().log("state: restored (%s)", loadedName.c_str());
      return;
    }
    if (!strcmp(key, "test_crash") && getenv("SXXL_TEST_CRASH")) {   // the offline test of the crash log only
      volatile int *z = nullptr;
      *z = 1;
    }
    finishLoad(false);
    if (loading) return;                       // the load owns the synth (a Q-Link moved meanwhile is dropped)
    if (!strcmp(key, "lfo_bpm")) return;
    auto it = keyIndex().find(key);
    if (it == keyIndex().end()) return;
    int i = it->second;
    const KeyDef &k = kKeys[i];
    float v = (float)atof(val);
    if (k.bind != B_ENGINE) {
      Parameter *p = resolve(k);
      if (!p) return;
      if (learn && i != P_SCENE) {
        learnTarget(p);
      }
      switch (k.bind) {
        case B_CONT: synth->setParameter01(synth->idForParameter(p), clampf(v, 0.f, 1.f), false, false); break;
        case B_INT: {
          int idx = clampi((int)lroundf(v), 0, k.nvals - 1);
          setInt(p, k.vals[idx]);
          break;
        }
        case B_BOOL: setInt(p, v >= 0.5f); break;
        case B_INTR: setInt(p, (int)lroundf(v)); break;
        default: break;
      }
      if (k.bind != B_CONT) bump();     // types, modes and the scene change what the pages show
      return;
    }
    switch (i) {
      case P_OSC_SEL: osc = clampi((int)lroundf(v), 0, n_oscs - 1); bump(); break;
      case P_LFO_SEL: lfo = clampi((int)lroundf(v), 0, 5); bump(); break;
      case P_FX_SEL: fxPos = clampi((int)lroundf(v), 0, n_fx_slots - 1); bump(); break;
      case P_WT: wtSelectPos((int)lroundf(v)); break;
      case P_PATCH: browse = clampi((int)lroundf(v), 0, std::max(0, numPatches() - 1)); bump(); break;
      case P_SEQ_ON:      // on: the LFO plays the steps; off: back to a Sine LFO
        if (v >= 0.5f) seqOn(); else if (lfoData().shape.val.i == lt_stepseq) setInt(&lfoData().shape, lt_sine);
        bump();
        break;
      case P_ROUTE_ON:
        learn = v >= 0.5f;
        modMsg = learn ? "Move a control to modulate" : "";
        bump();
        break;
      case P_FX_ON: {
        int bit = 1 << fxSlot();
        int d = patch().fx_disable.val.i;
        patch().fx_disable.val.i = v >= 0.5f ? (d & ~bit) : (d | bit);
        bump();
        break;
      }
      case P_SEQ_START: patch().stepsequences[scene()][lfoIndex()].loop_start = clampi((int)lroundf(v), 1, 16) - 1; break;
      case P_SEQ_END: patch().stepsequences[scene()][lfoIndex()].loop_end = clampi((int)lroundf(v), 1, 16) - 1; break;
      case P_MOD_SLOT: modSlot = clampi((int)lroundf(v), 1, 64) - 1; modSlot = std::min(modSlot, (int)modSlots().size()); bump(); break;
      case P_MOD_SRC: {
        int src = clampi((int)lroundf(v), 0, n_modsources - 2) + 1;
        ModSlot m;
        if (currentMod(m) && src != m.src) {          // re-route the slot from the new source
          if (synth->isValidModulation(m.ptag, (modsources)src)) {
            float d = synth->getModDepth01(m.ptag, (modsources)m.src, m.srcScene, m.index);
            synth->clearModulation(m.ptag, (modsources)m.src, m.srcScene, m.index, true);
            synth->setModDepth01(m.ptag, (modsources)src, scene(), 0, d);
            auto vv = modSlots();
            for (size_t j = 0; j < vv.size(); ++j)
              if (vv[j].ptag == m.ptag && vv[j].src == src) modSlot = (int)j;
          } else {
            modMsg = std::string(modsource_names[src]) + " can't modulate " + paramName(m.ptag);
          }
        } else {
          modNewSrc = src;
        }
        bump();
        break;
      }
      case P_MOD_DEPTH: {
        ModSlot m;
        if (currentMod(m)) synth->setModDepth01(m.ptag, (modsources)m.src, m.srcScene, m.index, clampf(v, -1.f, 1.f));
        break;
      }
      default:
        if (i >= P_SEQ_1 && i <= P_SEQ_16) {
          patch().stepsequences[scene()][lfoIndex()].steps[i - P_SEQ_1] = clampf(v, -1.f, 1.f);
        } else if (i >= P_MACRO_1 && i <= P_MACRO_8) {
          synth->setMacroParameter01(i - P_MACRO_1, clampf(v, 0.f, 1.f));
        } else if (isTrigger(i) && fires(i, v)) {
          action(i);
        }
        break;
    }
  }

  // ---- get ----
  int put(char *buf, int len, const std::string &s) { return snprintf(buf, len, "%s", s.c_str()) > 0 ? (int)strlen(buf) : 1; }

  int get(const char *key, char *buf, int len) {
    if (len <= 0) return 0;
    buf[0] = 0;
    if (!strcmp(key, "display_rev")) return snprintf(buf, len, "%u", rev);
    if (!strcmp(key, "state")) return getState(buf, len);
    finishLoad(false);
    if (loading) {                             // the last answers, until the load is done
      if (!strncmp(key, "patch_name", 10)) return put(buf, len, "Loading...");
      auto c = textCache.find(key);
      return c == textCache.end() ? 0 : put(buf, len, c->second);
    }
    int n = getNow(key, buf, len);
    if (n > 0) textCache[key].assign(buf);
    return n;
  }
  int getNow(const char *key, char *buf, int len) {
    if (!strcmp(key, "state")) return getState(buf, len);
    if (!strcmp(key, "test_removed_fx")) return snprintf(buf, len, "%d", removedFx);
    if (!strcmp(key, "test_user_dir")) return put(buf, len, userDir);
    if (!strcmp(key, "test_num_patches")) return snprintf(buf, len, "%d", numPatches());
    if (!strcmp(key, "test_num_wt")) return snprintf(buf, len, "%d", (int)wtOrder.size());
    std::string k(key);
    bool disp = false;
    if (k.size() > 8 && k.compare(k.size() - 8, 8, "_display") == 0) {
      disp = true;
      k.resize(k.size() - 8);
    }
    auto it = keyIndex().find(k);
    if (it == keyIndex().end()) return 0;
    int i = it->second;
    const KeyDef &kd = kKeys[i];
    if (kd.bind != B_ENGINE) {
      Parameter *p = resolve(kd);
      if (!p) return 0;
      if (disp) {
        if (p->ctrltype == ct_none) return put(buf, len, " ");
        char t[256];
        synth->getParameterDisplay(synth->idForParameter(p), t);
        return put(buf, len, t);
      }
      switch (kd.bind) {
        case B_CONT: return snprintf(buf, len, "%.6f", p->get_value_f01());
        case B_INT: {
          int best = 0;
          for (int j = 0; j < kd.nvals; ++j)
            if (kd.vals[j] == p->val.i) best = j;
          return snprintf(buf, len, "%d", best);
        }
        case B_BOOL: return snprintf(buf, len, "%d", p->val.b ? 1 : 0);
        case B_INTR: return snprintf(buf, len, "%d", clampi(p->val.i, (int)kd.lo, (int)kd.hi));
        default: return 0;
      }
    }
    auto &st = synth->storage;
    switch (i) {
      case P_OSC_SEL: return snprintf(buf, len, "%d", osc);
      case P_LFO_SEL: return snprintf(buf, len, "%d", lfo);
      case P_FX_SEL: return snprintf(buf, len, "%d", fxPos);
      case P_WT:
        if (disp) return put(buf, len, oscData().wavetable_display_name);
        return snprintf(buf, len, "%d", wtPos());
      case P_WT_NAME: return put(buf, len, oscData().wavetable_display_name);
      case P_WT_FOLDER: return put(buf, len, wtFolder() + (oscUsesWt() ? "" : "   (osc type: no wavetable)"));
      case P_WT_PIC: {
        int id = wtCurrent();
        int pic = id >= 0 && id < (int)wtPicOf.size() ? wtPicOf[id] : 0;
        if (disp) return snprintf(buf, len, "%d", pic);
        return snprintf(buf, len, "%d", pic);
      }
      case P_SEQ_ON: return snprintf(buf, len, "%d", lfoData().shape.val.i == lt_stepseq ? 1 : 0);
      case P_ROUTE_ON: return snprintf(buf, len, "%d", learn ? 1 : 0);
      case P_FX_ON: return snprintf(buf, len, "%d", (patch().fx_disable.val.i >> fxSlot() & 1) ? 0 : 1);
      case P_SEQ_START: return snprintf(buf, len, "%d", patch().stepsequences[scene()][lfoIndex()].loop_start + 1);
      case P_SEQ_END: return snprintf(buf, len, "%d", patch().stepsequences[scene()][lfoIndex()].loop_end + 1);
      case P_MOD_SLOT: {
        int n = (int)modSlots().size();
        if (disp) {
          char t[48];
          if (modSlot >= n) snprintf(t, sizeof t, "NEW (%d used)", n);
          else snprintf(t, sizeof t, "%d / %d", modSlot + 1, n);
          return put(buf, len, t);
        }
        return snprintf(buf, len, "%d", modSlot + 1);
      }
      case P_MOD_SRC: {
        ModSlot m;
        int src = currentMod(m) ? m.src : modNewSrc;
        return snprintf(buf, len, "%d", clampi(src - 1, 0, n_modsources - 2));
      }
      case P_MOD_DEPTH: {
        ModSlot m;
        float d = currentMod(m) ? synth->getModDepth01(m.ptag, (modsources)m.src, m.srcScene, m.index) : 0.f;
        if (disp) {
          char t[32];
          snprintf(t, sizeof t, "%+.1f %%", d * 100.f);
          return put(buf, len, t);
        }
        return snprintf(buf, len, "%.6f", d);
      }
      case P_MOD_TARGET: {
        ModSlot m;
        if (learn) return put(buf, len, "LEARN: move a control");
        return put(buf, len, currentMod(m) ? paramName(m.ptag) : std::string("(none: LEARN a target)"));
      }
      case P_MOD_INFO: return put(buf, len, modMsg);
      case P_SEQ_INFO: return put(buf, len, seqInfo());
      case P_PATCH: {
        if (disp) {
          int id = patchAt(browse);
          return put(buf, len, id >= 0 ? st.patch_list[id].name : std::string("-"));
        }
        return snprintf(buf, len, "%d", browse);
      }
      case P_PATCH_NAME: return put(buf, len, loading ? "Loading..." : loadedName);
      case P_PATCH_BROWSE: {
        int id = patchAt(browse);
        return put(buf, len, id >= 0 ? st.patch_list[id].name : std::string("-"));
      }
      case P_PATCH_CAT: {
        int id = patchAt(browse);
        return put(buf, len, id >= 0 ? categoryName(st.patch_list[id].category) : std::string(""));
      }
      default:
        if (i >= P_SEQ_1 && i <= P_SEQ_16) {
          float s = patch().stepsequences[scene()][lfoIndex()].steps[i - P_SEQ_1];
          if (disp) return snprintf(buf, len, "%+.2f", s);
          return snprintf(buf, len, "%.6f", s);
        }
        if (i >= P_MACRO_1 && i <= P_MACRO_8) {
          float m = synth->getMacroParameterTarget01(i - P_MACRO_1);   // where it is going (Surge smooths macros)
          if (disp) return snprintf(buf, len, "%d %%", (int)lroundf(m * 100.f));
          return snprintf(buf, len, "%.6f", m);
        }
        if (i >= P_MACRO_1_NAME && i <= P_MACRO_8_NAME) {
          const char *n = patch().CustomControllerLabel[i - P_MACRO_1_NAME];
          if (!n[0] || !strcmp(n, "-")) {
            char t[16];
            snprintf(t, sizeof t, "MACRO %d", i - P_MACRO_1_NAME + 1);
            return put(buf, len, t);
          }
          return put(buf, len, n);
        }
        return snprintf(buf, len, "0");     // triggers rest at 0
    }
  }

  // ---- state ----
  int getState(char *buf, int len) {
    finishLoad(false);
    if (loading) return 0;
    void *data = nullptr;
    unsigned n = synth->saveRaw(&data);
    char head[96];
    snprintf(head, sizeof head, "SXXL1 %d %d %d %d %d %d ", osc, lfo, fxPos, browse, modSlot, modNewSrc);
    // Surge's patch keeps an LFO's steps only while its shape is Step Seq; the STEP SEQ page edits any LFO's, so they
    // all go in the state too (restored after the patch)
    std::string steps = "STEPS";
    auto &P = patch();
    char t[48];
    for (int sc = 0; sc < n_scenes; ++sc)
      for (int l = 0; l < n_lfos; ++l) {
        auto &q = P.stepsequences[sc][l];
        for (int i = 0; i < n_stepseqsteps; ++i) snprintf(t, sizeof t, " %.6g", q.steps[i]), steps += t;
        snprintf(t, sizeof t, " %d %d %.6g %llu", q.loop_start, q.loop_end, q.shuffle, (unsigned long long)q.trigmask);
        steps += t;
      }
    std::string s = std::string(head) + b64enc((const unsigned char *)data, n) + " " + steps;
    if ((int)s.size() + 1 > len) return 0;     // never a cut state: the host keeps the last good one
    memcpy(buf, s.c_str(), s.size() + 1);
    return (int)s.size();
  }
  void setState(const char *s) {
    int o, l, f, b, ms, mn, used = 0;
    if (sscanf(s, "SXXL1 %d %d %d %d %d %d %n", &o, &l, &f, &b, &ms, &mn, &used) != 6 || !used) return;
    std::vector<unsigned char> raw;
    std::string body(s + used), steps;
    size_t sp = body.find(" STEPS");
    if (sp != std::string::npos) steps = body.substr(sp + 6), body.resize(sp);
    if (!b64dec(body.c_str(), raw) || raw.empty()) return;
    synth->loadRaw(raw.data(), (int)raw.size(), false);
    osc = clampi(o, 0, n_oscs - 1);
    lfo = clampi(l, 0, 5);
    fxPos = clampi(f, 0, n_fx_slots - 1);
    browse = clampi(b, 0, std::max(0, numPatches() - 1));
    loadedName = patch().name;
    if (!steps.empty()) {
      const char *q = steps.c_str();
      int nread = 0;
      for (int sc = 0; sc < n_scenes; ++sc)
        for (int l = 0; l < n_lfos; ++l) {
          auto &st = patch().stepsequences[sc][l];
          for (int i = 0; i < n_stepseqsteps; ++i) {
            float v;
            if (sscanf(q, " %f%n", &v, &nread) != 1) goto steps_done;
            st.steps[i] = v;
            q += nread;
          }
          int a, b;
          float sh;
          unsigned long long tm;
          if (sscanf(q, " %d %d %f %llu%n", &a, &b, &sh, &tm, &nread) != 4) goto steps_done;
          st.loop_start = clampi(a, 0, n_stepseqsteps - 1);
          st.loop_end = clampi(b, 0, n_stepseqsteps - 1);
          st.shuffle = sh;
          st.trigmask = tm;
          q += nread;
        }
    }
  steps_done:
    afterPatchLoad();
    modSlot = clampi(ms, 0, 63);
    modNewSrc = clampi(mn, 1, n_modsources - 1);
  }

  // ---- MIDI ----
  void midi(const uint8_t *m, int n) {
    if (n < 1 || loading) return;              // the load stops every voice anyway
    int st = m[0] & 0xf0, ch = m[0] & 0x0f;
    int d1 = n > 1 ? m[1] & 0x7f : 0, d2 = n > 2 ? m[2] & 0x7f : 0;
    switch (st) {
      case 0x90:
        if (d2) synth->playNote(ch, d1, d2, 0);
        else synth->releaseNote(ch, d1, 0);
        break;
      case 0x80: synth->releaseNote(ch, d1, d2); break;
      case 0xa0: synth->polyAftertouch(ch, d1, d2); break;
      case 0xb0:
        if (d1 == 120 || d1 == 123) synth->allNotesOff();
        else synth->channelController(ch, d1, d2);
        break;
      case 0xd0: synth->channelAftertouch(ch, d1); break;
      case 0xe0: synth->pitchBend(ch, (d2 << 7 | d1) - 8192); break;
      default: break;
    }
  }

  // ---- audio ----
  void songPos(double p, double b, int play, int nframes) {
    (void)nframes;
    if (loading) return;
    if (b > 0) bpm = b;
    playing = play;
    ppq = p;
    synth->time_data.tempo = bpm;
    if (p >= 0) synth->time_data.ppqPos = p;
  }

  void surgeBlock() {
    synth->process();
    if (!playing || ppq < 0) synth->time_data.ppqPos += BLOCK_SIZE * bpm / 60.0 / kSampleRate;
    memcpy(outL, synth->output[0], sizeof outL);
    memcpy(outR, synth->output[1], sizeof outR);
    outPos = 0;
    if (synth->patchChanged.exchange(false)) afterPatchLoad();
    if (revAgain > 0 && --revAgain == 0) ++rev;
  }

  void render(int16_t *out, int n) {
    ScopedDenormalDisable ftz;
    if ((int)bufL.size() < n) bufL.resize(n), bufR.resize(n);
    finishLoad(false);
    if (loading) {                             // silence while the patch loads
      memset(out, 0, sizeof(int16_t) * 2 * n);
      frames += n;
      return;
    }
    for (int i = 0; i < n; ++i) {
      if (outPos >= BLOCK_SIZE) surgeBlock();
      bufL[i] = outL[outPos];
      bufR[i] = outR[outPos];
      ++outPos;
    }
    for (int i = 0; i < n; ++i)
      if (!std::isfinite(bufL[i]) || !std::isfinite(bufR[i])) bufL[i] = bufR[i] = 0.f;   // never a NaN to MPC
    lim.Process(bufL.data(), bufR.data(), n, 0.0f, -0.3f, 100.0f, kSampleRate);
    for (int i = 0; i < n; ++i) {
      out[2 * i] = (int16_t)lroundf(clampf(bufL[i], -1.f, 1.f) * 32767.f);
      out[2 * i + 1] = (int16_t)lroundf(clampf(bufR[i], -1.f, 1.f) * 32767.f);
    }
    frames += n;
  }
};

// ---- the engine interface ---------------------------------------------------------------------------------------
// No exception may leave the plugin (it would end MPC): each entry point catches, logs and carries on.
#define GUARD(WHERE_, FAIL_)                                                          \
  catch (const std::exception &ex_) {                                             \
    sxxl::Diag::get().log("%s: exception %s", WHERE_, ex_.what());                    \
    FAIL_;                                                                        \
  }                                                                               \
  catch (...) {                                                                   \
    sxxl::Diag::get().log("%s: unknown exception", WHERE_);                         \
    FAIL_;                                                                        \
  }
void *e_create(const char *dir) {
  try {
    Inst *s = new Inst();
    if (!s->init(dir)) {
      delete s;
      return nullptr;
    }
    return s;
  }
  GUARD("create", return nullptr)
}
void e_destroy(void *p) {
  try { delete (Inst *)p; }
  GUARD("destroy", return)
}
void e_midi(void *p, const uint8_t *m, int n) {
  try { ((Inst *)p)->midi(m, n); }
  GUARD("midi", return)
}
void e_set(void *p, const char *k, const char *v) {
  try { ((Inst *)p)->set(k, v); }
  GUARD(k, return)
}
int e_get(void *p, const char *k, char *b, int n) {
  try { return ((Inst *)p)->get(k, b, n); }
  GUARD(k, return 0)
}
void e_render(void *p, int16_t *o, int n) {
  try { ((Inst *)p)->render(o, n); }
  GUARD("render", memset(o, 0, sizeof(int16_t) * 2 * n); return)
}
void e_song_pos(void *p, double ppq, double bpm, int playing, int n) {
  try { ((Inst *)p)->songPos(ppq, bpm, playing, n); }
  GUARD("song_pos", return)
}

const mpc_engine_t kEngine = {e_create, e_destroy, e_midi, e_set, e_get, e_render, nullptr, e_song_pos};

}  // namespace

extern "C" const mpc_engine_t *mpc_engine(void) { return &kEngine; }
