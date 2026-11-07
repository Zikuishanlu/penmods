"""Build the Windows onedir bundle (M6).

    python scripts/build_dist.py [--keep]

Outputs:
    dist/PenModsManager/PenModsManager.exe   (GUI, no console)
    dist/PenModsManager/penctl.exe           (C core, next to the GUI)
    dist/PenModsManager/_internal/...        (PySide6 + QML + data)

Requires PyInstaller inside .toolchain/site:
    python .toolchain/pip_patch.py install -q --target .toolchain/site \
        -i https://mirrors.aliyun.com/pypi/simple/ pyinstaller
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / ".toolchain" / "site"
BUILD = ROOT / "build"
DIST = ROOT / "dist"
APP = ROOT / "app"
WORK = ROOT / ".toolchain" / "pyinstaller"
ENTRY = ROOT / ".toolchain" / "dist_entry.py"
NAME = "PenModsManager"

ENTRY_SOURCE = """\
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "app"))

from penmanager.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
"""


def run(cmd: list[str], *, env: dict | None = None) -> None:
    print("+", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=str(ROOT), env=env)
    if proc.returncode != 0:
        raise SystemExit(f"command failed with {proc.returncode}: {cmd[0]}")


def main() -> int:
    if not SITE.is_dir():
        print(f"[dist] missing {SITE}; install PySide6/PyInstaller there first", file=sys.stderr)
        return 2

    # 1) C core first: the bundle ships build/penctl.exe
    run([sys.executable, str(ROOT / "scripts" / "build_core.py")])
    penctl = BUILD / "penctl.exe"
    if not penctl.is_file():
        print("[dist] penctl.exe missing", file=sys.stderr)
        return 2

    # 2) entry script for PyInstaller
    ENTRY.write_text(ENTRY_SOURCE, encoding="utf-8")

    # 3) PyInstaller onedir, windowed
    env = dict(**__import__("os").environ)
    env["PYTHONPATH"] = str(SITE) + (";" + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["ZIG_GLOBAL_CACHE_DIR"] = str(ROOT / ".toolchain" / "zig-cache")
    env["ZIG_LOCAL_CACHE_DIR"] = str(ROOT / ".toolchain" / "zig-cache" / "local")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        NAME,
        "--paths",
        str(APP),
        "--add-data",
        f"{APP / 'penmanager' / 'qml'};penmanager/qml",
        "--add-data",
        f"{APP / 'penmanager' / 'data'};penmanager/data",
        "--distpath",
        str(DIST),
        "--workpath",
        str(WORK),
        "--specpath",
        str(WORK),
        str(ENTRY),
    ]
    run(cmd, env=env)

    # 4) ship penctl.exe next to the exe (paths.penctl_path() looks there)
    target = DIST / NAME / "penctl.exe"
    shutil.copy2(penctl, target)
    print(f"[dist] copied {target.name} ({target.stat().st_size} bytes)")

    # 5) ship platform-tools (adb.exe finds its DLLs next to itself;
    #    penctl's adb_path() also looks next to penctl.exe) so a fresh
    #    machine does not need Android SDK installed.
    platform_tools = ROOT / ".toolchain" / "platform-tools"
    if platform_tools.is_dir():
        bundled = 0
        for item in sorted(platform_tools.iterdir()):
            if item.is_file() and item.suffix.lower() in (".exe", ".dll"):
                shutil.copy2(item, DIST / NAME / item.name)
                bundled += 1
        if bundled:
            print(f"[dist] bundled {bundled} platform-tools file(s) (adb.exe)")
    else:
        print("[dist] platform-tools missing; the app will need adb on PATH")

    exe = DIST / NAME / f"{NAME}.exe"
    if not exe.is_file():
        print("[dist] exe missing", file=sys.stderr)
        return 2
    total = sum(f.stat().st_size for f in (DIST / NAME).rglob("*") if f.is_file())
    print(f"[dist] {exe} ({total / 1048576:.1f} MB total)")
    print("[dist] verify:  dist\\PenModsManager\\PenModsManager.exe --screenshot shots\\dist.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
