#include "pen.h"

#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static char g_adb[MAX_PATH * 2];
static int g_adb_done = 0;

static void set_adb(const wchar_t *w) {
    char *u = pen_wide_to_utf8(w);
    if (!u) return;
    strncpy(g_adb, u, sizeof g_adb - 1);
    g_adb[sizeof g_adb - 1] = '\0';
    free(u);
}

/* Search order: PENCTL_ADB -> adb.exe next to penctl.exe -> PATH -> "adb". */
const char *adb_path(void) {
    if (g_adb_done) return g_adb;
    g_adb_done = 1;
    g_adb[0] = '\0';

    const char *env = getenv("PENCTL_ADB");
    if (env && env[0]) {
        wchar_t *w = pen_utf8_to_wide(env);
        if (w) {
            int exists = GetFileAttributesW(w) != INVALID_FILE_ATTRIBUTES;
            free(w);
            if (exists) {
                strncpy(g_adb, env, sizeof g_adb - 1);
                g_adb[sizeof g_adb - 1] = '\0';
                return g_adb;
            }
        }
    }

    wchar_t exe[MAX_PATH];
    DWORD n = GetModuleFileNameW(NULL, exe, MAX_PATH);
    if (n > 0 && n < MAX_PATH) {
        wchar_t *slash = wcsrchr(exe, L'\\');
        if (slash) {
            *slash = L'\0';
            wchar_t cand[MAX_PATH];
            _snwprintf(cand, MAX_PATH, L"%s\\adb.exe", exe);
            if (GetFileAttributesW(cand) != INVALID_FILE_ATTRIBUTES) {
                set_adb(cand);
                return g_adb;
            }
        }
    }

    wchar_t found[MAX_PATH];
    if (SearchPathW(NULL, L"adb.exe", NULL, MAX_PATH, found, NULL)) {
        set_adb(found);
        return g_adb;
    }
    return g_adb;
}

int adb_run(const char *serial, const char *const *argv, int argc, proc_result *r, int timeout_ms) {
    const char *adb = adb_path();
    if (!adb[0]) {
        memset(r, 0, sizeof *r);
        sb_init(&r->out);
        sb_init(&r->err);
        r->spawn_error = -2;
        return -1;
    }
    wsb cmd;
    wsb_init(&cmd);
    wsb_arg(&cmd, adb);
    if (serial && serial[0]) {
        wsb_arg(&cmd, "-s");
        wsb_arg(&cmd, serial);
    }
    for (int i = 0; i < argc; ++i) wsb_arg(&cmd, argv[i]);
    int rc = pen_run(wsb_cstr(&cmd), NULL, r, timeout_ms);
    wsb_free(&cmd);
    return rc;
}

int adb_shell(const char *serial, const char *remote_cmd, proc_result *r, int timeout_ms) {
    const char *argv[2];
    argv[0] = "shell";
    argv[1] = remote_cmd;
    return adb_run(serial, argv, 2, r, timeout_ms);
}

int cmd_version(int argc, char **argv) {
    (void)argc;
    (void)argv;
    sb out;
    sb_init(&out);
    sb_puts(&out, "{\"ok\":true,\"cmd\":\"version\",\"version\":\"" PENCTL_VERSION "\",\"platform\":\"windows\"}\n");
    int rc = write_stdout(&out);
    sb_free(&out);
    return rc == 0 ? 0 : 3;
}
