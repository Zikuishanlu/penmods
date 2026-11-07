"""Dev launcher: run the GUI straight from the checkout (no install needed)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
# PySide6 is installed --target into the checkout (see .toolchain/fetch_pyside.py).
SITE = ROOT / ".toolchain" / "site"
if SITE.is_dir():
    sys.path.insert(0, str(SITE))

from penmanager.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
