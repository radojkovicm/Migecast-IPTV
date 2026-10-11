"""Category drop-down with pinned categories on top and hidden ones left out.

Used by the TV, movies and series pages. Pinned categories are listed right
after the fixed entries (favorites, all, ...) with a 📌 mark, in the order
they were pinned; hidden categories are not listed at all. The preferences
are stored per section ("tv", "vod", "series") in the database.
"""
from typing import Iterable, List, Optional, Sequence, Tuple

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox

from core.db_access import Database
from ui.widgets import button

PIN_MARK = "📌  "
SECTIONS = (("tv", "📺  TV kanali"), ("vod", "🎬  Filmovi"), ("series", "📺  Serije"))


class CategoryCombo(QComboBox):
    """``currentData()`` is the category name or one of the special keys."""

    prefs_changed = pyqtSignal(str)  # section
    rebuilt = pyqtSignal()  # list rebuilt (signals are blocked while rebuilding)

    def __init__(self, section: str, specials: Sequence[Tuple[str, str]], parent=None):
        super().__init__(parent)
        self.section = section
        self.specials = list(specials)  # (text, key)
        self.categories: List[str] = []
        self.pinned: List[str] = []
        self.hidden: set = set()
        self.setMaxVisibleItems(16)

    def current_key(self) -> Optional[str]:
        return self.currentData()

    def is_category(self, key: Optional[str]) -> bool:
        return bool(key) and key not in {k for _t, k in self.specials}

    def set_categories(self, categories: Iterable[str], default_key: Optional[str] = None):
        """Replace the category list (new playlist); keeps the selection if possible."""
        self.categories = sorted({c for c in categories if c}, key=str.lower)
        self.reload(default_key=default_key)

    def reload(self, default_key: Optional[str] = None):
        """Re-read pinned/hidden categories and rebuild the list."""
        previous = self.current_key()
        self.pinned, self.hidden = Database().get_category_prefs(self.section)
        known = set(self.categories)
        pinned = [c for c in self.pinned if c in known and c not in self.hidden]
        rest = [c for c in self.categories if c not in self.hidden and c not in set(pinned)]
        self.blockSignals(True)
        self.clear()
        for text, key in self.specials:
            self.addItem(text, key)
        for name in pinned:
            self.addItem(PIN_MARK + name, name)
        if pinned and rest:
            self.insertSeparator(self.count())
        for name in rest:
            self.addItem(name, name)
        index = self.findData(previous) if previous is not None else -1
        if index < 0 and default_key is not None:
            index = self.findData(default_key)
        self.setCurrentIndex(max(index, 0))
        self.blockSignals(False)
        self.rebuilt.emit()

    def visible(self, category: Optional[str]) -> bool:
        """Items without a category are always shown."""
        return not category or category not in self.hidden

    def is_pinned(self, name: str) -> bool:
        return name in self.pinned

    def toggle_pin(self):
        key = self.current_key()
        if not self.is_category(key):
            return
        Database().set_category_pinned(self.section, key, not self.is_pinned(key))
        self.reload()
        self.prefs_changed.emit(self.section)


def pin_button(combo: CategoryCombo, min_width: int = 170):
    """Button next to the combo that pins / unpins the selected category."""
    btn = button("📌  Zakači", "secondary", None, min_width)

    def update(_index=None):
        key = combo.current_key()
        is_category = combo.is_category(key)
        btn.setEnabled(is_category)
        pinned = is_category and combo.is_pinned(key)
        btn.setText("📌  Otkači" if pinned else "📌  Zakači")
        btn.setToolTip("Skloni ovu kategoriju sa vrha liste" if pinned
                       else "Prikaži ovu kategoriju na vrhu liste")

    btn.clicked.connect(combo.toggle_pin)
    combo.currentIndexChanged.connect(update)
    combo.rebuilt.connect(update)
    update()
    return btn
