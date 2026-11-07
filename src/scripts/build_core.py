"""Build penctl.exe with a portable Zig toolchain (`zig cc`).

No CMake/MSVC on the dev machine; Zig ships a full C toolchain and links the
MinGW runtime, which keeps penctl.exe self-contained (no VC++ redist).
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "build")
SRC = os.path.join(ROOT, "core", "src")


def find_zig() -> str | None:
    for pattern in ("zig/zig.exe", "zig/**/zig.exe"):
        hits = glob.glob(os.path.join(ROOT, ".toolchain", pattern), recursive=True)
        if hits:
            return sorted(hits, key=len)[0]
    return shutil.which("zig")


def main() -> int:
    zig = find_zig()
    if not zig:
        print("zig not found: run `python .toolchain/fetch_zig.py` first", file=sys.stderr)
        return 1

    sources = sorted(glob.glob(os.path.join(SRC, "*.c")))
    if not sources:
        print(f"no C sources under {SRC}", file=sys.stderr)
        return 1

    os.makedirs(BUILD, exist_ok=True)
    exe = os.path.join(BUILD, "penctl.exe")
    cmd = [
        zig,
        "cc",
        "-std=c11",
        "-O2",
        "-Wall",
        "-Wextra",
        "-Wno-unused-parameter",
        "-o",
        exe,
        *sources,
    ]
    print(" ".join(cmd))
    env = dict(os.environ)
    cache = os.path.join(ROOT, ".toolchain", "zig-cache")
    env.setdefault("ZIG_GLOBAL_CACHE_DIR", cache)
    env.setdefault("ZIG_LOCAL_CACHE_DIR", os.path.join(cache, "local"))
    proc = subprocess.run(cmd, cwd=ROOT, env=env)
    if proc.returncode != 0:
        print("build failed", file=sys.stderr)
        return proc.returncode
    print(f"built {exe} ({os.path.getsize(exe)} bytes)")

    for name in ("fake_adb", "fake_ssh"):
        fake_src = os.path.join(ROOT, "tests", f"{name}.c")
        if not os.path.isfile(fake_src):
            continue
        fake = os.path.join(BUILD, f"{name}.exe")
        fcmd = [zig, "cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-o", fake, fake_src]
        fproc = subprocess.run(fcmd, cwd=ROOT, env=env)
        if fproc.returncode == 0:
            print(f"built {fake} ({os.path.getsize(fake)} bytes)  [test stand-in]")
            if name == "fake_ssh":
                # penctl looks for ssh.exe/scp.exe inside PENCTL_SSH's directory,
                # so expose the stand-in under its real filename.
                fakebin = os.path.join(BUILD, "fakebin")
                os.makedirs(fakebin, exist_ok=True)
                for tool in ("ssh.exe", "scp.exe"):
                    shutil.copyfile(fake, os.path.join(fakebin, tool))
                print(f"  installed stand-in as {os.path.join(fakebin, 'ssh.exe')}")
        else:
            print(f"warning: {name} build failed (offline tests will be skipped)", file=sys.stderr)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
