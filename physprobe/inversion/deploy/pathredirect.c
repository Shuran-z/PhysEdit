// LD_PRELOAD path redirection for the A800 evaluation host (no root, so the original absolute layout cannot be
// created). Any path beginning with one of FROM[i] is rewritten to TO[i] before the real libc call. Files keep their
// original bytes (the author's renderers verify sha256 of background profiles that embed absolute paths).
// Build: gcc -shared -fPIC -O2 -o libpathredirect.so pathredirect.c -ldl
#define _GNU_SOURCE
#include <dlfcn.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <dirent.h>
#include <unistd.h>
#include <utime.h>

static const char *FROM[] = {"/home/wangzijun_p25", "/data_cached/wangzijun_p25"};
static const char *TO[] = {"/workspace/wz/home/wangzijun_p25", "/workspace/wz/data_cached/wangzijun_p25"};
static __thread char B1[8192], B2[8192];

static const char *map(const char *p, char *buf) {
    if (!p || p[0] != '/') return p;
    for (unsigned i = 0; i < sizeof(FROM) / sizeof(FROM[0]); i++) {
        size_t n = strlen(FROM[i]);
        if (strncmp(p, FROM[i], n) == 0 && (p[n] == '/' || p[n] == 0)) {
            if (strlen(TO[i]) + strlen(p + n) + 1 > 8192) return p;
            strcpy(buf, TO[i]); strcat(buf, p + n); return buf;
        }
    }
    return p;
}
#define REAL(name) static __typeof__(&name) real_##name; if (!real_##name) real_##name = dlsym(RTLD_NEXT, #name)

int open(const char *p, int f, ...) { REAL(open); mode_t m = 0; if (f & (O_CREAT | O_TMPFILE)) { va_list a; va_start(a, f); m = va_arg(a, mode_t); va_end(a); } return real_open(map(p, B1), f, m); }
int open64(const char *p, int f, ...) { REAL(open64); mode_t m = 0; if (f & (O_CREAT | O_TMPFILE)) { va_list a; va_start(a, f); m = va_arg(a, mode_t); va_end(a); } return real_open64(map(p, B1), f, m); }
int openat(int d, const char *p, int f, ...) { REAL(openat); mode_t m = 0; if (f & (O_CREAT | O_TMPFILE)) { va_list a; va_start(a, f); m = va_arg(a, mode_t); va_end(a); } return real_openat(d, map(p, B1), f, m); }
int openat64(int d, const char *p, int f, ...) { REAL(openat64); mode_t m = 0; if (f & (O_CREAT | O_TMPFILE)) { va_list a; va_start(a, f); m = va_arg(a, mode_t); va_end(a); } return real_openat64(d, map(p, B1), f, m); }
FILE *fopen(const char *p, const char *m) { REAL(fopen); return real_fopen(map(p, B1), m); }
FILE *fopen64(const char *p, const char *m) { REAL(fopen64); return real_fopen64(map(p, B1), m); }
int stat(const char *p, struct stat *s) { REAL(stat); return real_stat(map(p, B1), s); }
int stat64(const char *p, struct stat64 *s) { REAL(stat64); return real_stat64(map(p, B1), s); }
int lstat(const char *p, struct stat *s) { REAL(lstat); return real_lstat(map(p, B1), s); }
int lstat64(const char *p, struct stat64 *s) { REAL(lstat64); return real_lstat64(map(p, B1), s); }
int fstatat(int d, const char *p, struct stat *s, int f) { REAL(fstatat); return real_fstatat(d, map(p, B1), s, f); }
int fstatat64(int d, const char *p, struct stat64 *s, int f) { REAL(fstatat64); return real_fstatat64(d, map(p, B1), s, f); }
int statx(int d, const char *p, int f, unsigned int mk, struct statx *s) { REAL(statx); return real_statx(d, map(p, B1), f, mk, s); }
// legacy versioned entry points still referenced by the conda python binary
int __xstat(int v, const char *p, struct stat *s) { static int (*r)(int, const char *, struct stat *); if (!r) r = dlsym(RTLD_NEXT, "__xstat"); return r(v, map(p, B1), s); }
int __xstat64(int v, const char *p, struct stat64 *s) { static int (*r)(int, const char *, struct stat64 *); if (!r) r = dlsym(RTLD_NEXT, "__xstat64"); return r(v, map(p, B1), s); }
int __lxstat(int v, const char *p, struct stat *s) { static int (*r)(int, const char *, struct stat *); if (!r) r = dlsym(RTLD_NEXT, "__lxstat"); return r(v, map(p, B1), s); }
int __lxstat64(int v, const char *p, struct stat64 *s) { static int (*r)(int, const char *, struct stat64 *); if (!r) r = dlsym(RTLD_NEXT, "__lxstat64"); return r(v, map(p, B1), s); }
int __fxstatat(int v, int d, const char *p, struct stat *s, int f) { static int (*r)(int, int, const char *, struct stat *, int); if (!r) r = dlsym(RTLD_NEXT, "__fxstatat"); return r(v, d, map(p, B1), s, f); }
int __fxstatat64(int v, int d, const char *p, struct stat64 *s, int f) { static int (*r)(int, int, const char *, struct stat64 *, int); if (!r) r = dlsym(RTLD_NEXT, "__fxstatat64"); return r(v, d, map(p, B1), s, f); }
int access(const char *p, int m) { REAL(access); return real_access(map(p, B1), m); }
int faccessat(int d, const char *p, int m, int f) { REAL(faccessat); return real_faccessat(d, map(p, B1), m, f); }
DIR *opendir(const char *p) { REAL(opendir); return real_opendir(map(p, B1)); }
ssize_t readlink(const char *p, char *b, size_t n) { REAL(readlink); return real_readlink(map(p, B1), b, n); }
ssize_t readlinkat(int d, const char *p, char *b, size_t n) { REAL(readlinkat); return real_readlinkat(d, map(p, B1), b, n); }
int mkdir(const char *p, mode_t m) { REAL(mkdir); return real_mkdir(map(p, B1), m); }
int chdir(const char *p) { REAL(chdir); return real_chdir(map(p, B1)); }
int unlink(const char *p) { REAL(unlink); return real_unlink(map(p, B1)); }
int rmdir(const char *p) { REAL(rmdir); return real_rmdir(map(p, B1)); }
int rename(const char *a, const char *b) { REAL(rename); return real_rename(map(a, B1), map(b, B2)); }
void *dlopen(const char *p, int f) { REAL(dlopen); return real_dlopen(map(p, B1), f); }
int execve(const char *p, char *const a[], char *const e[]) { REAL(execve); return real_execve(map(p, B1), a, e); }
int execv(const char *p, char *const a[]) { REAL(execv); return real_execv(map(p, B1), a); }
int truncate(const char *p, off_t n) { REAL(truncate); return real_truncate(map(p, B1), n); }
int utime(const char *p, const struct utimbuf *t) { REAL(utime); return real_utime(map(p, B1), t); }
int utimensat(int d, const char *p, const struct timespec t[2], int f) { REAL(utimensat); return real_utimensat(d, map(p, B1), t, f); }
char *realpath(const char *p, char *r) {
    REAL(realpath);
    char *o = real_realpath(map(p, B1), r);   // result keeps the mapped location; callers only use it to open files
    return o;
}
