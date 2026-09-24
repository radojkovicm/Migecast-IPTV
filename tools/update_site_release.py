"""Write site/release.json for the download page from a built installer.

Usage:
  python tools/update_site_release.py --version 2.0.0 \
      --installer installer/Output/MigeCast-Setup-2.0.0.exe \
      --url https://github.com/<owner>/<repo>/releases/download/v2.0.0/MigeCast-Setup-2.0.0.exe
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--installer", required=True)
    parser.add_argument("--url", required=True, help="final public download URL (GitHub Releases)")
    parser.add_argument("--out", default=str(ROOT / "site" / "release.json"))
    args = parser.parse_args()
    installer = Path(args.installer)
    digest = hashlib.sha256()
    with open(installer, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    data = {
        "version": args.version,
        "file": installer.name,
        "size_bytes": installer.stat().st_size,
        "sha256": digest.hexdigest(),
        "date": datetime.now(timezone.utc).strftime("%d.%m.%Y"),
        "url": args.url,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
