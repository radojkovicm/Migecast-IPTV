import logging
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
                             QWidget, QLabel, QPushButton, QLineEdit, QCheckBox,
                             QComboBox, QFileDialog, QListWidget, QSpinBox,
                             QGroupBox, QMessageBox, QFormLayout, QProgressDialog,
                             QInputDialog)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from core.playlist_parser import PlaylistParser
from core.database import Database
from utils.config import Config

logger = logging.getLogger(__name__)


class PlaylistLoaderThread(QThread):
    """Thread for loading playlist in background"""
    
    finished = pyqtSignal(list, list, list)  # channels, vod_items, series_items
    error = pyqtSignal(str)
    progress = pyqtSignal(str)
    
    def __init__(self, playlist_type: str, **kwargs):
        super().__init__()
        self.playlist_type = playlist_type
        self.kwargs = kwargs
    
    def run(self):
        """Load playlist"""
        try:
            if self.playlist_type == 'm3u':
                file_path = self.kwargs.get('file_path', '')
                if not file_path:
                    raise ValueError("M3U file path is empty")
                
                self.progress.emit("Učitavanje M3U fajla...")
                channels, vod_items, series_items = PlaylistParser.parse_m3u_file(file_path)
                
            elif self.playlist_type == 'xtream':
                server = self.kwargs.get('server_url', '')
                username = self.kwargs.get('username', '')
                password = self.kwargs.get('password', '')
                
                if not all([server, username, password]):
                    raise ValueError("Xtream credentials are incomplete")
                
                self.progress.emit("Povezivanje sa Xtream serverom...")
                channels, vod_items, series_items = PlaylistParser.parse_xtream_codes(
                    server, username, password
                )
            else:
                raise ValueError(f"Unknown playlist type: {self.playlist_type}")
            
            # Validate results
            if not isinstance(channels, list):
                channels = []
            if not isinstance(vod_items, list):
                vod_items = []
            if not isinstance(series_items, list):
                series_items = []
            
            self.progress.emit("Obrada podataka...")
            logger.info(f"Playlist loaded: {len(channels)} channels, {len(vod_items)} VOD, {len(series_items)} series")
            self.finished.emit(channels, vod_items, series_items)
        
        except Exception as e:
            error_msg = f"{str(type(e).__name__)}: {str(e)}"
            logger.error(f"Error in PlaylistLoaderThread.run(): {error_msg}", exc_info=True)
            self.error.emit(error_msg)


class SettingsDialog(QDialog):
    """Settings dialog window"""
    
    playlist_added = pyqtSignal(list, list, list)  # channels, vod_items, series_items
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = Config()
        self.loader_thread = None
        self.progress_dialog = None
        self.init_ui()
        self.load_settings()
    
    def init_ui(self):
        """Initialize UI"""
        self.setWindowTitle("⚙ Podešavanja - MigeCast IPTV")
        self.setMinimumSize(800, 600)
        
        layout = QVBoxLayout(self)
        
        # Tab widget
        tab_widget = QTabWidget()
        tab_widget.setStyleSheet("font-size: 14pt;")
        
        # Playlists tab
        tab_widget.addTab(self.create_playlists_tab(), "📋 Upravljanje Listama")
        
        # Display tab
        tab_widget.addTab(self.create_display_tab(), "🖥 Prikaz")
        
        # Player tab
        tab_widget.addTab(self.create_player_tab(), "▶ Player")
        
        # About tab
        tab_widget.addTab(self.create_about_tab(), "ℹ O Programu")
        
        layout.addWidget(tab_widget)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        save_btn = QPushButton("💾 Sačuvaj")
        save_btn.setStyleSheet("font-size: 16pt; padding: 10px 30px;")
        save_btn.clicked.connect(self.save_settings)
        button_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("✖ Otkaži")
        cancel_btn.setStyleSheet("font-size: 16pt; padding: 10px 30px;")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def create_playlists_tab(self) -> QWidget:
        """Create playlists management tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # M3U File section
        m3u_group = QGroupBox("📄 Dodaj M3U Fajl")
        m3u_group.setStyleSheet("font-size: 14pt; font-weight: bold;")
        m3u_layout = QVBoxLayout(m3u_group)
        
        path_layout = QHBoxLayout()
        self.m3u_path_input = QLineEdit()
        self.m3u_path_input.setPlaceholderText("Putanja do M3U fajla...")
        self.m3u_path_input.setStyleSheet("font-size: 14pt; padding: 8px;")
        path_layout.addWidget(self.m3u_path_input)
        
        browse_btn = QPushButton("📁 Pretraži")
        browse_btn.setStyleSheet("font-size: 14pt; padding: 8px 15px;")
        browse_btn.clicked.connect(self.browse_m3u_file)
        path_layout.addWidget(browse_btn)
        
        m3u_layout.addLayout(path_layout)
        
        load_m3u_btn = QPushButton("✓ Učitaj M3U Listu")
        load_m3u_btn.setStyleSheet("font-size: 14pt; padding: 10px 20px; background-color: #4CAF50; color: white;")
        load_m3u_btn.clicked.connect(self.load_m3u_file)
        m3u_layout.addWidget(load_m3u_btn)
        
        layout.addWidget(m3u_group)
        
        # Xtream Codes section
        xtream_group = QGroupBox("🌐 Dodaj Xtream Codes")
        xtream_group.setStyleSheet("font-size: 14pt; font-weight: bold;")
        xtream_layout = QFormLayout(xtream_group)
        
        self.xtream_server_input = QLineEdit()
        self.xtream_server_input.setPlaceholderText("http://server.com:port")
        self.xtream_server_input.setStyleSheet("font-size: 14pt; padding: 8px;")
        xtream_layout.addRow("Server URL:", self.xtream_server_input)
        
        self.xtream_username_input = QLineEdit()
        self.xtream_username_input.setPlaceholderText("Korisničko ime")
        self.xtream_username_input.setStyleSheet("font-size: 14pt; padding: 8px;")
        xtream_layout.addRow("Username:", self.xtream_username_input)
        
        self.xtream_password_input = QLineEdit()
        self.xtream_password_input.setPlaceholderText("Lozinka")
        self.xtream_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.xtream_password_input.setStyleSheet("font-size: 14pt; padding: 8px;")
        xtream_layout.addRow("Password:", self.xtream_password_input)
        
        load_xtream_btn = QPushButton("✓ Učitaj Xtream Listu")
        load_xtream_btn.setStyleSheet("font-size: 14pt; padding: 10px 20px; background-color: #4CAF50; color: white;")
        load_xtream_btn.clicked.connect(self.load_xtream_codes)
        xtream_layout.addRow("", load_xtream_btn)
        
        layout.addWidget(xtream_group)
        
        layout.addStretch()
        
        return widget
    
    def create_display_tab(self) -> QWidget:
        """Create display settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Max channels
        channels_layout = QHBoxLayout()
        channels_label = QLabel("Maksimalan broj kanala:")
        channels_label.setStyleSheet("font-size: 14pt;")
        channels_layout.addWidget(channels_label)
        
        self.max_channels_combo = QComboBox()
        self.max_channels_combo.addItems(["500", "1000", "Sve"])
        self.max_channels_combo.setStyleSheet("font-size: 14pt; padding: 5px;")
        channels_layout.addWidget(self.max_channels_combo)
        channels_layout.addStretch()
        
        layout.addLayout(channels_layout)
        
        # Max VOD
        vod_layout = QHBoxLayout()
        vod_label = QLabel("Maksimalan broj VOD:")
        vod_label.setStyleSheet("font-size: 14pt;")
        vod_layout.addWidget(vod_label)
        
        self.max_vod_combo = QComboBox()
        self.max_vod_combo.addItems(["200", "500", "Sve"])
        self.max_vod_combo.setStyleSheet("font-size: 14pt; padding: 5px;")
        vod_layout.addWidget(self.max_vod_combo)
        vod_layout.addStretch()
        
        layout.addLayout(vod_layout)
        
        layout.addStretch()
        
        return widget
    
    def create_player_tab(self) -> QWidget:
        """Create player settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Auto-reconnect
        reconnect_layout = QHBoxLayout()
        reconnect_label = QLabel("Auto-reconnect pokušaji:")
        reconnect_label.setStyleSheet("font-size: 14pt;")
        reconnect_layout.addWidget(reconnect_label)
        
        self.reconnect_spin = QSpinBox()
        self.reconnect_spin.setMinimum(1)
        self.reconnect_spin.setMaximum(10)
        self.reconnect_spin.setValue(3)
        self.reconnect_spin.setStyleSheet("font-size: 14pt; padding: 5px;")
        reconnect_layout.addWidget(self.reconnect_spin)
        reconnect_layout.addStretch()
        
        layout.addLayout(reconnect_layout)
        
        # Hardware acceleration
        self.hw_accel_check = QCheckBox("✓ Omogući hardversku akceleraciju")
        self.hw_accel_check.setChecked(True)
        self.hw_accel_check.setStyleSheet("font-size: 14pt;")
        layout.addWidget(self.hw_accel_check)
        
        layout.addStretch()
        
        return widget
    
    def create_about_tab(self) -> QWidget:
        """Create about tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Logo/Title
        title_label = QLabel("📺 MigeCast IPTV")
        title_label.setStyleSheet("font-size: 28pt; font-weight: bold; color: #4CAF50;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Version
        version_label = QLabel("Verzija: 1.0.0")
        version_label.setStyleSheet("font-size: 16pt;")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)
        
        # Description
        desc_label = QLabel("Profesionalna IPTV aplikacija za Windows")
        desc_label.setStyleSheet("font-size: 14pt; color: #666;")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc_label)
        
        # Copyright
        copyright_label = QLabel("© 2025 Mige. Sva prava zadržana.")
        copyright_label.setStyleSheet("font-size: 12pt; color: #999; margin-top: 20px;")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(copyright_label)
        
        layout.addStretch()
        
        return widget
    
    def browse_m3u_file(self):
        """Browse for M3U file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Izaberite M3U fajl",
            "",
            "M3U Files (*.m3u *.m3u8 *.txt);;All Files (*)"
        )
        if file_path:
            self.m3u_path_input.setText(file_path)
    
    def load_m3u_file(self):
        """Load M3U file with progress dialog"""
        try:
            file_path = self.m3u_path_input.text().strip()
            
            if not file_path:
                QMessageBox.warning(self, "Greška", "Molimo izaberite M3U fajl.")
                return
            
            # Ask for playlist name
            playlist_name, ok = QInputDialog.getText(
                self,
                "Ime Playliste",
                "Unesite ime za ovu playlistu:",
                QLineEdit.EchoMode.Normal,
                "Moja IPTV Lista"
            )
            
            if not ok or not playlist_name.strip():
                logger.info("M3U file loading cancelled by user")
                return
            
            # Create progress dialog
            self.progress_dialog = QProgressDialog("Učitavanje kanala...", None, 0, 0, self)
            self.progress_dialog.setWindowTitle("Učitavanje")
            self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            self.progress_dialog.setMinimumDuration(0)
            self.progress_dialog.setCancelButton(None)
            self.progress_dialog.show()
            
            # Start loader thread
            self.loader_thread = PlaylistLoaderThread('m3u', file_path=file_path)
            self.loader_thread.progress.connect(self.on_loading_progress)
            self.loader_thread.finished.connect(lambda ch, vod, ser: self.on_playlist_loaded(playlist_name, 'm3u', ch, vod, ser, path=file_path))
            self.loader_thread.error.connect(self.on_loading_error)
            self.loader_thread.start()
            
            logger.info(f"Loading M3U file: {file_path}")
        except Exception as e:
            logger.error(f"Error in load_m3u_file: {e}", exc_info=True)
            QMessageBox.critical(self, "Greška", f"Greška pri učitavanju:\n{str(e)}")
    
    def load_xtream_codes(self):
        """Load Xtream Codes playlist with progress dialog"""
        try:
            server = self.xtream_server_input.text().strip()
            username = self.xtream_username_input.text().strip()
            password = self.xtream_password_input.text().strip()
            
            if not all([server, username, password]):
                QMessageBox.warning(self, "Greška", "Molimo popunite sva polja.")
                return
            
            # Ask for playlist name
            playlist_name, ok = QInputDialog.getText(
                self,
                "Ime Playliste",
                "Unesite ime za ovu playlistu:",
                QLineEdit.EchoMode.Normal,
                "Moja Xtream Lista"
            )
            
            if not ok or not playlist_name.strip():
                logger.info("Xtream loading cancelled by user")
                return
            
            # Create progress dialog
            self.progress_dialog = QProgressDialog("Povezivanje sa serverom...", None, 0, 0, self)
            self.progress_dialog.setWindowTitle("Učitavanje")
            self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            self.progress_dialog.setMinimumDuration(0)
            self.progress_dialog.setCancelButton(None)
            self.progress_dialog.show()
            
            # Start loader thread
            self.loader_thread = PlaylistLoaderThread('xtream', server_url=server, username=username, password=password)
            self.loader_thread.progress.connect(self.on_loading_progress)
            self.loader_thread.finished.connect(lambda ch, vod, ser: self.on_playlist_loaded(playlist_name, 'xtream', ch, vod, ser, url=server, username=username, password=password))
            self.loader_thread.error.connect(self.on_loading_error)
            self.loader_thread.start()
            
            logger.info(f"Loading Xtream Codes from: {server}")
        except Exception as e:
            logger.error(f"Error in load_xtream_codes: {e}", exc_info=True)
            QMessageBox.critical(self, "Greška", f"Greška pri učitavanju:\n{str(e)}")
    
    def on_loading_progress(self, message: str):
        """Update progress dialog"""
        if self.progress_dialog:
            self.progress_dialog.setLabelText(message)
    
    def on_playlist_loaded(self, name: str, playlist_type: str, channels: list, vod_items: list, series_items: list, **kwargs):
        """Handle playlist loaded"""
        try:
            if self.progress_dialog:
                self.progress_dialog.close()
            
            # Check if we got any data
            if not channels and not vod_items and not series_items:
                logger.warning("Playlist loaded but contains no data")
                QMessageBox.warning(self, "Greška", "Playlista je prazna ili nema dostupnih stavki.")
                return
            
            # Save to database
            db = Database()
            
            if playlist_type == 'm3u':
                # For M3U, use 'path' as 'url'
                db.save_playlist(
                    name=name,
                    playlist_type='M3U',
                    url=kwargs.get('path', '')
                )
            elif playlist_type == 'xtream':
                # For Xtream, use server, username, password
                db.save_playlist(
                    name=name,
                    playlist_type='Xtream',
                    server=kwargs.get('url', ''),
                    username=kwargs.get('username', ''),
                    password=kwargs.get('password', '')
                )
            
            # Emit signal first to update main window
            self.playlist_added.emit(channels, vod_items, series_items)
            
            # Show success message
            QMessageBox.information(
                self,
                "Uspešno Učitano",
                f"Playlista: {name}\n\n"
                f"✓ {len(channels)} kanala\n"
                f"✓ {len(vod_items)} filmova\n"
                f"✓ {len(series_items)} serija"
            )
            
            # Close dialog after message
            self.accept()
            
        except Exception as e:
            logger.error(f"Error in on_playlist_loaded: {e}", exc_info=True)
            QMessageBox.critical(self, "Greška", f"Greška pri sačuvavanju playliste:\n{str(e)}")
    
    def on_loading_error(self, error_message: str):
        """Handle loading error"""
        if self.progress_dialog:
            self.progress_dialog.close()
        
        logger.error(f"Failed to load playlist: {error_message}")
        QMessageBox.critical(self, "Greška", f"Greška pri učitavanju:\n\n{error_message}")
    
    def load_settings(self):
        """Load settings from config"""
        self.max_channels_combo.setCurrentText(self.config.get('display', 'max_channels', '500'))
        self.max_vod_combo.setCurrentText(self.config.get('display', 'max_vod', '200'))
        self.reconnect_spin.setValue(self.config.get('player', 'reconnect_attempts', 3))
        self.hw_accel_check.setChecked(self.config.get('player', 'hw_acceleration', True))
    
    def save_settings(self):
        """Save settings to config"""
        self.config.set('display', 'max_channels', self.max_channels_combo.currentText())
        self.config.set('display', 'max_vod', self.max_vod_combo.currentText())
        self.config.set('player', 'reconnect_attempts', self.reconnect_spin.value())
        self.config.set('player', 'hw_acceleration', self.hw_accel_check.isChecked())
        
        self.config.save()
        
        QMessageBox.information(self, "Uspeh", "Podešavanja su sačuvana.")
        self.accept()