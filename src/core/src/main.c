#include "pen.h"

#include <stdio.h>
#include <string.h>
#include <stdlib.h>

const char *g_serial = NULL;
const char *g_cmd_name = "";
const char *g_known_hosts = NULL;

static int cmd_help(int argc, char **argv) {
    (void)argc;
    (void)argv;
    sb out;
    sb_init(&out);
    sb_puts(&out,
            "{\"ok\":true,\"version\":\"" PENCTL_VERSION "\",\"commands\":["
            "\"version\",\"detect\",\"device-info\",\"pkg-inspect\",\"shell\",\"push\",\"pull\"],\"usage\":["
            "\"penctl --ssh root@192.168.1.100 --key KEY shell uname -a\","
            "\"penctl --version\","
            "\"penctl --json detect\","
            "\"penctl --json device-info -s SERIAL\"]}\n");
    int rc = write_stdout(&out);
    sb_free(&out);
    return rc == 0 ? 0 : 3;
}

int main(int argc, char **argv) {
    const char *cmd = NULL;
    int json = 0;
    int arg_start = argc;

    for (int i = 1; i < argc; ++i) {
        const char *a = argv[i];
        if (strcmp(a, "--json") == 0) {
            json = 1;
        } else if (strcmp(a, "-s") == 0 || strcmp(a, "--serial") == 0) {
            if (i + 1 < argc) g_serial = argv[++i];
        } else if (strcmp(a, "--ssh") == 0) {
            if (i + 1 < argc) {
                g_host = argv[++i];
                g_transport = TRANSPORT_SSH;
            }
        } else if (strcmp(a, "--port") == 0) {
            if (i + 1 < argc) g_port = atoi(argv[++i]);
        } else if (strcmp(a, "--key") == 0) {
            if (i + 1 < argc) g_key = argv[++i];
        } else if (strcmp(a, "--known-hosts") == 0) {
            if (i + 1 < argc) g_known_hosts = argv[++i];
        } else if (strcmp(a, "--transport") == 0) {
            if (i + 1 < argc) g_transport = strcmp(argv[++i], "ssh") == 0 ? TRANSPORT_SSH : TRANSPORT_ADB;
        } else if (strcmp(a, "--version") == 0 || strcmp(a, "-V") == 0) {
            return cmd_version(0, NULL);
        } else if ((strcmp(a, "--help") == 0 || strcmp(a, "-h") == 0)) {
            return cmd_help(0, NULL);
        } else if (a[0] == '-') {
            sb out;
            sb_init(&out);
            emit_error(&out, "BAD_ARG", "unknown option");
            (void)write_stdout(&out);
            sb_free(&out);
            return 2;
        } else if (!cmd) {
            cmd = a;
            g_cmd_name = a;
            arg_start = i + 1;
            break; /* everything after the command belongs to the command */
        }
    }
    (void)json; /* every command emits JSON except --version/--help */

    if (!cmd) return cmd_help(0, NULL);
    if (strcmp(cmd, "version") == 0) return cmd_version(argc, argv);
    if (strcmp(cmd, "detect") == 0) return cmd_detect(argc, argv);
    if (strcmp(cmd, "device-info") == 0) return cmd_device_info(argc, argv);
    if (strcmp(cmd, "pkg-inspect") == 0) return cmd_pkg_inspect(argc, argv);
    if (strcmp(cmd, "shell") == 0) return cmd_shell(argc - arg_start, argv + arg_start);
    if (strcmp(cmd, "push") == 0) return cmd_push(argc - arg_start, argv + arg_start);
    if (strcmp(cmd, "pull") == 0) return cmd_pull(argc - arg_start, argv + arg_start);

    sb out;
    sb_init(&out);
    emit_error(&out, "UNKNOWN_COMMAND", "unknown command");
    (void)write_stdout(&out);
    sb_free(&out);
    return 2;
}
