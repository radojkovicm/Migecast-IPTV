"""Senior-friendly series screen with paged, full-width episode rows."""
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from PyQt6.QtCore import QAbstractListModel, QEvent, QModelIndex, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (QAbstractItemView, QComboBox, QFrame, QHBoxLayout, QListView,
                             QListWidget, QListWidgetItem, QStyle, QStyledItemDelegate,
                             QVBoxLayout, QWidget)

from core.db_access import Database
from core.m3u import episode_code, natural_key, parse_episode_info, sort_episodes
from models.series_item import SeriesItem
from ui.detail_common import DetailHeader, format_time
from ui.widgets import button, label
from utils import themes

ROW_H = 90
RANGE_SIZE = 5
NO_SEASON = "__none__"


def season_of(episode: SeriesItem) -> str:
    return episode.season if episode.season not in (None, "") else NO_SEASON


def display_title(episode: SeriesItem, series_name: str) -> str:
    if episode.episode_title:
        return episode.episode_title
    title = episode.name or ""
    info = parse_episode_info(title)
    if info and info.series_name == series_name:
        rest = title[len(series_name):] if title.startswith(series_name) else title
        rest = re.sub(r"(?i)^[\s\-–|:._]*(S\d+\s*[._-]?\s*E\d+|\d+x\d+|E\d+|(sezona|season)\s*\d+\D{0,6}(epizoda|episode)\s*\d+)"
                      r"[\s\-–|:._]*", "", rest).strip()
        if rest:
            return rest
    if info and info.series_name == series_name and episode.episode:
        return f"Epizoda {episode.episode}"
    return title or "Epizoda"


@dataclass
class EpisodeRow:
    episode: SeriesItem
    code: str
    title: str
    position: int = 0
    duration: int = 0
    completed: bool = False
    watched: bool = False
    is_last: bool = False

    @property
    def resumable(self) -> bool:
        return not self.completed and not self.watched and self.position > 30

    @property
    def is_watched(self) -> bool:
        return self.watched or self.completed


class EpisodeModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows: List[EpisodeRow] = []

    def set_rows(self, rows):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self.rows[index.row()]
        if role == Qt.ItemDataRole.UserRole:
            return row
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return f"{row.code} {row.title}"
        return None


class EpisodeDelegate(QStyledItemDelegate):
    """Paint one large row; double-clicking the row or clicking its button plays it."""

    action = pyqtSignal(str, object)  # 'resume' | 'play' | 'watched', EpisodeRow
    BTN_H = 54

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), ROW_H)

    def _buttons(self, rect, row: EpisodeRow):
        specs = []
        if row.resumable:
            specs.append(("play", "⏮ Od početka", 180, False))
        result = []
        x = rect.right() - 14
        y = rect.y() + (rect.height() - self.BTN_H) / 2
        for key, text, width, primary in reversed(specs):
            x -= width
            result.insert(0, (key, text, QRectF(x, y, width, self.BTN_H), primary))
            x -= 12
        return result

    def paint(self, painter: QPainter, option, index):
        row: EpisodeRow = index.data(Qt.ItemDataRole.UserRole)
        t = themes.current()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(option.rect).adjusted(4, 4, -4, -4)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        painter.setPen(QPen(QColor(t["accent"] if (selected or row.is_last) else t["border"]),
                            4 if selected else (3 if row.is_last else 1)))
        painter.setBrush(QColor(t["hover"] if hovered else t["surface"]))
        painter.drawRoundedRect(rect, 14, 14)

        badge = QRectF(rect.x() + 16, rect.y() + (rect.height() - 46) / 2, 126, 46)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(t["accent"] if not row.is_watched else t["surface2"]))
        painter.drawRoundedRect(badge, 10, 10)
        badge_font = QFont(painter.font())
        badge_font.setPointSize(16)
        badge_font.setBold(True)
        painter.setFont(badge_font)
        painter.setPen(QColor(t["accent_text"] if not row.is_watched else t["text"]))
        painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, row.code or "—")

        buttons = self._buttons(rect, row)
        text_left = badge.right() + 18
        text_right = buttons[0][2].x() - 16 if buttons else rect.right() - 16
        title_font = QFont(painter.font())
        title_font.setPointSize(15)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QColor(t["text"]))
        title_rect = QRectF(text_left, rect.y() + 8, text_right - text_left, 31)
        number = row.episode.episode or "—"
        generic_title = re.fullmatch(r"(?i)(episode|epizoda)\s*0*" + re.escape(str(number)),
                                     row.title.strip())
        title = f"Epizoda {number}" if generic_title else f"Epizoda {number}  ·  {row.title}"
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         painter.fontMetrics().elidedText(title, Qt.TextElideMode.ElideRight,
                                                          int(title_rect.width())))

        status_font = QFont(painter.font())
        status_font.setPointSize(12)
        status_font.setBold(False)
        painter.setFont(status_font)
        status_rect = QRectF(text_left, title_rect.bottom() + 2, text_right - text_left, 26)
        if row.is_watched:
            painter.setPen(QColor(t["accent"]))
            status = "✓ Odgledano"
        elif row.resumable:
            painter.setPen(QColor(t["muted"]))
            status = f"Gledano do {format_time(row.position)} od {format_time(row.duration)}"
        else:
            painter.setPen(QColor(t["muted"]))
            status = "Nije gledano"
        if row.is_last:
            status = "● Poslednje gledano  ·  " + status
        painter.drawText(status_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         painter.fontMetrics().elidedText(status, Qt.TextElideMode.ElideRight,
                                                          int(status_rect.width())))
        if row.resumable and row.duration:
            bar = QRectF(text_left, status_rect.bottom() + 1, min(320, text_right - text_left), 6)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(t["surface2"]))
            painter.drawRoundedRect(bar, 3, 3)
            painter.setBrush(QColor(t["accent"]))
            painter.drawRoundedRect(
                QRectF(bar.x(), bar.y(), bar.width() * min(1, row.position / row.duration), 6), 3, 3)

        button_font = QFont(painter.font())
        button_font.setPointSize(13)
        button_font.setBold(True)
        painter.setFont(button_font)
        for _key, text, brect, primary in buttons:
            painter.setPen(QPen(QColor(t["accent"] if primary else t["border"]), 2))
            painter.setBrush(QColor(t["accent"] if primary else t["secondary"]))
            painter.drawRoundedRect(brect, 12, 12)
            painter.setPen(QColor(t["accent_text"] if primary else t["text"]))
            painter.drawText(brect, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()

    def editorEvent(self, event, model, option, index):
        if event.type() in (QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonPress,
                            QEvent.Type.MouseButtonDblClick):
            row = index.data(Qt.ItemDataRole.UserRole)
            for key, _text, brect, _primary in self._buttons(
                    QRectF(option.rect).adjusted(4, 4, -4, -4), row):
                if brect.contains(event.position()):
                    if event.type() == QEvent.Type.MouseButtonRelease:
                        self.action.emit(key, row)
                    return True
        return super().editorEvent(event, model, option, index)


class SeriesDetailPage(QWidget):
    play_requested = pyqtSignal(object, list, int)  # episode, ordered episodes, resume seconds
    back_requested = pyqtSignal()
    retry_requested = pyqtSignal()
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.series_key = ""
        self.episodes: List[SeriesItem] = []
        self.ordered: List[SeriesItem] = []
        self.seasons: Dict[str, List[SeriesItem]] = {}
        self.current_season: Optional[str] = None
        self.range_index = 0
        self._continue_target = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 22, 32, 16)
        layout.setSpacing(16)
        self.header = DetailHeader("📺")
        self.header.poster.setFixedSize(200, 300)
        self.header.plot.setMaximumHeight(110)
        self.continue_btn = button("▶  Pusti", "primary", self._continue, 300)
        self.fav_btn = button("☆  Favorit", "secondary", self._toggle_favorite, 250)
        self.back_btn = button("⬅  Nazad", "secondary", self.back_requested.emit, 180)
        self.header.buttons.addWidget(self.continue_btn)
        self.header.buttons.addWidget(self.fav_btn)
        self.header.buttons.addStretch(1)
        self.back_btn.hide()  # the window header already has a big "Nazad" button
        layout.addWidget(self.header)

        body = QHBoxLayout()
        body.setSpacing(20)
        self.season_panel = QFrame()
        self.season_panel.setObjectName("SeasonPanel")
        self.season_panel.setFixedWidth(310)
        left = QVBoxLayout(self.season_panel)
        left.setContentsMargins(14, 12, 14, 14)
        left.setSpacing(10)
        season_heading = label("SEZONE", "h2")
        season_heading.setObjectName("SeasonHeading")
        left.addWidget(season_heading)
        self.season_list = QListWidget()
        self.season_list.setObjectName("SeasonList")
        self.season_list.setCursor(Qt.CursorShape.PointingHandCursor)
        self.season_list.currentRowChanged.connect(self._on_season_row)
        left.addWidget(self.season_list, 1)
        body.addWidget(self.season_panel)

        right = QVBoxLayout()
        bar = QHBoxLayout()
        self.episodes_title = label("Epizode", "h2")
        bar.addWidget(self.episodes_title, 1)
        self.total_label = label("", "muted")
        font = self.total_label.font()
        font.setPointSize(14)
        font.setBold(True)
        self.total_label.setFont(font)
        bar.addWidget(self.total_label)
        right.addLayout(bar)

        self.range_bar = QHBoxLayout()
        self.range_bar.setSpacing(10)
        self.prev_range_btn = button("◀  Prethodnih 5", "secondary", self._previous_range, 220)
        self.range_combo = QComboBox()
        self.range_combo.setMinimumWidth(360)
        self.range_combo.setMinimumHeight(60)
        self.range_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        range_font = self.range_combo.font()
        range_font.setPointSize(14)
        range_font.setBold(True)
        self.range_combo.setFont(range_font)
        self.range_combo.currentIndexChanged.connect(self._select_range)
        self.next_range_btn = button("Sledećih 5  ▶", "secondary", self._next_range, 220)
        self.range_bar.addWidget(self.prev_range_btn)
        self.range_bar.addWidget(self.range_combo)
        self.range_bar.addWidget(self.next_range_btn)
        self.range_bar.addStretch(1)
        right.addLayout(self.range_bar)

        self.message = label("", "h2", wrap=True)
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.retry_btn = button("↻  Pokušaj ponovo", "primary", self.retry_requested.emit, 260)
        self.message.hide()
        self.retry_btn.hide()
        right.addWidget(self.message)
        right.addWidget(self.retry_btn, 0, Qt.AlignmentFlag.AlignHCenter)

        self.view = QListView()
        self.view.setUniformItemSizes(True)
        self.view.setMouseTracking(True)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.view.verticalScrollBar().setSingleStep(36)
        self.model = EpisodeModel(self)
        self.delegate = EpisodeDelegate(self.view)
        self.delegate.action.connect(self._on_action)
        self.view.setModel(self.model)
        self.view.setItemDelegate(self.delegate)
        self.view.doubleClicked.connect(self._on_double_click)
        right.addWidget(self.view, 1)
        body.addLayout(right, 1)
        layout.addLayout(body, 1)

    # -- public ---------------------------------------------------------------------------

    def show_series(self, key: str, episodes: List[SeriesItem], loading: bool = False):
        self.series_key = key
        first = episodes[0] if episodes else None
        cover = next((e.cover for e in episodes if e.cover), None)
        info = first or SeriesItem(stream_id="", name=key, url="")
        self._header_info = (info, cover)
        self.set_episodes(episodes, loading=loading)

    def set_episodes(self, episodes: List[SeriesItem], loading: bool = False, error: str = ""):
        playable = [e for e in episodes if not e.is_series_stub]
        self.episodes = playable
        self.ordered = sort_episodes(playable)
        self.seasons = {}
        for episode in self.ordered:
            self.seasons.setdefault(season_of(episode), []).append(episode)
        info, cover = self._header_info
        season_count = len([s for s in self.seasons if s != NO_SEASON])
        meta = [info.year, f"⭐ {info.rating}" if info.rating and info.rating not in ("0", "0.0") else "",
                f"{season_count} {'sezona' if season_count != 1 else 'sezona'}" if season_count else "",
                f"{len(self.ordered)} epizoda" if self.ordered else ""]
        extra = "   ·   ".join(p for p in (info.genre or "", f"📁 {info.category}" if info.category else "") if p)
        self.header.set_info(self.series_key, meta, extra, info.plot, cover)

        self.message.setVisible(loading or bool(error) or not self.ordered)
        self.retry_btn.setVisible(bool(error))
        self.view.setVisible(bool(self.ordered))
        self.range_combo.setVisible(bool(self.ordered))
        self.prev_range_btn.setVisible(bool(self.ordered))
        self.next_range_btn.setVisible(bool(self.ordered))
        self.season_list.setEnabled(bool(self.ordered))
        if loading:
            self.message.setText("Učitavam epizode…")
        elif error:
            self.message.setText(f"Epizode nisu učitane.\n{error}")
        elif not self.ordered:
            self.message.setText("Ova serija trenutno nema dostupnih epizoda.")
        self._fill_seasons()
        self.refresh()

    def refresh(self, select_id: Optional[str] = None):
        """Re-read progress/favorite state (e.g. after playback)."""
        db = Database()
        state = db.get_series_state(self.series_key) or {}
        favorite = db.is_series_favorite(self.series_key)
        self.fav_btn.setText("★  Ukloni iz favorita" if favorite else "☆  Dodaj u favorite")
        ids = [e.stream_id for e in self.ordered]
        self._progress = db.get_progress_map(ids)
        self._watched = db.get_watched_series_ids(ids)
        self._last_id = state.get("episode_id")
        self._update_continue_button()
        season = state.get("season")
        if self._last_id:
            last = next((e for e in self.ordered if e.stream_id == self._last_id), None)
            if last is not None:
                season = season_of(last)
        self._select_season(season if season in self.seasons else (next(iter(self.seasons), None)))
        self._fill_episodes(select_id=select_id or self._last_id)

    def focus_episode(self, episode: SeriesItem):
        self._last_id = episode.stream_id
        self._select_season(season_of(episode))
        self._fill_episodes(select_id=episode.stream_id)

    # -- seasons -----------------------------------------------------------------------------

    def _season_label(self, season: str) -> str:
        count = len(self.seasons.get(season, []))
        if season == NO_SEASON:
            name = "Sve epizode" if len(self.seasons) == 1 else "Ostale epizode"
        else:
            name = f"Sezona {season}"
        return f"{name}\n{count} {'epizoda' if count != 1 else 'epizoda'}"

    def _fill_seasons(self):
        self.season_list.blockSignals(True)
        self.season_list.clear()
        keys = sorted(self.seasons, key=lambda s: (s == NO_SEASON, natural_key(s)))
        self._season_keys = keys
        for key in keys:
            item = QListWidgetItem(self._season_label(key))
            item.setSizeHint(QSize(260, 78))
            font = item.font()
            font.setPointSize(15)
            font.setBold(True)
            item.setFont(font)
            self.season_list.addItem(item)
        self.season_list.blockSignals(False)

    def _select_season(self, season: Optional[str]):
        if season is None or season not in self._season_keys:
            self.current_season = self._season_keys[0] if self._season_keys else None
        else:
            self.current_season = season
        if self.current_season is not None:
            self.season_list.blockSignals(True)
            self.season_list.setCurrentRow(self._season_keys.index(self.current_season))
            self.season_list.blockSignals(False)

    def _on_season_row(self, row: int):
        if 0 <= row < len(self._season_keys):
            self.current_season = self._season_keys[row]
            Database().set_series_state(self.series_key, season=self.current_season)
            self.range_index = 0
            self._fill_episodes()

    # -- episodes ----------------------------------------------------------------------------

    def _row(self, episode: SeriesItem) -> EpisodeRow:
        pos, dur, completed = self._progress.get(episode.stream_id, (0, 0, False))
        return EpisodeRow(episode=episode, code=episode_code(episode.season, episode.episode),
                          title=display_title(episode, self.series_key), position=pos, duration=dur,
                          completed=completed, watched=episode.stream_id in self._watched,
                          is_last=episode.stream_id == self._last_id)

    def _episode_number(self, episode: SeriesItem, fallback: int) -> str:
        return str(episode.episode or fallback)

    def _rebuild_range_selector(self, source: List[SeriesItem]):
        self.range_combo.blockSignals(True)
        self.range_combo.clear()
        for start in range(0, len(source), RANGE_SIZE):
            end = min(start + RANGE_SIZE, len(source))
            first = self._episode_number(source[start], start + 1)
            last = self._episode_number(source[end - 1], end)
            self.range_combo.addItem(f"Epizode {first}–{last} od ukupno {len(source)}")
        if self.range_combo.count():
            self.range_combo.setCurrentIndex(self.range_index)
        self.range_combo.blockSignals(False)
        self.prev_range_btn.setEnabled(self.range_index > 0)
        self.next_range_btn.setEnabled(self.range_index + 1 < self.range_combo.count())

    def _fill_episodes(self, select_id: Optional[str] = None):
        source = self.seasons.get(self.current_season, [])
        count = len(source)
        if self.current_season == NO_SEASON or self.current_season is None:
            self.episodes_title.setText(f"Epizode — ukupno {count}")
        else:
            self.episodes_title.setText(f"Sezona {self.current_season} — ukupno {count} epizoda")
        last_number = self._episode_number(source[-1], count) if source else "—"
        self.total_label.setText(f"POSLEDNJA EPIZODA: {last_number}")

        if select_id:
            selected_position = next((i for i, e in enumerate(source) if e.stream_id == select_id), None)
            if selected_position is not None:
                self.range_index = selected_position // RANGE_SIZE
        range_count = max(1, (count + RANGE_SIZE - 1) // RANGE_SIZE)
        self.range_index = min(max(0, self.range_index), range_count - 1)
        self._rebuild_range_selector(source)

        start = self.range_index * RANGE_SIZE
        rows = [self._row(e) for e in source[start:start + RANGE_SIZE]]
        self.model.set_rows(rows)
        selected_index = 0
        if select_id:
            selected_index = next((i for i, row in enumerate(rows)
                                   if row.episode.stream_id == select_id), 0)
        if rows:
            model_index = self.model.index(selected_index)
            self.view.setCurrentIndex(model_index)
            self.view.scrollToTop()

    def _select_range(self, index: int):
        if index < 0:
            return
        if index == self.range_index and self.model.rows:
            return
        self.range_index = index
        self._fill_episodes()

    def _previous_range(self):
        if self.range_index > 0:
            self.range_combo.setCurrentIndex(self.range_index - 1)

    def _next_range(self):
        if self.range_index + 1 < self.range_combo.count():
            self.range_combo.setCurrentIndex(self.range_index + 1)

    # -- actions ------------------------------------------------------------------------------

    def _update_continue_button(self):
        target, resume, text = None, 0, ""
        last = next((e for e in self.ordered if e.stream_id == self._last_id), None) if self._last_id else None
        if last is not None:
            row = self._row(last)
            if row.resumable:
                target, resume = last, row.position
                text = (f"▶  Nastavi: sezona {last.season or '—'}, "
                        f"epizoda {last.episode or '—'} od {format_time(row.position)}")
            else:
                index = self.ordered.index(last)
                if index + 1 < len(self.ordered):
                    target = self.ordered[index + 1]
                    text = (f"▶  Pusti sledeću: sezona {target.season or '—'}, "
                            f"epizoda {target.episode or '—'}")
        if target is None and self.ordered:
            target = self.ordered[0]
            text = "▶  Pusti prvu epizodu"
        self._continue_target = (target, resume) if target is not None else None
        self.continue_btn.setVisible(target is not None)
        self.continue_btn.setText(text)

    def _continue(self):
        if self._continue_target:
            episode, resume = self._continue_target
            self.play_requested.emit(episode, self.ordered, resume)

    def _on_double_click(self, index: QModelIndex):
        """A double-click anywhere on an episode row starts playback."""
        row = index.data(Qt.ItemDataRole.UserRole) if index.isValid() else None
        if row:
            resume = row.position if row.resumable else 0
            self.play_requested.emit(row.episode, self.ordered, resume)

    def _on_action(self, key: str, row: EpisodeRow):
        if key == "resume":
            self.play_requested.emit(row.episode, self.ordered, row.position)
        elif key == "play":
            self.play_requested.emit(row.episode, self.ordered, 0)

    def _toggle_favorite(self):
        Database().toggle_series_favorite(self.series_key)
        self.refresh()
        self.changed.emit()
