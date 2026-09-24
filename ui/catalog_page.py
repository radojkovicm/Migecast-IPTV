"""Movies and series catalog pages (search + category + poster grid)."""
import logging
from typing import List, Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLineEdit, QStackedLayout, QVBoxLayout, QWidget

from core.db_access import Database
from core.m3u import group_series, legacy_series_name, series_name_for
from ui.poster_grid import PosterGridView, PosterItem, PosterModel
from ui.widgets import button, label
from utils.image_cache import ImageLoader

logger = logging.getLogger(__name__)

CONTINUE = "▶  Nastavi gledanje"
FAVORITES = "⭐  Favoriti"


class CatalogPage(QWidget):
    item_selected = pyqtSignal(object)

    all_label = "Sve"
    search_hint = "Pretraga…"
    empty_favorites = "Još nemate favorite."
    glyph = "🎬"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.db = None
        self._entries = []  # (key, lower_title, category, PosterItem)
        self._categories: List[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 12)
        layout.setSpacing(14)

        bar = QHBoxLayout()
        bar.setSpacing(12)
        self.search = QLineEdit()
        self.search.setPlaceholderText(self.search_hint)
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(360)
        self.search.textChanged.connect(lambda _: self._debounce.start(250))
        self.category = QComboBox()
        self.category.setMinimumWidth(380)
        self.category.setMaxVisibleItems(14)
        self.category.currentIndexChanged.connect(lambda _: self.apply_filter())
        self.count = label("", "muted")
        bar.addWidget(label("🔍"))
        bar.addWidget(self.search, 2)
        bar.addWidget(self.category, 2)
        bar.addWidget(self.count)
        layout.addLayout(bar)

        self.stack = QStackedLayout()
        self.model = PosterModel(self)
        self.grid = PosterGridView()
        self.grid.setModel(self.model)
        self.grid.item_activated.connect(lambda item: self.item_selected.emit(item.payload))
        self.grid.verticalScrollBar().valueChanged.connect(lambda _: self._scroll_timer.start(120))
        self.empty = label("", "h2", wrap=True)
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        holder = QWidget()
        holder_layout = QVBoxLayout(holder)
        holder_layout.addWidget(self.empty)
        self.stack.addWidget(self.grid)
        self.stack.addWidget(holder)
        layout.addLayout(self.stack, 1)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self.apply_filter)
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.timeout.connect(ImageLoader.instance().cancel_queued)

    # -- to be implemented by subclasses -------------------------------------------

    def _continue_keys(self) -> List[str]:
        return []

    def _favorite_keys(self) -> set:
        return set()

    def _decorate(self, items: List[PosterItem]):
        """Update favorite/progress flags of the visible items."""

    # -- common ------------------------------------------------------------------------

    def _set_entries(self, entries, categories):
        self._entries = entries
        self._categories = sorted(categories, key=str.lower)
        self.category.blockSignals(True)
        previous = self.category.currentText()
        self.category.clear()
        self.category.addItems([CONTINUE, FAVORITES, self.all_label] + self._categories)
        if previous and self.category.findText(previous) >= 0:
            self.category.setCurrentText(previous)
        else:
            self.category.setCurrentText(FAVORITES if self._favorite_keys() else self.all_label)
        self.category.blockSignals(False)
        self.apply_filter()

    def apply_filter(self):
        choice = self.category.currentText()
        text = self.search.text().strip().lower()
        if choice == CONTINUE:
            order = {key: index for index, key in enumerate(self._continue_keys())}
            selected = [e for e in self._entries if e[0] in order]
            selected.sort(key=lambda e: order[e[0]])
        elif choice == FAVORITES:
            favorites = self._favorite_keys()
            selected = [e for e in self._entries if e[0] in favorites]
        elif choice == self.all_label or not choice:
            selected = self._entries
        else:
            selected = [e for e in self._entries if e[2] == choice]
        if text:
            words = text.split()
            selected = [e for e in selected if all(word in e[1] for word in words)]
        items = [e[3] for e in selected]
        self._decorate(items)
        ImageLoader.instance().cancel_queued()
        self.model.set_items(items)
        self.grid.scrollToTop()
        self.count.setText(f"{len(items)}")
        if items:
            self.stack.setCurrentIndex(0)
        else:
            if choice == FAVORITES and not text:
                self.empty.setText(self.empty_favorites)
            elif choice == CONTINUE and not text:
                self.empty.setText("Ovde će se pojaviti sadržaj koji ste počeli da gledate.")
            else:
                self.empty.setText("Nema rezultata. Probajte drugu reč ili kategoriju.")
            self.stack.setCurrentIndex(1)

    def refresh_flags(self):
        """Re-read favorites/progress (after returning from a detail page)."""
        self._decorate(self.model.items)
        self.model.refresh_rows(lambda item: True)

    def reset_search(self):
        self.search.clear()


class VODPage(CatalogPage):
    all_label = "🎬  Svi filmovi"
    search_hint = "Pretražite filmove…"
    empty_favorites = "Nemate omiljene filmove.\nOtvorite film i kliknite „⭐ Favorit“."

    def set_items(self, vod_items):
        self.db = Database()
        entries, categories = [], set()
        for vod in vod_items:
            item = PosterItem(key=vod.stream_id, title=vod.name, image=vod.cover, glyph="🎬", payload=vod,
                              subtitle=vod.year or "")
            entries.append((vod.stream_id, vod.name.lower(), vod.category, item))
            if vod.category:
                categories.add(vod.category)
        self._set_entries(entries, categories)

    def _continue_keys(self):
        return [p.stream_id for p in self.db.get_continue_watching(limit=80, content_type="vod")] if self.db else []

    def _favorite_keys(self):
        return self.db.get_all_vod_favorite_ids() if self.db else set()

    def _decorate(self, items):
        if not self.db:
            return
        favorites = self.db.get_all_vod_favorite_ids()
        watched = self.db.get_all_watched_vod_ids()
        progress = self.db.get_progress_map()
        for item in items:
            item.favorite = item.key in favorites
            pos = progress.get(item.key)
            item.watched = item.key in watched and not (pos and not pos[2])
            item.progress = (pos[0] / pos[1]) if pos and pos[1] and not pos[2] else -1.0


class SeriesPage(CatalogPage):
    all_label = "📺  Sve serije"
    search_hint = "Pretražite serije…"
    empty_favorites = "Nemate omiljene serije.\nOtvorite seriju i kliknite „⭐ Favorit“."

    def set_items(self, series_items):
        self.db = Database()
        groups = group_series(series_items)
        self.groups = groups
        entries, categories, renames = [], set(), {}
        for key, episodes in groups.items():
            first = episodes[0]
            cover = next((e.cover for e in episodes if e.cover), None)
            count = sum(1 for e in episodes if not e.is_series_stub)
            subtitle = f"{count} epizoda" if count > 1 else (first.year or "")
            item = PosterItem(key=key, title=key, image=cover, glyph="📺", subtitle=subtitle,
                              payload=(key, episodes))
            category = first.category or ""
            entries.append((key, key.lower(), category, item))
            if category:
                categories.add(category)
            legacy = legacy_series_name(first.name)
            if legacy and legacy != key:
                renames[legacy] = key
        if renames:
            self.db.rename_series_favorites(renames)
        self._set_entries(entries, categories)

    def _continue_keys(self):
        return self.db.get_recent_series_keys() if self.db else []

    def _favorite_keys(self):
        return self.db.get_all_series_favorite_ids() if self.db else set()

    def _decorate(self, items):
        if not self.db:
            return
        favorites = self.db.get_all_series_favorite_ids()
        for item in items:
            item.favorite = item.key in favorites


def series_key_for(item) -> str:
    return series_name_for(item)
