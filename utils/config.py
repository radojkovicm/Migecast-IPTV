"""User settings stored as JSON in the per-user data folder."""
import copy
import json
import logging
import os
import threading
from pathlib import Path
from typing import Optional

from utils import paths

logger = logging.getLogger(__name__)

DEFAULTS = {
    "appearance": {"theme": "dark"},
    "player": {"reconnect_attempts": 3, "hw_acceleration": True, "volume": 70},
    "playlists": {"auto_refresh": True, "refresh_interval_days": 7},
    "images": {"max_cache_mb": 300},
    "tmdb": {"api_key": ""},
}

_lock = threading.Lock()


class Config:
    """Configuration manager. Values are merged over :data:`DEFAULTS`."""

    def __init__(self, config_file: Optional[str] = None):
        self.config_file = Path(config_file) if config_file else paths.config_path()
        self.settings = {}
        self.load()

    def load(self):
        self.settings = copy.deepcopy(DEFAULTS)
        if not self.config_file.exists():
            return
        try:
            with open(self.config_file, "r", encoding="utf-8") as handle:
                stored = json.load(handle)
            if isinstance(stored, dict):
                for section, values in stored.items():
                    if isinstance(values, dict):
                        self.settings.setdefault(section, {}).update(values)
                    else:
                        self.settings[section] = values
        except (OSError, ValueError) as exc:
            logger.error("Failed to load configuration, using defaults: %s", exc)

    def save(self):
        with _lock:
            try:
                self.config_file.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.config_file.with_suffix(".tmp")
                with open(tmp, "w", encoding="utf-8") as handle:
                    json.dump(self.settings, handle, indent=2, ensure_ascii=False)
                os.replace(tmp, self.config_file)
            except OSError as exc:
                logger.error("Failed to save configuration: %s", exc)

    def get(self, section: str, key: str = None, default=None):
        if key is None:
            return self.settings.get(section, default)
        value = self.settings.get(section, {})
        if isinstance(value, dict) and key in value:
            return value[key]
        return default

    def set(self, section: str, key: str, value):
        self.settings.setdefault(section, {})[key] = value
