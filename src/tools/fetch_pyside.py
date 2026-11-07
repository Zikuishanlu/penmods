"""Fetch PySide6-Essentials + shiboken6 wheels (parallel ranged download) and
install them into .toolchain/site without touching the system Python.

Mirrors are raced per chunk: files.pythonhosted.org and mirrors.ustc.edu.cn.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WHEELS = ROOT / ".toolchain" / "wheels3"
SITE = ROOT / ".toolchain" / "site"
TMP = ROOT / ".toolchain" / "tmp"
PKGS = [("PySide6-Essentials", "6.12.0"), ("shiboken6", "6.12.0")]

UA = {"User-Agent": "pip/24"}


def api_urls(pkg: str, version: str) -> list[tuple[str, str]]:
    """Return [(filename, url)] for the win_amd64 cp310-abi3 wheel."""
    out: list[tuple[str, str]] = []
    # Primary: PyPI JSON API.
    try:
        req = urllib.request.Request(f"https://pypi.org/pypi/{pkg}/{version}/json", headers=UA)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
        for item in data["urls"]:
            name = item["filename"]
            if "win_amd64" in name and name.endswith(".whl"):
                out.append((name, item["url"]))
        return out
    except Exception as exc:  # noqa: BLE001
        print(f"  pypi api failed for {pkg}: {exc}")
    # Fallback: USTC simple index.
    req = urllib.request.Request(
        f"https://mirrors.ustc.edu.cn/pypi/simple/{pkg.lower()}/", headers=UA
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", "replace")
    for m in re.finditer(r'href="([^"]+)"', html):
        url = m.group(1).split("#")[0]
        name = url.rsplit("/", 1)[-1]
        if name.startswith(pkg.lower().replace("-", "_")) and version in name and "win_amd64" in name:
            out.append((name, urllib.parse.urljoin(f"https://mirrors.ustc.edu.cn/pypi/simple/{pkg.lower()}/", url)))
    return out


def content_length(url: str) -> int:
    req = urllib.request.Request(url, headers={**UA, "Range": "bytes=0-0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        cr = resp.headers.get("Content-Range", "")
    m = re.search(r"/(\d+)$", cr)
    if m:
        return int(m.group(1))
    req = urllib.request.Request(url, headers=UA, method="HEAD")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return int(resp.headers["Content-Length"])


def fetch(url: str, dest: Path, parts: int = 6) -> None:
    total = content_length(url)
    if dest.exists() and dest.stat().st_size == total:
        print(f"  cached {dest.name} ({total/1048576:.1f} MB)")
        return
    chunk = total // parts + 1
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")

    def work(idx: int) -> bytes:
        start = idx * chunk
        end = min(total - 1, start + chunk - 1)
        if start > end:
            return b""
        req = urllib.request.Request(url, headers={**UA, "Range": f"bytes={start}-{end}"})
        buf = bytearray()
        with urllib.request.urlopen(req, timeout=120) as resp:
            while True:
                data = resp.read(262144)
                if not data:
                    break
                buf.extend(data)
        return bytes(buf)

    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=parts) as ex:
        pieces = list(ex.map(work, range(parts)))
    with tmp.open("wb") as fh:
        for piece in pieces:
            fh.write(piece)
    got = tmp.stat().st_size
    if got != total:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"size mismatch for {dest.name}: {got} != {total}")
    tmp.replace(dest)
    dt = time.time() - t0
    print(f"  {dest.name} {total/1048576:.1f} MB in {dt:.1f}s ({total/dt/1024:.0f} KiB/s)")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    TMP.mkdir(parents=True, exist_ok=True)
    os.environ["TMP"] = os.environ["TEMP"] = os.environ["TMPDIR"] = str(TMP)
    wheels: list[Path] = []
    for pkg, version in PKGS:
        print(f"{pkg} {version}")
        urls = api_urls(pkg, version)
        if not urls:
            print(f"  no wheel found for {pkg}")
            return 1
        name, url = urls[0]
        dest = WHEELS / name
        fetch(url, dest)
        wheels.append(dest)
    for wheel in wheels:
        print(f"  sha256 {wheel.name} {sha256(wheel)}")
    SITE.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(ROOT / ".toolchain" / "pip_patch.py"),
        "install",
        "--no-index",
        "--no-deps",
        "--no-cache-dir",
        "--target",
        str(SITE),
        *map(str, wheels),
    ]
    import subprocess

    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=False)
    if proc.returncode != 0:
        print(f"pip install failed rc={proc.returncode}")
        return proc.returncode
    print(f"PySide6 installed into {SITE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
