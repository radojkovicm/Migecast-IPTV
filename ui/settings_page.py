"""Settings shown as a page inside the main window."""
import logging
import os
import subprocess
import sys

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QApplication, QButtonGroup, QFileDialog, QFormLayout, QFrame, QHBoxLayout,
                             QLineEdit, QScrollArea, QSpinBox, QStackedWidget, QVBoxLayout, QWidget)

from core.m3u import detect_xtream_url, looks_like_url, normalize_server_url
from ui.widgets import button, label
from utils import paths, themes
from utils.config import Config
from version import __build_date__, __version__

logger = logging.getLogger(__name__)


def card(title: str) -> tuple:
    frame = QFrame()
    frame.setProperty("role", "card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(28, 22, 28, 24)
    layout.setSpacing(14)
    layout.addWidget(label(title, "h2"))
    return frame, layout


class SettingsPage(QWidget):
    load_requested = pyqtSignal(dict, str)  # source, name
    refresh_requested = pyqtSignal()
    theme_changed = pyqtSignal(str)
    import_requested = pyqtSignal(str)
    player_settings_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.config = Config()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        content = QWidget()
        content.setObjectName("Page")
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(60, 26, 60, 40)
        layout.setSpacing(22)

        self.welcome = label("", "h2", wrap=True)
        self.welcome.hide()
        layout.addWidget(self.welcome)

        # -- current list ------------------------------------------------------------
        frame, box = card("📋  Moja lista")
        self.current_info = label("Lista još nije dodata.", wrap=True)
        self.refresh_btn = button("🔄  Osveži listu", "primary", self.refresh_requested.emit, 260)
        row = QHBoxLayout()
        row.addWidget(self.current_info, 1)
        row.addWidget(self.refresh_btn)
        box.addLayout(row)
        layout.addWidget(frame)

        # -- add list ----------------------------------------------------------------
        frame, box = card("➕  Dodaj ili promeni listu")
        box.addWidget(label("Izaberite kako ste dobili listu od vašeg IPTV dobavljača:", "muted", wrap=True))
        mode_row = QHBoxLayout()
        self.mode_group = QButtonGroup(self)
        self.mode_stack = QStackedWidget()
        for index, text in enumerate(("🌐  Internet adresa (link)", "📁  Fajl sa računara", "🔑  Xtream nalog")):
            btn = button(text, "toggle")
            btn.setCheckable(True)
            self.mode_group.addButton(btn, index)
            mode_row.addWidget(btn)
        self.mode_group.idClicked.connect(self._set_mode)
        box.addLayout(mode_row)

        # URL
        url_page = QWidget()
        url_layout = QVBoxLayout(url_page)
        url_layout.setContentsMargins(0, 8, 0, 0)
        url_row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://…  (nalepite link liste)")
        self.url_input.textChanged.connect(self._on_url_changed)
        url_row.addWidget(self.url_input, 1)
        url_row.addWidget(button("📋  Nalepi", "secondary", self._paste, 180))
        url_layout.addLayout(url_row)
        self.url_hint = label("", "ok", wrap=True)
        url_layout.addWidget(self.url_hint)
        self.mode_stack.addWidget(url_page)

        # File
        file_page = QWidget()
        file_layout = QHBoxLayout(file_page)
        file_layout.setContentsMargins(0, 8, 0, 0)
        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText("Izaberite .m3u ili .m3u8 fajl")
        file_layout.addWidget(self.file_input, 1)
        file_layout.addWidget(button("📁  Izaberi fajl", "secondary", self._browse, 220))
        self.mode_stack.addWidget(file_page)

        # Xtream
        xtream_page = QWidget()
        form = QFormLayout(xtream_page)
        form.setContentsMargins(0, 8, 0, 0)
        form.setVerticalSpacing(12)
        form.setHorizontalSpacing(18)
        self.server_input = QLineEdit()
        self.server_input.setPlaceholderText("http://server.com:8080")
        self.user_input = QLineEdit()
        self.pass_input = QLineEdit()
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        show_row = QHBoxLayout()
        show_row.addWidget(self.pass_input, 1)
        self.show_pass = button("👁  Prikaži", "secondary", self._toggle_password, 170)
        show_row.addWidget(self.show_pass)
        form.addRow(label("Adresa servera:"), self.server_input)
        form.addRow(label("Korisničko ime:"), self.user_input)
        form.addRow(label("Lozinka:"), show_row)
        self.mode_stack.addWidget(xtream_page)
        box.addWidget(self.mode_stack)

        name_row = QHBoxLayout()
        name_row.addWidget(label("Naziv liste (nije obavezno):"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("npr. Moja lista")
        name_row.addWidget(self.name_input, 1)
        box.addLayout(name_row)
        self.error = label("", "error", wrap=True)
        self.error.hide()
        box.addWidget(self.error)
        load_row = QHBoxLayout()
        load_row.addStretch()
        load_row.addWidget(button("✓  Učitaj listu", "primary", self._submit, 300))
        box.addLayout(load_row)
        layout.addWidget(frame)
        self.mode_group.button(0).setChecked(True)

        # -- appearance --------------------------------------------------------------
        frame, box = card("🎨  Izgled")
        theme_row = QHBoxLayout()
        self.theme_group = QButtonGroup(self)
        for theme_id, name in themes.get_theme_names():
            btn = button(name, "toggle")
            btn.setCheckable(True)
            btn.setProperty("theme_id", theme_id)
            self.theme_group.addButton(btn)
            theme_row.addWidget(btn)
            if theme_id == self.config.get("appearance", "theme", "dark"):
                btn.setChecked(True)
        self.theme_group.buttonClicked.connect(lambda b: self._change_theme(b.property("theme_id")))
        box.addLayout(theme_row)
        layout.addWidget(frame)

        # -- player -----------------------------------------------------------------------
        frame, box = card("▶  Plejer")
        reconnect_row = QHBoxLayout()
        reconnect_row.addWidget(label("Broj pokušaja ponovnog povezivanja kad se slika prekine:"), 1)
        self.reconnect_spin = QSpinBox()
        self.reconnect_spin.setRange(0, 10)
        self.reconnect_spin.setValue(int(self.config.get("player", "reconnect_attempts", 3)))
        self.reconnect_spin.setMinimumWidth(120)
        self.reconnect_spin.valueChanged.connect(self._save_player)
        reconnect_row.addWidget(self.reconnect_spin)
        box.addLayout(reconnect_row)
        layout.addWidget(frame)

        # -- about / data -------------------------------------------------------------------
        frame, box = card("ℹ  O programu")
        box.addWidget(label(f"MigeCast IPTV  –  verzija {__version__}  (build {__build_date__})"))
        box.addWidget(label(f"Vaši podaci (lista, omiljeni, istorija gledanja) čuvaju se u:\n{paths.user_data_root()}",
                            "muted", wrap=True))
        data_row = QHBoxLayout()
        data_row.addWidget(button("📂  Otvori folder sa podacima", "secondary", self._open_data_folder))
        data_row.addWidget(button("⤓  Uvezi podatke iz stare verzije", "secondary", self._import_old))
        data_row.addStretch()
        box.addLayout(data_row)
        layout.addWidget(frame)
        layout.addStretch()

    # -- state ---------------------------------------------------------------------------------

    def set_current_playlist(self, playlist, counts=None):
        if not playlist:
            self.current_info.setText("Lista još nije dodata. Dodajte je ispod.")
            self.refresh_btn.setEnabled(False)
            return
        self.refresh_btn.setEnabled(True)
        text = f"<b>{playlist.get('name', '')}</b>"
        if counts:
            text += f"<br>{counts[0]} kanala · {counts[1]} filmova · {counts[2]} serija"
        refreshed = playlist.get("last_refreshed")
        if refreshed:
            text += f"<br>Poslednje osveženo: {refreshed.strftime('%d.%m.%Y %H:%M')}"
        self.current_info.setText(text)

    def show_welcome(self, visible: bool):
        self.welcome.setText("👋  Dobrodošli! Da biste gledali TV, filmove i serije, dodajte IPTV listu "
                             "koju ste dobili od dobavljača.")
        self.welcome.setVisible(visible)

    def show_error(self, message: str):
        self.error.setText(message)
        self.error.setVisible(bool(message))

    # -- input -------------------------------------------------------------------------------

    def _set_mode(self, index: int):
        self.mode_stack.setCurrentIndex(index)
        self.show_error("")

    def _paste(self):
        text = QApplication.clipboard().text().strip()
        if not text:
            self.show_error("U memoriji (clipboard) nema teksta. Prvo kopirajte link liste.")
            return
        self.url_input.setText(text)

    def _on_url_changed(self, text: str):
        account = detect_xtream_url(text.strip())
        if account:
            self.url_hint.setText("✓ Prepoznat je Xtream nalog – program će ga učitati kao Xtream (brže i sa više podataka).")
        elif text.strip() and not looks_like_url(text.strip()):
            self.url_hint.setText("")
            self.show_error("Link treba da počinje sa http:// ili https://")
            return
        else:
            self.url_hint.setText("")
        self.show_error("")

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Izaberite IPTV listu", os.path.expanduser("~"),
                                              "IPTV liste (*.m3u *.m3u8 *.txt);;Svi fajlovi (*)")
        if path:
            self.file_input.setText(path)

    def _toggle_password(self):
        hidden = self.pass_input.echoMode() == QLineEdit.EchoMode.Password
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Normal if hidden else QLineEdit.EchoMode.Password)
        self.show_pass.setText("🙈  Sakrij" if hidden else "👁  Prikaži")

    def _submit(self):
        from core.playlist_service import PlaylistError, default_name, source_from_user_input
        self.show_error("")
        mode = self.mode_stack.currentIndex()
        try:
            if mode == 0:
                source = source_from_user_input(self.url_input.text())
                if source["type"] == "M3U" and not looks_like_url(source["url"]):
                    raise PlaylistError("Unesite link koji počinje sa http:// ili https://")
            elif mode == 1:
                path = self.file_input.text().strip()
                if not path:
                    raise PlaylistError("Izaberite fajl sa listom.")
                source = {"type": "M3U", "url": path}
            else:
                server = normalize_server_url(self.server_input.text())
                user = self.user_input.text().strip()
                password = self.pass_input.text().strip()
                if not (server and user and password):
                    raise PlaylistError("Popunite adresu servera, korisničko ime i lozinku.")
                account = detect_xtream_url(server)
                if account:
                    server = account.server
                source = {"type": "Xtream", "server": server, "username": user, "password": password}
        except PlaylistError as exc:
            self.show_error(str(exc))
            return
        name = self.name_input.text().strip() or default_name(source)
        self.load_requested.emit(source, name)

    def clear_inputs(self):
        for widget in (self.url_input, self.file_input, self.server_input, self.user_input, self.pass_input,
                       self.name_input):
            widget.clear()

    def _change_theme(self, theme_id: str):
        self.config.set("appearance", "theme", theme_id)
        self.config.save()
        self.theme_changed.emit(theme_id)

    def _save_player(self):
        self.config.set("player", "reconnect_attempts", self.reconnect_spin.value())
        self.config.save()
        self.player_settings_changed.emit()

    def _open_data_folder(self):
        folder = str(paths.user_data_root())
        try:
            if sys.platform == "win32":
                os.startfile(folder)  # noqa: S606 - opens Explorer
            else:
                subprocess.Popen(["xdg-open", folder])
        except OSError as exc:
            self.show_error(f"Folder nije moguće otvoriti: {exc}")

    def _import_old(self):
        path, _ = QFileDialog.getOpenFileName(self, "Izaberite migecast.db iz stare verzije (folder data)",
                                              os.path.expanduser("~"), "MigeCast baza (migecast.db)")
        if path:
            self.import_requested.emit(path)
