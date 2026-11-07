"""PenMods v2.7+ update-system: staged component installs via `penmods-update`.

Newer firmware installations keep immutable generations under
/userdisk/PenMods/update-system and select one active generation through a
symlink. Files there must never be replaced in place; components are staged with
`penmods-update stage DESCRIPTOR ARCHIVE`, which verifies hashes, extracts into a
pending generation and only enables it after a successful trial launch.

This module only stages (and optionally enables) components. It never writes into
the active generation directly.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from . import netutil, penctl, safe

MANIFEST_URL = "https://cdn.jsdelivr.net/gh/lyrecoul/penmods-ota@main/updates.json"
HELPER = "/userdata/PenMods/penmods-update"
STORE = "/userdisk/PenMods/update-system"
STAGE_DIR = "/userdisk/PenMods/update-system/staging"
DISABLED_MARKER = "/userdisk/PenMods/update-system/disabled"

COMPONENT_IDS = ("core", "player", "mathjax", "ppocr")


def _digest(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not _HEX64_RE.match(text):
        raise UpdateError("BAD_DIGEST", f"组件 sha256 不合法：{value!r}")
    return text


class UpdateError(Exception):
    def __init__(self, code: str, message: str, detail: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "detail": self.detail}


@dataclass
class ComponentVersion:
    id: str
    name: str
    version: str
    channel: str
    model: str
    arch: str
    size: int
    unpacked_size: int
    sha256: str
    download: str
    note: str = ""
    requires: dict[str, Any] | None = None
    health_protocol: int | None = None

    def descriptor(self) -> dict:
        data: dict[str, Any] = {
            "id": self.id,
            "version": self.version,
            "model": self.model,
            "arch": self.arch,
            "channel": self.channel,
            "size": self.size,
            "unpacked_size": self.unpacked_size,
            "sha256": self.sha256,
        }
        if self.health_protocol:
            data["health_protocol"] = self.health_protocol
        if self.requires:
            data["requires"] = self.requires
        return data


_VERSION_RE = re.compile(r"\d{1,4}\.\d{1,4}\.\d{1,4}\Z")
_HEX64_RE = re.compile(r"[0-9a-f]{64}\Z")


def _version_text(value: Any) -> str:
    if isinstance(value, list):
        text = ".".join(str(int(part)) for part in value)
    else:
        text = str(value or "").strip()
    if not text:
        raise UpdateError("BAD_VERSION", "组件版本为空")
    if not _VERSION_RE.match(text):
        raise UpdateError("BAD_VERSION", f"组件版本号不合法：{text}")
    return text


def fetch_manifest() -> dict:
    return netutil.get_json(MANIFEST_URL, timeout=30)


def parse_components(manifest: dict) -> list[dict]:
    """Return [{id, name, versions: [ComponentVersion]}] from an OTA manifest."""
    out: list[dict] = []
    for raw in manifest.get("components") or []:
        comp_id = str(raw.get("id") or "")
        if comp_id not in COMPONENT_IDS:
            continue
        versions: list[ComponentVersion] = []
        for entry in raw.get("versions") or []:
            try:
                versions.append(
                    ComponentVersion(
                        id=comp_id,
                        name=str(raw.get("name") or comp_id),
                        version=_version_text(entry.get("version")),
                        channel=str(entry.get("channel") or "dev"),
                        model=str(entry.get("model") or ""),
                        arch=str(entry.get("arch") or "aarch64"),
                        size=int(entry.get("size") or 0),
                        unpacked_size=int(entry.get("unpacked_size") or 0),
                        sha256=_digest(entry.get("sha256")),
                        download=str(entry.get("download") or ""),
                        note=str(entry.get("note") or ""),
                        requires=entry.get("requires"),
                        health_protocol=entry.get("health_protocol"),
                    )
                )
            except (TypeError, ValueError) as exc:
                raise UpdateError("BAD_MANIFEST", f"组件 {comp_id} 的版本条目非法：{exc}") from exc
        if versions:
            out.append({"id": comp_id, "name": str(raw.get("name") or comp_id), "versions": versions})
    if not out:
        raise UpdateError("NO_COMPONENTS", "manifest 里没有 components 数组")
    return out


def pick_version(versions: Iterable[ComponentVersion], model: str) -> ComponentVersion:
    candidates = [v for v in versions if not v.model or v.model == model]
    if not candidates:
        raise UpdateError("MODEL_MISMATCH", f"没有适用于 {model} 的组件版本")
    return candidates[0]


def shell(serial: str | None, command: str, timeout: float = 120) -> str:
    """Run a raw device shell command through penctl (plain text, not JSON)."""
    base = ["-s", serial] if serial else []
    try:
        return penctl.run_text(base + ["shell", command], timeout=timeout)
    except penctl.PenctlError as exc:
        raise UpdateError("SHELL_FAILED", f"设备命令失败：{command}", exc.detail or exc.message) from exc


def status(serial: str | None = None) -> dict:
    base = ["-s", serial] if serial else []
    try:
        text = penctl.run_text(base + ["shell", f"{HELPER} status"], timeout=60)
    except penctl.PenctlError as exc:
        raise UpdateError("HELPER_MISSING", f"设备上没有可用的 penmods-update：{exc.message}") from exc
    try:
        return json.loads(text.strip().splitlines()[-1])
    except (ValueError, IndexError) as exc:
        raise UpdateError("BAD_STATUS", f"无法解析 penmods-update status：{text[:300]}") from exc


def device_has_update_system(serial: str | None = None) -> bool:
    try:
        return "yes" in shell(serial, f"test -x {HELPER} && echo yes", timeout=60)
    except UpdateError:
        return False


def installed_versions(current: dict | None) -> dict[str, str]:
    out: dict[str, str] = {}
    if not current:
        return out
    for comp_id, meta in (current.get("components") or {}).items():
        out[comp_id] = str((meta or {}).get("version") or "")
    return out


def _version_tuple(text: Any) -> tuple[int, ...]:
    parts = re.findall(r"\d+", str(text or ""))[:3]
    return tuple(int(part) for part in parts) if parts else (0,)


def requires_state(requires: Any, installed: dict[str, str]) -> tuple[bool, str]:
    """Check a component's `requires` block against the installed versions.

    The manifest expresses inter-component dependencies either as
    {"core": "2.7.3"} or as {"core": {"min": "2.7.3", "max_exclusive": "3.0.0"}}
    (player 1.0.5 needs core >= 2.7.3). Returns (satisfied, reason when not).
    """
    if not isinstance(requires, dict):
        return True, ""
    for comp_id, spec in requires.items():
        minimum = ""
        maximum = ""
        if isinstance(spec, str):
            minimum = spec
        elif isinstance(spec, dict):
            minimum = str(spec.get("min") or "")
            maximum = str(spec.get("max_exclusive") or "")
        else:
            continue
        have = installed.get(comp_id, "")
        if minimum.strip() and _version_tuple(have) < _version_tuple(minimum):
            return False, f"需要 {comp_id} ≥ {minimum}，当前 {have or '未安装'}"
        if maximum.strip() and have and _version_tuple(have) >= _version_tuple(maximum):
            return False, f"需要 {comp_id} < {maximum}，当前 {have}"
    return True, ""


def plan(manifest: dict, current: dict | None) -> list[dict]:
    """Rows for the UI: component id/name/installed/latest/pending/note/size."""
    model = str(((current or {}).get("model")) or "YDP02X")
    installed = installed_versions(current)
    pending = (current or {}).get("pending_components") or {}
    rows: list[dict] = []
    for comp in parse_components(manifest):
        version = pick_version(comp["versions"], model)
        satisfied, reason = requires_state(version.requires, installed)
        current_version = installed.get(comp["id"], "")
        blocked = not satisfied and current_version != version.version
        newer_installed = bool(current_version) and _version_tuple(current_version) > _version_tuple(version.version)
        up_to_date = current_version == version.version or newer_installed
        note = version.note
        if newer_installed and not note:
            note = "设备通道没有更新的版本"
        rows.append(
            {
                "id": comp["id"],
                "name": comp["name"],
                "installed": current_version,
                "latest": version.version,
                "pending": bool(pending.get(comp["id"])),
                "note": note,
                "size": version.size,
                "required": comp["id"] == "core",
                "requires": version.requires or {},
                "up_to_date": up_to_date,
                "blocked": blocked,
                "blocked_reason": reason,
            }
        )
    return rows


def download(version: ComponentVersion, workdir: Path) -> Path:
    workdir.mkdir(parents=True, exist_ok=True)
    name = safe.safe_filename(f"{version.id}-{version.version}.zip")
    dest = workdir / name
    if dest.is_file() and dest.stat().st_size == version.size:
        return dest
    # the manifest declares the exact size, so a runaway download is caught early
    netutil.download(version.download, dest, sha256=version.sha256, timeout=600,
                     max_bytes=max(version.size * 2, 8 * 1024 * 1024))
    if dest.stat().st_size != version.size:
        raise UpdateError("SIZE_MISMATCH", f"{version.id} 包大小不符：{dest.stat().st_size} != {version.size}")
    return dest


def stage(version: ComponentVersion, workdir: Path, serial: str | None = None) -> dict:
    """Download, verify, push and stage one component; returns helper status."""
    zip_path = download(version, workdir)
    descriptor_path = workdir / safe.safe_filename(f"{version.id}-{version.version}.json", keep_suffix=False)
    descriptor_path.write_text(json.dumps(version.descriptor(), indent=2), encoding="utf-8")

    # staging inputs live in /tmp: the update-system store is owned by the helper
    remote_dir = f"/tmp/penmods-manager-{version.id}-{version.version}"
    remote_zip = f"{remote_dir}/{zip_path.name}"
    remote_desc = f"{remote_dir}/{descriptor_path.name}"
    base = ["-s", serial] if serial else []

    shell(serial, f"rm -rf {safe.shq(remote_dir)}; mkdir -p {safe.shq(remote_dir)}", timeout=60)
    penctl.run_checked(base + ["push", str(zip_path), remote_zip], timeout=600)
    penctl.run_checked(base + ["push", str(descriptor_path), remote_desc], timeout=120)
    try:
        text = shell(serial, f"{HELPER} stage {safe.shq(remote_desc)} {safe.shq(remote_zip)}", timeout=900)
    except UpdateError as exc:
        raise UpdateError("STAGE_FAILED", f"penmods-update stage 失败：{exc.message}", exc.detail) from exc
    finally:
        try:
            shell(serial, f"rm -rf {safe.shq(remote_dir)}", timeout=60)
        except UpdateError:
            pass
    return {"ok": True, "component": version.id, "version": version.version,
            "output": text.strip()[-1200:], "status": status(serial)}


def cancel(serial: str | None = None) -> dict:
    """Drop the pending generation (used to roll back a staged install)."""
    try:
        text = shell(serial, f"{HELPER} cancel", timeout=120)
    except UpdateError as exc:
        raise UpdateError("CANCEL_FAILED", exc.message, exc.detail) from exc
    return {"ok": True, "output": text.strip()[-800:], "status": status(serial)}


def enable(serial: str | None = None) -> dict:
    try:
        text = shell(serial, f"{HELPER} enable", timeout=300)
    except UpdateError as exc:
        raise UpdateError("ENABLE_FAILED", exc.message, exc.detail) from exc
    return {"ok": True, "output": text.strip()[-1200:], "status": status(serial)}
