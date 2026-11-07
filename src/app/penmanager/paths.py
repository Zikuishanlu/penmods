"""Filesystem locations for the app (dev checkout vs frozen bundle)."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return repo_root()


def penctl_path() -> Path | None:
    env = os.environ.get("PENCTL_EXE")
    if env and Path(env).is_file():
        return Path(env)
    candidates = []
    if is_frozen():
        candidates.append(app_dir() / "penctl.exe")
    candidates.append(app_dir() / "build" / "penctl.exe")
    for cand in candidates:
        if cand.is_file():
            return cand
    found = shutil.which("penctl")
    return Path(found) if found else None


def data_dir() -> Path:
    """Writable per-user (or per-checkout) area for caches and temp files."""
    if is_frozen():
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        # %TEMP% is deliberately not a candidate: it can be shared between
        # users, and this directory holds the (passphrase-less) SSH key.
        candidates = [
            Path(base) / "PenModsManager",
            app_dir() / "data",
        ]
        for cand in candidates:
            try:
                cand.mkdir(parents=True, exist_ok=True)
                probe = cand / ".write-test"
                probe.write_text("ok", encoding="utf-8")
                probe.unlink()
                return cand
            except OSError:
                continue
        return candidates[-1]
    return repo_root() / ".toolchain"


def tmp_dir() -> Path:
    d = data_dir() / "tmp"
    d.mkdir(parents=True, exist_ok=True)
    return d


def qml_dir() -> Path:
    return Path(__file__).resolve().parent / "qml"
