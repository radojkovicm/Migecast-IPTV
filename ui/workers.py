"""Background workers. Nothing here may touch widgets; results go back to
the GUI thread through queued signals."""
import logging
import threading
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

from core.net import CancelToken, Cancelled, NetworkError

logger = logging.getLogger(__name__)


class QThread(QObject):
    """Minimal QThread look-alike backed by a *daemon* Python thread.

    A blocking network call (e.g. a TCP connect to a dead server) cannot be
    interrupted. With a daemon thread the user can cancel instantly, the GUI
    ignores the late result, and closing the program never waits for or
    crashes on a still-running network request.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = None
        self.abandoned = False

    def start(self):
        self._thread = threading.Thread(target=self._run_safe, name=type(self).__name__, daemon=True)
        self._thread.start()

    def _run_safe(self):
        try:
            self.run()
        except Exception:
            logger.exception("Worker crashed")

    def run(self):
        raise NotImplementedError

    def isRunning(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def wait(self, msecs: int = 0) -> bool:
        if self._thread is None:
            return True
        self._thread.join(msecs / 1000 if msecs else None)
        return not self._thread.is_alive()


class StartupWorker(QThread):
    """Opens (and migrates) the database and loads the cached playlist."""

    progress = pyqtSignal(str)
    finished_ok = pyqtSignal(object, object)  # playlist dict or None, ParsedPlaylist or None
    failed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        from utils import startup_profiler
        try:
            from core import legacy_import
            legacy_import.import_legacy_install()
            from core.database import Database
            db = Database()
            startup_profiler.mark("database_ready")
            playlist = db.get_last_playlist()
            parsed = None
            if playlist:
                self.progress.emit("Učitavam listu…")
                from core.m3u import ParsedPlaylist
                channels, vod, series = db.load_cached_playlist(playlist["id"])
                parsed = ParsedPlaylist(channels, vod, series)
                startup_profiler.mark("playlist_cache_loaded")
            db.close_thread_session()
            self.finished_ok.emit(playlist, parsed)
        except Exception as exc:
            logger.exception("Startup failed")
            self.failed.emit(f"Greška pri otvaranju baze podataka: {exc}")


class PlaylistLoadWorker(QThread):
    """Downloads/parses a playlist, then stores it in the database.

    The cached content is replaced only after the new list was loaded
    successfully, so a failed or cancelled refresh keeps the old list."""

    progress = pyqtSignal(str)
    finished_ok = pyqtSignal(object, object)  # playlist dict, ParsedPlaylist
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, source: dict, name: str, playlist_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.source = source
        self.name = name
        self.playlist_id = playlist_id
        self.token = CancelToken()

    def cancel(self):
        self.token.cancel()

    def run(self):
        from core.database import Database
        from core.playlist_service import PlaylistError, load_playlist
        db = None
        try:
            parsed = load_playlist(self.source, cancel=self.token, progress=self.progress.emit)
            self.token.check()
            self.progress.emit("Čuvam listu…")
            db = Database()
            if self.source.get("type") == "Xtream":
                playlist_id = db.save_playlist(self.name, "Xtream", server=self.source["server"],
                                               username=self.source["username"], password=self.source["password"])
            else:
                playlist_id = db.save_playlist(self.name, "M3U", url=self.source["url"])
            if not playlist_id or not db.replace_cached_playlist(
                    playlist_id, parsed.channels, parsed.vod_items, parsed.series_items):
                raise PlaylistError("Lista je učitana, ali nije mogla da se sačuva.")
            self.finished_ok.emit(db.get_playlist(playlist_id), parsed)
        except Cancelled:
            self.cancelled.emit()
        except (PlaylistError, NetworkError) as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            logger.exception("Playlist loading failed")
            self.failed.emit(f"Neočekivana greška: {exc}")
        finally:
            if db is not None:
                db.close_thread_session()


class EpisodesWorker(QThread):
    """Loads the episodes of an Xtream series on demand."""

    finished_ok = pyqtSignal(str, list)
    failed = pyqtSignal(str, str)

    def __init__(self, series_key: str, stub, playlist: dict, parent=None):
        super().__init__(parent)
        self.series_key = series_key
        self.stub = stub
        self.playlist = playlist or {}
        self.token = CancelToken()

    def cancel(self):
        self.token.cancel()

    def run(self):
        from core import xtream
        try:
            episodes = xtream.fetch_series_episodes(self.playlist.get("server", ""), self.playlist.get("username", ""),
                                                    self.playlist.get("password", ""), self.stub, cancel=self.token)
            self.finished_ok.emit(self.series_key, episodes)
        except Cancelled:
            pass
        except NetworkError as exc:
            self.failed.emit(self.series_key, str(exc))
        except Exception as exc:
            logger.exception("Loading episodes failed")
            self.failed.emit(self.series_key, f"Greška: {exc}")
