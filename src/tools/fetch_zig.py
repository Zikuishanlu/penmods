"""Download a portable Zig toolchain (resumable, streams to disk).

Used as the Windows C/C++ compiler via `zig cc` / `zig c++`.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(HERE, "zig")
ARCHIVE = os.path.join(HERE, "zig.zip")
INDEX = "https://ziglang.org/download/index.json"
UA = {"User-Agent": "penmods-toolchain/1.0"}


def pick_url() -> tuple[str, str]:
    req = urllib.request.Request(INDEX, headers=UA, )
    with urllib.request.urlopen(req, timeout=60) as r:
        idx = json.load(r)
    versions = [k for k in idx if k != "master"]

    def vkey(v: str):
        try:
            return tuple(int(x) for x in v.split("."))
        except ValueError:
            return (0,)

    versions.sort(key=vkey, reverse=True)
    for v in versions:
        entry = idx[v]
        for plat in ("x86_64-windows", "x86_64-windows-gnu"):
            url = entry.get(plat, {}).get("tarball")
            if url:
                return v, url
    raise SystemExit("no windows zig build in index.json")


def download(url: str) -> None:
    """Download with resume + retries: this sandbox's egress resets long connections."""
    attempts = 0
    while True:
        have = os.path.getsize(ARCHIVE) if os.path.exists(ARCHIVE) else 0
        headers = dict(UA)
        if have:
            headers["Range"] = f"bytes={have}-"
        req = urllib.request.Request(url, headers=headers)
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=60) as r, open(ARCHIVE, "ab") as f:
                if have and r.status != 206:
                    print("server ignored Range, restarting from 0", flush=True)
                    f.truncate(0)
                    have = 0
                total = have + int(r.headers.get("Content-Length") or 0)
                print(f"resume at {have / 1e6:.1f} MB, total ~{total / 1e6:.1f} MB", flush=True)
                last = 0.0
                while True:
                    chunk = r.read(1 << 16)
                    if not chunk:
                        break
                    f.write(chunk)
                    have += len(chunk)
                    now = time.time()
                    if now - last > 3:
                        last = now
                        rate = have / 1e6 / max(now - t0, 0.001)
                        print(f"  {have / 1e6:6.1f} MB  ({rate:.2f} MB/s)", flush=True)
            return
        except (ConnectionResetError, TimeoutError, OSError) as exc:
            attempts += 1
            print(f"  connection dropped ({type(exc).__name__}: {exc}); attempt {attempts}", flush=True)
            if attempts >= 40:
                raise
            time.sleep(1.5)


def extract() -> None:
    os.makedirs(DEST, exist_ok=True)
    with zipfile.ZipFile(ARCHIVE) as z:
        names = z.namelist()
        root = names[0].split("/")[0] if names else ""
        z.extractall(DEST)
    # flatten the single top-level folder so zig.exe sits at DEST/zig.exe
    inner = os.path.join(DEST, root)
    if root and os.path.isdir(inner) and os.path.isfile(os.path.join(inner, "zig.exe")):
        for name in os.listdir(inner):
            src = os.path.join(inner, name)
            dst = os.path.join(DEST, name)
            if os.path.exists(dst):
                print("  skip existing", name, flush=True)
                continue
            os.replace(src, dst)
        os.rmdir(inner)
    print("extracted to", DEST, flush=True)
    for name in sorted(os.listdir(DEST)):
        print("  ", name, flush=True)


def main() -> int:
    ver, url = pick_url()
    print(f"zig {ver}: {url}", flush=True)
    download(url)
    size = os.path.getsize(ARCHIVE)
    print(f"archive complete: {size / 1e6:.1f} MB", flush=True)
    extract()
    os.remove(ARCHIVE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
