"""Small safety helpers shared by the install paths.

Everything here exists because of one rule: untrusted text (file names, plugin
ids, manifest versions, URLs) must never reach a device shell or a local file
path unchecked.
"""
from __future__ import annotations

import re
import urllib.parse

#: characters that may appear in a single path component we hand to the device
_PLAIN_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}\Z")
_SANITIZE = re.compile(r"[^A-Za-z0-9._-]+")

#: private hosts where plain http is acceptable (local index servers, tests)
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class SafetyError(ValueError):
    """Raised when an input cannot be made safe."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def shq(value: object) -> str:
    """Quote one value for a POSIX shell.

    Single quotes keep everything literal, including `$`, `;`, spaces and
    newlines; the only character that needs escaping is the quote itself.
    """
    text = "" if value is None else str(value)
    if "\x00" in text:
        raise SafetyError("BAD_CHAR", "字符串里不能有 NUL 字符")
    return "'" + text.replace("'", "'\\''") + "'"


def is_plain_name(name: str) -> bool:
    """True when `name` is a single safe path component (no separators)."""
    return bool(_PLAIN_NAME.match((name or "").strip()))


def safe_filename(name: str, *, fallback: str = "download.zip", keep_suffix: bool = True) -> str:
    """Build a filesystem-safe basename from untrusted text (never a path)."""
    base = str(name or "").replace("\\", "/").rsplit("/", 1)[-1]
    base = _SANITIZE.sub("_", base).strip("._") or fallback
    if keep_suffix and fallback.lower().endswith(".zip") and not base.lower().endswith(".zip"):
        base += ".zip"
    return base[:120]


def require_plain_name(name: str, *, what: str = "文件名") -> str:
    """Validate a device-side path component or raise SafetyError."""
    text = (name or "").strip()
    if not is_plain_name(text):
        raise SafetyError("BAD_NAME", f"{what}不合法：{name!r}")
    return text


def require_https(url: str, *, allow_localhost: bool = False, what: str = "链接") -> str:
    """Validate an absolute https:// URL (http only for localhost when allowed)."""
    text = (url or "").strip()
    parts = urllib.parse.urlsplit(text)
    if parts.scheme == "https" and parts.hostname:
        return text
    if allow_localhost and parts.scheme == "http" and (parts.hostname or "") in LOCAL_HOSTS:
        return text
    raise SafetyError("BAD_URL", f"{what}必须是 https://：{url}")


def is_https(url: str, *, allow_localhost: bool = False) -> bool:
    """Non-raising version of :func:`require_https` (used for UI checks/tests)."""
    try:
        require_https(url, allow_localhost=allow_localhost)
    except SafetyError:
        return False
    return True
