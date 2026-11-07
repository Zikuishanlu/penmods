/* penctl — C core for the PenMods Manager.
 * Stable contract: every subcommand with --json prints exactly one JSON object
 * to stdout (UTF-8, no BOM) and exits 0 on success, non-zero on failure. */
#ifndef PEN_H
#define PEN_H

#include <stddef.h>
#include <wchar.h>

#define PENCTL_VERSION "0.1.0"
#define PENCTL_MAX_OUT (8u * 1024u * 1024u)

/* ---------- UTF-8 string builder ---------- */
typedef struct {
    char  *data;
    size_t len;
    size_t cap;
} sb;

void sb_init(sb *b);
void sb_free(sb *b);
void sb_putn(sb *b, const char *s, size_t n);
void sb_puts(sb *b, const char *s);
void sb_putc(sb *b, char c);
void sb_printf(sb *b, const char *fmt, ...);
void sb_put_json_str(sb *b, const char *s); /* quoted + escaped; NULL -> "" */

/* ---------- UTF-16 <-> UTF-8 ---------- */
wchar_t *pen_utf8_to_wide(const char *s);   /* malloc'd, caller frees */
char    *pen_wide_to_utf8(const wchar_t *s); /* malloc'd, caller frees */
char    *pen_strdup(const char *s);
char    *pen_trim_dup(const char *s);       /* dup with leading/trailing space stripped */

/* ---------- UTF-16 command line builder ---------- */
typedef struct {
    wchar_t *buf;
    size_t   len;
    size_t   cap;
} wsb;

void        wsb_init(wsb *b);
void        wsb_free(wsb *b);
void        wsb_arg(wsb *b, const char *arg);   /* quotes as needed */
void        wsb_argw(wsb *b, const wchar_t *arg);
const wchar_t *wsb_cstr(wsb *b);

/* ---------- child process with captured stdout/stderr ---------- */
typedef struct {
    sb  out;
    sb  err;
    int exit_code;
    int timed_out;
    int spawn_error; /* 0 = started fine, -2 = adb not found, else Win32 error */
} proc_result;

int  pen_run(const wchar_t *cmdline, const char *stdin_utf8, proc_result *r, int timeout_ms);
void proc_result_free(proc_result *r);
int  proc_ok(const proc_result *r);            /* started, not timed out, exit 0 */

/* ---------- adb ---------- */
const char *adb_path(void);   /* "" when not found */
int  adb_run(const char *serial, const char *const *argv, int argc, proc_result *r, int timeout_ms);
int  adb_shell(const char *serial, const char *remote_cmd, proc_result *r, int timeout_ms);

/* ---------- transport (adb or ssh) ---------- */
#define TRANSPORT_ADB 0
#define TRANSPORT_SSH 1
extern int g_transport;
extern const char *g_host; /* user@host, SSH only */
extern int g_port;         /* 0 -> ssh default 22 */
extern const char *g_key;  /* private key path, SSH only */
extern const char *g_known_hosts; /* known_hosts path, SSH only (optional) */

int  t_shell(const char *remote_cmd, proc_result *r, int timeout_ms);
int  t_push(const char *local, const char *remote, proc_result *r, int timeout_ms);
int  t_pull(const char *remote, const char *local, proc_result *r, int timeout_ms);
int  t_needs_device(void);
const char *t_device_name(void);

/* ---------- output helpers ---------- */
void emit_ok_header(sb *b);
void emit_error(sb *b, const char *code, const char *message);
int  write_stdout(const sb *b);

/* ---------- commands ---------- */
extern const char *g_serial;
extern const char *g_cmd_name;
int cmd_version(int argc, char **argv);
int cmd_detect(int argc, char **argv);
int cmd_device_info(int argc, char **argv);
int cmd_pkg_inspect(int argc, char **argv);
int cmd_shell(int argc, char **argv);
int cmd_push(int argc, char **argv);
int cmd_pull(int argc, char **argv);

#endif /* PEN_H */
