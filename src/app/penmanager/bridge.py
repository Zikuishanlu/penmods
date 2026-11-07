"""QML-facing backend: every method returns a JSON-ish dict, never throws.

Long operations (network, installs, market) run on a worker thread and report
through the `taskFinished(id, result)` signal so the glass UI never blocks.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
import threading
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, Signal, Slot

from . import (__version__, installer, market, migration, netutil, ota, penctl, plugins,
               releases, sshsetup, update_system)
from .paths import data_dir, penctl_path, qml_dir


def _err(exc: Exception) -> dict:
    to_dict = getattr(exc, "to_dict", None)
    if callable(to_dict):
        return {"ok": False, "error": to_dict()}
    return {"ok": False, "error": {"code": type(exc).__name__, "message": str(exc)[:600]}}


class Backend(QObject):
    taskFinished = Signal(str, "QVariantMap")
    progress = Signal(str, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._workdir = data_dir() / "downloads"
        self._release: releases.Release | None = None
        self._plan: list[dict] | None = None
        self._index: dict | None = None
        self._ota_entries: list[ota.OtaEntry] | None = None
        self._busy: set[str] = set()
        self._lock = threading.Lock()

    # --------------------------------------------------------- update-system
    @Slot(str)
    def updateSystemStatus(self, serial: str) -> None:
        self._async("update-status", lambda: self._update_status(serial or None))

    def _update_status(self, serial: str | None) -> dict:
        try:
            return {"ok": True, "status": update_system.status(serial)}
        except Exception as exc:  # noqa: BLE001
            return _err(exc)

    @Slot(str)
    def updateComponents(self, serial: str) -> None:
        self._async("update-components", lambda: self._update_components(serial or None))

    def _update_components(self, serial: str | None) -> dict:
        try:
            manifest = update_system.fetch_manifest()
            current = update_system.status(serial)
            current.setdefault("model", "YDP02X")
            return {
                "ok": True,
                "status": current,
                "components": update_system.plan(manifest, current),
            }
        except Exception as exc:  # noqa: BLE001
            return _err(exc)

    @Slot(str, str)
    def stageComponent(self, component_id: str, serial: str) -> None:
        self._async("update-stage", lambda: self._stage_component(component_id, serial or None))

    def _stage_component(self, component_id: str, serial: str | None) -> dict:
        try:
            manifest = update_system.fetch_manifest()
            current = update_system.status(serial)
            current.setdefault("model", "YDP02X")
            entries = {c["id"]: c for c in update_system.parse_components(manifest)}
            if component_id not in entries:
                raise update_system.UpdateError("UNKNOWN_COMPONENT", f"未知组件：{component_id}")
            version = update_system.pick_version(
                entries[component_id]["versions"], str(current.get("model") or "YDP02X")
            )
            result = update_system.stage(version, self._workdir / "updates", serial)
            return {"ok": True, **result}
        except Exception as exc:  # noqa: BLE001
            return _err(exc)

    @Slot(str)
    def cancelPendingUpdate(self, serial: str) -> None:
        self._async("update-cancel", lambda: self._cancel_pending(serial or None))

    def _cancel_pending(self, serial: str | None) -> dict:
        try:
            return {"ok": True, **update_system.cancel(serial)}
        except Exception as exc:  # noqa: BLE001
            return _err(exc)

    @Slot(str)
    def enablePendingUpdate(self, serial: str) -> None:
        self._async("update-enable", lambda: self._enable_pending(serial or None))

    def _enable_pending(self, serial: str | None) -> dict:
        try:
            return {"ok": True, **update_system.enable(serial)}
        except Exception as exc:  # noqa: BLE001
            return _err(exc)

    # -------------------------------------------------- launcher migration 2.7.3
    @Slot(str)
    def migrationStatus(self, serial: str) -> None:
        self._async("migration-status", lambda: self._migration_status(serial or None))

    def _migration_status(self, serial: str | None) -> dict:
        try:
            out: dict[str, Any] = {"ok": True, "probe": migration.probe(serial)}
            try:
                release = releases.latest_release()
            except Exception as exc:  # noqa: BLE001 - offline is a normal state
                out.update({"release": {}, "asset": "", "asset_error": _err(exc)["error"]})
                return out
            out["release"] = {"tag": release.tag, "html_url": release.html_url}
            try:
                asset_name, meta = migration.find_asset(release)
            except migration.MigrationError as exc:
                out.update({"asset": "", "asset_error": exc.to_dict()})
                return out
            out.update(
                {
                    "asset": asset_name,
                    "size": int((meta or {}).get("size") or 0),
                    "version": migration.release_version(release, asset_name),
                }
            )
            return out
        except Exception as exc:  # noqa: BLE001
            return _err(exc)

    @Slot(str)
    def migrationInstall(self, serial: str) -> None:
        self._async("migration-install", lambda: self._migration_install(serial or None))

    def _migration_install(self, serial: str | None) -> dict:
        try:
            seen: list[str] = []

            def progress(message: str) -> None:
                seen.append(message)
                self.progress.emit("migration-install", message)

            result = migration.install(serial, self._workdir / "migration", progress=progress)
            return {"ok": True, "steps": seen, **result}
        except Exception as exc:  # noqa: BLE001
            return _err(exc)

    @Slot(str)
    def migrationRestart(self, serial: str) -> None:
        self._async("app-restart", lambda: self._restart_app(serial or None))

    def _restart_app(self, serial: str | None) -> dict:
        try:
            return {"ok": True, **migration.restart(serial)}
        except Exception as exc:  # noqa: BLE001
            return _err(exc)

    @Slot(str)
    def launcherVerify(self, serial: str) -> None:
        self._async("launcher-verify", lambda: self._launcher_verify(serial or None))

    def _launcher_verify(self, serial: str | None) -> dict:
        try:
            return {"ok": True, "probe": migration.probe(serial)}
        except Exception as exc:  # noqa: BLE001
            return _err(exc)

    @Slot(str)
    def rebootDevice(self, serial: str) -> None:
        self._async("reboot", lambda: self._reboot(serial or None))

    def _reboot(self, serial: str | None) -> dict:
        """Reboot the pen so the update helper can trial the staged generation."""
        base = ["-s", serial] if serial else []
        try:
            penctl.run_text(base + ["shell", "sync; sleep 1; reboot"], timeout=25)
        except penctl.PenctlError:
            # the adb connection usually dies mid-command; that is expected
            pass
        return {"ok": True, "message": "已发送重启命令，笔重启后会自动试用新组件"}

    # ------------------------------------------------------------ device config
    CONFIG_PATH = "/userdata/PenModsconfig.json"
    CONFIG_KEYS = ("adb_autorun", "ssh_autorun", "adb_skip_verification")

    @Slot(str)
    def readConfig(self, serial: str) -> None:
        self._async("config-read", lambda: self._read_config(serial or None))

    def _read_config(self, serial: str | None) -> dict:
        base = ["-s", serial] if serial else []
        try:
            raw = penctl.run_text(base + ["shell", f"cat {self.CONFIG_PATH}"], timeout=30)
        except penctl.PenctlError as exc:
            return {"ok": False, "error": exc.to_dict()}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {"ok": False, "error": {"code": "BAD_JSON", "message": "设备配置不是合法 JSON", "detail": raw[:800]}}
        if not isinstance(data, dict):
            return {"ok": False, "error": {"code": "BAD_JSON", "message": "设备配置不是对象"}}
        serv = data.get("serv")
        if not isinstance(serv, dict):
            serv = {}
        return {"ok": True, "config": serv, "raw": raw}

    @Slot(str, str)
    def writeConfig(self, serial: str, config_json: str) -> None:
        self._async("config-write", lambda: self._write_config(serial or None, config_json))

    def _write_config(self, serial: str | None, config_json: str) -> dict:
        try:
            data = json.loads(config_json)
        except json.JSONDecodeError:
            return {"ok": False, "error": {"code": "BAD_JSON", "message": "提交的配置不是合法 JSON"}}
        if not isinstance(data, dict):
            return {"ok": False, "error": {"code": "BAD_JSON", "message": "配置必须是对象"}}
        if not any(k in data for k in self.CONFIG_KEYS):
            return {"ok": False, "error": {"code": "NO_KEYS", "message": "没有可写的配置项"}}

        base = ["-s", serial] if serial else []
        # read the whole file first: the three switches live under "serv", and
        # everything else must stay byte-identical
        try:
            raw = penctl.run_text(base + ["shell", f"cat {self.CONFIG_PATH}"], timeout=30)
            full = json.loads(raw)
        except (penctl.PenctlError, json.JSONDecodeError) as exc:
            code = getattr(exc, "code", "BAD_JSON")
            return {"ok": False, "error": {"code": code, "message": f"读取现有配置失败: {exc}"}}
        if not isinstance(full, dict):
            return {"ok": False, "error": {"code": "BAD_JSON", "message": "设备配置不是对象"}}
        serv = full.get("serv")
        if not isinstance(serv, dict):
            serv = {}
        for key in self.CONFIG_KEYS:
            if key in data:
                serv[key] = bool(data[key])
        full["serv"] = serv

        local = data_dir() / "downloads" / "PenModsconfig.json.new"
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text(json.dumps(full, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        remote_new = self.CONFIG_PATH + ".penmanager-new"
        remote_bak = self.CONFIG_PATH + ".penmanager-bak"
        try:
            penctl.run_checked(base + ["push", str(local), remote_new], timeout=120)
            # keep one rollback copy, then swap in place
            penctl.run_text(base + ["shell",
                f"cp -f {self.CONFIG_PATH} {remote_bak} 2>/dev/null; "
                f"mv -f {remote_new} {self.CONFIG_PATH} && echo penmods-config-ok"], timeout=60)
        except penctl.PenctlError as exc:
            return {"ok": False, "error": exc.to_dict()}
        return {"ok": True, "message": "已写入设备配置（备份 .penmanager-bak），重启 PenMods 后生效",
                "config": serv}

    # ------------------------------------------------------------------ utils
    def _call(self, args: list[Any], serial: str | None = None, timeout: float = 180) -> dict:
        try:
            return penctl.run(args, serial=serial, timeout=timeout)
        except penctl.PenctlError as exc:
            return {"ok": False, "error": exc.to_dict()}
        except Exception as exc:  # noqa: BLE001 - never let a bug kill the UI
            return _err(exc)

    def _async(self, task_id: str, work: Callable[[], dict]) -> None:
        with self._lock:
            if task_id in self._busy:
                return
            self._busy.add(task_id)

        def runner() -> None:
            try:
                result = work()
            except Exception as exc:  # noqa: BLE001
                result = _err(exc)
            finally:
                with self._lock:
                    self._busy.discard(task_id)
            if not isinstance(result, dict):
                result = {"ok": True, "value": result}
            result.setdefault("ok", True)
            self.taskFinished.emit(task_id, result)

        threading.Thread(target=runner, name=f"penmods-{task_id}", daemon=True).start()

    @Slot(result="QVariantMap")
    def wallpapers(self) -> dict:
        """Bundled photo presets (Unsplash photos, shipped with the app)."""
        folder = Path(__file__).resolve().parent / "data" / "wallpapers"
        labels = {
            "photo-fjord.jpg": "峡湾",
            "photo-canyon.jpg": "晚霞峡谷",
            "photo-snow.jpg": "雪山",
            "photo-forest.jpg": "晨雾森林",
            "photo-wave.jpg": "海浪",
            "photo-jelly.jpg": "水母",
        }
        items = []
        try:
            for name in sorted(labels):
                path = folder / name
                if path.is_file():
                    items.append({"id": name, "label": labels[name], "path": str(path)})
        except OSError:
            items = []
        return {"ok": True, "items": items, "folder": str(folder)}

    @Slot(result="QVariantMap")
    def appInfo(self) -> dict:
        exe = penctl_path()
        return {
            "appVersion": __version__,
            "penctl": str(exe) if exe else "",
            "qml": str(qml_dir()),
            "data": str(data_dir()),
        }

    # ----------------------------------------------------------- disclaimer
    DISCLAIMER_NAME = "disclaimer.json"
    DISCLAIMER_VERSION = 2

    def _disclaimer_path(self) -> Path:
        return data_dir() / self.DISCLAIMER_NAME

    @Slot(result="QVariantMap")
    def disclaimerState(self) -> dict:
        """Whether the first-run safety notice was already accepted."""
        path = self._disclaimer_path()
        version = 0
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and isinstance(raw.get("version"), int):
                version = raw["version"]
        except (OSError, ValueError):
            version = 0
        accepted = version >= self.DISCLAIMER_VERSION
        return {
            "ok": True,
            "accepted": accepted,
            "version": version,
            "required": self.DISCLAIMER_VERSION,
            "path": str(path),
        }

    @Slot(result="QVariantMap")
    def acceptDisclaimer(self) -> dict:
        path = self._disclaimer_path()
        payload = {
            "version": self.DISCLAIMER_VERSION,
            "acceptedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, path)
        except OSError as exc:
            return {"ok": False, "error": {"code": "WRITE_FAILED", "message": str(exc)}}
        return {"ok": True, "version": self.DISCLAIMER_VERSION, "path": str(path)}

    # ------------------------------------------------------------ appearance
    UI_SETTINGS_NAME = "ui-settings.json"

    def _ui_settings_path(self) -> Path:
        return data_dir() / self.UI_SETTINGS_NAME

    @Slot(result="QVariantMap")
    def uiSettings(self) -> dict:
        """Light/dark mode, accent colour and wallpaper chosen in Settings."""
        path = self._ui_settings_path()
        defaults = {"mode": "light", "accent": "blue", "wallpaper": "aurora"}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"ok": True, "settings": defaults, "stored": False}
        if not isinstance(raw, dict):
            return {"ok": True, "settings": defaults, "stored": False}
        merged = dict(defaults)
        if raw.get("mode") in ("light", "dark"):
            merged["mode"] = raw["mode"]
        if isinstance(raw.get("accent"), str) and raw["accent"]:
            merged["accent"] = raw["accent"]
        if isinstance(raw.get("wallpaper"), str) and raw["wallpaper"]:
            merged["wallpaper"] = raw["wallpaper"]
        return {"ok": True, "settings": merged, "stored": True}

    @Slot(str, result="QVariantMap")
    def saveUiSettings(self, settings_json: str) -> dict:
        try:
            raw = json.loads(settings_json)
        except ValueError as exc:
            return {"ok": False, "error": {"code": "BAD_JSON", "message": str(exc)}}
        if not isinstance(raw, dict):
            return {"ok": False, "error": {"code": "BAD_JSON", "message": "settings must be an object"}}
        path = self._ui_settings_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(path)
        except OSError as exc:
            return {"ok": False, "error": {"code": "WRITE_FAILED", "message": str(exc)}}
        return {"ok": True, "path": str(path)}

    @Slot()
    def detect(self) -> None:
        self._async("detect", lambda: self._call(["detect"], timeout=60))

    @Slot(str)
    def deviceInfo(self, serial: str) -> None:
        self._async("device-info",
                    lambda: self._call(["device-info"], serial=serial or None, timeout=90))

    # ------------------------------------------------------------------- ssh
    @Slot(str)
    def sshOnboard(self, serial: str) -> None:
        self._async("ssh-onboard", lambda: self._ssh_onboard(serial))

    def _ssh_onboard(self, serial: str) -> dict:
        try:
            return sshsetup.onboard(serial)
        except Exception as exc:  # noqa: BLE001
            return _err(exc)

    @Slot(str)
    def sshProbe(self, host: str) -> None:
        self._async("ssh-probe", lambda: self._ssh_probe(host))

    def _ssh_probe(self, host: str) -> dict:
        try:
            return sshsetup.probe(host)
        except Exception as exc:  # noqa: BLE001
            return _err(exc)
    @Slot(result="QVariantMap")
    def sshState(self) -> dict:
        """Current SSH transport, plus where the key / known_hosts live."""
        transport = penctl.get_transport()
        key = sshsetup.private_key()
        known = sshsetup.known_hosts()
        return {
            "ok": True,
            "connected": bool(transport),
            "transport": transport or {},
            "key": str(key),
            "keyExists": key.is_file(),
            "knownHosts": str(known),
            "knownHostsExists": known.is_file(),
        }

    @Slot(str, str, str)
    def sshConnect(self, host: str, user: str, port: str) -> None:
        self._async("ssh-connect", lambda: self._ssh_connect(host, user, port))

    def _ssh_connect(self, host: str, user: str, port: str) -> dict:
        """Probe root@host over SSH with our key; on success every later command
        uses that channel instead of ADB."""
        target_host = (host or "").strip()
        if not target_host:
            return {"ok": False, "error": {"code": "BAD_ARG", "message": "请填写点读笔的 IP 或主机名"}}
        target_user = (user or "root").strip() or "root"
        try:
            target_port = int(str(port or "22").strip() or "22")
        except ValueError:
            target_port = 22
        try:
            key = sshsetup.ensure_keypair()
            probe = sshsetup.probe(f"{target_user}@{target_host}", key=key, port=target_port)
            if not probe.get("ok"):
                penctl.set_transport(None)
                detail = probe.get("error") or {
                    "code": "SSH_UNREACHABLE",
                    "message": (probe.get("output") or "").strip()
                    or "SSH 连不上：检查 Wi-Fi、IP、端口，以及是否已通过 ADB 部署过公钥",
                }
                return {"ok": False, "error": detail}
            transport = {
                "mode": "ssh",
                "host": target_host,
                "user": target_user,
                "port": target_port,
                "key": str(key),
                "known_hosts": str(sshsetup.known_hosts()),
            }
            penctl.set_transport(transport)
            info = self._call(["device-info"], timeout=120)
            derived = info.get("derived") if isinstance(info, dict) else None
            return {
                "ok": True,
                "transport": transport,
                "target": f"{target_user}@{target_host}",
                "info": info,
                "derived": derived or {},
            }
        except Exception as exc:  # noqa: BLE001
            penctl.set_transport(None)
            return _err(exc)

    def ssh_connect_blocking(self, host: str, user: str = "root", port: str = "22") -> dict:
        """Same as sshConnect but returns the result (used by CLI screenshot preflight)."""
        return self._ssh_connect(host, user, port)

    @Slot(result="QVariantMap")
    def sshDisconnect(self) -> dict:
        penctl.set_transport(None)
        return {"ok": True, "connected": False}

    @Slot(result="QVariantMap")
    def sshForgetHost(self) -> dict:
        """Drop the pinned host key (use after re-flashing a pen)."""
        known = sshsetup.known_hosts()
        try:
            if known.is_file():
                known.unlink()
        except OSError as exc:
            return _err(exc)
        penctl.set_transport(None)
        return {"ok": True, "knownHosts": str(known)}

    # --------------------------------------------------------------- release
    @Slot()
    def checkRelease(self) -> None:
        def work() -> dict:
            release = releases.latest_release()
            self._release = release
            self._plan = releases.component_plan(release)
            return {"ok": True, "release": release.to_dict(), "components": self._plan}

        self._async("release", work)

    @Slot(str)
    def planInstall(self, selected_csv: str) -> None:
        chosen = [s for s in (selected_csv or "").split(",") if s]

        def work() -> dict:
            release = self._release
            if release is None:
                release = releases.latest_release()
                self._release = release
            self._plan = releases.component_plan(release, chosen)
            return {"ok": True, "components": self._plan}

        self._async("plan", work)

    @Slot(str)
    def runInstall(self, serial: str) -> None:
        def work() -> dict:
            release = self._release
            if release is None:
                raise releases.ReleaseError("NO_RELEASE", "请先检查可用版本")
            plan = self._plan or releases.component_plan(release)
            workdir = self._workdir / release.tag.replace("/", "_")
            sums = releases.sums_for(release, workdir)
            payload: dict[str, Path] = {}
            for name in (releases.CORE_ASSET, releases.RESOURCES_ASSET):
                if name in release.assets:
                    try:
                        payload[name] = releases.fetch_asset(release, name, workdir, sums=sums)
                    except releases.ReleaseError:
                        if name == releases.CORE_ASSET:
                            raise
            for comp in plan:
                if comp["enabled"] and comp["id"] != "core":
                    try:
                        releases.fetch_asset(release, comp["asset"], workdir, sums=sums)
                    except releases.ReleaseError:
                        pass
            steps = installer.build_plan(installer.core_payload(payload), components=plan,
                                         workdir=workdir, fresh=True)
            events = installer.execute(steps, serial=serial or None)
            return {"ok": True, "release": release.tag, "events": events}

        self._async("install", work)

    @Slot()
    def rollback(self) -> None:
        self._async("rollback", lambda: {"ok": True, "events": installer.rollback()})

    # ------------------------------------------------------------------- ota
    @Slot(str)
    def checkOta(self, current: str) -> None:
        def work() -> dict:
            entries = ota.fetch_manifest()
            self._ota_entries = entries
            return {"ok": True, **ota.describe(entries, current or None),
                    "entries": [e.to_dict() for e in entries[:5]]}

        self._async("ota-check", work)

    @Slot(str)
    def applyOta(self, serial: str) -> None:
        def work() -> dict:
            entries = self._ota_entries
            if not entries:
                entries = ota.fetch_manifest()
            update = entries[0]
            workdir = self._workdir / f"ota-{update.text}"
            zip_path = ota.download_update(update, workdir)
            payload = ota.payload_files(zip_path)
            staging = workdir / "staging"
            steps = installer.ota_plan(payload, staging)
            events = installer.execute(steps, serial=serial or None)
            return {"ok": True, "version": update.text, "events": events}

        self._async("ota-apply", work)

    # --------------------------------------------------------------- plugins
    @Slot(str)
    def pluginList(self, serial: str) -> None:
        def work() -> dict:
            return {"ok": True, "plugins": plugins.list_installed(serial=serial or None)}

        self._async("plugin-list", work)

    @Slot(str, str)
    def pluginInstall(self, path: str, serial: str) -> None:
        def work() -> dict:
            pkg = plugins.inspect_zip(Path(path))
            result = plugins.install(pkg, serial=serial or None)
            return {"ok": result.get("ok", False), "package": pkg.to_dict(), "device": result}

        self._async("plugin-install", work)

    @Slot(str, str)
    def pluginUninstall(self, plugin_id: str, serial: str) -> None:
        self._async("plugin-remove", lambda: plugins.uninstall(plugin_id, serial=serial or None))

    @Slot(str, bool, str)
    def pluginToggle(self, plugin_id: str, enabled: bool, serial: str) -> None:
        self._async("plugin-toggle", lambda: plugins.set_enabled(plugin_id, enabled, serial=serial or None))

    # ---------------------------------------------------------------- market
    @Slot(str)
    def marketLoad(self, url: str) -> None:
        def work() -> dict:
            index = market.load_index(url)
            self._index = index
            return {"ok": True, **index}

        self._async("market-load", work)

    @Slot(str, str, str)
    def marketInstall(self, plugin_id: str, version: str, serial: str) -> None:
        def work() -> dict:
            index = self._index
            if not index:
                raise market.MarketError("NO_INDEX", "请先加载插件索引")
            item = next((p for p in index["plugins"] if p["id"] == plugin_id), None)
            if item is None:
                raise market.MarketError("NOT_FOUND", f"索引里没有插件 {plugin_id}")
            ver = next((v for v in item["versions"] if v["version"] == version), item["versions"][0])
            workdir = self._workdir / "market"
            workdir.mkdir(parents=True, exist_ok=True)
            zip_path = market.download_version(item, ver, workdir)
            pkg = plugins.inspect_zip(zip_path)
            installed = plugins.install(pkg, serial=serial or None)
            return {"ok": installed.get("ok", False), "plugin": item["id"], "package": pkg.to_dict(),
                    "device": installed}

        self._async("market-install", work)

    @Slot(str, str)
    def marketFromRepo(self, repo_url: str, serial: str) -> None:
        def work() -> dict:
            asset = market.repo_install_url(repo_url)
            workdir = self._workdir / "repo"
            workdir.mkdir(parents=True, exist_ok=True)
            name = safe.safe_filename(asset["name"])
            dest = workdir / name
            if not dest.is_file() or dest.stat().st_size != asset["size"]:
                netutil.download(asset["url"], dest, timeout=180,
                                 max_bytes=max(int(asset["size"] or 0) * 2, 16 * 1024 * 1024))
            pkg = plugins.inspect_zip(dest)
            installed = plugins.install(pkg, serial=serial or None)
            return {"ok": installed.get("ok", False), "repo": f"{asset['owner']}/{asset['repo']}",
                    "tag": asset["tag"], "package": pkg.to_dict(), "device": installed}

        self._async("market-repo", work)

    # ----------------------------------------------------------------- files
    @Slot(str, str)
    def listDir(self, path: str, serial: str) -> None:
        target = path or "/userdata/PenMods"

        def work() -> dict:
            script = f"ls -la {safe.shq(target)} 2>/dev/null || echo __missing__"
            base = ["-s", serial] if serial else []
            out = penctl.run_text(base + ["shell", script], timeout=60)
            if out.strip() == "__missing__":
                raise installer.InstallError("NOT_FOUND", f"目录不存在：{target}")
            rows = []
            for line in out.splitlines()[1:]:
                parts = line.split(None, 8)
                if len(parts) < 9:
                    continue
                name = parts[8]
                if name in (".", ".."):
                    continue
                rows.append({"mode": parts[0], "size": parts[4], "name": name})
            return {"ok": True, "path": target, "rows": rows}

        self._async("files", work)

    @Slot(str, str, str)
    def pullFile(self, remote: str, local: str, serial: str) -> None:
        def work() -> dict:
            base = ["-s", serial] if serial else []
            return penctl.run(base + ["pull", remote, local], timeout=600)

        self._async("pull", work)

    @Slot(str, str, str)
    def pushFile(self, local: str, remote: str, serial: str) -> None:
        def work() -> dict:
            base = ["-s", serial] if serial else []
            return penctl.run(base + ["push", local, remote], timeout=600)

        self._async("push", work)

    # -------------------------------------------------------------- terminal
    @Slot(str, str)
    def terminalRun(self, command: str, serial: str) -> None:
        def work() -> dict:
            base = ["-s", serial] if serial else []
            try:
                out = penctl.run_text(base + ["shell", command], timeout=120)
                return {"ok": True, "output": out}
            except penctl.PenctlError as exc:
                return {"ok": False, "output": "", "error": exc.to_dict()}

        self._async("terminal", work)
