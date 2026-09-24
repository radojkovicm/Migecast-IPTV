"""Shared widgets: buttons, loading overlay, toast and in-app dialogs.

All dialogs are frameless and drawn inside the main window, so the program
never shows old-style native Windows dialogs with title bars.
"""
from typing import Optional

from PyQt6.QtCore import QEvent, QEventLoop, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton,
                             QVBoxLayout, QWidget)


def button(text: str, role: str = "secondary", slot=None, min_width: int = 0) -> QPushButton:
    btn = QPushButton(text)
    btn.setProperty("role", role)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    if min_width:
        btn.setMinimumWidth(min_width)
    if slot:
        btn.clicked.connect(slot)
    return btn


def label(text: str = "", role: Optional[str] = None, wrap: bool = False) -> QLabel:
    lbl = QLabel(text)
    if role:
        lbl.setProperty("role", role)
    lbl.setWordWrap(wrap)
    return lbl


def repolish(widget: QWidget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class _CoverParent(QWidget):
    """Widget that always covers its parent (used for overlays)."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("Overlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        parent.installEventFilter(self)
        self.hide()

    def eventFilter(self, obj, event):
        if obj is self.parent() and event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self.setGeometry(self.parent().rect())
        return False

    def cover(self):
        self.setGeometry(self.parent().rect())
        self.raise_()
        self.show()


class LoadingOverlay(_CoverParent):
    """Large "Učitavam…" message with an indeterminate progress bar and an
    optional *Otkaži* (cancel) button. Blocks clicks on the page below."""

    cancel_requested = pyqtSignal()

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box = QFrame()
        box.setObjectName("OverlayBox")
        box.setMinimumWidth(620)
        inner = QVBoxLayout(box)
        inner.setContentsMargins(40, 36, 40, 36)
        inner.setSpacing(22)
        self.text = QLabel("Učitavam…")
        self.text.setObjectName("OverlayText")
        self.text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text.setWordWrap(True)
        self.detail = label("", "muted", wrap=True)
        self.detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(18)
        self.cancel_btn = button("✖  Otkaži", "danger", self.cancel_requested.emit, 220)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(self.cancel_btn)
        row.addStretch()
        inner.addWidget(self.text)
        inner.addWidget(self.detail)
        inner.addWidget(self.bar)
        inner.addLayout(row)
        layout.addWidget(box)
        self._show_timer = QTimer(self)
        self._show_timer.setSingleShot(True)
        self._show_timer.timeout.connect(self.cover)

    def start(self, text: str, cancellable: bool = True, delay_ms: int = 0):
        self.text.setText(text)
        self.detail.setText("")
        self.cancel_btn.setVisible(cancellable)
        self.cancel_btn.setEnabled(True)
        if delay_ms:
            self._show_timer.start(delay_ms)
        else:
            self.cover()

    def set_detail(self, text: str):
        self.detail.setText(text)

    def finish(self):
        self._show_timer.stop()
        self.hide()


class Toast(QFrame):
    """Short message at the bottom of the window that hides itself."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("Toast")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        self.text = QLabel()
        self.text.setWordWrap(True)
        layout.addWidget(self.text)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self.hide()

    def show_message(self, text: str, ms: int = 4500):
        self.text.setText(text)
        parent = self.parentWidget()
        width = min(900, parent.width() - 80)
        self.setFixedWidth(width)
        self.adjustSize()
        self.move((parent.width() - width) // 2, parent.height() - self.height() - 40)
        self.raise_()
        self.show()
        self._timer.start(ms)


class AppDialog(_CoverParent):
    """Frameless in-window message box. ``ask`` returns the chosen index."""

    def __init__(self, parent: QWidget, title: str, text: str, buttons, roles=None):
        super().__init__(parent)
        self._result = -1
        self._loop = None
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box = QFrame()
        box.setObjectName("DialogBox")
        box.setMinimumWidth(640)
        box.setMaximumWidth(900)
        inner = QVBoxLayout(box)
        inner.setContentsMargins(40, 32, 40, 32)
        inner.setSpacing(20)
        heading = label(title, "h2", wrap=True)
        body = label(text, wrap=True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        inner.addWidget(heading)
        inner.addWidget(body)
        row = QHBoxLayout()
        row.addStretch()
        roles = roles or ["primary"] + ["secondary"] * (len(buttons) - 1)
        for index, (text_, role) in enumerate(zip(buttons, roles)):
            row.addWidget(button(text_, role, lambda _=False, i=index: self._finish(i), 180))
        inner.addLayout(row)
        layout.addWidget(box)

    def _finish(self, index: int):
        self._result = index
        self.hide()
        if self._loop:
            self._loop.quit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._finish(-1)
        else:
            super().keyPressEvent(event)

    def exec_(self) -> int:
        self.cover()
        self.setFocus()
        self._loop = QEventLoop()
        self._loop.exec()
        self.deleteLater()
        return self._result


def info(parent: QWidget, title: str, text: str) -> None:
    AppDialog(parent.window(), title, text, ["U redu"]).exec_()


def ask(parent: QWidget, title: str, text: str, yes: str = "Da", no: str = "Ne", danger: bool = False) -> bool:
    roles = ["danger" if danger else "primary", "secondary"]
    return AppDialog(parent.window(), title, text, [yes, no], roles).exec_() == 0


def later(owner, msec: int, callback) -> None:
    """Run ``callback`` once after ``msec`` unless ``owner`` is deleted first.

    ``QTimer.singleShot(ms, lambda: ...)`` keeps firing after the widget is
    gone and then raises "wrapped C/C++ object has been deleted"."""
    timer = QTimer(owner)
    timer.setSingleShot(True)
    timer.timeout.connect(callback)
    timer.timeout.connect(timer.deleteLater)
    timer.start(msec)
