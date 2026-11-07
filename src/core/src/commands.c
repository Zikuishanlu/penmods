#include "pen.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* --------------------------------------------------------------- detect -- */

typedef struct {
    char *serial;
    char *state;
    char *model;
} adb_device;

static const char *find_sub(const char *hay, const char *needle) {
    return hay ? strstr(hay, needle) : NULL;
}

static char *field_after(const char *line, const char *key) {
    const char *p = find_sub(line, key);
    if (!p) return NULL;
    p += strlen(key);
    const char *end = p;
    while (*end && *end != ' ' && *end != '\t' && *end != '\r' && *end != '\n') ++end;
    size_t n = (size_t)(end - p);
    char *out = (char *)malloc(n + 1);
    if (!out) return NULL;
    memcpy(out, p, n);
    out[n] = '\0';
    return out;
}

static int parse_devices(const char *text, adb_device **out, int *count) {
    *out = NULL;
    *count = 0;
    int cap = 0;
    const char *p = text;
    while (p && *p) {
        const char *nl = strchr(p, '\n');
        size_t len = nl ? (size_t)(nl - p) : strlen(p);
        if (len > 0) {
            char *line = (char *)malloc(len + 1);
            if (!line) return -1;
            memcpy(line, p, len);
            line[len] = '\0';
            char *t = pen_trim_dup(line);
            free(line);
            if (t && t[0] && strncmp(t, "List of devices", 15) != 0 && strncmp(t, "*", 1) != 0 &&
                strncmp(t, "adb server", 10) != 0) {
                /* Read model: off the untouched line; the split below writes NULs. */
                char *model = field_after(t, "model:");
                char *sp = strpbrk(t, " \t");
                if (sp) {
                    *sp = '\0';
                    char *state = sp + 1;
                    while (*state == ' ' || *state == '\t') ++state;
                    char *state_end = state;
                    while (*state_end && *state_end != ' ' && *state_end != '\t') ++state_end;
                    *state_end = '\0';
                    if (*count == cap) {
                        cap = cap ? cap * 2 : 4;
                        adb_device *grown = (adb_device *)realloc(*out, sizeof(adb_device) * (size_t)cap);
                        if (!grown) {
                            free(t);
                            return -1;
                        }
                        *out = grown;
                    }
                    (*out)[*count].serial = pen_strdup(t);
                    (*out)[*count].state = pen_strdup(state);
                    (*out)[*count].model = model;
                    ++*count;
                }
            }
            free(t);
        }
        p = nl ? nl + 1 : NULL;
    }
    return 0;
}

static void free_devices(adb_device *devs, int count) {
    for (int i = 0; i < count; ++i) {
        free(devs[i].serial);
        free(devs[i].state);
        free(devs[i].model);
    }
    free(devs);
}

static char *adb_version_string(void) {
    proc_result r;
    const char *argv[] = {"version"};
    memset(&r, 0, sizeof r);
    sb_init(&r.out);
    sb_init(&r.err);
    if (adb_run(NULL, argv, 1, &r, 8000) != 0 || r.spawn_error != 0) {
        proc_result_free(&r);
        return NULL;
    }
    char *out = pen_strdup(r.out.data ? r.out.data : "");
    proc_result_free(&r);
    if (!out) return NULL;
    char *p = strstr(out, "version ");
    if (p) {
        p += 8;
        char *end = p;
        while (*end && *end != '\r' && *end != '\n' && *end != ' ') ++end;
        char *ver = (char *)malloc((size_t)(end - p) + 1);
        if (ver) {
            memcpy(ver, p, (size_t)(end - p));
            ver[end - p] = '\0';
        }
        free(out);
        return ver;
    }
    return out;
}

int cmd_detect(int argc, char **argv) {
    (void)argc;
    (void)argv;
    sb out;
    sb_init(&out);

    const char *adb = adb_path();
    int have_adb = adb[0] != '\0';
    proc_result r;

    if (!have_adb) {
        emit_error(&out, "ADB_MISSING",
                   "adb.exe not found: set PENCTL_ADB, put adb.exe next to penctl.exe, or add it to PATH");
        (void)write_stdout(&out);
        sb_free(&out);
        return 1;
    }

    const char *dev_argv[] = {"devices", "-l"};
    if (adb_run(NULL, dev_argv, 2, &r, 15000) != 0 || r.spawn_error != 0) {
        char msg[160];
        if (r.spawn_error) {
            snprintf(msg, sizeof msg, "adb could not be started (win32 error %d)", r.spawn_error);
        } else {
            snprintf(msg, sizeof msg, "adb devices exited with code %d", r.exit_code);
        }
        emit_error(&out, "ADB_FAILED", msg);
        (void)write_stdout(&out);
        proc_result_free(&r);
        sb_free(&out);
        return 1;
    }
    if (r.timed_out) {
        emit_error(&out, "TIMEOUT", "adb devices timed out (is another adb server holding the device?)");
        (void)write_stdout(&out);
        proc_result_free(&r);
        sb_free(&out);
        return 1;
    }

    adb_device *devs = NULL;
    int count = 0;
    parse_devices(r.out.data ? r.out.data : "", &devs, &count);

    char *ver = adb_version_string();

    sb_printf(&out, "{\"ok\":true,\"cmd\":\"detect\",\"adb\":{\"path\":");
    sb_put_json_str(&out, adb);
    sb_puts(&out, ",\"version\":");
    sb_put_json_str(&out, ver ? ver : "");
    sb_puts(&out, "},\"devices\":[");
    for (int i = 0; i < count; ++i) {
        if (i) sb_putc(&out, ',');
        sb_puts(&out, "{\"serial\":");
        sb_put_json_str(&out, devs[i].serial ? devs[i].serial : "");
        sb_puts(&out, ",\"state\":");
        sb_put_json_str(&out, devs[i].state ? devs[i].state : "");
        sb_puts(&out, ",\"model\":");
        sb_put_json_str(&out, devs[i].model ? devs[i].model : "");
        const char *shell = "unavailable";
        int penctl_ok = 0;
        int auth = 0;
        if (devs[i].state && strcmp(devs[i].state, "device") == 0) {
            proc_result probe;
            memset(&probe, 0, sizeof probe);
            sb_init(&probe.out);
            sb_init(&probe.err);
            shell = "error";
            if (adb_shell(devs[i].serial, "echo penctl-ok", &probe, 10000) == 0 && !probe.timed_out) {
                const char *text = probe.out.data ? probe.out.data : "";
                if (strstr(text, "penctl-ok")) {
                    shell = "ok";
                    penctl_ok = 1;
                } else if (strstr(text, "adb shell auth")) {
                    shell = "auth_required";
                    auth = 1;
                }
            }
            proc_result_free(&probe);
        }
        sb_puts(&out, ",\"shell\":");
        sb_put_json_str(&out, shell);
        sb_puts(&out, ",\"penctl_ok\":");
        sb_puts(&out, penctl_ok ? "true" : "false");
        sb_puts(&out, ",\"auth_required\":");
        sb_puts(&out, auth ? "true" : "false");
        sb_putc(&out, '}');
    }
    sb_puts(&out, "]}\n");

    int rc = write_stdout(&out);
    sb_free(&out);
    free_devices(devs, count);
    free(ver);
    proc_result_free(&r);
    return rc == 0 ? 0 : 3;
}

/* ---------------------------------------------------------- device-info -- */

static const struct {
    const char *key;
    const char *cmd;
} kInfoProbes[] = {
    {"version_raw", "cat /Version 2>/dev/null"},
    {"pcba", "get_pcba_version 2>/dev/null"},
    {"kernel", "uname -r 2>/dev/null"},
    {"penmods_installed", "test -f /userdata/PenMods/libPenMods.so && echo yes || echo no"},
    {"cfg_adb", "grep -o '\"adb_autorun\": *[a-z]*' /userdata/PenModsconfig.json 2>/dev/null | head -1"},
    {"cfg_ssh", "grep -o '\"ssh_autorun\": *[a-z]*' /userdata/PenModsconfig.json 2>/dev/null | head -1"},
    {"cfg_skip_auth", "grep -o '\"adb_skip_verification\": *[a-z]*' /userdata/PenModsconfig.json 2>/dev/null | head -1"},
    {"app_binary", "ls -l /oem/YoudaoDictPen/output/YoudaoDictPen 2>/dev/null"},
    {"usb_config", "cat /tmp/.usb_config 2>/dev/null"},
    {"sshd", "ps 2>/dev/null | grep sshd | grep -v grep"},
    {"storage", "df -h /userdata 2>/dev/null | tail -1 | tr -s ' ' | cut -d' ' -f2-5"},
    {"uptime", "uptime 2>/dev/null | sed 's/^.*up  *//; s/,.*//'"},
    {"penmods_model", "grep -o '\"model\":\"[A-Z0-9]*\"' /userdata/PenMods/ota-manifest.json 2>/dev/null | head -1 | cut -d'\"' -f4"},
};

static const char *kSupportedModels[] = {"YDP02X", "YDPG3", "YDP03X"};

/* Value of a probe by key (kInfoProbes order is the JSON order). */
static const char *probe_value(char **values, const char *key) {
    size_t n = sizeof kInfoProbes / sizeof kInfoProbes[0];
    for (size_t i = 0; i < n; ++i) {
        if (strcmp(kInfoProbes[i].key, key) == 0) return values[i] ? values[i] : "";
    }
    return "";
}

/* Value after "key" up to end of line, trimmed; NULL when absent. Caller frees. */
static char *line_value_after(const char *text, const char *key) {
    const char *p = text ? strstr(text, key) : NULL;
    if (!p) return NULL;
    p += strlen(key);
    while (*p == ' ' || *p == '\t' || *p == ':') ++p;
    const char *end = p;
    while (*end && *end != '\r' && *end != '\n') ++end;
    size_t len = (size_t)(end - p);
    while (len && (p[len - 1] == ' ' || p[len - 1] == '\t')) --len;
    char *out = (char *)malloc(len + 1);
    if (!out) return NULL;
    memcpy(out, p, len);
    out[len] = '\0';
    return out;
}

static int is_supported_model(const char *model) {
    if (!model || !model[0]) return 0;
    size_t n = sizeof kSupportedModels / sizeof kSupportedModels[0];
    for (size_t i = 0; i < n; ++i) {
        if (strcmp(model, kSupportedModels[i]) == 0) return 1;
    }
    return 0;
}

int cmd_device_info(int argc, char **argv) {
    (void)argc;
    (void)argv;
    sb out;
    sb_init(&out);

    if (t_needs_device()) {
        emit_error(&out, "NO_DEVICE", "device-info needs -s SERIAL (adb) or --ssh user@HOST");
        (void)write_stdout(&out);
        sb_free(&out);
        return 1;
    }

    size_t n = sizeof kInfoProbes / sizeof kInfoProbes[0];
    char **values = (char **)calloc(n, sizeof(char *));
    if (!values) {
        emit_error(&out, "OOM", "out of memory");
        (void)write_stdout(&out);
        sb_free(&out);
        return 1;
    }
    int spawned = 0;
    int answered = 0;
    int spawn_error = 0;
    int first_exit = 0;
    for (size_t i = 0; i < n; ++i) {
        proc_result r;
        memset(&r, 0, sizeof r);
        sb_init(&r.out);
        sb_init(&r.err);
        int started = t_shell(kInfoProbes[i].cmd, &r, 15000) == 0 && r.spawn_error == 0;
        if (started) {
            spawned++;
            if (r.exit_code == 0) {
                answered++;
            } else if (first_exit == 0) {
                first_exit = r.exit_code;
            }
        } else if (r.spawn_error != 0) {
            spawn_error = r.spawn_error;
        }
        values[i] = started ? pen_trim_dup(r.out.data ? r.out.data : "") : pen_strdup("");
        proc_result_free(&r);
    }

    if (answered == 0) {
        /* ssh.exe/scp.exe missing or the device dropped: say so instead of
           pretending a dead transport produced an empty device. */
        char msg[256];
        if (spawn_error) {
            snprintf(msg, sizeof msg, "transport could not be started (win32 error %d)", spawn_error);
        } else if (spawned > 0 && first_exit != 0) {
            snprintf(msg, sizeof msg, "%s exited with code %d before answering",
                     g_transport == TRANSPORT_SSH ? "ssh" : "adb", first_exit);
        } else {
            snprintf(msg, sizeof msg, "no probe could reach the device over %s",
                     g_transport == TRANSPORT_SSH ? "ssh" : "adb");
        }
        for (size_t i = 0; i < n; ++i) free(values[i]);
        free(values);
        emit_error(&out, "TRANSPORT_FAILED", msg);
        (void)write_stdout(&out);
        sb_free(&out);
        return 1;
    }

    /* Model: PenMods' own manifest wins on modded pens (pcba is a board code
       such as Exam_V0), then get_pcba_version, then the pcba: line of /Version. */
    char *pcba = pen_trim_dup(values[1] ? values[1] : "");
    if (pcba) {
        char *sp = strpbrk(pcba, " \t\r\n");
        if (sp) *sp = '\0';
    }
    char *model = pen_trim_dup(values[n - 1] ? values[n - 1] : "");
    if (!is_supported_model(model)) {
        free(model);
        model = is_supported_model(pcba) ? pen_strdup(pcba) : line_value_after(values[0], "pcba");
    }
    free(pcba);
    char *system_version = line_value_after(values[0], "Version");

    sb_printf(&out, "{\"ok\":true,\"cmd\":\"device-info\",\"serial\":");
    sb_put_json_str(&out, t_device_name());
    sb_puts(&out, ",\"info\":{");
    for (size_t i = 0; i < n; ++i) {
        if (i) sb_putc(&out, ',');
        sb_put_json_str(&out, kInfoProbes[i].key);
        sb_putc(&out, ':');
        sb_put_json_str(&out, values[i] ? values[i] : "");
    }
    sb_puts(&out, "},\"derived\":{\"model\":");
    sb_put_json_str(&out, model ? model : "");
    sb_puts(&out, ",\"model_supported\":");
    sb_puts(&out, is_supported_model(model) ? "true" : "false");
    sb_puts(&out, ",\"system_version\":");
    sb_put_json_str(&out, system_version ? system_version : "");
    sb_puts(&out, ",\"ssh_autostart\":");
    sb_puts(&out, strstr(probe_value(values, "cfg_ssh"), "true") ? "true" : "false");
    sb_puts(&out, ",\"adb_autostart\":");
    sb_puts(&out, strstr(probe_value(values, "cfg_adb"), "true") ? "true" : "false");
    sb_puts(&out, ",\"adb_skip_auth\":");
    sb_puts(&out, strstr(probe_value(values, "cfg_skip_auth"), "true") ? "true" : "false");
    sb_puts(&out, ",\"penmods_installed\":");
    const char *installed = values[3] ? values[3] : "";
    sb_puts(&out, strstr(installed, "yes") ? "true" : "false");
    sb_puts(&out, "}}\n");

    int rc = write_stdout(&out);
    for (size_t i = 0; i < n; ++i) free(values[i]);
    free(values);
    free(model);
    free(system_version);
    sb_free(&out);
    return rc == 0 ? 0 : 3;
}

int cmd_pkg_inspect(int argc, char **argv) {
    (void)argc;
    (void)argv;
    sb out;
    sb_init(&out);
    emit_error(&out, "NOT_IMPLEMENTED", "pkg inspect lands in milestone M3");
    (void)write_stdout(&out);
    sb_free(&out);
    return 1;
}

/* Raw shell passthrough for the terminal page: prints adb's own output. */
int cmd_shell(int argc, char **argv) {
    if (argc < 1) {
        sb out;
        sb_init(&out);
        emit_error(&out, "BAD_ARG", "shell needs a command, e.g. penctl shell ls /userdata");
        (void)write_stdout(&out);
        sb_free(&out);
        return 2;
    }
    if (t_needs_device()) {
        sb out;
        sb_init(&out);
        emit_error(&out, "NO_DEVICE", "shell needs -s SERIAL (adb) or --ssh user@HOST");
        (void)write_stdout(&out);
        sb_free(&out);
        return 1;
    }
    sb remote;
    sb_init(&remote);
    for (int i = 0; i < argc; ++i) {
        if (i) sb_putc(&remote, ' ');
        sb_puts(&remote, argv[i]);
    }
    char *remote_cmd = pen_strdup(remote.data ? remote.data : "");
    sb_free(&remote);
    if (!remote_cmd) return 1;

    proc_result r;
    memset(&r, 0, sizeof r);
    if (t_shell(remote_cmd, &r, 120000) != 0 || r.spawn_error != 0) {
        free(remote_cmd);
        proc_result_free(&r);
        sb out;
        sb_init(&out);
        emit_error(&out, "ADB_FAILED", "adb shell could not be started");
        (void)write_stdout(&out);
        sb_free(&out);
        return 1;
    }
    free(remote_cmd);
    if (r.out.data) {
        fwrite(r.out.data, 1, r.out.len, stdout);
        fflush(stdout);
    }
    int code = r.exit_code;
    if (code != 0 && r.err.data && r.err.len) {
        /* surface the remote stderr so callers can show ssh/scp's message */
        fwrite(r.err.data, 1, r.err.len, stdout);
        fflush(stdout);
    }
    proc_result_free(&r);
    return code == 0 ? 0 : 1;
}

/* ------------------------------------------------------------- push / pull -- */

static int finish_transfer(sb *out, const char *cmd, const char *src, const char *dst,
                           proc_result *r) {
    if (r->spawn_error != 0) {
        emit_error(out, r->spawn_error == -3 ? "NO_DEVICE" : "TOOL_MISSING",
                   "transfer tool could not be started");
        (void)write_stdout(out);
        return 1;
    }
    if (r->timed_out) {
        emit_error(out, "TIMEOUT", "transfer timed out");
        (void)write_stdout(out);
        return 1;
    }
    if (r->exit_code != 0) {
        const char *msg = r->err.data && r->err.len ? r->err.data : "transfer failed";
        emit_error(out, "TRANSFER_FAILED", msg);
        (void)write_stdout(out);
        return 1;
    }
    sb_printf(out, "{\"ok\":true,\"cmd\":\"%s\",\"src\":", cmd);
    sb_put_json_str(out, src);
    sb_puts(out, ",\"dst\":");
    sb_put_json_str(out, dst);
    sb_puts(out, ",\"device\":");
    sb_put_json_str(out, t_device_name());
    sb_puts(out, "}\n");
    int rc = write_stdout(out);
    return rc == 0 ? 0 : 3;
}

int cmd_push(int argc, char **argv) {
    sb out;
    sb_init(&out);
    if (argc != 2) {
        emit_error(&out, "BAD_ARG", "push needs <local> <remote>");
        (void)write_stdout(&out);
        sb_free(&out);
        return 2;
    }
    if (t_needs_device()) {
        emit_error(&out, "NO_DEVICE", "push needs -s SERIAL (adb) or --ssh user@HOST");
        (void)write_stdout(&out);
        sb_free(&out);
        return 1;
    }
    proc_result r;
    memset(&r, 0, sizeof r);
    t_push(argv[0], argv[1], &r, 600000);
    int code = finish_transfer(&out, "push", argv[0], argv[1], &r);
    proc_result_free(&r);
    sb_free(&out);
    return code;
}

int cmd_pull(int argc, char **argv) {
    sb out;
    sb_init(&out);
    if (argc != 2) {
        emit_error(&out, "BAD_ARG", "pull needs <remote> <local>");
        (void)write_stdout(&out);
        sb_free(&out);
        return 2;
    }
    if (t_needs_device()) {
        emit_error(&out, "NO_DEVICE", "pull needs -s SERIAL (adb) or --ssh user@HOST");
        (void)write_stdout(&out);
        sb_free(&out);
        return 1;
    }
    proc_result r;
    memset(&r, 0, sizeof r);
    t_pull(argv[0], argv[1], &r, 600000);
    int code = finish_transfer(&out, "pull", argv[0], argv[1], &r);
    proc_result_free(&r);
    sb_free(&out);
    return code;
}
