"""Settings card: choose which categories are shown and which are pinned on top.

For every section (TV, movies, series) the list shows all categories of the
current playlist with a *Prikaži* check box and a *Na vrhu* (pinned) toggle.
*Sakrij sve* hides every category so the user can then tick only the few
they want to keep. Categories that appear later (new provider categories)
are shown until the user hides them.
"""
from typing import Dict, List

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (QButtonGroup, QCheckBox, QHBoxLayout, QLineEdit, QListWidget,
                             QListWidgetItem, QVBoxLayout, QWidget)

from core.db_access import Database
from ui.category_combo import SECTIONS
from ui.widgets import button, label

ROW_HEIGHT = 72


class _CategoryRow(QWidget):
    def __init__(self, name: str, shown: bool, pinned: bool, on_shown, on_pinned):
        super().__init__()
        self.name = name
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 6, 12, 6)
        layout.setSpacing(12)
        self.check = QCheckBox(name)
        self.check.setChecked(shown)
        self.check.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check.toggled.connect(lambda checked: on_shown(name, checked))
        self.pin = button("", "toggle", None, 190)
        self.pin.setCheckable(True)
        self.pin.setStyleSheet("QPushButton { min-height: 0; padding: 4px 16px; }")
        self.pin.setFixedHeight(ROW_HEIGHT - 20)
        self.pin.setChecked(pinned)
        self.pin.toggled.connect(lambda checked: on_pinned(name, checked))
        self.pin.toggled.connect(self._update_pin_text)
        self._update_pin_text(pinned)
        layout.addWidget(self.check, 1)
        layout.addWidget(self.pin)

    def _update_pin_text(self, pinned: bool):
        self.pin.setText("📌  Na vrhu" if pinned else "Zakači na vrh")


class CategorySettings(QWidget):
    changed = pyqtSignal(str)  # section

    def __init__(self, parent=None):
        super().__init__(parent)
        self.categories: Dict[str, List[str]] = {key: [] for key, _name in SECTIONS}
        self.section = SECTIONS[0][0]
        self.rows: Dict[str, _CategoryRow] = {}
        self._loaded = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(label(
            "Zakačene kategorije (📌) prikazuju se na vrhu liste kategorija. Kategorije bez kvačice "
            "se ne prikazuju, ni u spisku ni pod „Sve“. Omiljeni i „Nastavi gledanje“ uvek prikazuju sve.",
            "muted", wrap=True))

        section_row = QHBoxLayout()
        self.section_group = QButtonGroup(self)
        for index, (key, name) in enumerate(SECTIONS):
            btn = button(name, "toggle")
            btn.setCheckable(True)
            btn.setProperty("section", key)
            self.section_group.addButton(btn, index)
            section_row.addWidget(btn)
        self.section_group.button(0).setChecked(True)
        self.section_group.idClicked.connect(lambda index: self.show_section(SECTIONS[index][0]))
        layout.addLayout(section_row)

        tools = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍  Pronađi kategoriju…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_search)
        tools.addWidget(self.search, 1)
        self.show_all_btn = button("☑  Prikaži sve", "secondary", lambda: self._set_all(True), 210)
        self.hide_all_btn = button("☐  Sakrij sve", "secondary", lambda: self._set_all(False), 210)
        tools.addWidget(self.show_all_btn)
        tools.addWidget(self.hide_all_btn)
        layout.addLayout(tools)

        self.summary = label("", "ok", wrap=True)
        layout.addWidget(self.summary)
        self.list = QListWidget()
        self.list.setObjectName("CategoryList")
        self.list.setMinimumHeight(ROW_HEIGHT * 6)
        self.list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list.verticalScrollBar().setSingleStep(30)
        self.list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        layout.addWidget(self.list)
        self._update_summary()

    # -- data ------------------------------------------------------------------------------

    def set_categories(self, categories: Dict[str, List[str]]):
        """Categories of the loaded playlist per section ("tv", "vod", "series")."""
        self.categories = {key: list(categories.get(key, [])) for key, _name in SECTIONS}
        self._loaded = True
        self.show_section(self.section)

    def reload(self):
        """Re-read the preferences (pins may have changed on a catalog page)."""
        if self._loaded:
            self.show_section(self.section)

    def show_section(self, section: str):
        self.section = section
        for btn in self.section_group.buttons():
            btn.setChecked(btn.property("section") == section)
        names = self.categories.get(section, [])
        pinned, hidden = Database().get_category_prefs(section) if names else ([], set())
        order = [n for n in pinned if n in set(names)]
        order += [n for n in names if n not in set(order)]
        self.list.setUpdatesEnabled(False)
        self.list.clear()
        self.rows = {}
        for name in order:
            row = _CategoryRow(name, name not in hidden, name in pinned, self._on_shown, self._on_pinned)
            item = QListWidgetItem(self.list)
            item.setSizeHint(QSize(0, ROW_HEIGHT))
            self.list.setItemWidget(item, row)
            self.rows[name] = row
        self.list.setUpdatesEnabled(True)
        self.show_all_btn.setEnabled(bool(names))
        self.hide_all_btn.setEnabled(bool(names))
        self.search.setEnabled(bool(names))
        self._apply_search()
        self._update_summary()

    # -- actions ----------------------------------------------------------------------------

    def _apply_search(self):
        words = self.search.text().strip().lower().split()
        for index in range(self.list.count()):
            item = self.list.item(index)
            name = self.list.itemWidget(item).name.lower()
            item.setHidden(bool(words) and not all(w in name for w in words))

    def _on_shown(self, name: str, shown: bool):
        Database().set_categories_hidden(self.section, [name], not shown)
        self._update_summary()
        self.changed.emit(self.section)

    def _on_pinned(self, name: str, pinned: bool):
        Database().set_category_pinned(self.section, name, pinned)
        self._update_summary()
        self.changed.emit(self.section)

    def _set_all(self, shown: bool):
        names = self.categories.get(self.section, [])
        if not names:
            return
        Database().set_categories_hidden(self.section, names, not shown)
        for row in self.rows.values():
            row.check.blockSignals(True)
            row.check.setChecked(shown)
            row.check.blockSignals(False)
        self._update_summary()
        self.changed.emit(self.section)

    def _update_summary(self):
        total = len(self.rows)
        if not total:
            self.summary.setText("Nema kategorija. Prvo učitajte listu." if not self._loaded
                                 else "Ova lista nema kategorija u ovom delu.")
            return
        shown = sum(1 for row in self.rows.values() if row.check.isChecked())
        pinned = sum(1 for row in self.rows.values() if row.pin.isChecked())
        self.summary.setText(f"Prikazano {shown} od {total} kategorija  ·  zakačeno na vrh: {pinned}")
