"""libVLC based video player.

libVLC is loaded in a background warm-up after the window appears. Importing
``vlc`` and scanning plugins can be slow on the first Windows run, but it must
never block the GUI or wait for the user's first ``play()`` click.
In the installed program libVLC and its plugins are bundled in
``_internal\\vlc``; users never need a separate VLC installation.
"""
import logging
import os
import sys
import threading
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from utils import paths

logger = logging.getLogger(__name__)

_vlc_module = None
_dll_directory_handle = None


def _configure_bundled_vlc():
    """Point python-vlc to the bundled libVLC (frozen build) if present."""
    global _dll_directory_handle
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
                    # Keep the handle alive for the process lifetime.  Closing or
                    # garbage-collecting it can make libVLC's dependent DLLs vanish
                    # from the Windows loader search path after the first import.
                    if _dll_directory_handle is None:
                        _dll_directory_handle = os.add_dll_directory(str(folder))
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
    initialization_finished = pyqtSignal(bool)
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
        self._initializing = False
        self._init_lock = threading.Lock()
        self._vlc_event.connect(self._on_vlc_event)
        self.reconnect_timer = QTimer(self)
        self.reconnect_timer.setSingleShot(True)
        self.reconnect_timer.timeout.connect(self.attempt_reconnect)

    # -- lazy init ------------------------------------------------------------

    @property
    def available(self) -> bool:
        return self._media_player is not None

    @property
    def is_initialized(self) -> bool:
        """Return readiness without ever doing slow work on the GUI thread."""
        return self._media_player is not None

    @property
    def media_player(self):
        """Return the player without triggering a blocking VLC initialisation."""
        return self._media_player

    def initialize_async(self) -> bool:
        """Start libVLC in a daemon worker so the Qt event loop stays responsive.

        Returns ``True`` when VLC was already ready.  Completion of a new or
        existing attempt is reported through ``initialization_finished``.
        """
        if self.is_initialized:
            return True
        if self._is_destroyed or self._initializing:
            return False
        self._initializing = True
        threading.Thread(
            target=self._initialize_worker,
            name="VLC-initializer",
            daemon=True,
        ).start()
        return False

    def _initialize_worker(self):
        ok = False
        try:
            ok = self.ensure_initialized()
        finally:
            self._initializing = False
            self.initialization_finished.emit(ok)

    def ensure_initialized(self) -> bool:
        with self._init_lock:
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
                instance = vlc.Instance(" ".join(args))
                if instance is None:
                    raise RuntimeError("vlc.Instance returned None")
                media_player = instance.media_player_new()
                if self._is_destroyed:
                    media_player.release()
                    instance.release()
                    return False
                media_player.audio_set_volume(self._volume)
                event_manager = media_player.event_manager()
                events = vlc.EventType
                event_manager.event_attach(events.MediaPlayerEncounteredError, lambda e: self._vlc_event.emit("error"))
                event_manager.event_attach(events.MediaPlayerPlaying, lambda e: self._vlc_event.emit("playing"))
                event_manager.event_attach(events.MediaPlayerPaused, lambda e: self._vlc_event.emit("paused"))
                event_manager.event_attach(events.MediaPlayerStopped, lambda e: self._vlc_event.emit("stopped"))
                event_manager.event_attach(events.MediaPlayerEndReached, lambda e: self._vlc_event.emit("ended"))
                self.instance = instance
                self._media_player = media_player
                self.event_manager = event_manager
                startup_profiler.mark("vlc_initialized")
                logger.info("VLC initialised in background")
                return True
            except Exception as exc:
                logger.error("Failed to initialise VLC: %s", exc)
                self.instance = None
                self._media_player = None
                return False

    # -- playback ---------------------------------------------------------------

    def play(self, url: str, _reconnect: bool = False) -> bool:
        # The UI starts initialisation asynchronously.  Never fall back to a
        # blocking first-time initialisation here because play() runs on Qt's
        # GUI thread.
        if not self.is_initialized:
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
