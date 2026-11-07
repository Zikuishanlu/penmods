"""Thin subprocess wrapper around the C core (penctl.exe).

Every GUI action funnels through here: the C process speaks JSON on stdout, so
the Python layer never parses device text itself.

Two environment quirks are handled here:
  * anonymous pipes are denied in this sandbox, so child output is redirected
    to temp files instead of PIPE;
  * children created with CREATE_NO_WINDOW die during DLL init, so we launch
    detached instead.
"""
from __future__ import annotations

import itertools
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from .paths import app_dir, data_dir, is_frozen, penctl_path, repo_root, tmp_dir

_seq = itertools.count()
_LAUNCH_FLAGS = subprocess.DETACHED_PROCESS if os.name == "nt" else 0

# Active transport: None/"adb" means `-s SERIAL`; {"mode": "ssh", ...} switches
# every penctl call to `--ssh root@host --key ...` (see set_transport()).
_transport: dict | None = None
_DEFAULT = object()


def set_transport(transport: dict | None) -> None:
    """Switch all later penctl calls to this transport (None = ADB)."""
    global _transport
    _transport = dict(transport) if transport else None


def get_transport() -> dict | None:
    return dict(_transport) if _transport else None


def transport_args(transport: dict | None) -> list[str]:
    """Build the global penctl flags for an SSH transport."""
    if not transport or transport.get("mode") != "ssh":
        return []
    host = str(transport.get("host") or "").strip()
    if not host:
        return []
    if "@" not in host:
        host = f"{transport.get('user') or 'root'}@{host}"
    args = ["--ssh", host]
    port = int(transport.get("port") or 0)
    if port > 0:
        args += ["--port", str(port)]
    key = transport.get("key")
    if key:
        args += ["--key", str(key)]
    known = transport.get("known_hosts")
    if known:
        args += ["--known-hosts", str(known)]
    return args


class PenctlError(RuntimeError):
    def __init__(self, code: str, message: str, detail: Any = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.detail = detail

    def to_dict(self) -> dict:
        out: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.detail is not None:
            out["detail"] = self.detail
        return out


def _exe() -> str:
    exe = penctl_path()
    if exe is None:
        raise PenctlError(
            "PENCTL_MISSING",
            "找不到 penctl 可执行文件，请先运行：python scripts/build_core.py",
        )
    return str(exe)


_adb_cache: dict[str, str | None] = {"path": None, "probed": False}


def adb_path() -> Path | None:
    """Locate adb.exe for the child process.

    penctl looks at $PENCTL_ADB, then next to penctl.exe, then PATH. A dev
    checkout keeps adb in .toolchain/platform-tools and build/penctl.exe has no
    sibling adb, so we hand the path over explicitly instead of relying on PATH.
    """
    if _adb_cache["probed"]:
        cached = _adb_cache["path"]
        return Path(cached) if cached else None

    candidates: list[Path] = []
    env = os.environ.get("PENCTL_ADB")
    if env:
        candidates.append(Path(env))
    if is_frozen():
        candidates.append(app_dir() / "adb.exe")
    candidates.append(repo_root() / ".toolchain" / "platform-tools" / "adb.exe")
    candidates.append(repo_root() / "adb.exe")
    found = shutil.which("adb")
    if found:
        candidates.append(Path(found))

    for cand in candidates:
        try:
            if cand.is_file():
                _adb_cache["path"] = str(cand)
                _adb_cache["probed"] = True
                return cand
        except OSError:
            continue
    _adb_cache["probed"] = True
    return None


def scratch_dir() -> Path:
    """Writable temp directory for adb's log and other child-process scratch files."""
    target = data_dir() / "tmp"
    try:
        target.mkdir(parents=True, exist_ok=True)
        return target
    except OSError:
        return tmp_dir()


def child_env() -> dict[str, str] | None:
    """Environment for penctl: expose adb explicitly so ADB_MISSING can't happen.

    adb writes adb.log into %TEMP% and refuses to start its daemon when that
    directory is read-only ("cannot open ... adb.log: Permission denied"), which
    surfaces to users as "adb can't connect". Point TMP/TEMP at our own
    writable scratch dir whenever the inherited one looks unusable.
    """
    adb = adb_path()
    if adb is None:
        return None
    env = dict(os.environ)
    env["PENCTL_ADB"] = str(adb)
    parent = str(adb.parent)
    path = env.get("PATH", "")
    if parent.lower() not in path.lower():
        env["PATH"] = parent + os.pathsep + path

    # Always hand adb our own scratch dir: inheriting %TEMP% is what breaks the
    # daemon on machines where that folder is read-only or ACL-restricted.
    scratch = str(scratch_dir())
    env["TMP"] = scratch
    env["TEMP"] = scratch
    return env


def _base_cmd(serial: str | None, transport: dict | None | object = _DEFAULT) -> list[str]:
    cmd = [_exe()]
    active = _transport if transport is _DEFAULT else transport
    ssh_args = transport_args(active if isinstance(active, dict) else None)
    if ssh_args:
        cmd += ssh_args
    elif serial:
        cmd += ["-s", serial]
    cmd.append("--json")
    return cmd


def _decode(data: bytes) -> str:
    return data.decode("utf-8", "replace")


def _temp_paths(tag: str) -> tuple[Path, Path]:
    tmp = tmp_dir()
    stamp = next(_seq)
    return tmp / f"penctl-{tag}-{os.getpid()}-{stamp}.out", tmp / f"penctl-{tag}-{os.getpid()}-{stamp}.err"


def _read_and_cleanup(out_p: Path, err_p: Path) -> tuple[str, str]:
    try:
        out = _decode(out_p.read_bytes()).strip()
        err = _decode(err_p.read_bytes()).strip()
    finally:
        for p in (out_p, err_p):
            try:
                p.unlink()
            except OSError:
                pass
    return out, err


def run_raw(argv: list[str], *, timeout: float = 60) -> tuple[int, str, str]:
    """Run any local program with file-redirected output (no anonymous pipes)."""
    out_p, err_p = _temp_paths("raw")
    try:
        with out_p.open("wb") as fo, err_p.open("wb") as fe:
            proc = subprocess.run(argv, stdout=fo, stderr=fe, timeout=timeout,
                                  creationflags=_LAUNCH_FLAGS, env=child_env())
        return proc.returncode, _decode(out_p.read_bytes()), _decode(err_p.read_bytes())
    except subprocess.TimeoutExpired as exc:
        raise PenctlError("TIMEOUT", "外部程序执行超时", " ".join(argv)) from exc
    except OSError as exc:
        raise PenctlError("SPAWN_FAILED", f"无法启动程序: {exc}") from exc
    finally:
        for path in (out_p, err_p):
            try:
                path.unlink()
            except OSError:
                pass


def run_text(args: list[Any], *, serial: str | None = None, timeout: float = 120,
             transport: dict | None | object = _DEFAULT) -> str:
    """Run a penctl command that prints raw text (shell/ssh passthrough)."""
    cmd = _base_cmd(serial, transport) + [str(a) for a in args]
    out_p, err_p = _temp_paths("text")
    try:
        with out_p.open("wb") as fo, err_p.open("wb") as fe:
            proc = subprocess.run(cmd, stdout=fo, stderr=fe, timeout=timeout,
                                  creationflags=_LAUNCH_FLAGS, env=child_env())
        code = proc.returncode
    except subprocess.TimeoutExpired as exc:
        raise PenctlError("TIMEOUT", f"penctl 执行超时（{timeout:.0f}s）") from exc
    except OSError as exc:
        raise PenctlError("SPAWN_FAILED", f"无法启动 penctl: {exc}") from exc
    out, err = _read_and_cleanup(out_p, err_p)
    if code != 0:
        raise PenctlError("SHELL_FAILED", err or out or f"exit {code}")
    return out


def run(args: list[Any], *, serial: str | None = None, timeout: float = 180,
        transport: dict | None | object = _DEFAULT) -> dict:
    """Run penctl and return the parsed JSON document (never raises for ok=false)."""
    cmd = _base_cmd(serial, transport) + [str(a) for a in args]
    out_p, err_p = _temp_paths("run")
    try:
        with out_p.open("wb") as fo, err_p.open("wb") as fe:
            proc = subprocess.run(cmd, stdout=fo, stderr=fe, timeout=timeout,
                                  creationflags=_LAUNCH_FLAGS, env=child_env())
        code = proc.returncode
    except subprocess.TimeoutExpired as exc:
        raise PenctlError("TIMEOUT", f"penctl 执行超时（{timeout:.0f}s）", " ".join(args)) from exc
    except OSError as exc:
        raise PenctlError("SPAWN_FAILED", f"无法启动 penctl: {exc}") from exc

    out, err = _read_and_cleanup(out_p, err_p)
    if not out:
        raise PenctlError("EMPTY_OUTPUT", f"penctl 没有输出（exit {code}）", err or None)
    try:
        data = json.loads(out)
    except json.JSONDecodeError as exc:
        raise PenctlError(
            "BAD_OUTPUT",
            "penctl 输出不是合法 JSON",
            {"stdout": out[:2000], "stderr": err[:2000]},
        ) from exc
    if isinstance(data, dict):
        data.setdefault("_exit_code", code)
        if err:
            data.setdefault("_stderr", err)
    return data


def run_checked(args: list[Any], *, serial: str | None = None, timeout: float = 180,
                transport: dict | None | object = _DEFAULT) -> dict:
    """Like run() but raises PenctlError when the document says ok=false."""
    data = run(args, serial=serial, timeout=timeout, transport=transport)
    if data.get("ok") is False:
        err = data.get("error") or {}
        raise PenctlError(
            str(err.get("code", "UNKNOWN")),
            str(err.get("message", "命令失败")),
            data.get("detail"),
        )
    return data


def stream(
    args: list[Any],
    *,
    serial: str | None = None,
    on_line: Callable[[str], None] | None = None,
    timeout: float = 600,
) -> int:
    """Run penctl streaming line-by-line (install progress, terminal bridge).

    Output is tailed from a temp file because PIPE handles are unavailable.
    """
    cmd = _base_cmd(serial) + [str(a) for a in args]
    log_p, err_p = _temp_paths("stream")
    deadline = time.monotonic() + timeout
    pending = b""
    pos = 0
    try:
        with log_p.open("wb") as fo, err_p.open("wb") as fe:
            try:
                proc = subprocess.Popen(cmd, stdout=fo, stderr=fe,
                                        creationflags=_LAUNCH_FLAGS, env=child_env())
            except OSError as exc:
                raise PenctlError("SPAWN_FAILED", f"无法启动 penctl: {exc}") from exc
        while True:
            eof = proc.poll() is not None
            with log_p.open("rb") as rf:
                rf.seek(pos)
                chunk = rf.read()
                pos = rf.tell()
            if chunk:
                pending += chunk
                *lines, pending = pending.split(b"\n")
                for raw in lines:
                    if on_line is not None:
                        on_line(_decode(raw).rstrip("\r"))
            if eof:
                if pending and on_line is not None:
                    on_line(_decode(pending).rstrip("\r"))
                break
            if time.monotonic() > deadline:
                proc.kill()
                raise PenctlError("TIMEOUT", f"penctl 执行超时（{timeout:.0f}s）")
            time.sleep(0.08)
        try:
            return proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            return -1
    finally:
        for p in (log_p, err_p):
            try:
                p.unlink()
            except OSError:
                pass
