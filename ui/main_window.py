"""Main window: header, home tiles and all pages inside one window.

Startup is asynchronous: the window is shown immediately, the database and
the cached playlist are loaded by :class:`ui.workers.StartupWorker` while a
large "Učitavam listu…" message is visible. Nothing heavy runs on the GUI
thread and VLC is preloaded in a worker as soon as the window appears.
"""
import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QMainWindow, QStackedWidget,
                             QVBoxLayout, QWidget)

from core.m3u import episode_code

from core.video_player import VideoPlayer
from ui.widgets import LoadingOverlay, Toast, ask, button, info, label, later
from utils import startup_profiler, themes
from utils.config import Config
from utils.image_cache import ImageLoader

logger = logging.getLogger(__name__)

HOME, TV, VOD, SERIES, VOD_DETAIL, SERIES_DETAIL, SETTINGS = range(7)
CRUMBS = {
    HOME: "Početna", TV: "Početna › 📺 TV", VOD: "Početna › 🎬 Filmovi", SERIES: "Početna › 📺 Serije",
    VOD_DETAIL: "Početna › 🎬 Filmovi › Detalji", SERIES_DETAIL: "Početna › 📺 Serije › Serija",
    SETTINGS: "Početna › ⚙ Podešavanja",
}


class MainWindow(QMainWindow):
    def __init__(self, video_player: Optional[VideoPlayer] = None, database=None, smoke_test: bool = False):
        super().__init__()
        self.config = Config()
        self.video_player = video_player or VideoPlayer(int(self.config.get("player", "reconnect_attempts", 3)))
        self.smoke_test = smoke_test
        self.playlist: Optional[dict] = None
        self.parsed = None
        self.history: List[int] = []
        self.loader_worker = None
        self.startup_worker = None
        self.episode_workers = {}
        self.episode_cache = {}
        self.series_queue = []
        self.series_index = -1
        self.current_vod = None
        self.current_series_key = ""
        self._loaded_once = False
        self._pages_built = False
        self._playback_wait_overlay = False

        self.setWindowTitle("MigeCast IPTV")
        self.setMinimumSize(1280, 720)
        self._build()
        self.video_player.initialization_finished.connect(self._on_player_initialized)
        self.playback_wait_timer = QTimer(self)
        self.playback_wait_timer.setSingleShot(True)
        self.playback_wait_timer.setInterval(30000)
        self.playback_wait_timer.timeout.connect(self._on_playback_wait_timeout)
        self._shortcuts()
        startup_profiler.mark("main_window_built")

    # ------------------------------------------------------------------ UI

    def _build(self):
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("Header")
        header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 12, 20, 12)
        header_layout.setSpacing(14)
        title = QLabel("📺 MigeCast IPTV")
        title.setObjectName("AppTitle")
        header_layout.addWidget(title)
        header_layout.addStretch()
        self.breadcrumb = QLabel(CRUMBS[HOME])
        self.breadcrumb.setObjectName("Breadcrumb")
        header_layout.addWidget(self.breadcrumb)
        header_layout.addStretch()
        self.back_btn = button("⬅  Nazad", "nav", self.go_back, 170)
        self.back_btn.hide()
        self.settings_btn = button("⚙  Podešavanja", "nav", lambda: self.go(SETTINGS), 230)
        self.exit_btn = button("✖  Izlaz", "exit", self.close, 150)
        header_layout.addWidget(self.back_btn)
        header_layout.addWidget(self.settings_btn)
        header_layout.addWidget(self.exit_btn)
        layout.addWidget(header)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        # Home: the three big tiles stay exactly where they were.
        home = QWidget()
        home.setObjectName("Page")
        home_layout = QVBoxLayout(home)
        home_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        home_layout.addStretch()
        tiles = QHBoxLayout()
        tiles.setSpacing(40)
        tiles.addStretch()
        self.tv_btn = button("📺\nTV", "tile", lambda: self.open_section(TV))
        self.vod_btn = button("🎬\nFilmovi", "tile", lambda: self.open_section(VOD))
        self.series_btn = button("📺\nSerije", "tile", lambda: self.open_section(SERIES))
        for tile in (self.tv_btn, self.vod_btn, self.series_btn):
            tiles.addWidget(tile)
        tiles.addStretch()
        home_layout.addLayout(tiles)
        self.home_status = label("", "h2", wrap=True)
        self.home_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        home_layout.addSpacing(30)
        home_layout.addWidget(self.home_status)
        home_layout.addStretch()
        self.stack.addWidget(home)

        self.overlay = LoadingOverlay(root)
        self.overlay.cancel_requested.connect(self.cancel_loading)
        self.toast = Toast(root)

    def _ensure_pages(self):
        """Build the TV, catalog, detail and settings pages.

        Deferred until after the window is visible: creating them (and
        polishing their style sheets) is the most expensive part of the first
        start on Windows, when antivirus software scans every Qt DLL.
        """
        if self._pages_built:
            return
        self._pages_built = True
        # TV page: channel list + embedded player
        from ui.live_tv_widget import LiveTVWidget
        from ui.player_widget import PlayerWidget
        tv = QWidget()
        tv.setObjectName("Page")
        tv_layout = QHBoxLayout(tv)
        tv_layout.setContentsMargins(0, 0, 0, 0)
        tv_layout.setSpacing(0)
        self.live_tv_widget = LiveTVWidget()
        self.live_tv_widget.setMaximumWidth(560)
        self.live_tv_widget.setMinimumWidth(420)
        self.live_tv_widget.channel_selected.connect(self.play_channel)
        tv_layout.addWidget(self.live_tv_widget)
        self.player_widget = PlayerWidget(self.video_player, self)
        self.player_widget.setMinimumWidth(640)
        self.player_widget.previous_requested.connect(self.live_tv_widget.select_previous_channel)
        self.player_widget.next_requested.connect(self.live_tv_widget.select_next_channel)
        self.player_widget.playback_exited.connect(self.on_playback_exited)
        self.player_widget.playback_finished.connect(self.on_playback_finished)
        self.player_widget.auto_play_next_episode.connect(self.play_next_episode)
        self.player_widget.video_frame.double_clicked.connect(self.player_widget.toggle_fullscreen)
        tv_layout.addWidget(self.player_widget, 1)
        self.stack.addWidget(tv)

        from ui.catalog_page import SeriesPage, VODPage
        from ui.series_detail_page import SeriesDetailPage
        from ui.settings_page import SettingsPage
        from ui.vod_detail_page import VODDetailPage
        self.vod_page = VODPage()
        self.vod_page.item_selected.connect(self.open_vod)
        self.series_page = SeriesPage()
        self.series_page.item_selected.connect(self.open_series)
        self.vod_detail = VODDetailPage()
        self.vod_detail.back_requested.connect(self.go_back)
        self.vod_detail.play_requested.connect(self.play_vod)
        self.vod_detail.changed.connect(self.vod_page.refresh_flags)
        self.series_detail = SeriesDetailPage()
        self.series_detail.back_requested.connect(self.go_back)
        self.series_detail.play_requested.connect(self.play_episode)
        self.series_detail.retry_requested.connect(lambda: self._load_xtream_episodes(self.current_series_key, force=True))
        self.series_detail.changed.connect(self.series_page.refresh_flags)
        self.settings_page = SettingsPage()
        self.settings_page.load_requested.connect(self.load_playlist)
        self.settings_page.refresh_requested.connect(lambda: self.refresh_playlist(silent=False))
        self.settings_page.theme_changed.connect(self.apply_theme)
        self.settings_page.import_requested.connect(self.import_old_database)
        self.settings_page.player_settings_changed.connect(self._apply_player_settings)
        for page in (self.vod_page, self.series_page, self.vod_detail, self.series_detail, self.settings_page):
            self.stack.addWidget(page)

        startup_profiler.mark("pages_built")
    def _shortcuts(self):
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.go_back)
        QShortcut(QKeySequence(Qt.Key.Key_Backspace), self, self._backspace)
        QShortcut(QKeySequence(Qt.Key.Key_F11), self, self._toggle_fullscreen)
        QShortcut(QKeySequence(Qt.Key.Key_PageDown), self, self._next_channel)
        QShortcut(QKeySequence(Qt.Key.Key_PageUp), self, self._previous_channel)

    def _toggle_fullscreen(self):
        if self._pages_built:
            self.player_widget.toggle_fullscreen()

    def _backspace(self):
        focus = QApplication.focusWidget()
        if focus is not None and focus.inherits("QLineEdit"):
            return
        self.go_back()

    def _next_channel(self):
        if self.stack.currentIndex() == TV:
            self.live_tv_widget.select_next_channel()

    def _previous_channel(self):
        if self.stack.currentIndex() == TV:
            self.live_tv_widget.select_previous_channel()

    # ------------------------------------------------------------------ theme

    def apply_theme(self, name: Optional[str] = None):
        name = name or self.config.get("appearance", "theme", "dark")
        themes.set_current(name)
        QApplication.instance().setStyleSheet(themes.generate_stylesheet(name))
        if self._pages_built:
            for view in (self.vod_page.grid, self.series_page.grid, self.series_detail.view, self.live_tv_widget.view):
                view.viewport().update()

    def _apply_player_settings(self):
        self.video_player.max_reconnect_attempts = int(Config().get("player", "reconnect_attempts", 3))

    # ------------------------------------------------------------------ navigation

    def go(self, page: int, push: bool = True):
        self._ensure_pages()
        current = self.stack.currentIndex()
        if current == page:
            return
        if current == TV and page != TV and self.player_widget.content_type == "tv":
            QTimer.singleShot(0, self.player_widget.stop)
            self.live_tv_widget.set_playing(None)
        if push:
            self.history.append(current)
        if page == HOME:
            self.history.clear()
        self.stack.setCurrentIndex(page)
        self.breadcrumb.setText(CRUMBS.get(page, ""))
        self.back_btn.setVisible(page != HOME)
        self.settings_btn.setEnabled(page != SETTINGS)
        if page == SETTINGS:
            self._update_settings_info()

    def go_back(self):
        if not self._pages_built or self.overlay.isVisible() or self.player_widget.is_fullscreen:
            return
        if self.stack.currentIndex() == HOME:
            return
        target = self.history.pop() if self.history else HOME
        self.go(target, push=False)
        if target in (VOD, SERIES):
            (self.vod_page if target == VOD else self.series_page).refresh_flags()

    def open_section(self, page: int):
        self._ensure_pages()
        if not self.parsed:
            if self.overlay.isVisible():
                return
            self.settings_page.show_welcome(True)
            self.go(SETTINGS)
            return
        counts = {TV: len(self.parsed.channels), VOD: len(self.parsed.vod_items), SERIES: len(self.parsed.series_items)}
        if counts[page] == 0:
            info(self, "Nema sadržaja", "Vaša lista ne sadrži ovaj tip sadržaja.")
            return
        self.go(page)

    # ------------------------------------------------------------------ startup

    def start(self):
        """Called right after the window is shown (the style sheet is already
        applied in main.py, so it is not applied a second time here)."""
        themes.set_current(self.config.get("appearance", "theme", "dark"))
        # Start the expensive one-time libVLC/plugin scan immediately after the
        # window appears. It stays on a worker thread, so navigation remains
        # responsive and the first movie/episode no longer initiates the work.
        if not self.smoke_test and os.environ.get("QT_QPA_PLATFORM", "").lower() != "offscreen":
            self.video_player.initialize_async()
        self.home_status.setText("Učitavam listu…")
        self.overlay.start("Učitavam listu…", cancellable=False)
        # Database and playlist cache load in a background thread while the
        # remaining pages are built on the GUI thread.
        from ui.workers import StartupWorker
        self.startup_worker = StartupWorker(self)
        self.startup_worker.progress.connect(self.overlay.text.setText)
        self.startup_worker.finished_ok.connect(self._on_startup_loaded)
        self.startup_worker.failed.connect(self._on_startup_failed)
        self.startup_worker.start()
        QTimer.singleShot(0, self._ensure_pages)
        QTimer.singleShot(15000, ImageLoader.instance().prune_disk_async)

    def _on_startup_loaded(self, playlist, parsed):
        self._ensure_pages()
        self.playlist = playlist
        if parsed is not None and parsed.total:
            self._show_playlist(parsed)
            startup_profiler.mark("playlist_shown")
            self._maybe_auto_refresh()
        elif playlist:
            # A list is configured but nothing is cached (e.g. interrupted first load).
            self.overlay.finish()
            self.refresh_playlist(silent=False)
        else:
            self.overlay.finish()
            self.home_status.setText("Dodajte IPTV listu u Podešavanjima da biste počeli.")
            self.settings_page.show_welcome(True)
            self.go(SETTINGS)
            startup_profiler.mark("first_run_ready")
        self._finish_startup()

    def _on_startup_failed(self, message: str):
        self._ensure_pages()
        self.overlay.finish()
        self.home_status.setText(message)
        info(self, "Greška", message)
        self._finish_startup()

    def _finish_startup(self):
        self._loaded_once = True
        report = startup_profiler.env_report_path()
        if report:
            startup_profiler.write_report(report)
        if self.smoke_test:
            QTimer.singleShot(1500, self.close)

    def _maybe_auto_refresh(self):
        if not self.playlist or not self.config.get("playlists", "auto_refresh", True):
            return
        last = self.playlist.get("last_refreshed")
        days = int(self.config.get("playlists", "refresh_interval_days", 7))
        if last is None or datetime.now() - last > timedelta(days=days):
            later(self, 3000, lambda: self.refresh_playlist(silent=True))

    def _show_playlist(self, parsed):
        self.parsed = parsed
        self.overlay.finish()
        self.live_tv_widget.load_channels(parsed.channels)
        self.vod_page.set_items(parsed.vod_items)
        self.series_page.set_items(parsed.series_items)
        self.episode_cache.clear()
        series_count = len(getattr(self.series_page, "groups", {}) or {})
        self.tv_btn.setText(f"📺\nTV\n({len(parsed.channels)})")
        self.vod_btn.setText(f"🎬\nFilmovi\n({len(parsed.vod_items)})")
        self.series_btn.setText(f"📺\nSerije\n({series_count})")
        self.home_status.setText("")
        self.settings_page.show_welcome(False)
        self._update_settings_info()

    def _update_settings_info(self):
        counts = None
        if self.parsed:
            counts = (len(self.parsed.channels), len(self.parsed.vod_items),
                      len(getattr(self.series_page, "groups", {}) or {}))
        self.settings_page.set_current_playlist(self.playlist, counts)

    # ------------------------------------------------------------------ playlist loading

    def load_playlist(self, source: dict, name: str, playlist_id: Optional[int] = None, silent: bool = False):
        if self.loader_worker is not None and self.loader_worker.isRunning():
            if silent:
                return
            self.loader_worker.cancel()
            self.loader_worker.abandoned = True
        from ui.workers import PlaylistLoadWorker
        worker = PlaylistLoadWorker(source, name, playlist_id, self)
        self.loader_worker = worker
        worker.silent = silent
        if not silent:
            self.overlay.start("Učitavam listu…", cancellable=True)
            worker.progress.connect(self.overlay.set_detail)
        else:
            self.toast.show_message("🔄 Osvežavam listu u pozadini…")
        worker.finished_ok.connect(self._on_list_loaded)
        worker.failed.connect(self._on_list_failed)
        worker.cancelled.connect(self._on_list_cancelled)
        worker.start()

    def refresh_playlist(self, silent: bool = False):
        if not self.playlist:
            info(self, "Nema liste", "Prvo dodajte IPTV listu.")
            return
        p = self.playlist
        if p.get("type") == "Xtream":
            source = {"type": "Xtream", "server": p.get("server", ""), "username": p.get("username", ""),
                      "password": p.get("password", "")}
        else:
            source = {"type": "M3U", "url": p.get("url", "")}
        self.load_playlist(source, p.get("name") or "Moja lista", p.get("id"), silent=silent)

    def cancel_loading(self):
        """Cancel immediately; a network call still blocking in the worker
        finishes in the background and its result is ignored."""
        worker = self.loader_worker
        if worker is not None:
            worker.cancel()
            worker.abandoned = True
            self._on_list_cancelled()

    def _on_list_loaded(self, playlist, parsed):
        if getattr(self.sender(), "abandoned", False):
            return
        silent = getattr(self.sender(), "silent", False)
        self.playlist = playlist
        current = self.stack.currentIndex()
        self._show_playlist(parsed)
        self.settings_page.clear_inputs()
        summary = (f"Lista učitana: {len(parsed.channels)} kanala, {len(parsed.vod_items)} filmova, "
                   f"{len(getattr(self.series_page, 'groups', {}) or {})} serija.")
        self.toast.show_message(("✓ Lista je osvežena. " if silent else "✓ ") + summary)
        if not silent:
            self.go(HOME)
        elif current in (VOD_DETAIL, SERIES_DETAIL):
            pass  # do not pull the user away from what they are looking at
        if self.smoke_test:
            QTimer.singleShot(500, self.close)

    def _on_list_failed(self, message: str):
        if getattr(self.sender(), "abandoned", False):
            return
        silent = getattr(self.sender(), "silent", False)
        self.overlay.finish()
        if silent:
            self.toast.show_message(f"Lista nije osvežena: {message} Koristi se sačuvana lista.", 7000)
            return
        if self.stack.currentIndex() != SETTINGS:
            self.go(SETTINGS)
        self.settings_page.show_error(message)
        extra = "\n\nPrethodno sačuvana lista je i dalje dostupna." if self.parsed else ""
        info(self, "Lista nije učitana", message + extra)

    def _on_list_cancelled(self):
        if getattr(self.sender(), "abandoned", False):
            return  # already handled when the user pressed "Otkaži"
        self.overlay.finish()
        self.toast.show_message("Učitavanje je otkazano." + (" Koristi se sačuvana lista." if self.parsed else ""))

    def import_old_database(self, path: str):
        if not ask(self, "Uvoz podataka",
                   "Trenutni podaci biće zamenjeni podacima iz izabranog fajla.\n"
                   "Rezervna kopija trenutnih podataka čuva se automatski u folderu backups.\n\nNastaviti?"):
            return
        from core.database import Database
        from core import legacy_import
        try:
            Database.reset_instance()
            legacy_import.import_database_file(path)
        except Exception as exc:
            logger.exception("Import failed")
            info(self, "Uvoz nije uspeo", str(exc))
        self.parsed = None
        self.start()

    # ------------------------------------------------------------------ opening content

    def open_vod(self, vod):
        self.vod_detail.show_item(vod)
        self.go(VOD_DETAIL)

    def open_series(self, payload):
        key, episodes = payload
        self.current_series_key = key
        stub = next((e for e in episodes if e.is_series_stub), None)
        if stub is not None:
            cached = self.episode_cache.get(key)
            self.series_detail.show_series(key, cached or episodes, loading=cached is None)
            if cached is None:
                self._load_xtream_episodes(key)
        else:
            self.series_detail.show_series(key, episodes)
        self.go(SERIES_DETAIL)

    def _load_xtream_episodes(self, key: str, force: bool = False):
        groups = getattr(self.series_page, "groups", {}) or {}
        stub = next((e for e in groups.get(key, []) if e.is_series_stub), None)
        if stub is None or (key in self.episode_workers and self.episode_workers[key].isRunning()):
            return
        if force:
            self.series_detail.set_episodes(groups.get(key, []), loading=True)
        from ui.workers import EpisodesWorker
        worker = EpisodesWorker(key, stub, self.playlist, self)
        worker.finished_ok.connect(self._on_episodes_loaded)
        worker.failed.connect(self._on_episodes_failed)
        self.episode_workers[key] = worker
        worker.start()

    def _on_episodes_loaded(self, key: str, episodes: list):
        self.episode_cache[key] = episodes
        if key == self.current_series_key and self.stack.currentIndex() == SERIES_DETAIL:
            self.series_detail.set_episodes(episodes)

    def _on_episodes_failed(self, key: str, message: str):
        if key == self.current_series_key:
            groups = getattr(self.series_page, "groups", {}) or {}
            self.series_detail.set_episodes(groups.get(key, []), error=message)

    # ------------------------------------------------------------------ playback

    def _url(self, url: str) -> str:
        from core.playlist_service import resolve_stream_url
        return resolve_stream_url(url, self.playlist)

    def _prepare_playback(self):
        """Make a slow first VLC start visible instead of looking frozen."""
        if self.video_player.is_initialized:
            return
        self._playback_wait_overlay = True
        self.overlay.start("Pokrećem video plejer…", cancellable=False)
        self.overlay.set_detail("Prvo pokretanje može potrajati. Program i dalje radi.")
        self.playback_wait_timer.start()
        self.video_player.initialize_async()

    def _on_player_initialized(self, ok: bool):
        if not self._playback_wait_overlay:
            return
        self._playback_wait_overlay = False
        self.playback_wait_timer.stop()
        self.overlay.finish()
        if not ok:
            self.toast.show_message("Video plejer nije mogao da se pokrene.")

    def _on_playback_wait_timeout(self):
        if not self._playback_wait_overlay or self.video_player.is_initialized:
            return
        self._playback_wait_overlay = False
        self.overlay.finish()
        self.toast.show_message("Video plejer se nije pokrenuo. Ponovo pokrenite program.", 7000)

    def play_channel(self, channel):
        logger.info("Playing a TV channel")
        self._prepare_playback()
        self.player_widget.play_url(self._url(channel.url), content_type="tv", content_title=channel.name)

    def play_vod(self, vod, resume_seconds: int = 0):
        self.current_vod = vod
        self._prepare_playback()
        self.player_widget.play_url(self._url(vod.url), content_type="vod", content_title=vod.name,
                                    stream_id=str(vod.stream_id), resume_position=resume_seconds or None)
        if self.video_player.is_initialized:
            QTimer.singleShot(400, self.player_widget.enter_fullscreen)
        else:
            self.player_widget.fullscreen_when_ready = True

    def play_episode(self, episode, ordered: list, resume_seconds: int = 0):
        from core.database import Database
        self._prepare_playback()
        self.series_queue = list(ordered)
        self.series_index = next((i for i, e in enumerate(self.series_queue) if e.stream_id == episode.stream_id), -1)
        key = self.current_series_key
        Database().set_series_state(key, season=episode.season or "__none__", episode_id=episode.stream_id)
        next_info = None
        if 0 <= self.series_index < len(self.series_queue) - 1:
            nxt = self.series_queue[self.series_index + 1]
            next_info = {"title": nxt.name, "stream_id": nxt.stream_id, "season": nxt.season, "episode": nxt.episode}
        code = episode_code(episode.season, episode.episode)
        from ui.series_detail_page import display_title
        title = f"{key}  ·  {code}  {display_title(episode, key)}".strip()
        was_fullscreen = self.player_widget.is_fullscreen
        self.player_widget.play_url(self._url(episode.url), content_type="series", next_episode_info=next_info,
                                    content_title=title, stream_id=str(episode.stream_id),
                                    resume_position=resume_seconds or None)
        if not was_fullscreen:
            if self.video_player.is_initialized:
                QTimer.singleShot(400, self.player_widget.enter_fullscreen)
            else:
                self.player_widget.fullscreen_when_ready = True
        if self.stack.currentIndex() == SERIES_DETAIL:
            self.series_detail.focus_episode(episode)

    def play_next_episode(self):
        if 0 <= self.series_index < len(self.series_queue) - 1:
            self.play_episode(self.series_queue[self.series_index + 1], self.series_queue, 0)

    def on_playback_finished(self, content_type: str):
        from core.database import Database
        db = Database()
        if content_type == "vod" and self.current_vod is not None:
            db.mark_vod_watched(self.current_vod.stream_id, self.current_vod.name)
        elif content_type == "series" and 0 <= self.series_index < len(self.series_queue):
            episode = self.series_queue[self.series_index]
            db.mark_series_watched(episode.stream_id, episode.name, self.current_series_key,
                                   episode.season or "", episode.episode or "")

    def on_playback_exited(self):
        page = self.stack.currentIndex()
        if page == VOD_DETAIL:
            self.vod_detail.refresh()
            self.vod_page.refresh_flags()
        elif page == SERIES_DETAIL:
            self.series_detail.refresh()
            self.series_page.refresh_flags()
        self.activateWindow()

    # ------------------------------------------------------------------ shutdown

    def closeEvent(self, event):
        logger.info("Closing application")
        try:
            if self._pages_built:
                self.player_widget.stop()
        except Exception as exc:
            logger.error("Error stopping player: %s", exc)
        for worker in [self.loader_worker, self.startup_worker, *self.episode_workers.values()]:
            if worker is not None and worker.isRunning():
                if hasattr(worker, "cancel"):
                    worker.cancel()
                worker.abandoned = True
                worker.wait(1500)  # daemon threads: never block closing for long
        ImageLoader.instance().cleanup()
        self.video_player.cleanup()
        event.accept()
