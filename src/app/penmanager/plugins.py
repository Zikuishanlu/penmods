"""Plugin packages: validate a zip, plan the device-side swap, and run it.

Layout on the pen: /userdisk/PenMods/plugins/<id>/{metadata.json, *.qml, *.so}.
`.disabled` disables a plugin; `.loading` is the crash-recovery marker owned by
PenMods itself, so the manager never creates or deletes it.
"""
from __future__ import annotations

import json
import re
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from . import penctl, safe

PLUGINS_ROOT = "/userdisk/PenMods/plugins"
STAGING_ROOT = "/userdisk/PenMods/.penmods-manager/staging"
BACKUP_ROOT = "/userdisk/PenMods/.penmods-manager/backups"

MAX_ENTRIES = 10000
MAX_TOTAL = 256 * 1024 * 1024
MAX_FILE = 128 * 1024 * 1024
MAX_METADATA = 1024 * 1024

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_REQUIRED = ("id", "name", "version")


class PluginError(RuntimeError):
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
class Package:
    path: Path
    plugin_id: str
    metadata: dict = field(default_factory=dict)
    files: list[str] = field(default_factory=list)
    total_size: int = 0
    has_native: bool = False

    def to_dict(self) -> dict:
        return {
            "path": str(self.path),
            "id": self.plugin_id,
            "name": self.metadata.get("name", ""),
            "version": self.metadata.get("version", ""),
            "author": self.metadata.get("author", ""),
            "description": self.metadata.get("description", ""),
            "files": len(self.files),
            "total_size": self.total_size,
            "native": self.has_native,
        }


def _safe_rel(name: str) -> str:
    rel = name.replace("\\", "/")
    if rel.startswith("./"):
        rel = rel[2:]
    parts = rel.split("/")
    if not rel or rel.startswith("/") or any(p in ("", ".", "..") for p in parts):
        raise PluginError("UNSAFE_PATH", f"插件包包含危险路径：{name}")
    return rel


def inspect_zip(path: Path) -> Package:
    """Validate a plugin/installer zip without touching the device."""
    try:
        with zipfile.ZipFile(path) as zf:
            infos = [i for i in zf.infolist() if not i.is_dir()]
            if not infos:
                raise PluginError("EMPTY_ZIP", "插件包是空的")
            if len(infos) > MAX_ENTRIES:
                raise PluginError("TOO_MANY_FILES", f"插件包条目过多：{len(infos)}")
            total = 0
            names: list[str] = []
            for info in infos:
                rel = _safe_rel(info.filename)
                if (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise PluginError("SYMLINK_REFUSED", f"插件包包含符号链接：{rel}")
                if info.file_size > MAX_FILE:
                    raise PluginError("FILE_TOO_BIG", f"文件过大：{rel}")
                if info.compress_size and info.file_size > 4 * 1024 * 1024 and                         info.file_size / info.compress_size > 200:
                    raise PluginError("ZIP_BOMB", f"压缩比异常：{rel}")
                total += info.file_size
                if total > MAX_TOTAL:
                    raise PluginError("ZIP_TOO_BIG", "插件包解压后过大")
                names.append(rel)

            root = _common_root(names)
            meta_name = f"{root}metadata.json" if root else "metadata.json"
            if meta_name not in names:
                raise PluginError("NO_METADATA", "插件包根部缺少 metadata.json")
            raw = zf.read(meta_name)
            if len(raw) > MAX_METADATA:
                raise PluginError("METADATA_TOO_BIG", "metadata.json 过大")
            try:
                metadata = json.loads(raw.decode("utf-8-sig", "replace"))
            except json.JSONDecodeError as exc:
                raise PluginError("BAD_METADATA", "metadata.json 不是合法 JSON", str(exc)) from exc
            if not isinstance(metadata, dict):
                raise PluginError("BAD_METADATA", "metadata.json 必须是对象")
            for key in _REQUIRED:
                if not str(metadata.get(key) or "").strip():
                    raise PluginError("BAD_METADATA", f"metadata.json 缺少字段 {key}")
            plugin_id = str(metadata["id"]).strip()
            if not _ID_RE.match(plugin_id):
                raise PluginError("BAD_ID", f"插件 id 不合法：{plugin_id}")
            has_native = any(n.endswith(".so") for n in names)
            pkg = Package(
                path=path,
                plugin_id=plugin_id,
                metadata=metadata,
                files=names,
                total_size=total,
                has_native=has_native,
            )
            if pkg.metadata.get("main_so") and not has_native:
                raise PluginError("MISSING_SO", "metadata 声明了 main_so 但包里没有 .so")
            return pkg
    except zipfile.BadZipFile as exc:
        raise PluginError("BAD_ZIP", "不是有效的 zip 文件", str(exc)) from exc


def _common_root(names: list[str]) -> str:
    """When every file sits under one wrapper directory, treat it as the root."""
    tops = {n.split("/", 1)[0] for n in names}
    if len(tops) != 1:
        return ""
    top = next(iter(tops))
    if all(n.startswith(top + "/") for n in names):
        return top + "/"
    return ""


def stage_dir() -> str:
    return f"{STAGING_ROOT}/{uuid.uuid4().hex[:12]}"


def install_steps(pkg: Package, staging: str) -> list[str]:
    """Device-side commands: stage → swap → clean, all atomic via `mv -f`."""
    target = f"{PLUGINS_ROOT}/{pkg.plugin_id}"
    backup = f"{BACKUP_ROOT}/{pkg.plugin_id}.{uuid.uuid4().hex[:8]}"
    t, b, stg = safe.shq(target), safe.shq(backup), safe.shq(staging)
    return [
        f"mkdir -p {safe.shq(PLUGINS_ROOT)} {safe.shq(STAGING_ROOT)} {safe.shq(BACKUP_ROOT)}",
        f"rm -rf {stg} && mkdir -p {stg}",
        f"if [ -e {t} ]; then mv -f {t} {b}; fi",
        # if the swap fails the previous version goes straight back
        f"if mv -f {stg} {t}; then chmod -R a+rX {t}; "
        f"elif [ -e {b} ]; then mv -f {b} {t}; fi",
        f"if [ -e {t}/metadata.json ]; then echo installed; else echo failed; fi",
    ]


def install(pkg: Package, *, serial: str | None = None, timeout: float = 300) -> dict:
    """Upload the package contents and swap them in atomically."""
    staging = stage_dir()
    remote_zip = f"/tmp/penmods-plugin-{uuid.uuid4().hex[:8]}.zip"
    penctl.run_checked(["-s", serial, "push", str(pkg.path), remote_zip], timeout=180) if serial else \
        penctl.run_checked(["push", str(pkg.path), remote_zip], timeout=180)
    unzip_cmd = (
        f"rm -rf '{staging}' && mkdir -p '{staging}' && "
        f"unzip -q -o '{remote_zip}' -d '{staging}' || exit 9; "
        f"rm -f '{remote_zip}'"
    )
    if serial:
        penctl.run_text(["-s", serial, "shell", unzip_cmd], timeout=timeout)
    else:
        penctl.run_text(["shell", unzip_cmd], timeout=timeout)
    # wrapper dir -> flatten so metadata.json sits at the plugin root
    flatten = (
        f"d='{staging}'; "
        f"if [ ! -f \"$d/metadata.json\" ]; then inner=$(ls -d \"$d\"/*/ 2>/dev/null | head -1); "
        f"if [ -n \"$inner\" ] && [ -f \"$inner/metadata.json\" ]; then "
        f"cd \"$inner\" && mv * \"$d\"/ 2>/dev/null; cd /; fi; fi; echo staged"
    )
    if serial:
        penctl.run_text(["-s", serial, "shell", flatten], timeout=60)
    else:
        penctl.run_text(["shell", flatten], timeout=60)
    steps = install_steps(pkg, staging)
    last = ""
    for cmd in steps:
        if serial:
            last = penctl.run_text(["-s", serial, "shell", cmd], timeout=timeout)
        else:
            last = penctl.run_text(["shell", cmd], timeout=timeout)
    return {"ok": "installed" in last, "id": pkg.plugin_id, "staging": staging, "output": last.strip()[:200]}


def _checked_id(plugin_id: str) -> str:
    text = (plugin_id or "").strip()
    if not _ID_RE.match(text):
        raise PluginError("BAD_ID", f"插件 id 不合法：{plugin_id!r}")
    return text


def set_enabled(plugin_id: str, enabled: bool, *, serial: str | None = None) -> dict:
    plugin_id = _checked_id(plugin_id)
    flag = f"{PLUGINS_ROOT}/{plugin_id}/.disabled"
    cmd = f"rm -f {safe.shq(flag)}" if enabled else f"touch {safe.shq(flag)}"
    out = penctl.run_text(["-s", serial, "shell", cmd]) if serial else penctl.run_text(["shell", cmd])
    return {"ok": True, "id": plugin_id, "enabled": enabled, "output": out.strip()[:200]}


def uninstall(plugin_id: str, *, serial: str | None = None) -> dict:
    plugin_id = _checked_id(plugin_id)
    target = f"{PLUGINS_ROOT}/{plugin_id}"
    trash = f"{BACKUP_ROOT}/{plugin_id}.removed.{uuid.uuid4().hex[:8]}"
    cmd = (
        f"mkdir -p {safe.shq(BACKUP_ROOT)}; "
        f"if [ -e {safe.shq(target)} ]; then mv -f {safe.shq(target)} {safe.shq(trash)} && echo removed; "
        f"else echo missing; fi"
    )
    out = penctl.run_text(["-s", serial, "shell", cmd]) if serial else penctl.run_text(["shell", cmd])
    return {"ok": "removed" in out, "id": plugin_id, "output": out.strip()[:200]}


def list_installed(*, serial: str | None = None) -> list[dict]:
    """Read plugin dirs + metadata.json over the active transport."""
    nl = chr(92) + "n"
    script = (
        "cd " + safe.shq(PLUGINS_ROOT) + " 2>/dev/null || exit 0; "
        'for d in */; do d=${d%/}; [ -f "$d/metadata.json" ] || continue; '
        + 'printf "===PLUGIN:%s' + nl + '" "$d"; cat "$d/metadata.json"; '
        + 'printf "' + nl + '===END' + nl + '"; done'
    )
    args = ["-s", serial, "shell", script] if serial else ["shell", script]
    try:
        raw = penctl.run_text(args, timeout=60)
    except penctl.PenctlError:
        return []
    out: list[dict] = []
    for block in (raw or "").split("===PLUGIN:")[1:]:
        head, _, rest = block.partition(chr(10))
        plugin_id = head.strip()
        if not plugin_id:
            continue
        meta_raw = rest.split("===END", 1)[0].strip()
        entry: dict = {"id": plugin_id, "meta_raw": meta_raw}
        meta = None
        try:
            meta = json.loads(meta_raw or "{}")
        except json.JSONDecodeError:
            meta = None
        if isinstance(meta, dict):
            entry.update({k: meta.get(k, "") for k in ("name", "version", "description", "author")})
        entry["enabled"] = not plugin_id.endswith(".disabled")
        out.append(entry)
    return out
