"""SSH onboarding: local keypair, key deployment over ADB, and a reachability probe.

The pen exposes sshd on Wi-Fi (PenMods `ssh_autorun`). We never ship a password
and never enable password login: we append our public key to
`/root/.ssh/authorized_keys` over ADB, then use `ssh -i key` for everything else.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from . import penctl
from .paths import data_dir

KEY_NAME = "penmods_ed25519"


def _openssh(program: str) -> str | None:
    """Locate an OpenSSH tool, preferring the copy Windows ships.

    PATH on a developer box may resolve to msys/cygwin builds, which abort
    during runtime init when spawned from a GUI process; System32/OpenSSH is
    the one that actually works for us.
    """
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    candidate = system_root / "System32" / "OpenSSH" / f"{program}.exe"
    if candidate.is_file():
        return str(candidate)
    return shutil.which(program)


def key_dir() -> Path:
    path = data_dir() / "ssh"
    path.mkdir(parents=True, exist_ok=True)
    return path


def private_key() -> Path:
    return key_dir() / KEY_NAME


def known_hosts() -> Path:
    """Host keys we trust for the pen (created on first successful connect)."""
    return key_dir() / "known_hosts"


def public_key() -> Path:
    return key_dir() / f"{KEY_NAME}.pub"


def ensure_keypair() -> Path:
    """Create an ed25519 keypair without a passphrase; never overwrite one."""
    key = private_key()
    if key.is_file() and public_key().is_file():
        return key
    ssh_keygen = _openssh("ssh-keygen")
    if not ssh_keygen:
        raise RuntimeError("ssh-keygen not found (OpenSSH client is required)")
    code, _out, err = penctl.run_raw(
        [ssh_keygen, "-t", "ed25519", "-N", "", "-C", "penmods-manager", "-f", str(key)],
        timeout=60,
    )
    if code != 0 and not key.is_file():
        raise RuntimeError(f"ssh-keygen failed: {err.strip()[:400]}")
    return key


def deploy_key(serial: str) -> dict:
    """Append our public key to the pen's /root/.ssh/authorized_keys over ADB."""
    key = ensure_keypair()
    pub = public_key().read_text(encoding="utf-8").strip()
    if not pub:
        raise RuntimeError("public key file is empty")

    remote_tmp = "/tmp/penmods_key.pub"
    penctl.run_checked(["-s", serial, "push", str(public_key()), remote_tmp], timeout=60,
                       transport={"mode": "adb"})
    script = (
        "mkdir -p /root/.ssh && chmod 700 /root/.ssh && "
        f"grep -qxF '{pub}' /root/.ssh/authorized_keys 2>/dev/null || "
        f"cat {remote_tmp} >> /root/.ssh/authorized_keys; "
        "chmod 600 /root/.ssh/authorized_keys; "
        f"rm -f {remote_tmp}; "
        "echo key-installed"
    )
    out = penctl.run_text(["-s", serial, "shell", script], timeout=60,
                          transport={"mode": "adb"})
    return {
        "ok": True,
        "key": str(key),
        "installed": "key-installed" in (out or ""),
    }


def wifi_address(serial: str) -> str | None:
    """Return the Wi-Fi IPv4 address reported by wlan0, if any."""
    try:
        out = penctl.run_text(
            ["-s", serial, "shell", "ip -4 addr show wlan0 2>/dev/null || ifconfig wlan0 2>/dev/null"],
            timeout=30, transport={"mode": "adb"},
        )
    except penctl.PenctlError:
        return None
    match = re.search(r"inet (?:addr:)?(\d+\.\d+\.\d+\.\d+)", out or "")
    return match.group(1) if match else None


def probe(host: str, key: Path | None = None, port: int = 0) -> dict:
    """Try `shell echo penmods-ssh-ok` over SSH; returns a small status dict."""
    key = key or private_key()
    args = ["--ssh", host, "--key", str(key), "--known-hosts", str(known_hosts())]
    if port:
        args += ["--port", str(port)]
    args += ["shell", "echo penmods-ssh-ok"]
    try:
        out = penctl.run_text(args, timeout=30)
        return {"ok": "penmods-ssh-ok" in (out or ""), "host": host, "output": (out or "").strip()[:200]}
    except penctl.PenctlError as exc:
        return {"ok": False, "host": host, "error": exc.to_dict()}


def onboard(serial: str) -> dict:
    """Key + address + probe in one call; used by the GUI connection page."""
    host = wifi_address(serial)
    deployed = deploy_key(serial)
    if not host:
        return {"ok": False, "key": deployed["key"], "error": {"code": "NO_WIFI",
                "message": "设备没有 Wi-Fi 地址，先把笔连到和电脑同一个网络"}}
    result = probe(f"root@{host}")
    return {"ok": result.get("ok", False), "host": f"root@{host}", "key": deployed["key"],
            "installed": deployed.get("installed"), "probe": result}
