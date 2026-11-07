"""PenMods OTA channel: manifest parsing, version compare, payload download.

The device updater downloads `update_vX.Y.Z.zip` and runs `_do_update.sh`. This
manager does the same work from the PC instead: verify the zip, extract the
payload, push it over the selected transport, then restart the pen UI.
"""
from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path

from . import netutil

DEFAULT_MANIFEST_URL = "https://cdn.jsdelivr.net/gh/lyrecoul/penmods-ota@main/updates.json"


class OtaError(RuntimeError):
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


@dataclass
class OtaEntry:
    version: tuple[int, int, int]
    note: str
    size: int
    download: str
    md5: str

    @property
    def text(self) -> str:
        return ".".join(str(p) for p in self.version)

    def to_dict(self) -> dict:
        return {
            "version": self.text,
            "note": self.note,
            "size": self.size,
            "download": self.download,
            "md5": self.md5,
        }


def parse_version(text: str) -> tuple[int, int, int]:
    parts = [int(p) for p in str(text).strip().lstrip("vV").split(".")[:3] if p.isdigit()]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])  # type: ignore[return-value]


def parse_manifest(doc: dict) -> list[OtaEntry]:
    """Legacy shape: {status, versions:[{version:[X,Y,Z], note, size, download, md5}]}."""
    out: list[OtaEntry] = []
    for item in doc.get("versions") or []:
        raw = item.get("version")
        if isinstance(raw, list):
            version = tuple(int(p) for p in (list(raw) + [0, 0, 0])[:3])
        else:
            version = parse_version(str(raw or "0"))
        download = str(item.get("download") or "")
        if not download:
            continue
        out.append(
            OtaEntry(
                version=version,  # type: ignore[arg-type]
                note=str(item.get("note") or ""),
                size=int(item.get("size") or 0),
                download=download,
                md5=str(item.get("md5") or "").lower(),
            )
        )
    out.sort(key=lambda e: e.version, reverse=True)
    return out


def fetch_manifest(url: str = DEFAULT_MANIFEST_URL) -> list[OtaEntry]:
    try:
        doc = netutil.get_json(url)
    except netutil.NetError as exc:
        raise OtaError(exc.code, "无法获取 OTA 清单", exc.detail) from exc
    entries = parse_manifest(doc)
    if not entries:
        raise OtaError("EMPTY_MANIFEST", "OTA 清单里没有可用版本")
    return entries


def pick_update(entries: list[OtaEntry], current: str | None) -> OtaEntry | None:
    """Highest version strictly newer than `current` (None when up to date)."""
    if not entries:
        return None
    newest = entries[0]
    if current and parse_version(current) >= newest.version:
        return None
    return newest


def download_update(entry: OtaEntry, workdir: Path, progress=None) -> Path:
    dest = workdir / Path(entry.download).name
    if dest.is_file():
        if not entry.md5 or netutil.md5_file(dest) == entry.md5:
            return dest
        dest.unlink()
    try:
        path = netutil.download(entry.download, dest, timeout=180, progress=progress)
    except netutil.NetError as exc:
        raise OtaError(exc.code, exc.message, exc.detail) from exc
    if entry.md5 and netutil.md5_file(path) != entry.md5:
        path.unlink(missing_ok=True)
        raise OtaError("CHECKSUM_MISMATCH", f"{path.name} 的 MD5 与清单不一致")
    if entry.size and path.stat().st_size != entry.size:
        raise OtaError("SIZE_MISMATCH", f"{path.name} 大小 {path.stat().st_size} 与清单 {entry.size} 不一致")
    return path


def payload_files(zip_path: Path) -> dict[str, bytes]:
    """Read the update zip into memory: {relative name: bytes}.

    The OTA zip is small (~5 MB) and flat (libPenMods.so, resources, script),
    so holding it is cheaper than a second temp file dance.
    """
    try:
        with zipfile.ZipFile(zip_path) as zf:
            bad = zf.testzip()
            if bad is not None:
                raise OtaError("ZIP_CORRUPT", f"更新包损坏：{bad}")
            out: dict[str, bytes] = {}
            for info in zf.infolist():
                if info.is_dir():
                    continue
                name = info.filename.replace("\\", "/")
                if name.startswith("/") or ".." in name.split("/"):
                    raise OtaError("ZIP_UNSAFE", f"更新包包含危险路径：{name}")
                if info.file_size > 64 * 1024 * 1024:
                    raise OtaError("ZIP_TOO_BIG", f"更新包内文件过大：{name}")
                out[name] = zf.read(info)
            return out
    except zipfile.BadZipFile as exc:
        raise OtaError("ZIP_CORRUPT", "更新包不是有效 zip", str(exc)) from exc


def describe(entries: list[OtaEntry], current: str | None) -> dict:
    """Small snapshot for the install page: current, available, up_to_date."""
    update = pick_update(entries, current)
    return {
        "current": current or "",
        "up_to_date": update is None,
        "available": update.to_dict() if update else None,
        "count": len(entries),
    }


def load_local_manifest(path: Path) -> list[OtaEntry]:
    """Parse a manifest cached on disk (used by tests and offline mode)."""
    return parse_manifest(json.loads(path.read_text(encoding="utf-8")))
