"""libVLC based video player.

libVLC is loaded lazily on the first ``play()`` call: importing ``vlc`` and
scanning the VLC plugins costs 0.5–3 s, which used to delay startup.
In the installed program libVLC and its plugins are bundled in
``_internal\\vlc``; users never need a separate VLC installation.
"""
import logging
import os
import sys
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from utils import paths

logger = logging.getLogger(__name__)

_vlc_module = None


def _configure_bundled_vlc():
    """Point python-vlc to the bundled libVLC (frozen build) if present."""
    candidates = [paths.bundle_dir() / "vlc", paths.app_dir() / "vlc"]
    for folder in candidates:
        lib = folder / ("libvlc.dll" if sys.platform == "win32" else "libvlc.so")
        if lib.exists():
            os.environ["PYTHON_VLC_LIB_PATH"] = str(lib)
            plugins = folder / "plugins"
            if plugins.is_dir():
                os.environ["PYTHON_VLC_MODULE_PATH"] = str(plugins)
                os.environ["VLC_PLUGIN_PATH"] = str(plugins)
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(str(folder))
                except OSError:
                    pass
            return folder
    return None


def load_vlc():
    """Import python-vlc once; returns the module or ``None`` if unavailable."""
    global _vlc_module
    if _vlc_module is not None:
        return _vlc_module
    _configure_bundled_vlc()
    try:
        import vlc  # noqa: WPS433 - deliberate lazy import
        _vlc_module = vlc
    except Exception as exc:  # OSError / FileNotFoundError when libvlc is missing
        logger.error("libVLC could not be loaded: %s", exc)
        _vlc_module = False
    return _vlc_module or None


class VideoPlayer(QObject):
    """VLC player with lazy initialisation and bounded auto-reconnect."""

    state_changed = pyqtSignal(str)  # playing, paused, stopped, ended, error, buffering, reconnecting
    error_occurred = pyqtSignal()
    _vlc_event = pyqtSignal(str)  # marshals VLC callbacks (VLC thread) to the GUI thread

    def __init__(self, reconnect_attempts: int = 3):
        super().__init__()
        self._is_destroyed = False
        self.instance = None
        self._media_player = None
        self.event_manager = None
        self.max_reconnect_attempts = reconnect_attempts
        self.reconnect_attempt = 0
        self.current_url = None
        self._volume = 70
        self._vlc_event.connect(self._on_vlc_event)
        self.reconnect_timer = QTimer(self)
        self.reconnect_timer.setSingleShot(True)
        self.reconnect_timer.timeout.connect(self.attempt_reconnect)

    # -- lazy init ------------------------------------------------------------

    @property
    def available(self) -> bool:
        return self.ensure_initialized()

    @property
    def media_player(self):
        """The libVLC media player (created on first access)."""
        if self._media_player is None and not self._is_destroyed:
            self.ensure_initialized()
        return self._media_player

    def ensure_initialized(self) -> bool:
        if self._media_player is not None:
            return True
        if self._is_destroyed:
            return False
        vlc = load_vlc()
        if not vlc:
            return False
        try:
            from utils import startup_profiler
            args = ["--network-caching=1500", "--live-caching=1500", "--no-video-title-show",
                    "--no-stats", "--no-osd", "--quiet", "--no-snapshot-preview", "--no-lua",
                    "--http-reconnect"]
            self.instance = vlc.Instance(" ".join(args))
            if self.instance is None:
                raise RuntimeError("vlc.Instance returned None")
            self._media_player = self.instance.media_player_new()
            self._media_player.audio_set_volume(self._volume)
            self.event_manager = self._media_player.event_manager()
            events = vlc.EventType
            self.event_manager.event_attach(events.MediaPlayerEncounteredError, lambda e: self._vlc_event.emit("error"))
            self.event_manager.event_attach(events.MediaPlayerPlaying, lambda e: self._vlc_event.emit("playing"))
            self.event_manager.event_attach(events.MediaPlayerPaused, lambda e: self._vlc_event.emit("paused"))
            self.event_manager.event_attach(events.MediaPlayerStopped, lambda e: self._vlc_event.emit("stopped"))
            self.event_manager.event_attach(events.MediaPlayerEndReached, lambda e: self._vlc_event.emit("ended"))
            startup_profiler.mark("vlc_initialized")
            return True
        except Exception as exc:
            logger.error("Failed to initialise VLC: %s", exc)
            self.instance = None
            self._media_player = None
            return False

    # -- playback ---------------------------------------------------------------

    def play(self, url: str, _reconnect: bool = False) -> bool:
        if not self.ensure_initialized():
            self.state_changed.emit("error")
            return False
        self.current_url = url
        if not _reconnect:
            self.reconnect_attempt = 0
        try:
            media = self.instance.media_new(url)
            media.add_option(":http-user-agent=VLC/3.0.21 LibVLC/3.0.21")
            self._media_player.set_media(media)
            media.release()
            self._media_player.play()
            logger.info("Playback started")  # URL intentionally not logged
            return True
        except Exception as exc:
            logger.error("Failed to start playback: %s", exc)
            self.state_changed.emit("error")
            return False

    def pause(self):
        if self._media_player and self._media_player.is_playing():
            self._media_player.pause()

    def resume(self):
        if self._media_player and not self._media_player.is_playing():
            self._media_player.play()

    def stop(self):
        self.current_url = None
        self.reconnect_timer.stop()
        if self._media_player:
            try:
                self._media_player.stop()
            except Exception as exc:
                logger.error("Error while stopping: %s", exc)

    def set_volume(self, volume: int):
        self._volume = int(volume)
        if self._media_player:
            self._media_player.audio_set_volume(self._volume)

    # -- events -------------------------------------------------------------------

    def _on_vlc_event(self, state: str):
        if self._is_destroyed:
            return
        if state == "playing":
            self.reconnect_attempt = 0
        elif state == "error":
            if self.current_url and self.reconnect_attempt < self.max_reconnect_attempts:
                self.state_changed.emit("reconnecting")
                self.reconnect_timer.start(2000 * (self.reconnect_attempt + 1))
                self.error_occurred.emit()
                return
            logger.warning("Playback failed after %d reconnect attempts", self.reconnect_attempt)
        self.state_changed.emit(state)

    def attempt_reconnect(self):
        if not self.current_url:
            return
        self.reconnect_attempt += 1
        logger.info("Reconnecting %d/%d", self.reconnect_attempt, self.max_reconnect_attempts)
        self.play(self.current_url, _reconnect=True)

    def cleanup(self):
        if self._is_destroyed:
            return
        self._is_destroyed = True
        self.reconnect_timer.stop()
        try:
            if self._media_player:
                self._media_player.stop()
                self._media_player.release()
            if self.instance:
                self.instance.release()
        except Exception as exc:
            logger.error("Error during VLC cleanup: %s", exc)
        self._media_player = None
        self.instance = None
