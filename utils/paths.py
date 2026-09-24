"""Filesystem locations used by MigeCast.

All user data (database, settings, encryption key, image cache and logs)
lives in a per-user folder that is *outside* of the installation folder:

* Windows: ``%LOCALAPPDATA%\\MigeCast``
* Other:   ``$XDG_DATA_HOME/MigeCast`` or ``~/.local/share/MigeCast``

This keeps user data intact when the program is upgraded, uninstalled or
reinstalled. ``MIGECAST_DATA_DIR`` overrides the location (used by tests and
by the installer smoke tests).
"""
import os
import sys
from pathlib import Path

from version import APP_ID


def is_frozen() -> bool:
    """True when running from a PyInstaller bundle."""
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    """Folder that contains the program files (read-only at runtime)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def bundle_dir() -> Path:
    """Folder that contains bundled resources (PyInstaller ``_internal``)."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return app_dir()


def user_data_root() -> Path:
    override = os.environ.get("MIGECAST_DATA_DIR")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / APP_ID
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / APP_ID


def data_dir() -> Path:
    return user_data_root() / "data"


def cache_dir() -> Path:
    return user_data_root() / "cache"


def image_cache_dir() -> Path:
    return cache_dir() / "images"


def logs_dir() -> Path:
    return user_data_root() / "logs"


def backups_dir() -> Path:
    return user_data_root() / "backups"


def database_path() -> Path:
    return data_dir() / "migecast.db"


def config_path() -> Path:
    return data_dir() / "config.json"


def ensure_user_dirs() -> None:
    for folder in (data_dir(), image_cache_dir(), logs_dir(), backups_dir()):
        folder.mkdir(parents=True, exist_ok=True)


def legacy_data_dirs() -> list:
    """Folders where version 1.x kept its ``data`` folder (relative paths).

    Version 1.x wrote ``data/migecast.db`` relative to the working directory,
    which normally was the folder of the unpacked program.
    """
    candidates = []
    for base in (app_dir(), Path.cwd()):
        folder = (base / "data").resolve()
        if folder not in candidates:
            candidates.append(folder)
    return candidates


def resource_path(*parts: str) -> Path:
    return bundle_dir().joinpath("resources", *parts)
