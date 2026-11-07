/* fake_ssh.c — deterministic stand-in for OpenSSH's ssh.exe in offline tests.
 *
 * Usage mirrors `ssh [options] host command`:
 *   fake_ssh.exe -i key -o BatchMode=yes -o StrictHostKeyChecking=accept-new
 *                -o UserKnownHostsFile=... -o ConnectTimeout=10 -p 22 root@host "cmd"
 *
 * It answers the handful of commands penctl issues (device-info probes and the
 * SSH reachability probe) with canned pen output. Anything else returns an
 * empty stdout, like a command that prints nothing.
 */
#include <stdio.h>
#include <string.h>

static int has(const char *hay, const char *needle) {
    return hay && strstr(hay, needle) != NULL;
}

int main(int argc, char **argv) {
    const char *cmd = NULL;
    int i = 1;

    /* skip options; -i/-o/-p/-F/-l/-P take a value */
    for (; i < argc; ++i) {
        const char *a = argv[i];
        if (a[0] == '-') {
            if (strcmp(a, "-i") == 0 || strcmp(a, "-o") == 0 || strcmp(a, "-p") == 0 ||
                strcmp(a, "-F") == 0 || strcmp(a, "-l") == 0) {
                ++i;
            }
            continue;
        }
        /* first non-option is the host */
        if (i + 1 < argc) cmd = argv[i + 1];
        break;
    }

    if (!cmd) {
        fputs("fake_ssh: no command\n", stderr);
        return 255;
    }

    if (has(cmd, "echo penmods-ssh-ok")) {
        puts("penmods-ssh-ok");
    } else if (has(cmd, "uname -r")) {
        puts("4.4.159");
    } else if (has(cmd, "uname -a")) {
        puts("Linux YoudaoDictionaryPen-667 4.4.159 #1 SMP Fri Aug 18 16:54:58 HKT 2023 aarch64 GNU/Linux");
    } else if (has(cmd, "cat /Version")) {
        puts("Build_Time: Fri Aug 18 17:07:17 HKT 2023");
        puts("Version: 2.1.2");
        puts("pcba: Exam_V0");
    } else if (has(cmd, "get_pcba_version")) {
        puts("Exam_V0");
    } else if (has(cmd, "libPenMods.so")) {
        puts("yes");
    } else if (has(cmd, "adb_autorun")) {
        puts("\"adb_autorun\": true");
    } else if (has(cmd, "ssh_autorun")) {
        puts("\"ssh_autorun\": true");
    } else if (has(cmd, "adb_skip_verification")) {
        puts("\"adb_skip_verification\": true");
    } else if (has(cmd, "YoudaoDictPen")) {
        puts("-rwxr-xr-x 1 root root 10923704 Oct 17 23:19 /oem/YoudaoDictPen/output/YoudaoDictPen");
    } else if (has(cmd, "usb_config")) {
        puts("usb_adb_en");
    } else if (has(cmd, "sshd")) {
        puts("sshd: /usr/sbin/sshd [listener]");
    } else if (has(cmd, "df -h")) {
        puts("248M 32M 217M 13%");
    } else if (has(cmd, "uptime")) {
        puts("0:15");
    } else if (has(cmd, "ota-manifest.json")) {
        puts("YDP02X");
    } else if (has(cmd, "cat /userdata/PenModsconfig.json")) {
        puts("{\"serv\":{\"adb_autorun\":true,\"adb_skip_verification\":true,\"ssh_autorun\":true}}");
    } else if (has(cmd, "ls -la")) {
        puts("-rw-r--r-- 1 root root 9887800 Jan  1 00:00 libPenMods.so");
    }
    return 0;
}
