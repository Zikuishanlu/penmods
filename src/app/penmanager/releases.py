"""PenMods release metadata: what we install on a fresh pen and which optional
components exist.

The manager never re-hosts PenMods binaries. It resolves the upstream GitHub
release, downloads the asset the user picked, verifies it against the release's
SHA256SUMS, and only then touches the device.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import netutil

API_LATEST = "https://api.github.com/repos/Lyrecoul/PenMods/releases/latest"
API_TAGS = "https://api.github.com/repos/Lyrecoul/PenMods/releases?per_page=10"

# asset name -> what it is
CORE_ASSET = "libPenMods.so"
RESOURCES_ASSET = "libPenModsResources.so"
FFMPEG_ASSET = "ffmpegplayer-plugin.zip"
MATHJAX_ASSET = "mathjax-server.zip"
PPOCR_ASSET = "penmods-ppocr.sh"
SUMS_ASSET = "SHA256SUMS"

# Optional components. `required=True` ones are part of the core install and
# are never offered as a choice (user requirement: 本体必装、无选项).
COMPONENTS: tuple[dict, ...] = (
    {
        "id": "core",
        "title": "PenMods 本体",
        "desc": "libPenMods.so + libPenModsResources.so，安装管理器必装，无法取消。",
        "required": True,
        "assets": (CORE_ASSET, RESOURCES_ASSET, SUMS_ASSET),
        "action": "core",
    },
    {
        "id": "ffmpegplayer",
        "title": "视频播放器插件",
        "desc": "FFmpegPlayer（QML 插件）：让文件管理器/外部播放器能直接播放视频。",
        "required": False,
        "assets": (FFMPEG_ASSET,),
        "action": "qml_dir",
        "remote_root": "/userdata/PenMods/qml",
    },
    {
        "id": "mathjax",
        "title": "MathJax 公式渲染",
        "desc": "本地 LaTeX→PNG 服务，供 AI 助手渲染公式；安装后需在 PenMods 设置里指向可执行文件。",
        "required": False,
        "assets": (MATHJAX_ASSET,),
        "action": "extract_dir",
        "remote_root": "/userdata/PenMods/mathjax-server",
    },
    {
        "id": "ppocr",
        "title": "PP-OCR 离线识别",
        "desc": "单文件安装器：装上 OCR 后端（约 8 MB），支持拍照/截屏取词。",
        "required": False,
        "assets": (PPOCR_ASSET,),
        "action": "script",
        "remote_root": "/userdata/PenMods",
    },
)

REQUIRED_IDS = tuple(c["id"] for c in COMPONENTS if c["required"])


class ReleaseError(RuntimeError):
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
class Release:
    tag: str
    name: str
    html_url: str
    published_at: str
    body: str = ""
    assets: dict[str, dict] = field(default_factory=dict)

    def asset_url(self, name: str) -> str | None:
        meta = self.assets.get(name)
        return meta["url"] if meta else None

    def asset_size(self, name: str) -> int:
        meta = self.assets.get(name)
        return int(meta.get("size") or 0) if meta else 0

    def to_dict(self) -> dict:
        return {
            "tag": self.tag,
            "name": self.name,
            "html_url": self.html_url,
            "published_at": self.published_at,
            "assets": {k: {"size": v.get("size")} for k, v in self.assets.items()},
        }


def _parse_release(doc: dict) -> Release:
    assets: dict[str, dict] = {}
    for item in doc.get("assets") or []:
        name = item.get("name") or ""
        if not name:
            continue
        assets[name] = {
            "url": item.get("browser_download_url") or "",
            "size": item.get("size") or 0,
        }
    return Release(
        tag=str(doc.get("tag_name") or doc.get("name") or ""),
        name=str(doc.get("name") or ""),
        html_url=str(doc.get("html_url") or ""),
        published_at=str(doc.get("published_at") or ""),
        body=str(doc.get("body") or ""),
        assets=assets,
    )


def latest_release() -> Release:
    """Latest PenMods release, with the assets the manager knows how to use."""
    try:
        doc = netutil.get_json(API_LATEST)
    except netutil.NetError as exc:
        if exc.code == "HTTP_STATUS" and "403" in exc.message:
            raise ReleaseError(
                "RATE_LIMITED",
                "GitHub API 触发了未登录限流（403），请稍后重试或改用 OTA 更新通道。",
                exc.detail,
            ) from exc
        raise ReleaseError(exc.code, exc.message, exc.detail) from exc
    release = _parse_release(doc)
    if not release.assets:
        raise ReleaseError("NO_ASSETS", f"发布 {release.tag} 没有可下载资产")
    return release


def component_plan(release: Release, selected: list[str] | None = None) -> list[dict]:
    """Resolve the component list for the install page.

    Every required component is always present (and marked so); optional ones
    carry `enabled` = whether the user picked it this time.
    """
    picked = set(selected or [])
    plan: list[dict] = []
    for comp in COMPONENTS:
        missing = [a for a in comp["assets"] if a not in release.assets and a != SUMS_ASSET]
        entry = {
            "id": comp["id"],
            "title": comp["title"],
            "desc": comp["desc"],
            "required": bool(comp["required"]),
            "enabled": bool(comp["required"]) or comp["id"] in picked,
            "asset": comp["assets"][0],
            "size": release.asset_size(comp["assets"][0]),
            "available": not missing and not (comp["id"] == "core" and CORE_ASSET not in release.assets),
            "missing": missing,
        }
        plan.append(entry)
    return plan


def sums_for(release: Release, workdir: Path) -> dict[str, str]:
    """Download and parse SHA256SUMS; returns {asset name: sha256}."""
    sums = release.assets.get(SUMS_ASSET)
    if not sums or not sums["url"]:
        return {}
    dest = workdir / SUMS_ASSET
    netutil.download(sums["url"], dest, timeout=30)
    return netutil.parse_sha256sums(dest.read_text(encoding="utf-8", errors="replace"))


def fetch_asset(release: Release, name: str, workdir: Path, *, sums: dict[str, str] | None = None) -> Path:
    """Download one release asset into `workdir`, verifying it when possible."""
    meta = release.assets.get(name)
    if not meta or not meta["url"]:
        raise ReleaseError("ASSET_MISSING", f"发布 {release.tag} 里没有 {name}")
    expected = (sums or {}).get(name)
    dest = workdir / name
    if dest.is_file() and (not expected or netutil.sha256_file(dest).lower() == expected):
        return dest
    try:
        return netutil.download(meta["url"], dest, sha256=expected, timeout=120)
    except netutil.NetError as exc:
        raise ReleaseError(exc.code, exc.message, exc.detail) from exc
