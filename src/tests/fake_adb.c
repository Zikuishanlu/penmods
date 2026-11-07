/* fake_adb.exe - a tiny stand-in for adb.exe so the core can be tested offline.
 *
 * Supports just enough of the real interface for `penctl detect`/`device-info`:
 *   fake_adb version
 *   fake_adb devices [-l]
 *   fake_adb [-s SERIAL] shell <command...>
 */
#include <stdio.h>
#include <string.h>

static int has(const char *hay, const char *needle) { return strstr(hay, needle) != NULL; }

static void join(int argc, char **argv, int from, char *out, size_t cap) {
    out[0] = '\0';
    for (int i = from; i < argc; i++) {
        size_t used = strlen(out);
        if (used + strlen(argv[i]) + 2 >= cap) break;
        if (from < i) strcat(out, " ");
        strcat(out, argv[i]);
    }
}

int main(int argc, char **argv) {
    int i = 1;
    if (i < argc && strcmp(argv[i], "-s") == 0 && i + 1 < argc) i += 2;
    if (i >= argc) {
        printf("fake adb\n");
        return 1;
    }

    const char *cmd = argv[i];
    if (strcmp(cmd, "version") == 0) {
        printf("Android Debug Bridge version 1.0.41\nVersion 35.0.2-android-tools\n");
        return 0;
    }
    if (strcmp(cmd, "devices") == 0) {
        printf("List of devices attached\n");
        if (i + 1 < argc && strcmp(argv[i + 1], "-l") == 0) {
            printf("R58MFAKEDEV\tdevice product:YDP02X model:YDP02X device:YDP02X "
                   "transport_id:3 usb:1-1.2\n");
        } else {
            printf("R58MFAKEDEV\tdevice\n");
        }
        printf("\n");
        return 0;
    }
    if (strcmp(cmd, "shell") == 0) {
        char line[2048];
        join(argc, argv, i + 1, line, sizeof line);
        if (has(line, "auth")) {
            printf("success\n");
            return 0;
        }
        if (has(line, "penctl-ok")) {
            printf("penctl-ok\n");
            return 0;
        }
        if (has(line, "uname")) {
            printf("Linux localhost 4.4.189 #1 SMP PREEMPT aarch64 GNU/Linux\n");
            return 0;
        }
        if (has(line, "get_pcba_version")) {
            printf("YDP02X\n");
            return 0;
        }
        if (has(line, "test -f /userdata/PenMods/libPenMods.so")) {
            printf("yes\n");
            return 0;
        }
        if (has(line, "/Version")) {
            printf("Version: 2.0.8\npcba: YDP02X\n");
            return 0;
        }
        if (has(line, "getprop")) {
            printf("[ro.product.model]: [YDP02X]\n[ro.build.version.release]: [8.1.0]\n");
            return 0;
        }
        if (has(line, "ota-manifest")) {
            /* older PenMods installs have no manifest: let the pcba fallback win */
            return 0;
        }
        if (has(line, "uptime")) {
            printf("10:24am  up   3:07,  0 users,  load average: 0.12, 0.08, 0.03\n");
            return 0;
        }
        if (has(line, "df ")) {
            printf("/dev/block/mmcblk0p8 28712960 12000000 16712960 42%% /userdata\n");
            return 0;
        }
        printf("\n");
        return 0;
    }

    fprintf(stderr, "fake adb: unsupported command %s\n", cmd);
    return 1;
}
