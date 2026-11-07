"""M0 smoke test for the C core: exercises the JSON contract without a device.

Run:  python tests/smoke_core.py
Exit code 0 means every assertion passed.
"""
from __future__ import annotations

import itertools
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PENCTL = ROOT / "build" / "penctl.exe"

failures: list[str] = []
_counter = itertools.count()


def run(*args: str, env: dict | None = None) -> tuple[int, str, str]:
    """Run penctl redirecting to files: this sandbox denies anonymous pipes."""
    tmp = ROOT / ".toolchain" / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    out_path = tmp / f"smoke-{os.getpid()}-{next(_counter)}.out"
    err_path = tmp / f"smoke-{os.getpid()}-{next(_counter)}.err"
    try:
        with out_path.open("w", encoding="utf-8") as fo, err_path.open("w", encoding="utf-8") as fe:
            proc = subprocess.run(
                [str(PENCTL), *args],
                stdout=fo,
                stderr=fe,
                text=True,
                encoding="utf-8",
                env=env or dict(os.environ),
            )
        return (
            proc.returncode,
            out_path.read_text(encoding="utf-8", errors="replace"),
            err_path.read_text(encoding="utf-8", errors="replace"),
        )
    finally:
        for p in (out_path, err_path):
            try:
                p.unlink()
            except OSError:
                pass


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name} {detail}")
        failures.append(name)


def parse_json(out: str) -> dict | None:
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def main() -> int:
    if not PENCTL.is_file():
        print(f"missing {PENCTL}; run: python scripts/build_core.py", file=sys.stderr)
        return 2

    print("penctl JSON contract:")

    code, out, _ = run("--version")
    check("--version exits 0", code == 0, f"code={code}")
    check("--version mentions 0.1.0", "0.1.0" in out, out.strip()[:80])

    code, out, _ = run("--help")
    check("--help exits 0", code == 0, f"code={code}")
    help_doc = parse_json(out)
    check("--help emits JSON", help_doc is not None)
    if help_doc:
        check("--help lists detect", "detect" in (help_doc.get("commands") or []))

    env = dict(os.environ)
    env["PENCTL_ADB"] = str(ROOT / "definitely-missing-adb.exe")
    code, out, _ = run("--json", "detect", env=env)
    doc = parse_json(out)
    check("detect without adb -> ok=false", code == 1, f"code={code}")
    check("detect without adb -> ADB_MISSING", bool(doc) and doc.get("error", {}).get("code") == "ADB_MISSING")

    code, out, _ = run("--json", "device-info")
    doc = parse_json(out)
    check("device-info without -s -> NO_DEVICE", code == 1 and bool(doc)
          and doc.get("error", {}).get("code") == "NO_DEVICE", out.strip()[:120])

    fake_adb = ROOT / "build" / "fake_adb.exe"
    if fake_adb.is_file():
        fake_env = dict(os.environ)
        fake_env["PENCTL_ADB"] = str(fake_adb)
        code, out, _ = run("--json", "detect", env=fake_env)
        doc = parse_json(out) or {}
        devices = doc.get("devices") or []
        check("detect (fake adb) -> ok=true", code == 0 and doc.get("ok") is True, out.strip()[:160])
        check("detect (fake adb) finds one device", len(devices) == 1, f"devices={devices}")
        if devices:
            dev = devices[0]
            check("detect: serial parsed", dev.get("serial") == "R58MFAKEDEV", str(dev))
            check("detect: state=device", dev.get("state") == "device", str(dev))
            check("detect: model parsed", dev.get("model") == "YDP02X", str(dev))
            check("detect: shell ok", dev.get("shell") == "ok", str(dev))
            check("detect: penctl_ok", dev.get("penctl_ok") is True, str(dev))
        code, out, _ = run("--json", "-s", "R58MFAKEDEV", "device-info", env=fake_env)
        info = parse_json(out) or {}
        check("device-info (fake adb) -> ok=true", code == 0 and info.get("ok") is True, out.strip()[:200])
        derived = info.get("derived") or {}
        check("device-info: derived model", derived.get("model") == "YDP02X", str(derived))
        check("device-info: model supported", derived.get("model_supported") is True, str(derived))
        check("device-info: system version", derived.get("system_version") == "2.0.8", str(derived))
        check("device-info: penmods installed", derived.get("penmods_installed") is True, str(derived))

        code, out, _ = run("-s", "R58MFAKEDEV", "shell", "echo", "penctl-ok", env=fake_env)
        check("shell -> raw output", code == 0 and out.strip() == "penctl-ok", f"code={code} out={out!r}")

        code, out, _ = run("--json", "shell", "ls", env=fake_env)
        doc = parse_json(out) or {}
        check("shell without -s -> NO_DEVICE", code == 1 and doc.get("error", {}).get("code") == "NO_DEVICE", out.strip()[:120])

        code, out, _ = run("--json", "shell", env=fake_env)
        doc = parse_json(out) or {}
        check("shell without args -> BAD_ARG", code == 2 and doc.get("error", {}).get("code") == "BAD_ARG", out.strip()[:120])
    else:
        print("  skip fake adb checks (build/fake_adb.exe missing)")

    fake_ssh = ROOT / "build" / "fakebin" / "ssh.exe"
    if fake_ssh.is_file():
        ssh_env = dict(os.environ)
        ssh_env["PENCTL_SSH"] = str(fake_ssh)
        key = ROOT / ".toolchain" / "ssh" / "penmods_ed25519"
        code, out, _ = run("--json", "--ssh", "root@192.168.1.100", "--key", str(key),
                           "device-info", env=ssh_env)
        doc = parse_json(out) or {}
        check("ssh device-info -> ok=true", code == 0 and doc.get("ok") is True, out.strip()[:200])
        d = doc.get("derived") or {}
        check("ssh device-info: model", d.get("model") == "YDP02X", str(d))
        check("ssh device-info: system version", d.get("system_version") == "2.1.2", str(d))
        check("ssh device-info: serial is the target", doc.get("serial") == "root@192.168.1.100", str(doc.get("serial")))
        code, out, _ = run("--ssh", "root@192.168.1.100", "--key", str(key),
                           "shell", "echo", "penmods-ssh-ok", env=ssh_env)
        check("ssh shell -> raw output", code == 0 and out.strip() == "penmods-ssh-ok", f"code={code} out={out!r}")
        missing_env = dict(os.environ)
        missing_env["PENCTL_SSH"] = str(ROOT / "build" / "missing-ssh.exe")
        code, out, _ = run("--json", "--ssh", "root@192.168.1.100", "--key", str(key),
                           "device-info", env=missing_env)
        # no ssh tool must surface as an error, never as an empty "ok" device.
        doc = parse_json(out) or {}
        check("ssh without a usable binary -> error",
              code == 1 and doc.get("ok") is False, out.strip()[:160])
    else:
        print("  skip fake ssh checks (build/fake_ssh.exe missing)")

    code, out, _ = run("--json", "pkg-inspect", "x.zip")
    doc = parse_json(out)
    check("pkg-inspect -> NOT_IMPLEMENTED", code == 1 and bool(doc)
          and doc.get("error", {}).get("code") == "NOT_IMPLEMENTED")

    code, out, _ = run("--json", "bogus")
    doc = parse_json(out)
    check("unknown command -> UNKNOWN_COMMAND", code == 2 and bool(doc)
          and doc.get("error", {}).get("code") == "UNKNOWN_COMMAND")

    if failures:
        print(f"\n{len(failures)} check(s) failed: {', '.join(failures)}")
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
