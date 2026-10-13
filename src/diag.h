// SPDX-License-Identifier: GPL-3.0-or-later
// SurgeXXL's crash log: <user folder>/surgexxl.log (/sdcard/SurgeXXL/surgexxl.log on a Force).
//
// A plugin crash takes MPC down ("Your Force recovered from an internal error") and leaves nothing behind, so the
// plugin writes its own trail: a line per event that matters (instance made, LOAD started and finished, a state
// restored, any exception caught), and, if MPC is about to die of a signal (SIGSEGV, SIGBUS, SIGILL, SIGFPE, SIGABRT),
// the signal, the faulting address, the program counter and link register and a backtrace, each as an offset into
// surgexxl.so (the release keeps its symbol table, so an offset names the function), then MPC's own handler runs as
// before. Every thread the plugin makes gets an alternate signal stack, so a stack overflow is logged too.
#pragma once
#include <execinfo.h>
#include <sys/syscall.h>
#include <fcntl.h>
#include <signal.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <ucontext.h>
#include <unistd.h>

#include <string>

namespace sxxl {

struct Diag {
  int fd = -1;
  uintptr_t lo = 0, hi = 0;        // surgexxl.so's mapped range
  struct sigaction old[32];
  bool installed = false;

  static Diag &get() {
    static Diag d;
    return d;
  }

  // a hex number into buf (async-signal-safe), returns the end
  static char *hex(char *p, uintptr_t v) {
    char t[2 * sizeof v + 1];
    int n = 0;
    do t[n++] = "0123456789abcdef"[v & 15], v >>= 4; while (v);
    *p++ = '0', *p++ = 'x';
    while (n) *p++ = t[--n];
    return p;
  }
  static char *str(char *p, const char *s) {
    while (*s) *p++ = *s++;
    return p;
  }
  void raw(const char *s, size_t n) {
    if (fd >= 0) {
      ssize_t r = write(fd, s, n);
      (void)r;
    }
  }
  // "name+0x123 (surgexxl.so)" or the absolute address when it is not ours
  char *where(char *p, uintptr_t a) {
    if (a >= lo && a < hi) return str(hex(str(p, "surgexxl.so+"), a - lo), "");
    return hex(p, a);
  }

  void open(const std::string &dir) {
    if (fd >= 0) return;
    mkdir(dir.c_str(), 0755);
    std::string path = dir + "/surgexxl.log";
    struct stat st;
    int flags = O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC;
    if (stat(path.c_str(), &st) == 0 && st.st_size > 512 * 1024) flags |= O_TRUNC;   // keep it small
    fd = ::open(path.c_str(), flags, 0644);
    findSelf();
  }

  void findSelf() {
    FILE *m = fopen("/proc/self/maps", "r");
    if (!m) return;
    char line[512];
    while (fgets(line, sizeof line, m)) {
      if (!strstr(line, "surgexxl")) continue;
      unsigned long a, b;
      if (sscanf(line, "%lx-%lx", &a, &b) != 2) continue;
      if (!lo || a < lo) lo = a;
      if (b > hi) hi = b;
    }
    fclose(m);
  }

  void log(const char *fmt, ...) {
    if (fd < 0) return;
    char buf[1024];
    time_t t = time(nullptr);
    struct tm tm;
    localtime_r(&t, &tm);
    int n = (int)strftime(buf, sizeof buf, "%Y-%m-%d %H:%M:%S ", &tm);
    va_list ap;
    va_start(ap, fmt);
    int m = vsnprintf(buf + n, sizeof buf - n - 1, fmt, ap);
    va_end(ap);
    if (m < 0) m = 0;
    n += m < (int)sizeof buf - n - 1 ? m : (int)sizeof buf - n - 2;
    buf[n++] = '\n';
    raw(buf, n);
  }

  static void altStack() {
    static thread_local char *mem = nullptr;
    if (mem) return;
    const size_t sz = 64 * 1024;
    mem = (char *)malloc(sz);
    if (!mem) return;
    stack_t ss;
    memset(&ss, 0, sizeof ss);
    ss.ss_sp = mem;
    ss.ss_size = sz;
    sigaltstack(&ss, nullptr);
  }

  void install() {
    if (installed) return;
    installed = true;
    altStack();
    void *prime[2];
    backtrace(prime, 2);                // loads the unwinder now, not inside the handler
    static const int sigs[] = {SIGSEGV, SIGBUS, SIGILL, SIGFPE, SIGABRT};
    for (int s : sigs) {
      struct sigaction sa;
      memset(&sa, 0, sizeof sa);
      sa.sa_sigaction = onSignal;
      sa.sa_flags = SA_SIGINFO | SA_ONSTACK;
      sigemptyset(&sa.sa_mask);
      sigaction(s, &sa, &old[s]);
    }
  }

  static void onSignal(int sig, siginfo_t *si, void *uc) {
    Diag &d = get();
    char b[256], *p = b;
    p = str(p, "*** signal ");
    p = hex(p, (uintptr_t)sig);
    p = str(p, " (");
    p = str(p, sig == SIGSEGV ? "SIGSEGV" : sig == SIGBUS ? "SIGBUS" : sig == SIGILL ? "SIGILL" : sig == SIGFPE ? "SIGFPE" : "SIGABRT");
    p = str(p, ") thread ");
    p = hex(p, (uintptr_t)syscall(SYS_gettid));
    p = str(p, " fault addr ");
    p = hex(p, (uintptr_t)si->si_addr);
#if defined(__arm__)
    const ucontext_t *u = (const ucontext_t *)uc;
    p = str(p, " pc ");
    p = d.where(p, (uintptr_t)u->uc_mcontext.arm_pc);
    p = str(p, " lr ");
    p = d.where(p, (uintptr_t)u->uc_mcontext.arm_lr);
    p = str(p, " sp ");
    p = hex(p, (uintptr_t)u->uc_mcontext.arm_sp);
#else
    (void)uc;
#endif
    *p++ = '\n';
    d.raw(b, p - b);
    sigaction(sig, &d.old[sig], nullptr);   // from here a fault inside this handler goes straight to MPC's
    void *frames[48];
    int n = backtrace(frames, 48);
    for (int i = 0; i < n; ++i) {
      p = str(b, "  #");
      p = hex(p, (uintptr_t)i);
      *p++ = ' ';
      p = d.where(p, (uintptr_t)frames[i]);
      *p++ = '\n';
      d.raw(b, p - b);
    }
#if defined(__arm__)
    // backtrace() needs libgcc_s and may find nothing on ARM: also list the words on the stack that point into
    // surgexxl.so's code (likely return addresses, innermost first)
    if (d.lo) {
      d.raw("  stack words into surgexxl.so:\n", 33);
      const uintptr_t *w = (const uintptr_t *)u->uc_mcontext.arm_sp;
      int shown = 0;
      for (int i = 0; i < 1024 && shown < 40; ++i) {
        uintptr_t v = w[i];
        if (v >= d.lo && v < d.hi) {
          p = str(b, "    ");
          p = d.where(p, v);
          *p++ = '\n';
          d.raw(b, p - b);
          ++shown;
        }
      }
    }
#endif
    // the executable mappings, to place addresses outside surgexxl.so
    int m = ::open("/proc/self/maps", O_RDONLY);
    if (m >= 0) {
      d.raw("  executable maps:\n", 19);
      char mb[4096], line[512];
      int ln = 0;
      ssize_t r;
      while ((r = read(m, mb, sizeof mb)) > 0)
        for (ssize_t i = 0; i < r; ++i) {
          if (ln < (int)sizeof line - 1) line[ln++] = mb[i];
          if (mb[i] != '\n') continue;
          if (ln > 24 && memchr(line, 'x', 24)) d.raw(line, ln);   // the perms field: r-xp
          ln = 0;
        }
      close(m);
    }
    // MPC's own handler, as if we were never here
    sigaction(sig, &d.old[sig], nullptr);
    if (sig == SIGABRT) raise(sig);     // a fault re-runs the instruction and lands in the old handler
  }
};

}  // namespace sxxl
