"""Live TV channel list (model/view: fast with thousands of channels)."""
import logging
from typing import List

from PyQt6.QtCore import QAbstractListModel, QEvent, QModelIndex, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import (QAbstractItemView, QComboBox, QLineEdit, QListView, QStyle,
                             QStyledItemDelegate, QVBoxLayout, QWidget)

from core.db_access import Database
from models.channel import Channel
from ui.widgets import label
from utils import themes
from utils.image_cache import ImageLoader

logger = logging.getLogger(__name__)

ROW_H = 76
STAR_W = 64
FAVORITES = "⭐  Omiljeni kanali"
ALL = "📺  Svi kanali"


class ChannelModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.channels: List[Channel] = []
        self.favorites = set()
        self.playing_id = None
        self._rows_by_url = {}
        ImageLoader.instance().image_ready.connect(self._on_image)

    def set_channels(self, channels, favorites):
        self.beginResetModel()
        self.channels = channels
        self.favorites = favorites
        self._rows_by_url = {}
        for row, channel in enumerate(channels):
            if channel.logo:
                self._rows_by_url.setdefault(channel.logo, []).append(row)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.channels)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        channel = self.channels[index.row()]
        if role == Qt.ItemDataRole.UserRole:
            return channel
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return channel.name
        return None

    def _on_image(self, url):
        for row in self._rows_by_url.get(url, ()):
            idx = self.index(row)
            self.dataChanged.emit(idx, idx)

    def update_all(self):
        if self.channels:
            self.dataChanged.emit(self.index(0), self.index(len(self.channels) - 1))


class ChannelDelegate(QStyledItemDelegate):
    favorite_clicked = pyqtSignal(object)

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), ROW_H)

    def paint(self, painter: QPainter, option, index):
        channel: Channel = index.data(Qt.ItemDataRole.UserRole)
        model: ChannelModel = index.model()
        t = themes.current()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(option.rect).adjusted(4, 3, -4, -3)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        playing = channel.channel_id == model.playing_id
        background = t["accent"] if (selected or playing) else (t["hover"] if hovered else t["surface"])
        text_color = t["accent_text"] if (selected or playing) else t["text"]
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(background))
        painter.drawRoundedRect(rect, 12, 12)

        logo = QRectF(rect.x() + 10, rect.y() + 8, 88, rect.height() - 16)
        pixmap = ImageLoader.instance().pixmap(channel.logo, int(logo.width()), int(logo.height())) if channel.logo else None
        if pixmap is not None and not pixmap.isNull():
            painter.drawPixmap(int(logo.x() + (logo.width() - pixmap.width()) / 2),
                               int(logo.y() + (logo.height() - pixmap.height()) / 2), pixmap)
        else:
            glyph = QFont(painter.font())
            glyph.setPointSize(22)
            painter.setFont(glyph)
            painter.setPen(QColor(text_color))
            painter.drawText(logo, Qt.AlignmentFlag.AlignCenter, "📺")

        name_font = QFont(painter.font())
        name_font.setPointSize(15)
        name_font.setBold(True)
        painter.setFont(name_font)
        painter.setPen(QColor(text_color))
        text_rect = QRectF(logo.right() + 14, rect.y(), rect.width() - logo.width() - STAR_W - 40, rect.height())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         painter.fontMetrics().elidedText(("▶ " if playing else "") + channel.name,
                                                          Qt.TextElideMode.ElideRight, int(text_rect.width())))

        star_rect = self.star_rect(option.rect)
        star_font = QFont(painter.font())
        star_font.setPointSize(22)
        painter.setFont(star_font)
        is_favorite = channel.channel_id in model.favorites
        painter.setPen(QColor(t["star"] if is_favorite else (text_color if hovered or selected else t["muted"])))
        painter.drawText(star_rect, Qt.AlignmentFlag.AlignCenter, "★" if is_favorite else "☆")
        painter.restore()

    @staticmethod
    def star_rect(rect) -> QRectF:
        return QRectF(rect.right() - STAR_W - 6, rect.y(), STAR_W, rect.height())

    def editorEvent(self, event, model, option, index):
        if event.type() == QEvent.Type.MouseButtonRelease and self.star_rect(option.rect).contains(event.position()):
            self.favorite_clicked.emit(index.data(Qt.ItemDataRole.UserRole))
            return True
        if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick) and \
                self.star_rect(option.rect).contains(event.position()):
            return True
        return super().editorEvent(event, model, option, index)


class LiveTVWidget(QWidget):
    channel_selected = pyqtSignal(Channel)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.all_channels: List[Channel] = []
        self.db = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 8, 8)
        layout.setSpacing(10)
        self.category = QComboBox()
        self.category.setMaxVisibleItems(14)
        self.category.currentIndexChanged.connect(lambda _: self.filter_channels())
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍  Pretražite kanale…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _: self._debounce.start(200))
        self.view = QListView()
        self.view.setUniformItemSizes(True)
        self.view.setMouseTracking(True)
        self.view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.view.verticalScrollBar().setSingleStep(30)
        self.view.setCursor(Qt.CursorShape.PointingHandCursor)
        self.model = ChannelModel(self)
        self.delegate = ChannelDelegate(self.view)
        self.delegate.favorite_clicked.connect(self.toggle_favorite)
        self.view.setModel(self.model)
        self.view.setItemDelegate(self.delegate)
        self.view.clicked.connect(self._on_clicked)
        self.empty = label("", "muted", wrap=True)
        self.empty.hide()
        layout.addWidget(self.category)
        layout.addWidget(self.search)
        layout.addWidget(self.empty)
        layout.addWidget(self.view, 1)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self.filter_channels)

    def load_channels(self, channels: List[Channel]):
        self.db = Database()
        self.all_channels = channels
        categories = sorted({c.category for c in channels if c.category}, key=str.lower)
        favorites = self.db.get_favorite_channel_ids()
        self.category.blockSignals(True)
        self.category.clear()
        self.category.addItems([FAVORITES, ALL] + categories)
        self.category.setCurrentText(FAVORITES if favorites else ALL)
        self.category.blockSignals(False)
        self.filter_channels()

    def filter_channels(self):
        favorites = self.db.get_favorite_channel_ids() if self.db else set()
        choice = self.category.currentText()
        if choice == FAVORITES:
            channels = [c for c in self.all_channels if c.channel_id in favorites]
        elif choice == ALL or not choice:
            channels = self.all_channels
        else:
            channels = [c for c in self.all_channels if c.category == choice]
        words = self.search.text().strip().lower().split()
        if words:
            channels = [c for c in channels if all(w in c.name.lower() for w in words)]
        ImageLoader.instance().cancel_queued()
        self.model.set_channels(channels, favorites)
        if not channels:
            self.empty.setText("Nema omiljenih kanala. Kliknite ☆ pored kanala da ga dodate."
                               if choice == FAVORITES and not words else "Nema kanala za ovu pretragu.")
            self.empty.show()
        else:
            self.empty.hide()

    def toggle_favorite(self, channel: Channel):
        if not self.db:
            return
        self.db.toggle_channel_favorite(channel.channel_id, channel.name)
        self.model.favorites = self.db.get_favorite_channel_ids()
        if self.category.currentText() == FAVORITES:
            self.filter_channels()
        else:
            self.model.update_all()

    def _on_clicked(self, index):
        channel = index.data(Qt.ItemDataRole.UserRole)
        if channel:
            self.set_playing(channel)
            self.channel_selected.emit(channel)

    def set_playing(self, channel):
        self.model.playing_id = channel.channel_id if channel else None
        self.model.update_all()

    def _step(self, delta: int):
        count = self.model.rowCount()
        if not count:
            return
        current = self.view.currentIndex().row()
        row = (current + delta) % count if current >= 0 else 0
        index = self.model.index(row)
        self.view.setCurrentIndex(index)
        self.view.scrollTo(index)
        self._on_clicked(index)

    def select_next_channel(self):
        self._step(1)

    def select_previous_channel(self):
        self._step(-1)

    def cleanup(self):
        pass
