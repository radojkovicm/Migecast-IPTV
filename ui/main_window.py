import logging
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                    QTabWidget, QPushButton, QLabel, QStatusBar, QMessageBox)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut
from core.video_player import VideoPlayer
from core.database import Database
from ui.settings_dialog import SettingsDialog
from models.channel import Channel
from models.vod_item import VODItem
from models.series_item import SeriesItem

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self, video_player: VideoPlayer):
        super().__init__()
        self.video_player = video_player
        self.db = Database()
        self.current_playlist_data = None
        
        from ui.player_widget import PlayerWidget
        from ui.live_tv_widget import LiveTVWidget
        from ui.vod_widget import VODWidget
        from ui.series_widget import SeriesWidget
        
        self.PlayerWidget = PlayerWidget
        self.LiveTVWidget = LiveTVWidget
        self.VODWidget = VODWidget
        self.SeriesWidget = SeriesWidget
        
        self.init_ui()
        self.setup_shortcuts()
        
        QTimer.singleShot(100, self.check_saved_playlist)
    
    def init_ui(self):
        """Initialize UI"""
        self.setWindowTitle("MigeCast IPTV")
        self.setMinimumSize(1280, 720)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Top bar
        top_bar = QWidget()
        top_bar.setStyleSheet("background-color: #1e1e1e; padding: 10px;")
        top_bar_layout = QHBoxLayout(top_bar)
        
        title_label = QLabel("📺 MigeCast IPTV")
        title_label.setStyleSheet("font-size: 20pt; font-weight: bold; color: white;")
        top_bar_layout.addWidget(title_label)
        
        top_bar_layout.addStretch()
        
        settings_btn = QPushButton("⚙️ Podešavanja")
        settings_btn.setStyleSheet("font-size: 14pt; padding: 8px 16px; background-color: #333; color: white; border: none;")
        settings_btn.clicked.connect(self.show_settings)
        top_bar_layout.addWidget(settings_btn)
        
        main_layout.addWidget(top_bar)
        
        # Content area
        content_layout = QHBoxLayout()
        
        # Left side: Tabs
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("font-size: 14pt;")
        
        # Live TV tab
        self.live_tv_widget = self.LiveTVWidget()
        self.live_tv_widget.channel_selected.connect(self.play_channel)
        self.tab_widget.addTab(self.live_tv_widget, "📺 TV")
        
        # VOD (Movies) tab
        self.vod_widget = self.VODWidget()
        self.vod_widget.vod_selected.connect(self.play_vod)
        self.tab_widget.addTab(self.vod_widget, "🎬 Filmovi")
        
        # Series tab
        self.series_widget = self.SeriesWidget()
        self.series_widget.series_selected.connect(self.play_series)
        self.tab_widget.addTab(self.series_widget, "📺 Serije")
        
        # Connect tab change signal
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        
        content_layout.addWidget(self.tab_widget, stretch=1)
        
        # Right side: Video player
        self.player_widget = self.PlayerWidget(self.video_player)
        self.player_widget.setMinimumWidth(640)
        
        self.player_widget.previous_requested.connect(self.play_previous)
        self.player_widget.next_requested.connect(self.play_next)
        
        content_layout.addWidget(self.player_widget, stretch=2)
        
        main_layout.addLayout(content_layout)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Spremno")
        
        logger.info("Main window initialized")
    
    def on_tab_changed(self, index: int):
        """Handle tab change - show/hide player based on tab"""
        # Index 0 = TV, 1 = Filmovi, 2 = Serije
        if index == 0:
            # TV tab - show player, limit tab width
            self.player_widget.show()
            self.tab_widget.setMaximumWidth(500)
        else:
            # Filmovi/Serije - hide player, expand tabs to full width
            self.player_widget.hide()
            self.tab_widget.setMaximumWidth(16777215)  # Qt max value (no limit)
        
        logger.debug(f"Tab changed to index {index}, player visible: {index == 0}")
    
    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        fullscreen_shortcut = QShortcut(QKeySequence(Qt.Key.Key_F11), self)
        fullscreen_shortcut.activated.connect(self.player_widget.toggle_fullscreen)
        
        play_pause_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        play_pause_shortcut.activated.connect(self.player_widget.toggle_play_pause)
        
        next_shortcut = QShortcut(QKeySequence(Qt.Key.Key_PageDown), self)
        next_shortcut.activated.connect(self.play_next)
        
        prev_shortcut = QShortcut(QKeySequence(Qt.Key.Key_PageUp), self)
        prev_shortcut.activated.connect(self.play_previous)
        
        esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        esc_shortcut.activated.connect(self.player_widget.exit_fullscreen)
        
        logger.info("Keyboard shortcuts configured")
    
    def check_saved_playlist(self):
        """Check if there's a saved playlist to load"""
        saved_playlist = self.db.get_last_playlist()
        if saved_playlist:
            playlist_name = saved_playlist.get('name', 'Unknown')
            logger.info(f"Loading saved playlist: {playlist_name}")
            self.status_bar.showMessage(f"Učitavanje liste: {playlist_name}...")
            QTimer.singleShot(100, lambda: self.load_saved_playlist(saved_playlist))
        else:
            QTimer.singleShot(500, self.show_welcome_dialog)
    
    def load_saved_playlist(self, saved_playlist: dict):
        """Load saved playlist"""
        try:
            from core.playlist_parser import PlaylistParser
            
            if saved_playlist.get('type') == 'M3U':
                url = saved_playlist.get('url', '')
                if not url:
                    logger.warning("M3U URL is empty")
                    self.show_welcome_dialog()
                    return
                channels, vod_items, series_items = PlaylistParser.parse_m3u_file(url)
            elif saved_playlist.get('type') == 'Xtream':
                server = saved_playlist.get('server', '')
                username = saved_playlist.get('username', '')
                password = saved_playlist.get('password', '')
                if not all([server, username, password]):
                    logger.warning("Xtream credentials incomplete")
                    self.show_welcome_dialog()
                    return
                channels, vod_items, series_items = PlaylistParser.parse_xtream_codes(server, username, password)
            else:
                logger.warning(f"Unknown playlist type: {saved_playlist.get('type')}")
                self.show_welcome_dialog()
                return
            
            if not channels and not vod_items and not series_items:
                logger.warning("Playlist loaded but contains no data")
                self.status_bar.showMessage("Lista je prazna ili nije mogla biti učitana")
                QTimer.singleShot(2000, self.show_welcome_dialog)
                return
            
            self.current_playlist_data = {
                'channels': channels,
                'vod_items': vod_items,
                'series_items': series_items
            }
            
            self.live_tv_widget.load_channels(channels)
            self.vod_widget.load_vod_items(vod_items)
            self.series_widget.load_series_items(series_items)
            
            self.status_bar.showMessage(f"Lista učitana: {len(channels)} kanala, {len(vod_items)} filmova, {len(series_items)} serija")
            logger.info(f"Successfully loaded playlist with {len(channels)} channels, {len(vod_items)} VOD items, {len(series_items)} series")
            
        except Exception as e:
            logger.error(f"Failed to load saved playlist: {e}", exc_info=True)
            self.status_bar.showMessage("Greška pri učitavanju liste")
            QMessageBox.warning(self, "Greška", f"Greška pri učitavanju liste:\n{str(e)}")
            QTimer.singleShot(2000, self.show_welcome_dialog)
    
    def show_welcome_dialog(self):
        """Show welcome dialog"""
        msg = QMessageBox(self)
        msg.setWindowTitle("Dobrodošli u MigeCast IPTV")
        msg.setText("Dobrodošli!\n\nDa biste počeli, dodajte IPTV listu preko Podešavanja.")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.exec()
        QTimer.singleShot(200, self.show_settings)
    
    def show_settings(self):
        """Show settings dialog"""
        try:
            dialog = SettingsDialog(self)
            dialog.playlist_added.connect(self.on_playlist_added)
            result = dialog.exec()
            logger.info(f"Settings dialog closed with result: {result}")
        except Exception as e:
            logger.error(f"Error showing settings dialog: {e}", exc_info=True)
            QMessageBox.critical(self, "Greška", f"Greška pri otvaranju podešavanja:\n{str(e)}")
    
    def on_playlist_added(self, channels: list, vod_items: list, series_items: list):
        """Handle new playlist added from settings"""
        self.current_playlist_data = {
            'channels': channels,
            'vod_items': vod_items,
            'series_items': series_items
        }
        
        self.live_tv_widget.load_channels(channels)
        self.vod_widget.load_vod_items(vod_items)
        self.series_widget.load_series_items(series_items)
        
        self.status_bar.showMessage(f"Lista učitana: {len(channels)} kanala, {len(vod_items)} filmova, {len(series_items)} serija")
    
    def play_channel(self, channel: Channel):
        """Play selected channel"""
        logger.info(f"Playing channel: {channel.name}")
        self.player_widget.play_url(channel.url)
        self.status_bar.showMessage(f"Reprodukcija: {channel.name}")
    
    def play_vod(self, vod_item: VODItem):
        """Play selected VOD item - show detail dialog"""
        logger.info(f"Opening VOD detail: {vod_item.name}")
        
        from ui.vod_detail_dialog import VODDetailDialog
        
        dialog = VODDetailDialog(vod_item, self.vod_widget.image_cache, self.db, self)
        dialog.play_clicked.connect(lambda: self.start_vod_playback(vod_item))
        dialog.favorite_changed.connect(self.vod_widget.refresh_favorites)
        dialog.exec()
    
    def start_vod_playback(self, vod_item: VODItem):
        """Start VOD playback"""
        logger.info(f"Playing VOD: {vod_item.name}")
        
        # Show player and switch to TV tab for playback
        self.tab_widget.setCurrentIndex(0)
        self.player_widget.show()
        self.tab_widget.setMaximumWidth(500)
        
        self.player_widget.play_url(vod_item.url)
        self.status_bar.showMessage(f"Reprodukcija: {vod_item.name}")
        self.db.mark_vod_watched(vod_item.stream_id, vod_item.name)
    
    def play_series(self, series_item: SeriesItem):
        """Play selected series - show episode selection dialog"""
        logger.info(f"Opening series detail: {series_item.name}")
        
        QMessageBox.information(
            self, 
            "Serije", 
            f"Detalji i izbor epizoda za '{series_item.name}' dolazi uskoro!\n\n"
            "Biće omogućeno:\n"
            "• Pregled svih sezona i epizoda\n"
            "• Opis serije i epizoda\n"
            "• Dodavanje u favorite\n"
            "• Praćenje odgledanog"
        )
    
    def play_next(self):
        """Play next channel/item"""
        current_tab = self.tab_widget.currentIndex()
        if current_tab == 0:
            self.live_tv_widget.select_next_channel()
    
    def play_previous(self):
        """Play previous channel/item"""
        current_tab = self.tab_widget.currentIndex()
        if current_tab == 0:
            self.live_tv_widget.select_previous_channel()
    
    def closeEvent(self, event):
        """Handle window close event"""
        logger.info("Application closing - starting cleanup...")
        
        try:
            if self.video_player:
                logger.info("Stopping video player...")
                self.video_player.stop()
        except Exception as e:
            logger.error(f"Error stopping video player: {e}")
        
        try:
            if hasattr(self, 'live_tv_widget'):
                logger.info("Cleaning up LiveTVWidget...")
                self.live_tv_widget.cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up LiveTVWidget: {e}")
        
        try:
            if hasattr(self, 'vod_widget'):
                logger.info("Cleaning up VODWidget...")
                self.vod_widget.cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up VODWidget: {e}")
        
        try:
            if hasattr(self, 'series_widget') and hasattr(self.series_widget, 'cleanup'):
                logger.info("Cleaning up SeriesWidget...")
                self.series_widget.cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up SeriesWidget: {e}")
        
        event.accept()
        logger.info("Application closed successfully")