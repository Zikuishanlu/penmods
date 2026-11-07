"""HTTP helpers: resumable downloads, checksums and small JSON GETs.

urllib is used on purpose: the C core only speaks to the device, so the
manager app owns the network side.
"""
from __future__ import annotations

import hashlib
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

from . import safe

USER_AGENT = "PenModsManager/0.1 (+https://github.com/lyrecoul/PenMods)"
Progress = Callable[[int, int], None]


class NetError(RuntimeError):
    def __init__(self, code: str, message: str, detail: str | None = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.detail = detail

    def to_dict(self) -> dict:
        out = {"code": self.code, "message": self.message}
        if self.detail:
            out["detail"] = self.detail[:2000]
        return out


def _opener() -> urllib.request.OpenerDirector:
    ctx = ssl.create_default_context()
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))


def _checked_url(url: str, *, allow_localhost: bool = True) -> str:
    """Only https (or http to localhost) is allowed for network fetches."""
    try:
        return safe.require_https(url, allow_localhost=allow_localhost, what="下载地址")
    except safe.SafetyError as exc:
        raise NetError(exc.code, exc.message) from exc


def get_json(url: str, *, timeout: float = 20, headers: dict | None = None) -> dict:
    url = _checked_url(url)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        with _opener().open(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        raise NetError("HTTP_STATUS", f"HTTP {exc.code} · {url}", exc.read()[:500].decode("utf-8", "replace")) from exc
    except urllib.error.URLError as exc:
        raise NetError("NETWORK", f"无法连接 {urllib.parse.urlsplit(url).netloc}", str(exc.reason)) from exc
    except TimeoutError as exc:
        raise NetError("TIMEOUT", f"请求超时：{url}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise NetError("BAD_JSON", "响应不是合法 JSON", raw[:500].decode("utf-8", "replace")) from exc


def sha256_file(path: Path, *, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def md5_file(path: Path, *, chunk: int = 1 << 20) -> str:
    h = hashlib.md5()
    with path.open("rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def download(
    url: str,
    dest: Path,
    *,
    sha256: str | None = None,
    timeout: float = 60,
    progress: Progress | None = None,
    max_attempts: int = 3,
    max_bytes: int | None = 256 * 1024 * 1024,
) -> Path:
    """Download `url` to `dest`, resuming partial files, then verify sha256.

    `max_bytes` caps the download so a wrong URL (or a hostile one) cannot fill
    the disk before the checksum check ever runs.
    """
    url = _checked_url(url)
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    attempt = 0
    while True:
        attempt += 1
        have = part.stat().st_size if part.exists() else 0
        if max_bytes is not None and have > max_bytes:
            part.unlink(missing_ok=True)
            raise NetError("TOO_LARGE", f"已下载的数据超过上限：{dest.name}")
        headers = {"User-Agent": USER_AGENT}
        if have:
            headers["Range"] = f"bytes={have}-"
        req = urllib.request.Request(url, headers=headers)
        try:
            with _opener().open(req, timeout=timeout) as resp:
                total = int(resp.headers.get("Content-Length") or 0) + have
                mode = "ab" if have and resp.status == 206 else "wb"
                with part.open(mode) as fh:
                    done = have if mode == "ab" else 0
                    while True:
                        block = resp.read(1 << 20)
                        if not block:
                            break
                        fh.write(block)
                        done += len(block)
                        if max_bytes is not None and done > max_bytes:
                            raise NetError("TOO_LARGE", f"下载超过上限：{dest.name}")
                        if progress is not None:
                            progress(done, total)
            break
        except NetError:
            part.unlink(missing_ok=True)
            raise
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ConnectionError) as exc:
            if attempt >= max_attempts:
                raise NetError("DOWNLOAD_FAILED", f"下载失败：{dest.name}", str(exc)) from exc
            time.sleep(1.5 * attempt)

    if sha256 and sha256_file(part).lower() != sha256.lower():
        part.unlink(missing_ok=True)
        raise NetError("CHECKSUM_MISMATCH", f"{dest.name} 的 SHA256 校验失败")
    part.replace(dest)
    return dest


def parse_sha256sums(text: str) -> dict[str, str]:
    """Parse a `sha256sum`-style file: `<hex>  <name>` per line."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        name = parts[-1]
        if name.startswith("*"):          # sha256sum -b style binary marker
            name = name[1:]
        if name.startswith("./"):         # ./dir/file -> dir/file
            name = name[2:]
        digest = parts[0].lower()
        if len(digest) == 64:
            out[name] = digest
    return out
