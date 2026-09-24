"""Poster grid (movies and series) implemented with model/view.

Painting a few visible cards with a delegate is much cheaper than creating a
QWidget per movie: scrolling stays smooth with tens of thousands of items and
posters are requested only for cards that are actually painted.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional

from PyQt6.QtCore import QAbstractListModel, QModelIndex, QRect, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QAbstractItemView, QListView, QStyle, QStyledItemDelegate

from utils import themes
from utils.image_cache import ImageLoader

CARD_W, CARD_H = 224, 386
POSTER_H = 300
GRID = QSize(CARD_W + 18, CARD_H + 18)


@dataclass
class PosterItem:
    key: str
    title: str
    image: Optional[str] = None
    subtitle: str = ""
    favorite: bool = False
    progress: float = -1.0   # 0..1, -1 = none
    watched: bool = False
    glyph: str = "🎬"
    payload: object = None


class PosterModel(QAbstractListModel):
    ItemRole = Qt.ItemDataRole.UserRole + 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items: List[PosterItem] = []
        self._rows_by_url: Dict[str, List[int]] = {}
        loader = ImageLoader.instance()
        loader.image_ready.connect(self._on_image)
        loader.image_failed.connect(self._on_image)

    def set_items(self, items: List[PosterItem]):
        self.beginResetModel()
        self.items = items
        self._rows_by_url = {}
        for row, item in enumerate(items):
            if item.image:
                self._rows_by_url.setdefault(item.image, []).append(row)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.items)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        item = self.items[index.row()]
        if role == self.ItemRole:
            return item
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return item.title
        return None

    def item_at(self, row: int) -> Optional[PosterItem]:
        return self.items[row] if 0 <= row < len(self.items) else None

    def refresh_rows(self, predicate):
        for row, item in enumerate(self.items):
            if predicate(item):
                idx = self.index(row)
                self.dataChanged.emit(idx, idx)

    def _on_image(self, url: str):
        for row in self._rows_by_url.get(url, ()):
            idx = self.index(row)
            self.dataChanged.emit(idx, idx)


def _rounded(rect: QRectF, radius: float) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path


class PosterDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QSize(CARD_W, CARD_H)

    def paint(self, painter: QPainter, option, index):
        item: PosterItem = index.data(PosterModel.ItemRole)
        if item is None:
            return
        t = themes.current()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        cell = option.rect
        card = QRectF(cell.x() + (cell.width() - CARD_W) / 2, cell.y() + 6, CARD_W, CARD_H - 12)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)

        painter.setPen(QPen(QColor(t["accent"] if (hovered or selected) else t["border"]), 4 if hovered else 1.5))
        painter.setBrush(QColor(t["surface"]))
        painter.drawPath(_rounded(card, 14))

        poster = QRectF(card.x() + 8, card.y() + 8, card.width() - 16, POSTER_H - 16)
        painter.save()
        painter.setClipPath(_rounded(poster, 10))
        painter.fillRect(poster, QColor(t["surface2"]))
        pixmap = ImageLoader.instance().pixmap(item.image, int(poster.width()), int(poster.height())) if item.image else None
        if pixmap is not None and not pixmap.isNull():
            x = poster.x() + (poster.width() - pixmap.width()) / 2
            y = poster.y() + (poster.height() - pixmap.height()) / 2
            painter.drawPixmap(int(x), int(y), pixmap)
        else:
            glyph_font = QFont(painter.font())
            glyph_font.setPointSize(48)
            painter.setFont(glyph_font)
            painter.setPen(QColor(t["muted"]))
            painter.drawText(poster, Qt.AlignmentFlag.AlignCenter, item.glyph)
        if item.progress >= 0:
            bar = QRectF(poster.x(), poster.bottom() - 10, poster.width(), 10)
            painter.fillRect(bar, QColor(0, 0, 0, 160))
            painter.fillRect(QRectF(bar.x(), bar.y(), bar.width() * min(1.0, item.progress), bar.height()),
                             QColor(t["accent"]))
        painter.restore()

        if item.favorite:
            badge = QRectF(poster.right() - 48, poster.y() + 8, 40, 40)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, 190))
            painter.drawEllipse(badge)
            star_font = QFont(painter.font())
            star_font.setPointSize(18)
            painter.setFont(star_font)
            painter.setPen(QColor(t["star"]))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, "★")
        if item.watched:
            badge = QRectF(poster.x() + 8, poster.y() + 8, 40, 40)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(t["accent"]))
            painter.drawEllipse(badge)
            check_font = QFont(painter.font())
            check_font.setPointSize(16)
            check_font.setBold(True)
            painter.setFont(check_font)
            painter.setPen(QColor(t["accent_text"]))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, "✓")

        text_rect = QRectF(card.x() + 12, poster.bottom() + 10, card.width() - 24, card.bottom() - poster.bottom() - 16)
        title_font = QFont(painter.font())
        title_font.setPointSize(13)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QColor(t["text"]))
        metrics = painter.fontMetrics()
        lines = _wrap(item.title, metrics, int(text_rect.width()), 2)
        y = text_rect.y()
        for line in lines:
            painter.drawText(QRectF(text_rect.x(), y, text_rect.width(), metrics.height()),
                             Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, line)
            y += metrics.height()
        if item.subtitle:
            sub_font = QFont(painter.font())
            sub_font.setPointSize(11)
            sub_font.setBold(False)
            painter.setFont(sub_font)
            painter.setPen(QColor(t["muted"]))
            painter.drawText(QRectF(text_rect.x(), y + 2, text_rect.width(), painter.fontMetrics().height()),
                             Qt.AlignmentFlag.AlignHCenter, painter.fontMetrics().elidedText(
                                 item.subtitle, Qt.TextElideMode.ElideRight, int(text_rect.width())))
        painter.restore()


def _wrap(text: str, metrics, width: int, max_lines: int) -> List[str]:
    words = (text or "").split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if metrics.horizontalAdvance(candidate) <= width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
            if len(lines) == max_lines - 1:
                break
    remaining = words[len(" ".join(lines + [current]).split()):]
    if remaining:
        current = f"{current} {' '.join(remaining)}"
    if current:
        lines.append(current)
    lines = lines[:max_lines]
    return [metrics.elidedText(line, Qt.TextElideMode.ElideRight, width) for line in lines]


class PosterGridView(QListView):
    item_activated = pyqtSignal(object)  # PosterItem

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setUniformItemSizes(True)
        self.setGridSize(GRID)
        self.setSpacing(0)
        self.setWrapping(True)
        self.setMouseTracking(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.verticalScrollBar().setSingleStep(40)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setLayoutMode(QListView.LayoutMode.Batched)
        self.setBatchSize(200)
        self.setItemDelegate(PosterDelegate(self))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(self._emit)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.currentIndex().isValid():
            self._emit(self.currentIndex())
            return
        super().keyPressEvent(event)

    def _emit(self, index):
        item = index.data(PosterModel.ItemRole)
        if item is not None:
            self.item_activated.emit(item)
