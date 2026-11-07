"""Fetch Google's platform-tools (adb.exe + USB DLLs) into .toolchain/platform-tools."""
from __future__ import annotations

import io
import os
import sys
import urllib.request
import zipfile
from pathlib import Path

URL = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".toolchain" / "platform-tools"
WANT = {"adb.exe", "AdbWinApi.dll", "AdbWinUsbApi.dll"}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    if all((OUT / name).is_file() for name in WANT):
        print(f"already present: {OUT}")
        return 0
    zip_path = OUT / "platform-tools.zip"
    for attempt in range(3):
        try:
            print(f"downloading {URL} (attempt {attempt + 1})")
            req = urllib.request.Request(URL, headers={"User-Agent": "penmods-manager"})
            with urllib.request.urlopen(req, timeout=120) as resp, zip_path.open("wb") as fh:
                total = int(resp.headers.get("Content-Length") or 0)
                done = 0
                while True:
                    chunk = resp.read(1 << 16)
                    if not chunk:
                        break
                    fh.write(chunk)
                    done += len(chunk)
                    if done % (4 << 20) < (1 << 16):
                        print(f"  {done / 1048576:.1f}/{total / 1048576:.1f} MB", flush=True)
            break
        except Exception as exc:  # noqa: BLE001
            print(f"  failed: {exc}")
    if not zip_path.is_file() or zip_path.stat().st_size < 1_000_000:
        print("download failed", file=sys.stderr)
        return 1
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            name = info.filename.rsplit("/", 1)[-1]
            if name in WANT:
                target = OUT / name
                with zf.open(info) as src, target.open("wb") as dst:
                    dst.write(src.read())
                print(f"  extracted {name} ({target.stat().st_size} bytes)")
    zip_path.unlink(missing_ok=True)
    missing = [n for n in WANT if not (OUT / n).is_file()]
    if missing:
        print(f"missing after extract: {missing}", file=sys.stderr)
        return 1
    print(f"platform-tools ready: {OUT / 'adb.exe'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
