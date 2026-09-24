"""Encryption of sensitive values (Xtream passwords).

The Fernet key is stored in ``<data>/secret.key``. On Windows the key file
is additionally protected with DPAPI (``CryptProtectData``), so copying the
database and key file to another Windows account or computer does not reveal
the passwords. Version 1.x kept the key in ``data/.env``; that key is imported
automatically so old encrypted passwords keep working.
"""
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from utils import paths

logger = logging.getLogger(__name__)

_DPAPI_MAGIC = b"MCDPAPI1"


# ---------------------------------------------------------------------------
# DPAPI helpers (Windows only, no extra dependencies)
# ---------------------------------------------------------------------------

def _dpapi(data: bytes, protect: bool) -> Optional[bytes]:
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        buffer = ctypes.create_string_buffer(data, len(data))
        blob_in = DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
        blob_out = DATA_BLOB()
        crypt32 = ctypes.windll.crypt32
        func = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
        ok = func(ctypes.byref(blob_in), None, None, None, None, 0x1, ctypes.byref(blob_out))
        if not ok:
            return None
        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)
    except Exception as exc:  # pragma: no cover - platform specific
        logger.warning("DPAPI unavailable: %s", exc)
        return None


def _read_key_file(path: Path) -> Optional[bytes]:
    raw = path.read_bytes().strip()
    if raw.startswith(_DPAPI_MAGIC):
        return _dpapi(raw[len(_DPAPI_MAGIC):], protect=False)
    return raw or None


def _write_key_file(path: Path, key: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    protected = _dpapi(key, protect=True)
    payload = _DPAPI_MAGIC + protected if protected else key
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(payload)
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)


def read_legacy_env_key(env_file: Path) -> Optional[bytes]:
    """Read ENCRYPTION_KEY from a version 1.x ``.env`` file."""
    try:
        for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line.startswith("ENCRYPTION_KEY"):
                value = line.split("=", 1)[1].strip().strip("'\"")
                return value.encode("utf-8") if value else None
    except OSError:
        return None
    return None


class SecurityManager:
    """Encrypts and decrypts short secrets with a per-user Fernet key."""

    def __init__(self, key_path: Optional[Path] = None):
        self.key_path = Path(key_path) if key_path else paths.data_dir() / "secret.key"
        self.cipher = Fernet(self._load_or_create_key())

    def _load_or_create_key(self) -> bytes:
        if self.key_path.exists():
            key = _read_key_file(self.key_path)
            if key:
                try:
                    Fernet(key)
                    return key
                except ValueError:
                    logger.error("Stored encryption key is invalid; a new key will be created")
            else:
                logger.error("Stored encryption key could not be read; a new key will be created")
            backup = self.key_path.with_suffix(".unreadable")
            try:
                os.replace(self.key_path, backup)
            except OSError:
                pass

        # Import the key of version 1.x if present next to the database.
        legacy_env = self.key_path.parent / ".env"
        key = read_legacy_env_key(legacy_env) if legacy_env.exists() else None
        if key:
            try:
                Fernet(key)
                logger.info("Imported encryption key from version 1.x")
            except ValueError:
                key = None
        if not key:
            key = Fernet.generate_key()
            logger.info("Generated new encryption key")
        _write_key_file(self.key_path, key)
        return key

    def import_key(self, key: bytes) -> "Fernet":
        """Return a cipher for a foreign key (used when importing old databases)."""
        return Fernet(key)

    def encrypt_password(self, password: str) -> str:
        if not password:
            return ""
        return self.cipher.encrypt(password.encode("utf-8")).decode("utf-8")

    def decrypt_password(self, encrypted_password: str) -> str:
        if not encrypted_password:
            return ""
        try:
            return self.cipher.decrypt(encrypted_password.encode("utf-8")).decode("utf-8")
        except (InvalidToken, ValueError):
            logger.error("Password decryption failed (wrong key)")
            return ""

    def is_encrypted(self, value: str) -> bool:
        if not value:
            return False
        try:
            self.cipher.decrypt(value.encode("utf-8"))
            return True
        except (InvalidToken, ValueError):
            return False

    @staticmethod
    def get_tmdb_api_key() -> str:
        """TMDB is optional. The key comes from the environment or settings;
        no key is shipped with the program."""
        key = os.environ.get("MIGECAST_TMDB_API_KEY") or os.environ.get("TMDB_API_KEY")
        if key:
            return key
        try:
            from utils.config import Config
            return Config().get("tmdb", "api_key", "") or ""
        except Exception:
            return ""
