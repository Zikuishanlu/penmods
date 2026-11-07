"""Offline tests for the pure-Python layers (no device, no network).

Run with: python tests/test_offline.py
"""
from __future__ import annotations

import json
import os
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from penmanager import migration, netutil, ota, plugins, releases, update_system  # noqa: E402
from penmanager.paths import tmp_dir  # noqa: E402

FAILED = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global FAILED
    if ok:
        print(f"  ok   {label}")
    else:
        FAILED += 1
        print(f"  FAIL {label}  {detail}")


def expect_error(label: str, code: str, fn) -> None:
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        got = getattr(exc, "code", "")
        check(label, got == code, f"expected {code}, got {got}: {exc}")
    else:
        check(label, False, "no error raised")


def make_zip(path: Path, files: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return path


def test_sha256sums() -> None:
    print("[netutil]")
    text = "a" * 64 + "  libPenMods.so\n" + "b" * 32 + "  ignored\n" + "c" * 64 + " *update_v2.6.3.zip\n"
    sums = netutil.parse_sha256sums(text)
    check("parses two valid entries", len(sums) == 2, str(sums))
    check("strips the binary marker", sums.get("update_v2.6.3.zip") == "c" * 64, str(sums))


def test_ota() -> None:
    print("[ota]")
    doc = {
        "status": "ok",
        "versions": [
            {"version": [2, 6, 2], "note": "old", "size": 10, "download": "https://x/update_v2.6.2.zip", "md5": "a" * 32},
            {"version": [2, 6, 3], "note": "new", "size": 20, "download": "https://x/update_v2.6.3.zip", "md5": "b" * 32},
        ],
    }
    entries = ota.parse_manifest(doc)
    check("manifest sorted newest first", entries[0].version == (2, 6, 3), str(entries[0].version))
    check("version text", entries[0].text == "2.6.3", entries[0].text)
    check("update picked for 2.6.2", ota.pick_update(entries, "2.6.2") is entries[0])
    check("no update when current is newest", ota.pick_update(entries, "2.6.3") is None)
    snap = ota.describe(entries, "2.6.1")
    check("describe exposes update", snap["up_to_date"] is False and snap["available"]["version"] == "2.6.3", str(snap))

    tmp = tmp_dir()
    good = tmp / "update_v9.9.9.zip"
    make_zip(good, {"libPenMods.so": b"\x7fELF", "_do_update.sh": b"#!/bin/sh\n"})
    payload = ota.payload_files(good)
    check("payload read", set(payload) == {"libPenMods.so", "_do_update.sh"}, str(list(payload)))

    bad = tmp / "unsafe.zip"
    make_zip(bad, {"../evil.sh": b"x"})
    expect_error("zip-slip refused", "ZIP_UNSAFE", lambda: ota.payload_files(bad))

    corrupt = tmp / "corrupt.zip"
    corrupt.write_bytes(b"not a zip")
    expect_error("corrupt zip refused", "ZIP_CORRUPT", lambda: ota.payload_files(corrupt))


def test_releases() -> None:
    print("[releases]")
    release = releases.Release(
        tag="v2.6.3",
        name="2.6.3",
        html_url="https://example/rel",
        published_at="2026-10-31",
        assets={
            releases.CORE_ASSET: {"url": "https://x/libPenMods.so", "size": 9887800},
            releases.RESOURCES_ASSET: {"url": "https://x/res.so", "size": 1523544},
            releases.FFMPEG_ASSET: {"url": "https://x/ffmpeg.zip", "size": 5798553},
        },
    )
    plan = releases.component_plan(release, selected=["ffmpegplayer"])
    by_id = {c["id"]: c for c in plan}
    check("core always enabled", by_id["core"]["enabled"] is True and by_id["core"]["required"] is True)
    check("picked optional enabled", by_id["ffmpegplayer"]["enabled"] is True)
    check("unpicked optional disabled", by_id["mathjax"]["enabled"] is False)
    check("missing asset flagged", by_id["mathjax"]["available"] is False, str(by_id["mathjax"]))
    check("sizes carried", by_id["core"]["size"] == 9887800, str(by_id["core"]["size"]))
    check("required ids", releases.REQUIRED_IDS == ("core",), str(releases.REQUIRED_IDS))


META = json.dumps({"id": "com.example.demo", "name": "Demo", "version": "1.0.0"}).encode()


def test_plugins() -> None:
    print("[plugins]")
    tmp = tmp_dir()

    flat = make_zip(tmp / "flat.zip", {"metadata.json": META, "main.qml": b"import QtQuick", "libdemo.so": b"\x7fELF"})
    pkg = plugins.inspect_zip(flat)
    check("flat package id", pkg.plugin_id == "com.example.demo", pkg.plugin_id)
    check("native detected", pkg.has_native is True)

    wrapped = make_zip(tmp / "wrapped.zip", {"demo/metadata.json": META, "demo/main.qml": b"import QtQuick"})
    check("wrapper dir accepted", plugins.inspect_zip(wrapped).plugin_id == "com.example.demo")

    no_meta = make_zip(tmp / "nometa.zip", {"main.qml": b"x"})
    expect_error("metadata required", "NO_METADATA", lambda: plugins.inspect_zip(no_meta))

    bad_meta = make_zip(tmp / "badmeta.zip", {"metadata.json": b'{"id": "x"}'})
    expect_error("metadata fields required", "BAD_METADATA", lambda: plugins.inspect_zip(bad_meta))

    bad_id = make_zip(tmp / "badid.zip", {"metadata.json": json.dumps({"id": "../x", "name": "n", "version": "1"}).encode()})
    expect_error("illegal id refused", "BAD_ID", lambda: plugins.inspect_zip(bad_id))

    slip = make_zip(tmp / "slip.zip", {"metadata.json": META, "../evil": b"x"})
    expect_error("zip-slip refused", "UNSAFE_PATH", lambda: plugins.inspect_zip(slip))

    steps = plugins.install_steps(pkg, "/tmp/staging-x")
    check("swap uses mv -f", any("mv -f" in s for s in steps), str(steps))
    check("install checks metadata", any("metadata.json" in s for s in steps), str(steps))


def test_update_system() -> None:
    print("[update_system]")
    manifest = {
        "status": 200,
        "components": [
            {
                "id": "core",
                "name": "PenMods",
                "versions": [
                    {
                        "version": [2, 7, 0],
                        "model": "YDP02X",
                        "arch": "aarch64",
                        "channel": "dev",
                        "size": 5204710,
                        "unpacked_size": 11525656,
                        "sha256": "a" * 64,
                        "download": "https://example.invalid/core.zip",
                        "health_protocol": 1,
                    }
                ],
            },
            {
                "id": "player",
                "name": "player",
                "versions": [
                    {
                        "version": [1, 0, 3],
                        "model": "YDP02X",
                        "arch": "aarch64",
                        "channel": "dev",
                        "size": 5798553,
                        "unpacked_size": 12566779,
                        "sha256": "b" * 64,
                        "download": "https://example.invalid/player.zip",
                        "requires": {"core": {"min": "2.7.0", "max_exclusive": "3.0.0"}},
                    }
                ],
            },
            {"id": "bogus", "name": "bogus", "versions": []},
        ],
    }
    comps = update_system.parse_components(manifest)
    check("only known component ids kept", [c["id"] for c in comps] == ["core", "player"], str([c["id"] for c in comps]))

    core = update_system.pick_version(comps[0]["versions"], "YDP02X")
    desc = core.descriptor()
    check("descriptor has stage fields", all(k in desc for k in ("id", "version", "model", "arch", "channel", "size", "unpacked_size", "sha256")), str(desc))
    check("core descriptor carries health_protocol", desc.get("health_protocol") == 1, str(desc))
    check("version list rendered as X.Y.Z", desc["version"] == "2.7.0", desc["version"])
    check("no requires key when absent", "requires" not in desc, str(desc))

    player = update_system.pick_version(comps[1]["versions"], "YDP02X")
    check("player descriptor keeps requires", player.descriptor().get("requires") == {"core": {"min": "2.7.0", "max_exclusive": "3.0.0"}})

    expect_error("unknown model refused", "MODEL_MISMATCH", lambda: update_system.pick_version(comps[0]["versions"], "P5"))

    current = {
        "model": "YDP02X",
        "components": {"core": {"version": "2.7.0"}},
        "pending_components": {"player": {"version": "1.0.3"}},
    }
    rows = update_system.plan(manifest, current)
    check("plan lists both components", [r["id"] for r in rows] == ["core", "player"], str(rows))
    check("plan reports installed version", rows[0]["installed"] == "2.7.0", str(rows[0]))
    check("plan reports pending flag", rows[1]["pending"] is True, str(rows[1]))
    check("core row marked required", rows[0]["required"] is True)
    check("installed_versions maps ids", update_system.installed_versions(current) == {"core": "2.7.0"})
    expect_error("empty versions refused", "BAD_VERSION", lambda: update_system._version_text(""))
    expect_error("malformed manifest refused", "NO_COMPONENTS", lambda: update_system.parse_components({"components": []}))

    satisfied, reason = update_system.requires_state({"core": {"min": "2.7.0"}}, {"core": "2.7.0"})
    check("requires satisfied at the minimum", satisfied is True and reason == "", f"{satisfied} {reason}")
    satisfied, reason = update_system.requires_state({"core": {"min": "2.7.3"}}, {"core": "2.7.0"})
    check("requires blocked below minimum", satisfied is False and "2.7.3" in reason, reason)

    # Player 1.0.5 asks for core >= 2.7.3: the row must be blocked until core moves.
    newer = {
        "status": 200,
        "components": [
            {"id": "core", "name": "PenMods", "versions": [{"version": [2, 7, 0], "model": "YDP02X",
                                                           "arch": "aarch64", "channel": "dev", "size": 1,
                                                           "unpacked_size": 1, "sha256": "a" * 64,
                                                           "download": "https://example.invalid/c.zip"}]},
            {"id": "player", "name": "player", "versions": [{"version": [1, 0, 5], "model": "YDP02X",
                                                             "arch": "aarch64", "channel": "dev", "size": 1,
                                                             "unpacked_size": 1, "sha256": "b" * 64,
                                                             "download": "https://example.invalid/p.zip",
                                                             "requires": {"core": {"min": "2.7.3"}}}]},
        ],
    }
    blocked_rows = update_system.plan(newer, current)
    check("dependent row blocked on old core", blocked_rows[1]["blocked"] is True, str(blocked_rows[1]))
    check("blocked row explains the requirement", "core" in blocked_rows[1]["blocked_reason"],
          blocked_rows[1]["blocked_reason"])
    newer_core = {"model": "YDP02X", "components": {"core": {"version": "2.7.3"}}}
    check("dependency satisfied after core upgrade", update_system.plan(newer, newer_core)[1]["blocked"] is False)


def test_migration() -> None:
    """The V2.7.3 full-migration package needs the right zip and version parsing."""
    print("[migration]")
    check("version parsed from tag", migration.version_tuple("V2.7.3") == (2, 7, 3), str(migration.version_tuple("V2.7.3")))
    check("short version accepted", migration.version_tuple("2.7") == (2, 7), str(migration.version_tuple("2.7")))
    check("broken launcher list", migration.BROKEN_LAUNCHERS == ("2.7.0", "2.7.1"), str(migration.BROKEN_LAUNCHERS))

    release = releases.Release(
        tag="V2.7.3",
        name="V2.7.3",
        html_url="https://example.invalid/V2.7.3",
        published_at="",
        assets={
            "update_v2.7.1.zip": {"url": "https://example.invalid/old.zip", "size": 1},
            "update_v2.7.3.zip": {"url": "https://example.invalid/mig.zip", "size": 5693376},
            "core_v2.7.3.zip": {"url": "https://example.invalid/core.zip", "size": 1},
        },
    )
    name, meta = migration.find_asset(release)
    check("picks the update zip", name == "update_v2.7.3.zip", name)
    check("newest migration package wins", meta["size"] == 5693376, str(meta))
    check("version read from asset name", migration.release_version(release, name) == "2.7.3",
          migration.release_version(release, name))
    check("version falls back to the tag", migration.release_version(release, "weird.zip") == "2.7.3",
          migration.release_version(release, "weird.zip"))
    empty = releases.Release(tag="V2.7.3", name="", html_url="", published_at="", assets={})
    expect_error("missing migration package refused", "NO_MIGRATION_ASSET", lambda: migration.find_asset(empty))


def test_safety() -> None:
    """The checks that stop untrusted text from reaching a shell or a path."""
    from penmanager import installer, market, safe

    print("safety helpers")
    check("shq keeps a quote literal", safe.shq("it's") == "'it'\\''s'", safe.shq("it's"))
    check("shq wraps commands as data", safe.shq("a; reboot") == "'a; reboot'", safe.shq("a; reboot"))
    check("safe_filename drops traversal", safe.safe_filename("core-../../../../x.zip") == "x.zip",
          safe.safe_filename("core-../../../../x.zip"))
    check("safe_filename strips separators", "/" not in safe.safe_filename("a/b/c.zip"))
    check("plain name accepted", safe.is_plain_name("libPenMods.so"))
    check("plain name rejects quotes", not safe.is_plain_name("a'b"))
    check("bad name raises", _raises(lambda: safe.require_plain_name("../x")))

    expect_error("http url refused", "BAD_URL", lambda: netutil.get_json("http://evil.example.com/i.json"))
    expect_error("http index refused", "BAD_URL", lambda: market.fetch_index("http://evil.example.com/i.json"))
    check("localhost http allowed", safe.is_https("http://localhost:8000/i.json", allow_localhost=True))
    check("https accepted", safe.is_https("https://example.com/i.json"))
    check("validate_remote rejects http", market.validate_remote("http://x") is False)
    check("example index is not installable",
          market.example_index()["plugins"][0]["installable"] is False)

    bad_ip = tmp_dir() / "symlink.zip"
    with zipfile.ZipFile(bad_ip, "w") as zf:
        info = zipfile.ZipInfo("evil/link")
        info.external_attr = (0o120777 << 16)
        zf.writestr(info, "/etc/passwd")
    expect_error("redirect path", "UNSAFE_PATH", lambda: plugins.inspect_zip(_zip_with(tmp_dir() / "trav.zip", {"../evil.txt": b"x"})))
    expect_error("symlink refused", "SYMLINK_REFUSED", lambda: plugins.inspect_zip(bad_ip))
    expect_error("bad plugin id refused (no device call)", "BAD_ID",
                 lambda: plugins.set_enabled("x'; reboot; #", True))

    steps = [s.command for s in installer.patch_steps()]
    check("launcher is swapped atomically", any("mv -f YoudaoDictPen.penmods-new YoudaoDictPen" in c for c in steps), str(steps))
    check("launcher is never removed first", not any("pre-penmods.bak" in c for c in steps), str(steps))

    expect_error("manifest version cannot traverse", "BAD_VERSION",
                 lambda: update_system._version_text("2.7.0/../../x"))


def _raises(fn) -> bool:
    try:
        fn()
    except Exception:  # noqa: BLE001
        return True
    return False


def _zip_with(path: Path, files: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return path


def test_plugin_listing() -> None:
    """The device prints plugin dirs between markers; metadata may span lines."""

    import penmanager.penctl as penctl_mod
    import penmanager.plugins as plugins_mod

    nl = chr(10)
    sample = (
        "===PLUGIN:bili_plugin" + nl + '{"id": "com.bilipocket.player",' + nl
        + ' "name": "bili", "version": "1.7.5"}' + nl + "===END" + nl
        + "===PLUGIN:broken" + nl + "not json" + nl + "===END" + nl
    )
    original = penctl_mod.run_text
    penctl_mod.run_text = lambda *a, **k: sample  # type: ignore[assignment]
    try:
        rows = plugins_mod.list_installed()
    finally:
        penctl_mod.run_text = original  # type: ignore[assignment]

    check("listing keeps multi-line metadata", len(rows) == 2, str(rows))
    check("listing parses name/version", rows[0].get("name") == "bili" and rows[0].get("version") == "1.7.5")
    check("listing tolerates broken metadata", rows[1].get("id") == "broken" and rows[1].get("meta_raw") == "not json")
    check("listing marks enabled", rows[0].get("enabled") is True and rows[1].get("enabled") is True)


def test_transport_args() -> None:
    from penmanager import penctl

    check("adb transport adds no ssh flags",
          penctl.transport_args({"mode": "adb"}) == [], str(penctl.transport_args({"mode": "adb"})))
    args = penctl.transport_args({
        "mode": "ssh", "host": "192.168.1.100", "user": "root", "port": 22,
        "key": "k", "known_hosts": "kh",
    })
    check("ssh transport -> --ssh user@host", args[:2] == ["--ssh", "root@192.168.1.100"], str(args))
    check("ssh transport -> --port", "--port" in args and args[args.index("--port") + 1] == "22", str(args))
    check("ssh transport -> --key", "--key" in args and args[args.index("--key") + 1] == "k", str(args))
    check("ssh transport -> --known-hosts", "--known-hosts" in args, str(args))
    check("ssh transport keeps target order", args[0] == "--ssh", str(args))


def test_adb_env() -> None:
    from penmanager import penctl

    adb = penctl.adb_path()
    check("adb_path resolves a real adb.exe in dev checkout",
          adb is not None and str(adb).lower().endswith("adb.exe"), str(adb))

    env = penctl.child_env()
    check("child_env exposes PENCTL_ADB", env is not None and "PENCTL_ADB" in env, str(env and env.get("PENCTL_ADB")))
    if env is not None and adb is not None:
        check("child_env puts adb dir on PATH",
              str(adb.parent).lower() in env.get("PATH", "").lower(), env.get("PATH", "")[:120])
        from pathlib import Path
        check("child_env PENCTL_ADB points at the resolved file",
              Path(env["PENCTL_ADB"]) == Path(adb), env["PENCTL_ADB"])
        tmp = Path(env.get("TMP", ""))
        check("child_env redirects TMP to a writable scratch dir",
              tmp.is_dir() and os.access(str(tmp), os.W_OK), str(tmp))
        check("child_env TMP/TEMP agree", env.get("TMP") == env.get("TEMP"), str(env.get("TEMP")))


def main() -> int:
    test_sha256sums()
    test_ota()
    test_releases()
    test_plugins()
    test_update_system()
    test_migration()
    test_safety()
    test_transport_args()
    test_adb_env()
    test_plugin_listing()
    print()
    if FAILED:
        print(f"{FAILED} check(s) failed")
        return 1
    print("all offline checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
