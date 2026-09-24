"""Shared parts of the movie and series detail pages."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.widgets import label
from utils.image_cache import ImageLoader

POSTER_W, POSTER_H = 240, 360


def format_time(seconds: int) -> str:
    seconds = max(0, int(seconds or 0))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


class PosterLabel(QLabel):
    """Poster that loads asynchronously and shows a placeholder meanwhile."""

    def __init__(self, glyph: str = "🎬", width: int = POSTER_W, height: int = POSTER_H):
        super().__init__()
        self.glyph = glyph
        self.url = None
        self.setFixedSize(width, height)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setProperty("role", "poster")
        loader = ImageLoader.instance()
        loader.image_ready.connect(self._on_ready)

    def set_url(self, url):
        self.url = url
        pixmap = ImageLoader.instance().pixmap(url, self.width(), self.height()) if url else None
        self._show(pixmap)

    def _show(self, pixmap):
        if pixmap is not None and not pixmap.isNull():
            self.setText("")
            self.setPixmap(pixmap)
        else:
            self.setPixmap(QPixmap())
            self.setText(self.glyph)

    def _on_ready(self, url):
        if url == self.url:
            self._show(ImageLoader.instance().pixmap(url, self.width(), self.height()))


class DetailHeader(QWidget):
    """Poster on the left; title, meta line, plot and action buttons right."""

    def __init__(self, glyph: str):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(28)
        self.poster = PosterLabel(glyph)
        layout.addWidget(self.poster, 0, Qt.AlignmentFlag.AlignTop)
        right = QVBoxLayout()
        right.setSpacing(12)
        self.title = label("", "title", wrap=True)
        self.meta = label("", "muted", wrap=True)
        self.extra = label("", "muted", wrap=True)
        self.plot = label("", wrap=True)
        self.plot.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.plot.setMaximumHeight(150)
        self.buttons = QHBoxLayout()
        self.buttons.setSpacing(14)
        self.status = label("", "ok", wrap=True)
        right.addWidget(self.title)
        right.addWidget(self.meta)
        right.addWidget(self.extra)
        right.addWidget(self.plot)
        right.addSpacing(8)
        right.addWidget(self.status)
        right.addLayout(self.buttons)
        right.addStretch(1)
        layout.addLayout(right, 1)
        self.plot.setMinimumHeight(0)

    def set_info(self, title, meta_parts, extra, plot, cover):
        self.title.setText(title)
        self.meta.setText("   ·   ".join(p for p in meta_parts if p))
        self.extra.setText(extra or "")
        self.extra.setVisible(bool(extra))
        self.plot.setText(plot or "Opis nije dostupan.")
        self.poster.set_url(cover)


def separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedHeight(2)
    return line
