#include "pen.h"

#include <windows.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ---------------------------------------------------------------- sb ---- */

void sb_init(sb *b) {
    b->data = NULL;
    b->len = 0;
    b->cap = 0;
}

void sb_free(sb *b) {
    free(b->data);
    sb_init(b);
}

static void sb_reserve(sb *b, size_t extra) {
    size_t need = b->len + extra + 1;
    if (need <= b->cap) return;
    size_t cap = b->cap ? b->cap : 256;
    while (cap < need) cap *= 2;
    char *p = (char *)realloc(b->data, cap);
    if (!p) {
        fputs("penctl: out of memory\n", stderr);
        exit(70);
    }
    b->data = p;
    b->cap = cap;
}

void sb_putn(sb *b, const char *s, size_t n) {
    if (!s || n == 0) return;
    sb_reserve(b, n);
    memcpy(b->data + b->len, s, n);
    b->len += n;
    b->data[b->len] = '\0';
}

void sb_puts(sb *b, const char *s) {
    if (s) sb_putn(b, s, strlen(s));
}

void sb_putc(sb *b, char c) {
    sb_putn(b, &c, 1);
}

void sb_printf(sb *b, const char *fmt, ...) {
    char tmp[4096];
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf(tmp, sizeof tmp, fmt, ap);
    va_end(ap);
    if (n < 0) return;
    if ((size_t)n < sizeof tmp) {
        sb_putn(b, tmp, (size_t)n);
        return;
    }
    char *big = (char *)malloc((size_t)n + 1);
    if (!big) return;
    va_start(ap, fmt);
    vsnprintf(big, (size_t)n + 1, fmt, ap);
    va_end(ap);
    sb_putn(b, big, (size_t)n);
    free(big);
}

void sb_put_json_str(sb *b, const char *s) {
    sb_putc(b, '"');
    if (s) {
        for (const unsigned char *p = (const unsigned char *)s; *p; ++p) {
            unsigned char c = *p;
            switch (c) {
            case '"': sb_puts(b, "\\\""); break;
            case '\\': sb_puts(b, "\\\\"); break;
            case '\n': sb_puts(b, "\\n"); break;
            case '\r': sb_puts(b, "\\r"); break;
            case '\t': sb_puts(b, "\\t"); break;
            default:
                if (c < 0x20) {
                    char esc[8];
                    snprintf(esc, sizeof esc, "\\u%04x", (unsigned)c);
                    sb_puts(b, esc);
                } else {
                    sb_putc(b, (char)c);
                }
            }
        }
    }
    sb_putc(b, '"');
}

/* --------------------------------------------------------- utf8 <-> utf16 */

wchar_t *pen_utf8_to_wide(const char *s) {
    if (!s) return NULL;
    int n = MultiByteToWideChar(CP_UTF8, 0, s, -1, NULL, 0);
    if (n <= 0) return NULL;
    wchar_t *w = (wchar_t *)malloc(sizeof(wchar_t) * (size_t)n);
    if (!w) return NULL;
    MultiByteToWideChar(CP_UTF8, 0, s, -1, w, n);
    return w;
}

char *pen_wide_to_utf8(const wchar_t *w) {
    if (!w) return NULL;
    int n = WideCharToMultiByte(CP_UTF8, 0, w, -1, NULL, 0, NULL, NULL);
    if (n <= 0) return NULL;
    char *s = (char *)malloc((size_t)n);
    if (!s) return NULL;
    WideCharToMultiByte(CP_UTF8, 0, w, -1, s, n, NULL, NULL);
    return s;
}

char *pen_strdup(const char *s) {
    if (!s) return NULL;
    size_t n = strlen(s);
    char *p = (char *)malloc(n + 1);
    if (!p) return NULL;
    memcpy(p, s, n + 1);
    return p;
}

char *pen_trim_dup(const char *s) {
    if (!s) return pen_strdup("");
    const char *a = s;
    while (*a == ' ' || *a == '\t' || *a == '\r' || *a == '\n') ++a;
    const char *b = a + strlen(a);
    while (b > a && (b[-1] == ' ' || b[-1] == '\t' || b[-1] == '\r' || b[-1] == '\n')) --b;
    size_t n = (size_t)(b - a);
    char *p = (char *)malloc(n + 1);
    if (!p) return NULL;
    memcpy(p, a, n);
    p[n] = '\0';
    return p;
}

/* ----------------------------------------------------------------- wsb -- */

void wsb_init(wsb *b) {
    b->buf = NULL;
    b->len = 0;
    b->cap = 0;
}

void wsb_free(wsb *b) {
    free(b->buf);
    wsb_init(b);
}

static void wsb_reserve(wsb *b, size_t extra) {
    size_t need = b->len + extra + 1;
    if (need <= b->cap) return;
    size_t cap = b->cap ? b->cap : 256;
    while (cap < need) cap *= 2;
    wchar_t *p = (wchar_t *)realloc(b->buf, cap * sizeof(wchar_t));
    if (!p) {
        fputs("penctl: out of memory\n", stderr);
        exit(70);
    }
    b->buf = p;
    b->cap = cap;
}

static void wsb_putc(wsb *b, wchar_t c) {
    wsb_reserve(b, 1);
    b->buf[b->len++] = c;
    b->buf[b->len] = L'\0';
}

static void wsb_putw(wsb *b, const wchar_t *s) {
    if (!s) return;
    size_t n = wcslen(s);
    wsb_reserve(b, n);
    memcpy(b->buf + b->len, s, n * sizeof(wchar_t));
    b->len += n;
    b->buf[b->len] = L'\0';
}

/* Append one argument, quoting it the way the MSVC/CRT command-line parser
 * expects, so programs built with CommandLineToArgvW-style parsing (adb) see
 * exactly the bytes we intended. */
static void wsb_put_quoted(wsb *b, const wchar_t *arg) {
    int need_quotes = (arg[0] == L'\0');
    for (const wchar_t *p = arg; *p; ++p) {
        if (*p == L' ' || *p == L'\t' || *p == L'"') {
            need_quotes = 1;
            break;
        }
    }
    if (!need_quotes) {
        wsb_putw(b, arg);
        return;
    }
    wsb_putc(b, L'"');
    size_t backslashes = 0;
    for (const wchar_t *p = arg; *p; ++p) {
        if (*p == L'\\') {
            ++backslashes;
            continue;
        }
        if (*p == L'"') {
            for (size_t i = 0; i < backslashes * 2 + 1; ++i) wsb_putc(b, L'\\');
            wsb_putc(b, L'"');
            backslashes = 0;
            continue;
        }
        for (size_t i = 0; i < backslashes; ++i) wsb_putc(b, L'\\');
        backslashes = 0;
        wsb_putc(b, *p);
    }
    for (size_t i = 0; i < backslashes * 2; ++i) wsb_putc(b, L'\\');
    wsb_putc(b, L'"');
}

void wsb_arg(wsb *b, const char *arg) {
    wchar_t *w = pen_utf8_to_wide(arg ? arg : "");
    if (!w) return;
    if (b->len > 0) wsb_putc(b, L' ');
    wsb_put_quoted(b, w);
    free(w);
}

void wsb_argw(wsb *b, const wchar_t *arg) {
    if (!arg) return;
    if (b->len > 0) wsb_putc(b, L' ');
    wsb_put_quoted(b, arg);
}

const wchar_t *wsb_cstr(wsb *b) {
    return b->buf ? b->buf : L"";
}

/* ------------------------------------------------------------ processes -- */

typedef struct {
    HANDLE h;
    sb    *b;
} reader_arg;

static void close_if(HANDLE *h) {
    if (*h && *h != INVALID_HANDLE_VALUE) {
        CloseHandle(*h);
        *h = NULL;
    }
}

static DWORD WINAPI reader_main(LPVOID param) {
    reader_arg *r = (reader_arg *)param;
    char buf[8192];
    DWORD got = 0;
    while (ReadFile(r->h, buf, (DWORD)sizeof buf, &got, NULL) && got > 0) {
        if (r->b->len + got > PENCTL_MAX_OUT) break;
        sb_putn(r->b, buf, got);
    }
    return 0;
}

/* Some hardened/sandboxed environments deny CreatePipe; fall back to temp files. */
static int make_temp_path(wchar_t *path) {
    wchar_t dir[MAX_PATH];
    DWORD n = GetTempPathW(MAX_PATH, dir);
    if (n == 0 || n >= MAX_PATH) return 0;
    return GetTempFileNameW(dir, L"pen", 0, path) != 0;
}

static void read_temp_file(HANDLE h, sb *b) {
    LARGE_INTEGER zero;
    zero.QuadPart = 0;
    if (!SetFilePointerEx(h, zero, NULL, FILE_BEGIN)) return;
    char buf[8192];
    DWORD got = 0;
    while (ReadFile(h, buf, (DWORD)sizeof buf, &got, NULL) && got > 0) {
        if (b->len + got > PENCTL_MAX_OUT) break;
        sb_putn(b, buf, got);
    }
}

int pen_run(const wchar_t *cmdline, const char *stdin_utf8, proc_result *r, int timeout_ms) {    memset(r, 0, sizeof *r);
    sb_init(&r->out);
    sb_init(&r->err);
    if (!cmdline || !cmdline[0]) {
        r->spawn_error = ERROR_INVALID_PARAMETER;
        return -1;
    }

    SECURITY_ATTRIBUTES sa;
    sa.nLength = sizeof sa;
    sa.lpSecurityDescriptor = NULL;
    sa.bInheritHandle = TRUE;

    HANDLE out_r = NULL, out_w = NULL, err_r = NULL, err_w = NULL;
    HANDLE in_r = NULL, in_w = NULL, nul = NULL;
    wchar_t out_path[MAX_PATH] = {0}, err_path[MAX_PATH] = {0}, in_path[MAX_PATH] = {0};
    int out_file = 0, err_file = 0;
    int rc = -1;

    if (CreatePipe(&out_r, &out_w, &sa, 64 * 1024)) {
        if (!SetHandleInformation(out_r, HANDLE_FLAG_INHERIT, 0)) goto done;
    } else {
        out_r = NULL;
        if (!make_temp_path(out_path)) goto done;
        out_w = CreateFileW(out_path, GENERIC_READ | GENERIC_WRITE,
                            FILE_SHARE_READ | FILE_SHARE_WRITE, &sa, CREATE_ALWAYS,
                            FILE_ATTRIBUTE_TEMPORARY, NULL);
        if (out_w == INVALID_HANDLE_VALUE) {
            out_w = NULL;
            goto done;
        }
        out_file = 1;
    }

    if (CreatePipe(&err_r, &err_w, &sa, 64 * 1024)) {
        if (!SetHandleInformation(err_r, HANDLE_FLAG_INHERIT, 0)) goto done;
    } else {
        err_r = NULL;
        if (!make_temp_path(err_path)) goto done;
        err_w = CreateFileW(err_path, GENERIC_READ | GENERIC_WRITE,
                            FILE_SHARE_READ | FILE_SHARE_WRITE, &sa, CREATE_ALWAYS,
                            FILE_ATTRIBUTE_TEMPORARY, NULL);
        if (err_w == INVALID_HANDLE_VALUE) {
            err_w = NULL;
            goto done;
        }
        err_file = 1;
    }

    HANDLE child_stdin;
    if (stdin_utf8) {
        if (CreatePipe(&in_r, &in_w, &sa, 64 * 1024)) {
            if (!SetHandleInformation(in_w, HANDLE_FLAG_INHERIT, 0)) goto done;
            child_stdin = in_r;
        } else {
            in_w = NULL;
            if (!make_temp_path(in_path)) goto done;
            in_r = CreateFileW(in_path, GENERIC_READ | GENERIC_WRITE,
                               FILE_SHARE_READ | FILE_SHARE_WRITE, &sa, CREATE_ALWAYS,
                               FILE_ATTRIBUTE_TEMPORARY, NULL);
            if (in_r == INVALID_HANDLE_VALUE) {
                in_r = NULL;
                goto done;
            }
            DWORD wrote = 0;
            WriteFile(in_r, stdin_utf8, (DWORD)strlen(stdin_utf8), &wrote, NULL);
            LARGE_INTEGER zero;
            zero.QuadPart = 0;
            SetFilePointerEx(in_r, zero, NULL, FILE_BEGIN);
            child_stdin = in_r;
        }
    } else {
        nul = CreateFileW(L"NUL", GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, &sa,
                          OPEN_EXISTING, 0, NULL);
        if (nul == INVALID_HANDLE_VALUE) {
            nul = NULL;
            goto done;
        }
        child_stdin = nul;
    }

    STARTUPINFOW si;
    memset(&si, 0, sizeof si);
    si.cb = sizeof si;
    si.dwFlags = STARTF_USESTDHANDLES;
    si.hStdOutput = out_w;
    si.hStdError = err_w;
    si.hStdInput = child_stdin;

    PROCESS_INFORMATION pi;
    memset(&pi, 0, sizeof pi);

    wchar_t *mutable_cmd = _wcsdup(cmdline);
    if (!mutable_cmd) goto done;
    /* DETACHED_PROCESS, not CREATE_NO_WINDOW: children created with
     * CREATE_NO_WINDOW die with 0xC0000142 before main in this sandbox. */
    BOOL started = CreateProcessW(NULL, mutable_cmd, NULL, NULL, TRUE, DETACHED_PROCESS, NULL,
                                  NULL, &si, &pi);
    free(mutable_cmd);
    if (!started) {
        r->spawn_error = (int)GetLastError();
        goto done;
    }
    /* Pipe write ends must be closed so readers see EOF; file handles stay open
     * because we read the child's output back through them. */
    if (!out_file) close_if(&out_w);
    if (!err_file) close_if(&err_w);
    close_if(&in_r);

    if (stdin_utf8 && in_w) {
        DWORD written = 0;
        WriteFile(in_w, stdin_utf8, (DWORD)strlen(stdin_utf8), &written, NULL);
        close_if(&in_w);
    }

    reader_arg ro = {out_r, &r->out};
    reader_arg re = {err_r, &r->err};
    HANDLE threads[2] = {NULL, NULL};
    if (!out_file && out_r) threads[0] = CreateThread(NULL, 0, reader_main, &ro, 0, NULL);
    if (!err_file && err_r) threads[1] = CreateThread(NULL, 0, reader_main, &re, 0, NULL);

    DWORD wait = WaitForSingleObject(pi.hProcess, (DWORD)(timeout_ms > 0 ? timeout_ms : INFINITE));
    if (wait == WAIT_TIMEOUT) {
        r->timed_out = 1;
        TerminateProcess(pi.hProcess, 1);
        WaitForSingleObject(pi.hProcess, 5000);
    }
    for (int i = 0; i < 2; ++i) {
        if (threads[i]) {
            WaitForSingleObject(threads[i], 10000);
            CloseHandle(threads[i]);
        }
    }
    if (out_file) read_temp_file(out_w, &r->out);
    if (err_file) read_temp_file(err_w, &r->err);
    DWORD code = 0;
    GetExitCodeProcess(pi.hProcess, &code);
    r->exit_code = (int)code;
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    rc = 0;

done:
    close_if(&nul);
    close_if(&out_r);
    close_if(&out_w);
    close_if(&err_r);
    close_if(&err_w);
    close_if(&in_r);
    close_if(&in_w);
    if (out_path[0]) DeleteFileW(out_path);
    if (err_path[0]) DeleteFileW(err_path);
    if (in_path[0]) DeleteFileW(in_path);
    return rc;
}

void proc_result_free(proc_result *r) {
    sb_free(&r->out);
    sb_free(&r->err);
    memset(r, 0, sizeof *r);
}

int proc_ok(const proc_result *r) {
    return r->spawn_error == 0 && !r->timed_out && r->exit_code == 0;
}

/* -------------------------------------------------------------- output -- */

void emit_ok_header(sb *b) {
    sb_puts(b, "{\"ok\":true");
}

void emit_error(sb *b, const char *code, const char *message) {
    sb_puts(b, "{\"ok\":false,\"cmd\":");
    sb_put_json_str(b, g_cmd_name ? g_cmd_name : "");
    sb_puts(b, ",\"error\":{\"code\":");
    sb_put_json_str(b, code);
    sb_puts(b, ",\"message\":");
    sb_put_json_str(b, message);
    sb_puts(b, "}}\n");
}

int write_stdout(const sb *b) {
    if (!b->data || b->len == 0) return 0;
    HANDLE h = GetStdHandle(STD_OUTPUT_HANDLE);
    if (h == INVALID_HANDLE_VALUE || h == NULL) return -1;
    DWORD written = 0;
    if (!WriteFile(h, b->data, (DWORD)b->len, &written, NULL)) return -1;
    return 0;
}
