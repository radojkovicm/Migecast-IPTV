"""Verify the PyInstaller output before it is packed into the installer.

* every runtime component is present (Qt, Python, MSVC runtime, libVLC + plugins)
* no private data slipped in (databases, logs, keys, playlists, caches)

Usage: python tools/verify_bundle.py dist/MigeCast
"""
import sys
from pathlib import Path

REQUIRED = [
    "MigeCast.exe",
    "_internal/python311.dll",
    "_internal/vcruntime140.dll",
    "_internal/vlc/libvlc.dll",
    "_internal/vlc/libvlccore.dll",
    "_internal/vlc/plugins/plugins.dat",
    "_internal/vlc/plugins/access/libhttp_plugin.dll",
    "_internal/vlc/plugins/demux/libts_plugin.dll",
    "_internal/vlc/plugins/codec/libavcodec_plugin.dll",
    "_internal/vlc/plugins/video_output/libdirect3d11_plugin.dll",
    "_internal/vlc/plugins/audio_output/libmmdevice_plugin.dll",
    "_internal/PyQt6/Qt6/bin/Qt6Core.dll",
    "_internal/PyQt6/Qt6/bin/Qt6Gui.dll",
    "_internal/PyQt6/Qt6/bin/Qt6Widgets.dll",
    "_internal/PyQt6/Qt6/bin/MSVCP140.dll",
    "_internal/PyQt6/Qt6/plugins/platforms/qwindows.dll",
    "_internal/PyQt6/Qt6/plugins/imageformats/qjpeg.dll",
    "_internal/resources/migecast.ico",
]

FORBIDDEN_SUFFIXES = {".db", ".sqlite", ".db-wal", ".db-shm", ".log", ".m3u", ".m3u8", ".env", ".key"}
FORBIDDEN_NAMES = {"config.json", "secret.key", ".env", "migecast.db"}
FORBIDDEN_DIRS = {"cache", "logs", "backups"}


def main(folder: str) -> int:
    root = Path(folder)
    errors = []
    lower = {str(p.relative_to(root)).replace("\\", "/").lower(): p for p in root.rglob("*")}
    for rel in REQUIRED:
        if rel.lower() not in lower:
            errors.append(f"missing: {rel}")
    plugins = [p for p in lower if p.startswith("_internal/vlc/plugins/") and p.endswith(".dll")]
    if len(plugins) < 150:
        errors.append(f"only {len(plugins)} VLC plugins found")
    for rel, path in lower.items():
        name = path.name.lower()
        if path.is_file() and (path.suffix.lower() in FORBIDDEN_SUFFIXES or name in FORBIDDEN_NAMES):
            errors.append(f"private/unexpected file in bundle: {rel}")
        if path.is_dir() and name in FORBIDDEN_DIRS and "/vlc/" not in rel:
            errors.append(f"unexpected folder in bundle: {rel}")
    size = sum(p.stat().st_size for p in lower.values() if p.is_file())
    print(f"bundle: {len(lower)} entries, {size / 1024 / 1024:.1f} MB, {len(plugins)} VLC plugins")
    for error in errors:
        print("ERROR:", error)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "dist/MigeCast"))
