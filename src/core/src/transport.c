/* transport.c — ADB / SSH transport behind one small interface.
 *
 * ADB is driven through adb.exe; SSH through Windows' OpenSSH (ssh.exe/scp.exe)
 * in BatchMode with a key file, so the GUI never has to type a password.
 */
#include "pen.h"

#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int g_transport = TRANSPORT_ADB;
const char *g_host = NULL; /* user@host for SSH */
int g_port = 0;            /* 0 -> ssh default */
const char *g_key = NULL;  /* private key path for SSH */

static char g_ssh[MAX_PATH * 2];
static int g_ssh_done = 0;

static const wchar_t *find_tool(const wchar_t *name, wchar_t *buf) {
    if (SearchPathW(NULL, name, NULL, MAX_PATH, buf, NULL)) return buf;
    return NULL;
}

static const char *ssh_path(void) {
    if (g_ssh_done) return g_ssh;
    g_ssh_done = 1;
    g_ssh[0] = '\0';
    /* PENCTL_SSH pins the ssh.exe to use (tests, or a portable OpenSSH
       bundle); only trusted when the file actually exists. */
    {
        const char *override = getenv("PENCTL_SSH");
        if (override && override[0]) {
            wchar_t *w = pen_utf8_to_wide(override);
            if (w) {
                if (GetFileAttributesW(w) != INVALID_FILE_ATTRIBUTES) {
                    char *u = pen_strdup(override);
                    if (u) {
                        char *slash = strrchr(u, '\\');
                        if (!slash) slash = strrchr(u, '/');
                        if (slash) *slash = '\0';
                        strncpy(g_ssh, u, sizeof g_ssh - 1);
                        g_ssh[sizeof g_ssh - 1] = '\0';
                        free(u);
                    }
                }
                free(w);
            }
            if (g_ssh[0]) return g_ssh;
        }
    }
    /* Prefer the Windows-bundled OpenSSH over whatever PATH may hold: a
       msys/cygwin ssh accepts our argv but then dies in its own runtime
       init when started from a GUI process. */
    {
        const char *sysroot = getenv("SystemRoot");
        if (sysroot && sysroot[0]) {
            wchar_t candidate[MAX_PATH];
            wchar_t *root = pen_utf8_to_wide(sysroot);
            if (root) {
                if (_snwprintf(candidate, MAX_PATH - 1,
                               L"%ls\\System32\\OpenSSH\\ssh.exe", root) > 0 &&
                    GetFileAttributesW(candidate) != INVALID_FILE_ATTRIBUTES) {
                    candidate[MAX_PATH - 1] = L'\0';
                    char *u = pen_wide_to_utf8(candidate);
                    if (u) {
                        char *slash = strrchr(u, '\\');
                        if (slash) *slash = '\0';
                        strncpy(g_ssh, u, sizeof g_ssh - 1);
                        g_ssh[sizeof g_ssh - 1] = '\0';
                        free(u);
                    }
                }
                free(root);
                if (g_ssh[0]) return g_ssh;
            }
        }
    }

    wchar_t found[MAX_PATH];
    const wchar_t *names[] = {L"ssh.exe", L"scp.exe"};
    for (int i = 0; i < 2; ++i) {
        if (!find_tool(names[i], found)) continue;
        char *u = pen_wide_to_utf8(found);
        if (!u) continue;
        /* strip the file name: keep the directory */
        char *slash = strrchr(u, '\\');
        if (!slash) slash = strrchr(u, '/');
        if (slash) *slash = '\0';
        strncpy(g_ssh, u, sizeof g_ssh - 1);
        g_ssh[sizeof g_ssh - 1] = '\0';
        free(u);
        return g_ssh;
    }
    return g_ssh;
}

static void ssh_tool_path(const wchar_t *tool, wchar_t *out) {
    const char *dir = ssh_path();
    if (dir[0]) {
        wchar_t *w = pen_utf8_to_wide(dir);
        if (w) {
            _snwprintf(out, MAX_PATH, L"%s\\%s", w, tool);
            free(w);
            if (GetFileAttributesW(out) != INVALID_FILE_ATTRIBUTES) return;
        }
    }
    wcscpy(out, tool);
}

static void add_ssh_common(wsb *cmd) {
    if (g_key && g_key[0]) {
        wsb_arg(cmd, "-i");
        wsb_arg(cmd, g_key);
    }
    wsb_arg(cmd, "-o");
    wsb_arg(cmd, "BatchMode=yes");
    /* accept-new pins the key the first time and rejects a different one after
       that: trust-on-first-use instead of trusting whatever answers. */
    wsb_arg(cmd, "-o");
    wsb_arg(cmd, "StrictHostKeyChecking=accept-new");
    if (g_known_hosts && g_known_hosts[0]) {
        static char hosts_opt[MAX_PATH * 2];
        _snprintf(hosts_opt, sizeof hosts_opt, "UserKnownHostsFile=%s", g_known_hosts);
        wsb_arg(cmd, "-o");
        wsb_arg(cmd, hosts_opt);
    }
    wsb_arg(cmd, "-o");
    wsb_arg(cmd, "ConnectTimeout=10");
}

static int ssh_run_argv(const wchar_t *tool, const char *const *argv, int argc, proc_result *r,
                        int timeout_ms) {
    wchar_t exe[MAX_PATH];
    ssh_tool_path(tool, exe);
    wsb cmd;
    wsb_init(&cmd);
    wsb_argw(&cmd, exe);
    add_ssh_common(&cmd);
    if (wcscmp(tool, L"scp.exe") == 0) {
        if (g_port > 0) {
            char port[16];
            _snprintf(port, sizeof port, "%d", g_port);
            wsb_arg(&cmd, "-P");
            wsb_arg(&cmd, port);
        }
    } else if (g_port > 0) {
        char port[16];
        _snprintf(port, sizeof port, "%d", g_port);
        wsb_arg(&cmd, "-p");
        wsb_arg(&cmd, port);
    }
    if (!g_host || !g_host[0]) {
        wsb_free(&cmd);
        memset(r, 0, sizeof *r);
        sb_init(&r->out);
        sb_init(&r->err);
        r->spawn_error = -3;
        return -1;
    }
    for (int i = 0; i < argc; ++i) wsb_arg(&cmd, argv[i]);
    int rc = pen_run(wsb_cstr(&cmd), NULL, r, timeout_ms);
    wsb_free(&cmd);
    return rc;
}

int t_shell(const char *remote_cmd, proc_result *r, int timeout_ms) {
    if (g_transport == TRANSPORT_SSH) {
        const char *argv[2];
        argv[0] = g_host;
        argv[1] = remote_cmd;
        return ssh_run_argv(L"ssh.exe", argv, 2, r, timeout_ms);
    }
    return adb_shell(g_serial, remote_cmd, r, timeout_ms);
}

/* scp needs host:path as a single argument. */
static char *scp_target(const char *remote_path) {
    sb b;
    sb_init(&b);
    sb_puts(&b, g_host ? g_host : "");
    sb_putc(&b, ':');
    sb_puts(&b, remote_path);
    char *out = pen_strdup(b.data ? b.data : "");
    sb_free(&b);
    return out;
}

int t_push(const char *local, const char *remote, proc_result *r, int timeout_ms) {
    if (g_transport == TRANSPORT_SSH) {
        char *tgt = scp_target(remote);
        if (!tgt) return -1;
        const char *argv[2];
        argv[0] = local;
        argv[1] = tgt;
        int rc = ssh_run_argv(L"scp.exe", argv, 2, r, timeout_ms);
        free(tgt);
        return rc;
    }
    const char *argv[2];
    argv[0] = local;
    argv[1] = remote;
    return adb_run(g_serial, (const char *const[]){ "push", argv[0], argv[1] }, 3, r, timeout_ms);
}

int t_pull(const char *remote, const char *local, proc_result *r, int timeout_ms) {
    if (g_transport == TRANSPORT_SSH) {
        char *tgt = scp_target(remote);
        if (!tgt) return -1;
        const char *argv[2];
        argv[0] = tgt;
        argv[1] = local;
        int rc = ssh_run_argv(L"scp.exe", argv, 2, r, timeout_ms);
        free(tgt);
        return rc;
    }
    return adb_run(g_serial, (const char *const[]){ "pull", remote, local }, 3, r, timeout_ms);
}

int t_needs_device(void) {
    if (g_transport == TRANSPORT_SSH) return !(g_host && g_host[0]);
    return !(g_serial && g_serial[0]);
}

const char *t_device_name(void) {
    if (g_transport == TRANSPORT_SSH) return g_host ? g_host : "";
    return g_serial ? g_serial : "";
}
