"""Movie details shown inside the main window."""
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from core.db_access import Database
from models.vod_item import VODItem
from ui.detail_common import DetailHeader, format_time
from ui.widgets import button


class VODDetailPage(QWidget):
    play_requested = pyqtSignal(object, int)  # VODItem, resume position in seconds (0 = start)
    back_requested = pyqtSignal()
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.vod: VODItem = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        self.header = DetailHeader("🎬")
        layout.addWidget(self.header)
        layout.addStretch(1)

        self.resume_btn = button("▶  Nastavi", "primary", self._resume, 260)
        self.play_btn = button("▶  Pusti", "primary", self._play_start, 220)
        self.fav_btn = button("☆  Favorit", "secondary", self._toggle_favorite, 220)
        self.watched_btn = button("✓  Odgledano", "secondary", self._toggle_watched, 220)
        self.back_btn = button("⬅  Nazad", "secondary", self.back_requested.emit, 180)
        for btn in (self.resume_btn, self.play_btn, self.fav_btn, self.watched_btn):
            self.header.buttons.addWidget(btn)
        self.header.buttons.addStretch(1)
        self.back_btn.hide()  # the window header already has a big "Nazad" button

    def show_item(self, vod: VODItem):
        self.vod = vod
        meta = [vod.year, f"⭐ {vod.rating}" if vod.rating and vod.rating not in ("0", "0.0") else "",
                vod.duration, vod.genre]
        extra = "   ·   ".join(p for p in (f"📁 {vod.category}" if vod.category else "",
                                           f"Režija: {vod.director}" if vod.director else "",
                                           f"Uloge: {vod.cast}" if vod.cast else "") if p)
        self.header.set_info(vod.name, meta, extra, vod.plot, vod.cover)
        self.refresh()

    def refresh(self):
        if not self.vod:
            return
        db = Database()
        progress = db.get_watch_progress(self.vod.stream_id)
        resumable = bool(progress and not progress.completed and progress.position_seconds > 30)
        self.resume_pos = progress.position_seconds if resumable else 0
        self.resume_btn.setVisible(resumable)
        if resumable:
            self.resume_btn.setText(f"▶  Nastavi od {format_time(progress.position_seconds)}")
            self.play_btn.setText("⏮  Od početka")
            self.play_btn.setProperty("role", "secondary")
        else:
            self.play_btn.setText("▶  Pusti")
            self.play_btn.setProperty("role", "primary")
        self.play_btn.style().unpolish(self.play_btn)
        self.play_btn.style().polish(self.play_btn)
        favorite = db.is_vod_favorite(self.vod.stream_id)
        self.fav_btn.setText("★  Ukloni iz favorita" if favorite else "☆  Dodaj u favorite")
        watched = db.is_vod_watched(self.vod.stream_id) and not resumable
        self.watched_btn.setText("↺  Nije odgledano" if watched else "✓  Odgledano")
        if resumable:
            self.header.status.setText(f"Gledali ste do {format_time(progress.position_seconds)}"
                                       f" od {format_time(progress.duration_seconds)}.")
        else:
            self.header.status.setText("✓ Odgledano" if watched else "")
        (self.resume_btn if resumable else self.play_btn).setFocus()

    def _resume(self):
        self.play_requested.emit(self.vod, self.resume_pos)

    def _play_start(self):
        self.play_requested.emit(self.vod, 0)

    def _toggle_favorite(self):
        Database().toggle_vod_favorite(self.vod.stream_id, self.vod.name)
        self.refresh()
        self.changed.emit()

    def _toggle_watched(self):
        db = Database()
        if self.watched_btn.text().startswith("↺"):
            db.mark_vod_unwatched(self.vod.stream_id)
        else:
            db.mark_vod_watched(self.vod.stream_id, self.vod.name)
            db.delete_watch_progress(self.vod.stream_id)
        self.refresh()
        self.changed.emit()
