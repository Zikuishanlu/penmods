"""Plugin market: protocol v1 index files and GitHub-repository direct installs.

Protocol v1 (compatible with PenManager's docs/plugin-market-v1.md): a single
HTTPS JSON document, no GitHub API in the default path.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from . import netutil, plugins, safe

SCHEMA_VERSION = 1

# Public registry shipped with this project (Zikuishanlu/penmods): the repo's own
# plugins/ folder. Regenerate plugins/index.json with scripts/make_market_index.py
# after replacing any bundle.
DEFAULT_INDEX_URL = "https://raw.githubusercontent.com/Zikuishanlu/penmods/main/plugins/index.json"

_GITHUB_RE = re.compile(r"^https?://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?(?:/.*)?$")


class MarketError(RuntimeError):
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


def _require_str(item: dict, key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise MarketError("BAD_INDEX", f"索引条目缺少字段 {key}")
    return value.strip()


def validate_index(doc: dict) -> list[dict]:
    """Validate a protocol-v1 index and return a normalised plugin list."""
    version = doc.get("schema_version")
    if version != SCHEMA_VERSION:
        raise MarketError("BAD_SCHEMA", f"不支持的索引版本：{version}（需要 {SCHEMA_VERSION}）")
    raw_plugins = doc.get("plugins")
    if not isinstance(raw_plugins, list):
        raise MarketError("BAD_INDEX", "索引缺少 plugins 数组")
    out: list[dict] = []
    for item in raw_plugins:
        if not isinstance(item, dict):
            raise MarketError("BAD_INDEX", "plugins 里出现了非对象条目")
        pid = _require_str(item, "id")
        if not plugins._ID_RE.match(pid):
            raise MarketError("BAD_ID", f"插件 id 不合法：{pid}")
        versions = item.get("versions")
        if not isinstance(versions, list) or not versions:
            raise MarketError("BAD_INDEX", f"{pid} 没有可用版本")
        norm_versions: list[dict] = []
        for ver in versions:
            if not isinstance(ver, dict):
                raise MarketError("BAD_INDEX", f"{pid} 的版本条目不是对象")
            url = _require_str(ver, "url")
            digest = _require_str(ver, "sha256").lower()
            if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise MarketError("BAD_INDEX", f"{pid} 的 sha256 不是 64 位十六进制")
            if not url.startswith("https://"):
                raise MarketError("BAD_URL", f"{pid} 的下载地址必须是 https")
            norm_versions.append(
                {
                    "version": str(ver.get("version") or ""),
                    "url": url,
                    "sha256": digest,
                    # all-zero digests are placeholders (the bundled example):
                    # the page must not pretend they can be installed
                    "installable": digest != "0" * 64,
                    "devices": list(ver.get("devices") or []),
                    "min_penmods": str(ver.get("min_penmods") or ""),
                    "native": bool(ver.get("native")),
                    "roots": list(ver.get("roots") or []),
                }
            )
        out.append(
            {
                "id": pid,
                "name": str(item.get("name") or pid),
                "summary": str(item.get("summary") or ""),
                "author": str(item.get("author") or ""),
                "repository": str(item.get("repository") or ""),
                "icon": str(item.get("icon") or ""),
                "versions": norm_versions,
                "installable": any(v["installable"] for v in norm_versions),
            }
        )
    return out


EXAMPLE_INDEX_PATH = Path(__file__).with_name("data") / "example_index.json"


def example_index() -> dict:
    """The bundled schema template — useful before a registry exists."""
    doc = json.loads(EXAMPLE_INDEX_PATH.read_text(encoding="utf-8"))
    doc["_ok"] = True
    plugin_list = validate_index(doc)
    return {"schema_version": SCHEMA_VERSION, "name": str(doc.get("name") or "示例索引"),
            "url": str(EXAMPLE_INDEX_PATH), "plugins": plugin_list, "example": True}


def _read_local(source: str) -> dict:
    raw = source[len("file://"):] if source.startswith("file://") else source
    path = Path(raw)
    if not path.exists():
        raise MarketError("FILE_MISSING", f"找不到索引文件：{path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MarketError("BAD_INDEX_FILE", f"索引文件读取失败：{path}", str(exc)) from exc


def load_index(source: str = "") -> dict:
    """Load an index from https://, a local path, file://, or the bundled example."""
    source = (source or "").strip()
    if not source:
        return example_index()
    if source.startswith("file://") or "://" not in source:
        return fetch_index(source, local=True)
    return fetch_index(source)


def fetch_index(url: str = DEFAULT_INDEX_URL, local: bool = False) -> dict:
    if local:
        doc = _read_local(url)
    else:
        try:
            safe.require_https(url, allow_localhost=True, what="索引地址")
        except safe.SafetyError as exc:
            raise MarketError(exc.code, exc.message) from exc
        try:
            doc = netutil.get_json(url)
        except netutil.NetError as exc:
            raise MarketError(exc.code, f"无法获取插件索引：{url}", exc.detail) from exc
    plugin_list = validate_index(doc)
    return {"schema_version": SCHEMA_VERSION, "name": str(doc.get("name") or "PenMods 插件市场"),
            "url": url, "plugins": plugin_list}


def search(plugin_list: list[dict], query: str) -> list[dict]:
    needle = (query or "").strip().lower()
    if not needle:
        return plugin_list
    return [
        p for p in plugin_list
        if needle in p["id"].lower() or needle in p["name"].lower() or needle in p["summary"].lower()
    ]


def download_version(plugin: dict, version: dict, workdir) -> "object":
    from pathlib import Path

    name = safe.safe_filename(f"{plugin['id']}-{version['version'] or 'latest'}.zip")
    dest = Path(workdir) / name
    try:
        return netutil.download(version["url"], dest, sha256=version["sha256"], timeout=120,
                               max_bytes=128 * 1024 * 1024)
    except netutil.NetError as exc:
        raise MarketError(exc.code, exc.message, exc.detail) from exc


def parse_github_url(url: str) -> tuple[str, str]:
    match = _GITHUB_RE.match((url or "").strip())
    if not match:
        raise MarketError("BAD_REPO", f"不是 GitHub 仓库链接：{url}")
    return match.group(1), match.group(2)


def repo_release_assets(owner: str, repo: str) -> dict:
    """List release assets of a plugin repository (direct .zip links)."""
    try:
        doc = netutil.get_json(f"https://api.github.com/repos/{owner}/{repo}/releases/latest")
    except netutil.NetError as exc:
        raise MarketError(exc.code, f"无法读取 {owner}/{repo} 的发布", exc.detail) from exc
    assets = doc.get("assets") or []
    return {
        "tag": str(doc.get("tag_name") or ""),
        "assets": [
            {
                "name": str(a.get("name") or ""),
                "url": str(a.get("browser_download_url") or ""),
                "size": int(a.get("size") or 0),
            }
            for a in assets
            if str(a.get("name") or "").endswith(".zip")
        ],
    }


def repo_install_url(url: str) -> dict:
    """Resolve a GitHub repo link to its newest plugin zip asset."""
    owner, repo = parse_github_url(url)
    info = repo_release_assets(owner, repo)
    zips = [a for a in info["assets"] if a["url"].startswith("https://")]
    if not zips:
        raise MarketError("NO_ASSET", f"{owner}/{repo} 的最新发布里没有 .zip 插件包")
    asset = max(zips, key=lambda a: a["size"])
    return {"owner": owner, "repo": repo, "tag": info["tag"], **asset}


def validate_remote(url: str, *, allow_localhost: bool = False) -> bool:
    """Protocol v1 requires https (localhost stays allowed for local indexes)."""
    return safe.is_https(url, allow_localhost=allow_localhost)
