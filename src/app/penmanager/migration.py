"""PenMods v2.7.3 launcher migration.

V2.7.0 / V2.7.1 shipped an update launcher with a cold-boot defect (the pen can
fail to reach the system, reboot in a loop, or fall back to stock). Updating the
core component or swapping the two `.so` files does *not* repair the standalone
launcher or the boot script: those devices need the full `update_v<ver>.zip`
migration package once.

The manager therefore never stages the migration through `penmods-update`. It
downloads the package from the upstream release, verifies it against
`SHA256SUMS`, pushes it into `/userdisk/PenMods/install-<ver>/`, unpacks it there
and runs the package's own `_do_update.sh`, which is exactly what the release
notes tell users to do by hand.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

from . import releases, safe, update_system

MIGRATION_PREFIX = "update_v"
MIGRATION_SUFFIX = ".zip"
LAUNCHER_MARK = "PenMods guarded launcher v3"
RUN_DICT_PEN = "/usr/bin/runDictPen"
INSTALL_ROOT = "/userdisk/PenMods"

# launcher cores with the cold-boot defect: a full migration is mandatory
BROKEN_LAUNCHERS = ("2.7.0", "2.7.1")
# first release whose guarded launcher is safe to keep
SAFE_LAUNCHER = (2, 7, 3)


class MigrationError(RuntimeError):
    def __init__(self, code: str, message: str, detail: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "detail": self.detail}


def version_tuple(text: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", str(text or ""))[:3]
    return tuple(int(p) for p in parts) if parts else (0,)


def find_asset(release: releases.Release) -> tuple[str, dict]:
    """Pick the `update_v<ver>.zip` full migration package of a release."""
    candidates = [
        (name, meta)
        for name, meta in (release.assets or {}).items()
        if name.startswith(MIGRATION_PREFIX) and name.endswith(MIGRATION_SUFFIX) and meta.get("url")
    ]
    if not candidates:
        raise MigrationError(
            "NO_MIGRATION_ASSET",
            f"发布 {release.tag} 里没有 update_v*.zip 完整迁移包",
        )
    candidates.sort(key=lambda item: version_tuple(item[0]), reverse=True)
    return candidates[0]


def release_version(release: releases.Release, asset_name: str) -> str:
    match = re.search(r"update_v([0-9][0-9.]*)\.zip$", asset_name)
    if match:
        return match.group(1)
    return str(release.tag or "").lstrip("vV")


def launcher_state(serial: str | None = None) -> dict:
    """Whether /usr/bin/runDictPen already carries the guarded v3 launcher."""
    command = (
        f"if [ -f {safe.shq(RUN_DICT_PEN)} ]; then "
        f"grep -c {safe.shq(LAUNCHER_MARK)} {safe.shq(RUN_DICT_PEN)} 2>/dev/null || echo 0; "
        "else echo missing; fi"
    )
    try:
        out = update_system.shell(serial, command, timeout=60).strip().splitlines()
    except update_system.UpdateError:
        return {"path": RUN_DICT_PEN, "present": False, "guarded": False, "raw": ""}
    raw = out[-1] if out else ""
    present = raw != "missing"
    try:
        matches = int(raw or 0)
    except ValueError:
        matches = 0
    return {"path": RUN_DICT_PEN, "present": present, "guarded": matches > 0, "raw": raw}


def probe(serial: str | None = None) -> dict:
    """Device launcher state plus whether the full migration is required."""
    helper_error = ""
    status: dict = {}
    try:
        status = update_system.status(serial)
    except update_system.UpdateError as exc:
        helper_error = exc.message

    components = status.get("components") or {}
    core = ""
    if isinstance(components, dict):
        core = str((components.get("core") or {}).get("version") or "")
    launcher = launcher_state(serial)
    launcher_ready = status.get("launcher_ready")

    reasons: list[str] = []
    if core in BROKEN_LAUNCHERS:
        reasons.append(f"当前 core {core} 的启动器有冷启动缺陷，必须跑一次完整迁移包")
    elif helper_error and not core:
        reasons.append("设备上没有可用的 penmods-update，可能还是旧布局")
    elif version_tuple(core) < SAFE_LAUNCHER and not launcher["guarded"]:
        reasons.append(f"启动器不是 guarded v3（core {core or '未知'}）")
    if launcher["present"] and not launcher["guarded"]:
        reasons.append("/usr/bin/runDictPen 里没有 guarded v3 入口")
    if launcher_ready is False:
        reasons.append("penmods-update 报告 launcher_ready = false")

    return {
        "ok": True,
        "core": core,
        "helper_error": helper_error,
        "status": status,
        "launcher": launcher,
        "launcher_ready": launcher_ready,
        "pending": status.get("pending"),
        "trial": status.get("trial"),
        "needs_migration": bool(reasons),
        "reasons": reasons,
        "safe_launcher": ".".join(str(p) for p in SAFE_LAUNCHER),
        "broken_launchers": list(BROKEN_LAUNCHERS),
    }


def install(
    serial: str | None = None,
    workdir: Path | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict:
    """Download, verify, push and run the full v2.7.3+ migration package."""
    say = progress or (lambda _msg: None)
    workdir = workdir or Path(".")

    say("读取 GitHub 最新发布…")
    release = releases.latest_release()
    asset_name, meta = find_asset(release)
    version = release_version(release, asset_name)

    before = probe(serial)
    model = str(((before.get("status") or {}).get("model")) or "YDP02X")
    if model and model not in ("YDP02X", "YDPG3", "YDP03X"):
        raise MigrationError("MODEL_MISMATCH", f"迁移包只面向 YDP02X / YDPG3，当前设备模型是 {model}")

    say(f"校验 SHA256SUMS 并下载 {asset_name}…")
    sums = releases.sums_for(release, workdir)
    package = releases.fetch_asset(release, asset_name, workdir, sums=sums)
    if sums and asset_name not in sums:
        raise MigrationError("SUM_MISSING", f"SHA256SUMS 里没有 {asset_name}，拒绝安装")

    remote_dir = f"{INSTALL_ROOT}/install-{version}"
    remote_zip = f"{remote_dir}/{asset_name}"
    say(f"上传到 {remote_zip}…")
    update_system.shell(serial, f"mkdir -p {safe.shq(remote_dir)}", timeout=60)
    base = ["-s", serial] if serial else []
    _penctl_run(base + ["push", str(package), remote_zip], timeout=900)

    say("解包…")
    update_system.shell(serial, f"cd {safe.shq(remote_dir)} && unzip -o {safe.shq(asset_name)}", timeout=600)

    say("运行 _do_update.sh（不要断电）…")
    output = update_system.shell(
        serial,
        f"cd {safe.shq(remote_dir)} && sh _do_update.sh",
        timeout=1200,
    )

    say("重新读取启动器状态…")
    after = probe(serial)
    return {
        "ok": True,
        "version": version,
        "asset": asset_name,
        "size": int(meta.get("size") or 0),
        "remote": remote_zip,
        "output": output.strip()[-2000:],
        "before": before,
        "probe": after,
        "restart_hint": "迁移完成后需要重启一次应用：penmods-update 自带 16 秒冷却，不要连续杀进程。",
    }


def restart(serial: str | None = None) -> dict:
    """Restart the reading app so the new launcher takes over (16s guard)."""
    try:
        update_system.shell(serial, "sync; killall -TERM YoudaoDictPen", timeout=60)
    except update_system.UpdateError as exc:
        raise MigrationError("RESTART_FAILED", f"重启应用失败：{exc.message}", exc.detail) from exc
    return {"ok": True, "message": "已发送重启命令；守护器会等 16 秒再拉起新启动器。"}


def _penctl_run(argv: list[str], timeout: float) -> None:
    from . import penctl

    try:
        penctl.run_checked(argv, timeout=timeout)
    except penctl.PenctlError as exc:
        raise MigrationError("PUSH_FAILED", "上传迁移包失败", exc.detail or exc.message) from exc
