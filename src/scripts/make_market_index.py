"""Generate the protocol-v1 market index for the plugin bundles.

The index needs absolute HTTPS URLs, so it is produced **after** the bundles have
a public home (GitHub raw, a CDN, an object store...). Nothing here is uploaded.

Usage:
    python src/tools/make_market_index.py --base-url https://raw.githubusercontent.com/<owner>/<repo>/main/plugins
    python src/tools/make_market_index.py --base-url https://example.com/penmods --out plugins/index.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

REQUIRED = ("id", "name", "version", "author", "description")
DEVICES = ["YDP02X", "YDPG3", "YDP03X"]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_metadata(bundle: Path) -> dict:
    with zipfile.ZipFile(bundle) as archive:
        for name in archive.namelist():
            if name.endswith("metadata.json") and name.count("/") <= 1:
                return json.loads(archive.read(name).decode("utf-8-sig"))
    raise SystemExit(f"{bundle.name}: no metadata.json at the archive root")


def build(plugins_dir: Path, base_url: str) -> dict:
    base = base_url.rstrip("/") + "/"
    entries = []
    for bundle in sorted(plugins_dir.glob("*.zip")):
        meta = read_metadata(bundle)
        missing = [key for key in REQUIRED if not str(meta.get(key) or "").strip()]
        if missing:
            print(f"skip {bundle.name}: missing {', '.join(missing)}", file=sys.stderr)
            continue
        native = bool(meta.get("main_so"))
        entries.append(
            {
                "id": meta["id"],
                "name": meta["name"],
                "summary": meta.get("description", ""),
                "author": meta.get("author", ""),
                "repository": "",
                "icon": "",
                "versions": [
                    {
                        "version": meta["version"],
                        "url": base + bundle.name,
                        "sha256": sha256_file(bundle),
                        "devices": DEVICES,
                        "min_penmods": "2.0.0",
                        "native": native,
                        "roots": [],
                    }
                ],
            }
        )
    entries.sort(key=lambda item: item["id"])
    return {"schema_version": 1, "name": "PenMods 管理器插件索引", "plugins": entries}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugins", default="plugins", help="directory holding the .zip bundles")
    parser.add_argument("--base-url", required=True, help="public HTTPS prefix the bundles live under")
    parser.add_argument("--out", default="plugins/index.json", help="output index path")
    args = parser.parse_args(argv)

    if not args.base_url.startswith("https://"):
        raise SystemExit("--base-url must be https:// (the app rejects plain http)")

    plugins_dir = Path(args.plugins)
    doc = build(plugins_dir, args.base_url)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    sums = out.parent / "SHA256SUMS"
    sums.write_text(
        "".join(
            f"{entry['versions'][0]['sha256']}  {Path(entry['versions'][0]['url']).name}\n"
            for entry in doc["plugins"]
        ),
        encoding="utf-8",
    )
    print(f"wrote {out} ({len(doc['plugins'])} plugins) and {sums}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
