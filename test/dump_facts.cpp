// SPDX-License-Identifier: GPL-3.0-or-later
// Writes tools/surge_facts.json: Surge's own parameter names, option labels and per-type oscillator and FX parameter names,
// from the vendored engine, for tools/gen_params.py and tools/panel.py.   dump_facts <Surge data folder> > tools/surge_facts.json
#include "SurgeSynthesizer.h"
#include "Oscillator.h"
#include "Effect.h"
#include <cstdio>
#include <unistd.h>
#include <string>
struct PL : SurgeSynthesizer::PluginLayer {
  void surgeParameterUpdated(const SurgeSynthesizer::ID &, float) override {}
  void surgeMacroUpdated(long, float) override {}
};
static std::string esc(const char *s){ std::string o; for(;*s;s++){ if(*s=='"'||*s=='\\') o+='\\'; o+=*s;} return o; }
static void param(Parameter &p, bool last=false, bool opts=true){
  printf("{\"id\":%d,\"name\":\"%s\",\"full\":\"%s\",\"storage\":\"%s\",\"ct\":%d,\"vt\":%d", p.id, esc(p.get_name()).c_str(), esc(p.get_full_name()).c_str(), esc(p.get_storage_name()).c_str(), p.ctrltype, p.valtype);
  if (p.valtype==vt_int && opts){
    printf(",\"min\":%d,\"max\":%d,\"def\":%d,\"opts\":[", p.val_min.i, p.val_max.i, p.val_default.i);
    int keep=p.val.i;
    for(int i=p.val_min.i;i<=p.val_max.i && i-p.val_min.i<400;i++){ p.val.i=i; char t[256]; p.get_display(t); printf("%s\"%s\"", i>p.val_min.i?",":"", esc(t).c_str()); }
    p.val.i=keep; printf("]");
  } else if (p.valtype==vt_bool) printf(",\"def\":%d", (int)p.val_default.b);
  else if (p.valtype==vt_float) printf(",\"min\":%g,\"max\":%g,\"def\":%g", p.val_min.f, p.val_max.f, p.val_default.f);
  printf("}%s\n", last?"":",");
}
int main(int argc,char**argv){
  PL pl; auto *s = new SurgeSynthesizer(&pl, argv[1]); s->setSamplerate(44100);
  for(int k=0;k<100;k++){ s->process(); usleep(1000);} 
  auto &P = s->storage.getPatch(); auto &sc = P.scene[0];
  printf("{\"scene\":[\n");
  for (auto *pp : P.param_ptr) { if (pp->scene==1) param(*pp); }
  printf("{\"end\":1}],\n\"global\":[\n");
  for (auto *pp : P.param_ptr) { if (pp->scene==0) param(*pp); }
  printf("{\"end\":1}],\n\"osc_types\":[\n");
  for (int t=0;t<n_osc_types;t++){
    sc.osc[0].type.val.i=t;
    unsigned char buf[oscillator_buffer_size];
    auto *o = spawn_osc(t, &s->storage, &sc.osc[0], nullptr, buf);
    if (o){ o->init_ctrltypes(); o->init_default_values(); }
    printf("{\"type\":%d,\"name\":\"%s\",\"params\":[\n", t, osc_type_names[t]);
    for(int i=0;i<n_osc_params;i++) param(sc.osc[0].p[i], i==n_osc_params-1);
    printf("]}%s\n", t==n_osc_types-1?"":",");
    if (o) o->~Oscillator();
  }
  printf("],\n\"fx_types\":[\n");
  for (int t=0;t<n_fx_types;t++){
    auto &fx = P.fx[0]; fx.type.val.i=t;
    Effect *e = spawn_effect(t, &s->storage, &fx, P.globaldata);
    if (e){ e->init_ctrltypes(); e->init_default_values(); } else { for(int i=0;i<n_fx_params;i++) fx.p[i].set_type(ct_none); }
    printf("{\"type\":%d,\"name\":\"%s\",\"groups\":[", t, fx_type_names[t]);
    bool first=true;
    if (e) for(int g=0; g<16; g++){ const char *gl=e->group_label(g); if(!gl) continue; printf("%s{\"i\":%d,\"label\":\"%s\",\"y\":%d}", first?"":",", g, esc(gl).c_str(), e->group_label_ypos(g)); first=false; }
    printf("],\"params\":[\n");
    for(int i=0;i<n_fx_params;i++){ auto &p=fx.p[i]; printf("{\"i\":%d,\"name\":\"%s\",\"ct\":%d,\"posy\":%d,\"posy_offset\":%d,\"vt\":%d}%s\n", i, esc(p.get_name()).c_str(), p.ctrltype, p.posy, p.posy_offset, p.valtype, i==n_fx_params-1?"":","); }
    printf("]}%s\n", t==n_fx_types-1?"":",");
    delete e;
  }
  printf("],\n\"mod_sources\":[");
  for (int m=0;m<n_modsources;m++) printf("%s\"%s\"", m?",":"", esc(modsource_names[m]).c_str());
  printf("],\n\"wt\":%zu,\"patches\":%zu}\n", s->storage.wt_list.size(), s->storage.patch_list.size());
  for(int k=0;k<20;k++){ s->process(); usleep(1000);} 
  delete s;
}
