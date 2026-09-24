"""Import user data from MigeCast 1.x.

Version 1.x kept ``data/migecast.db``, ``data/.env`` (encryption key) and
``data/config.json`` next to the program. On first start of 2.x the files are
*copied* (never moved or deleted) into ``%LOCALAPPDATA%\\MigeCast\\data``.
"""
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from utils import paths

logger = logging.getLogger(__name__)

_FILES = ("migecast.db", ".env", "config.json")


def _copy_from(folder: Path, target: Path) -> bool:
    if not (folder / "migecast.db").is_file():
        return False
    target.mkdir(parents=True, exist_ok=True)
    for name in _FILES:
        source = folder / name
        if source.is_file() and not (target / name).exists():
            shutil.copy2(source, target / name)
    return True


def import_legacy_install() -> Optional[Path]:
    """Copy data of an old portable install if the new data folder is empty."""
    target = paths.data_dir()
    if (target / "migecast.db").exists():
        return None
    for folder in paths.legacy_data_dirs():
        try:
            if folder == target.resolve():
                continue
            if _copy_from(folder, target):
                logger.info("Imported data from version 1.x folder")
                return folder
        except OSError as exc:
            logger.warning("Legacy import failed: %s", exc)
    return None


def import_database_file(db_file: Path) -> None:
    """Replace the current database with ``db_file`` (manual import).

    The current database and key are backed up first. The caller must make
    sure no :class:`core.database.Database` instance is open.
    """
    db_file = Path(db_file)
    if not db_file.is_file():
        raise FileNotFoundError(db_file)
    target = paths.data_dir()
    target.mkdir(parents=True, exist_ok=True)
    backups = paths.backups_dir()
    backups.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    for name in ("migecast.db", "secret.key"):
        current = target / name
        if current.exists():
            shutil.copy2(current, backups / f"before-import-{stamp}-{name}")
    for suffix in ("-wal", "-shm"):
        leftover = target / f"migecast.db{suffix}"
        if leftover.exists():
            leftover.unlink()
    shutil.copy2(db_file, target / "migecast.db")
    old_env = db_file.parent / ".env"
    if old_env.is_file():
        shutil.copy2(old_env, target / ".env")
        key = target / "secret.key"
        if key.exists():
            key.unlink()  # backed up above; SecurityManager re-imports from .env
    logger.info("Database imported from file")
