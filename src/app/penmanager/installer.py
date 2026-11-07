"""Device-side install transactions.

Two paths share the same planner:
  * fresh install / repair: stage the PenMods core libs, patch the launcher
    binary to `NEEDED libPenMods.so`, swap everything in with `mv -f`;
  * OTA update: stage the update payload and swap the same files.

Safety rules (from docs/PLAN.md and PenMods' own AGENTS.md):
  * never overwrite a mapped .so in place — always `.tmp` + `mv -f`;
  * restart the UI with `killall YoudaoDictPen` instead of patching a live map;
  * keep the launcher backup so a rollback is one command.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import penctl, safe

MOD_DIR = "/userdata/PenMods"
APP_DIR = "/oem/YoudaoDictPen/output"
APP_BIN = f"{APP_DIR}/YoudaoDictPen"
PATCHELF = "/usr/bin/patchelf"

BACKUPS = (f"{APP_DIR}/YoudaoDictPen.original_bak", f"{APP_DIR}/YoudaoDictPen.bak")
CORE_NAMES = ("libPenMods.so", "libPenModsResources.so")


class InstallError(RuntimeError):
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
class Step:
    title: str
    kind: str  # "shell" | "push" | "note"
    command: str = ""
    local: str = ""
    remote: str = ""
    optional: bool = False
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "kind": self.kind,
            "command": self.command,
            "local": self.local,
            "remote": self.remote,
            "optional": self.optional,
        }


def core_payload(libs: dict[str, Path]) -> dict[str, Path]:
    """Keep only the .so files we actually ship; resources are optional."""
    return {name: path for name, path in libs.items() if name in CORE_NAMES and path.is_file()}


def needs_patchcheck() -> Step:
    return Step(
        title="确认 patchelf 与启动器状态",
        kind="shell",
        command=(
            f"test -x {PATCHELF} && echo patchelf-ok || echo patchelf-missing; "
            f"ls -1 {APP_DIR}/YoudaoDictPen* 2>/dev/null"
        ),
    )


def remount_step() -> Step:
    return Step(
        title="让系统分区可写（只在需要时）",
        kind="shell",
        command=(
            "if touch /test_write_permission 2>/dev/null; then rm -f /test_write_permission; "
            "echo already-rw; else mount -o remount,rw / && rm -f /test_write_permission && echo remounted; fi"
        ),
    )


def stage_core_steps(payload: dict[str, Path]) -> list[Step]:
    steps = [Step(title=f"准备 {MOD_DIR}", kind="shell",
                  command=f"mkdir -p {MOD_DIR} && chmod 755 {MOD_DIR} && echo dir-ready")]
    for name in payload:
        steps.append(Step(
            title=f"上传 {name} 到临时文件",
            kind="push",
            local=str(payload[name]),
            remote=f"/tmp/{name}.penmods-new",
        ))
    for name in payload:
        steps.append(Step(
            title=f"原子替换 {name}（不覆盖已映射的 so）",
            kind="shell",
            command=(
                f"if [ -f /tmp/{name}.penmods-new ]; then "
                f"mv -f /tmp/{name}.penmods-new {MOD_DIR}/{name}.tmp && "
                f"chmod 644 {MOD_DIR}/{name}.tmp && mv -f {MOD_DIR}/{name}.tmp {MOD_DIR}/{name} && "
                f"echo swapped-{name}; else echo missing-{name}; fi"
            ),
        ))
    return steps


def patch_steps() -> list[Step]:
    """Make the launcher load libPenMods.so without rewriting a running map.

    The launcher path must always exist: we patch a *copy* and rename it over
    the original with a single atomic `mv`, so a crash in between leaves either
    the old or the new binary, never nothing.
    """
    add_needed = (
        f"cd {APP_DIR} && "
        f"[ -f YoudaoDictPen.original_bak ] || cp -f YoudaoDictPen YoudaoDictPen.original_bak; "
        f"cp -f YoudaoDictPen YoudaoDictPen.penmods-new && "
        f"{PATCHELF} --add-needed {MOD_DIR}/libPenMods.so YoudaoDictPen.penmods-new && "
        f"chmod 755 YoudaoDictPen.penmods-new && "
        f"mv -f YoudaoDictPen.penmods-new YoudaoDictPen && echo patched"
    )
    verify = (
        f"{PATCHELF} --print-needed {APP_BIN} | grep -q libPenMods.so && echo need-ok || echo need-missing; "
        f"ls -l {MOD_DIR}/libPenMods.so"
    )
    return [
        Step(title="给启动器写入 libPenMods.so 依赖", kind="shell", command=add_needed),
        Step(title="校验启动器依赖与库文件", kind="shell", command=verify),
    ]


def restart_step() -> Step:
    return Step(
        title="重启点读笔主界面（让新库生效）",
        kind="shell",
        command="killall YoudaoDictPen 2>/dev/null; sync; echo ui-restarted",
    )


def component_steps(plan: list[dict], workdir: Path) -> list[Step]:
    """Optional components: qml plugin zip, mathjax zip, ppocr installer script."""
    steps: list[Step] = []
    for comp in plan:
        if not comp.get("enabled") or comp["id"] == "core":
            continue
        action = comp.get("action")
        raw_asset = str(comp.get("asset") or "")
        try:
            asset_name = safe.require_plain_name(raw_asset, what="组件文件名")
        except safe.SafetyError as exc:
            steps.append(Step(title=f"跳过 {comp['title']}（{exc.message}）", kind="note", optional=True))
            continue
        asset = workdir / asset_name
        if not asset.is_file():
            steps.append(Step(title=f"跳过 {comp['title']}（文件未下载）", kind="note", optional=True))
            continue
        remote = "/tmp/" + asset_name
        steps.append(Step(title=f"上传 {comp['title']}", kind="push", local=str(asset), remote=remote))
        if action == "qml_dir":
            cmd = f"mkdir -p /userdata/PenMods/qml && cd /userdata/PenMods/qml && unzip -o -q {safe.shq(remote)} && echo qml-ok"
        elif action == "extract_dir":
            cmd = f"mkdir -p /userdata/PenMods/mathjax-server && cd /userdata/PenMods/mathjax-server && unzip -o -q {safe.shq(remote)} && echo mathjax-ok"
        elif action == "script":
            cmd = f"chmod +x {safe.shq(remote)} && sh {safe.shq(remote)} install && echo ppocr-ok"
        else:
            cmd = "echo unknown-component"
        steps.append(Step(title=f"安装 {comp['title']}", kind="shell", command=cmd))
        steps.append(Step(title=f"清理 {asset_name}", kind="shell",
                          command=f"rm -f {safe.shq(remote)}", optional=True))
    return steps


def build_plan(payload: dict[str, Path], *, components: list[dict] | None = None,
               workdir: Path | None = None, fresh: bool = True) -> list[Step]:
    steps: list[Step] = [needs_patchcheck()]
    if fresh:
        steps.append(remount_step())
    steps.extend(stage_core_steps(payload))
    steps.extend(patch_steps())
    if components and workdir:
        steps.extend(component_steps(components, workdir))
    steps.append(restart_step())
    return steps


def ota_plan(payload: dict[str, bytes], staging: Path) -> list[Step]:
    """Write the OTA payload to `staging`, then swap the files into place."""
    staging.mkdir(parents=True, exist_ok=True)
    steps: list[Step] = []
    for name, data in payload.items():
        try:
            name = safe.require_plain_name(name, what="更新包文件名")
        except safe.SafetyError as exc:
            raise InstallError(exc.code, exc.message) from exc
        target = staging / name
        target.write_bytes(data)
        if name.endswith(".so") or name.endswith(".sh"):
            steps.append(Step(title=f"上传 {name}", kind="push", local=str(target), remote=f"/tmp/{name}.penmods-new"))
            steps.append(Step(
                title=f"替换 {name}",
                kind="shell",
                command=(
                    f"if [ -f /tmp/{name}.penmods-new ]; then mkdir -p {MOD_DIR}; "
                    f"mv -f /tmp/{name}.penmods-new {safe.shq(MOD_DIR + '/' + name + '.tmp')} && "
                    f"chmod 644 {safe.shq(MOD_DIR + '/' + name + '.tmp')} && "
                    f"mv -f {safe.shq(MOD_DIR + '/' + name + '.tmp')} {safe.shq(MOD_DIR + '/' + name)} && "
                    f"echo swapped-{name}; fi"
                ),
            ))
    steps.append(restart_step())
    return steps


def execute(steps: list[Step], *, serial: str | None = None, on_event=None) -> list[dict]:
    """Run a plan over the active transport; returns one result per step."""
    base = ["-s", serial] if serial else []
    results: list[dict] = []
    for index, step in enumerate(steps):
        entry = {"index": index, **step.to_dict()}
        try:
            if step.kind == "push":
                data = penctl.run(base + ["push", step.local, step.remote], timeout=600)
                entry["ok"] = data.get("ok") is True
                entry["output"] = data.get("error", {}).get("message", "") if not entry["ok"] else ""
            elif step.kind == "shell":
                out = penctl.run_text(base + ["shell", step.command], timeout=600)
                entry["ok"] = True
                entry["output"] = out.strip()[-1000:]
                low = entry["output"].lower()
                if "patchelf-missing" in low or "need-missing" in low:
                    entry["ok"] = False
                    entry["output"] = entry["output"] + "\n设备缺少 patchelf 或注入未生效"
            else:
                entry["ok"] = True
                entry["output"] = "skipped"
        except penctl.PenctlError as exc:
            entry["ok"] = False
            entry["output"] = f"{exc.code}: {exc.message}"
            if not step.optional:
                results.append(entry)
                raise InstallError(exc.code, f"{step.title} 失败：{exc.message}", exc.detail) from exc
        results.append(entry)
        if on_event is not None:
            on_event(entry)
    return results


def rollback(*, serial: str | None = None) -> list[dict]:
    """Restore the launcher and drop the injected libs."""
    base = ["-s", serial] if serial else []
    cmds = [
        f"if [ -f {safe.shq(BACKUPS[0])} ]; then cp -f {safe.shq(BACKUPS[0])} {safe.shq(APP_BIN)} && echo restored-original; "
        f"elif [ -f {safe.shq(BACKUPS[1])} ]; then cp -f {safe.shq(BACKUPS[1])} {safe.shq(APP_BIN)} && echo restored-bak; fi",
        f"rm -f {safe.shq(MOD_DIR + '/libPenMods.so')} {safe.shq(MOD_DIR + '/libPenModsResources.so')}",
        "killall YoudaoDictPen 2>/dev/null; echo rolled-back",
    ]
    out = []
    for cmd in cmds:
        try:
            out.append({"ok": True, "output": penctl.run_text(base + ["shell", cmd], timeout=180).strip()[-500:]})
        except penctl.PenctlError as exc:
            out.append({"ok": False, "output": f"{exc.code}: {exc.message}"})
    return out


def installed_version(*, serial: str | None = None) -> str:
    """Best-effort installed PenMods version (manifest/update-system aware)."""
    base = ["-s", serial] if serial else []
    script = (
        "cat /userdata/PenMods/ota-manifest.json 2>/dev/null | head -c 2000; "
        "ls /userdisk/PenMods/update-system 2>/dev/null | head -3"
    )
    try:
        raw = penctl.run_text(base + ["shell", script], timeout=60)
    except penctl.PenctlError:
        return ""
    import re

    match = re.search(r'penmods-ota@v(\d+\.\d+\.\d+)', raw or "")
    return match.group(1) if match else ""
