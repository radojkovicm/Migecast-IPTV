import logging
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                    QPushButton, QLabel, QStatusBar, QMessageBox, QStackedWidget)
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
        self.current_mode = 'menu'
        self.previous_mode = 'tv'  # Track the mode before playback for proper return
        self.current_detail_dialog = None  # Keep reference to detail dialog during playback
        
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
        
        # Breadcrumb label
        self.breadcrumb_label = QLabel("Početna")
        self.breadcrumb_label.setStyleSheet("font-size: 14pt; color: #aaa;")
        top_bar_layout.addWidget(self.breadcrumb_label)
        
        top_bar_layout.addStretch()
        
        self.back_btn = QPushButton("⬅️ Nazad")
        self.back_btn.setStyleSheet("""
            QPushButton {
                font-size: 14pt; 
                padding: 8px 16px; 
                background-color: #333; 
                color: white; 
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #4CAF50;
            }
        """)
        self.back_btn.clicked.connect(self.show_menu)
        self.back_btn.hide()
        top_bar_layout.addWidget(self.back_btn)
        
        settings_btn = QPushButton("⚙️ Podešavanja")
        settings_btn.setStyleSheet("""
            QPushButton {
                font-size: 14pt; 
                padding: 8px 16px; 
                background-color: #333; 
                color: white; 
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #555;
            }
        """)
        settings_btn.clicked.connect(self.show_settings)
        top_bar_layout.addWidget(settings_btn)
        
        main_layout.addWidget(top_bar)
        
        # Stacked widget for menu and content
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)
        
        # Menu page
        self.menu_page = QWidget()
        self.menu_page.setStyleSheet("background-color: #1e1e1e; color: white;")
        menu_layout = QVBoxLayout(self.menu_page)
        menu_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        menu_title = QLabel("Izaberite kategoriju")
        menu_title.setStyleSheet("font-size: 24pt; color: white; margin-bottom: 20px;")
        menu_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        menu_layout.addWidget(menu_title)
        
        menu_layout.addStretch()
        
        # TV button
        self.tv_btn = QPushButton("📺 TV")
        self.tv_btn.setStyleSheet("""
            QPushButton {
                font-size: 18pt; 
                padding: 15px; 
                margin: 10px 100px; 
                background-color: #444; 
                color: white; 
                border: none; 
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #4CAF50;
            }
        """)
        self.tv_btn.clicked.connect(lambda: self.show_category('tv'))
        menu_layout.addWidget(self.tv_btn)
        
        # VOD button
        self.vod_btn = QPushButton("🎬 Filmovi")
        self.vod_btn.setStyleSheet("""
            QPushButton {
                font-size: 18pt; 
                padding: 15px; 
                margin: 10px 100px; 
                background-color: #444; 
                color: white; 
                border: none; 
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #4CAF50;
            }
        """)
        self.vod_btn.clicked.connect(lambda: self.show_category('vod'))
        menu_layout.addWidget(self.vod_btn)
        
        # Series button
        self.series_btn = QPushButton("📺 Serije")
        self.series_btn.setStyleSheet("""
            QPushButton {
                font-size: 18pt; 
                padding: 15px; 
                margin: 10px 100px; 
                background-color: #444; 
                color: white; 
                border: none; 
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #4CAF50;
            }
        """)
        self.series_btn.clicked.connect(lambda: self.show_category('series'))
        menu_layout.addWidget(self.series_btn)
        
        menu_layout.addStretch()
        
        self.stacked_widget.addWidget(self.menu_page)
        
        # Content page - sa nested QStackedWidget za kategorije
        self.content_page = QWidget()
        content_layout = QHBoxLayout(self.content_page)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # Category stacked widget (zamena za QTabWidget)
        self.category_stack = QStackedWidget()
        
        # TV category (sa player-om)
        tv_container = QWidget()
        tv_layout = QHBoxLayout(tv_container)
        tv_layout.setContentsMargins(0, 0, 0, 0)
        tv_layout.setSpacing(0)
        
        self.live_tv_widget = self.LiveTVWidget()
        self.live_tv_widget.channel_selected.connect(self.play_channel)
        self.live_tv_widget.setMaximumWidth(500)
        tv_layout.addWidget(self.live_tv_widget)
        
        self.player_widget = self.PlayerWidget(self.video_player)
        self.player_widget.setMinimumWidth(640)
        self.player_widget.previous_requested.connect(self.play_previous)
        self.player_widget.next_requested.connect(self.play_next)
        self.player_widget.playback_exited.connect(self.on_playback_exited)
        tv_layout.addWidget(self.player_widget, stretch=1)
        
        self.category_stack.addWidget(tv_container)  # Index 0 - TV
        
        # VOD category (bez player-a)
        self.vod_widget = self.VODWidget()
        self.vod_widget.vod_selected.connect(self.play_vod)
        self.category_stack.addWidget(self.vod_widget)  # Index 1 - VOD
        
        # Series category (bez player-a)
        self.series_widget = self.SeriesWidget()
        self.series_widget.series_selected.connect(self.play_series)
        self.category_stack.addWidget(self.series_widget)  # Index 2 - Series
        
        content_layout.addWidget(self.category_stack)
        
        self.stacked_widget.addWidget(self.content_page)
        
        # Initially show menu
        self.stacked_widget.setCurrentIndex(0)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Izaberite kategoriju")
        
        logger.info("Main window initialized")
    
    def show_menu(self):
        """Show main menu"""
        # STOP VIDEO PLAYER when returning to menu
        if self.video_player:
            logger.info("Stopping video player before returning to menu")
            self.video_player.stop()
        
        self.stacked_widget.setCurrentIndex(0)
        self.back_btn.hide()
        self.breadcrumb_label.setText("Početna")
        self.current_mode = 'menu'
        self.status_bar.showMessage("Izaberite kategoriju")
    
    def on_playback_exited(self):
        """Handle user exiting from playback - return to the detail dialog or category"""
        logger.info(f"Playback exited - stopping player")
        
        # Exit fullscreen if still in fullscreen
        if self.player_widget.isFullScreen():
            self.player_widget.exit_fullscreen()
        
        # Stop video player with extra delay to ensure VLC processes stop command
        if self.video_player:
            self.video_player.stop()
        
        # Also stop the player widget
        self.player_widget.stop()
        
        # Add small delay to ensure player stops
        QTimer.singleShot(100, self._complete_playback_exit)
    
    def _complete_playback_exit(self):
        """Complete the playback exit process after player has stopped"""
        # If we have a detail dialog, bring it back to front
        if self.current_detail_dialog:
            logger.info("Returning to detail dialog")
            # Return to category view to show the dialog properly
            self.stacked_widget.setCurrentIndex(1)
            # Ensure dialog is visible and on top
            self.current_detail_dialog.setVisible(True)
            self.current_detail_dialog.show()
            self.current_detail_dialog.raise_()
            self.current_detail_dialog.activateWindow()
            self.current_detail_dialog.setFocus()
        else:
            # Otherwise return to the category view
            logger.info(f"Returning to {self.previous_mode} category")
            self.show_category(self.previous_mode)
    
    def show_category(self, mode: str):
        """Show selected category"""
        # STOP VIDEO PLAYER when switching categories
        if self.video_player:
            logger.info(f"Stopping video player before switching to {mode}")
            self.video_player.stop()

        self.stacked_widget.setCurrentIndex(1)
        self.back_btn.show()

        if mode == 'tv':
            self.category_stack.setCurrentIndex(0)
            self.breadcrumb_label.setText("Početna > 📺 TV")
        elif mode == 'vod':
            self.category_stack.setCurrentIndex(1)
            self.breadcrumb_label.setText("Početna > 🎬 Filmovi")
        elif mode == 'series':
            self.category_stack.setCurrentIndex(2)
            self.breadcrumb_label.setText("Početna > 📺 Serije")

        self.current_mode = mode
        self.status_bar.showMessage(f"Kategorija: {mode}")
    
    def update_menu_counts(self):
        """Update menu buttons with item counts"""
        if self.current_playlist_data:
            channels = self.current_playlist_data.get('channels', [])
            vod_items = self.current_playlist_data.get('vod_items', [])
            series_items = self.current_playlist_data.get('series_items', [])
            
            self.tv_btn.setText(f"📺 TV ({len(channels)})")
            self.vod_btn.setText(f"🎬 Filmovi ({len(vod_items)})")
            self.series_btn.setText(f"📺 Serije ({len(series_items)})")
    
    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        # Fullscreen
        fullscreen_shortcut = QShortcut(QKeySequence(Qt.Key.Key_F11), self)
        fullscreen_shortcut.activated.connect(self.player_widget.toggle_fullscreen)
        
        # Play/Pause
        play_pause_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        play_pause_shortcut.activated.connect(self.player_widget.toggle_play_pause)
        
        # Next channel (TV only)
        next_shortcut = QShortcut(QKeySequence(Qt.Key.Key_PageDown), self)
        next_shortcut.activated.connect(self.play_next)
        
        # Previous channel (TV only)
        prev_shortcut = QShortcut(QKeySequence(Qt.Key.Key_PageUp), self)
        prev_shortcut.activated.connect(self.play_previous)
        
        # ESC - exit fullscreen ili nazad na meni
        esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        esc_shortcut.activated.connect(self.handle_escape)
        
        # Backspace - nazad na meni
        backspace_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Backspace), self)
        backspace_shortcut.activated.connect(self.handle_backspace)
        
        logger.info("Keyboard shortcuts configured")
    
    def handle_escape(self):
        """Handle ESC key - exit fullscreen, return to dialog, or go back to menu"""
        # Priority 1: Exit fullscreen if in fullscreen
        if self.player_widget.isFullScreen():
            logger.info("ESC pressed in fullscreen - exiting fullscreen and stopping player")
            # Exit fullscreen
            self.player_widget.exit_fullscreen()
            # Stop the player immediately
            if self.video_player:
                self.video_player.stop()
            self.player_widget.stop()
            # Return to previous state
            if self.current_detail_dialog:
                self.current_detail_dialog.setVisible(True)
                self.current_detail_dialog.show()
                self.current_detail_dialog.raise_()
                self.current_detail_dialog.activateWindow()
            return
        
        # Priority 2: If player is visible and detail dialog exists, bring dialog to front
        if self.stacked_widget.currentIndex() == 0 and self.current_detail_dialog:
            self.on_playback_exited()
            return
        
        # Priority 3: Go back to menu if not in menu
        if self.current_mode != 'menu':
            self.show_menu()
    
    
    def handle_backspace(self):
        """Handle Backspace key - go back to menu"""
        if self.current_mode != 'menu' and not self.player_widget.isFullScreen():
            self.show_menu()
    
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
    
    def load_saved_playlist(self, saved_playlist: dict, force_refresh: bool = False):
        """Load saved playlist (from cache or re-parse if force_refresh)"""
        try:
            from core.playlist_parser import PlaylistParser
            
            if saved_playlist.get('type') == 'M3U':
                url = saved_playlist.get('url', '')
                if not url:
                    logger.warning("M3U URL is empty")
                    self.show_welcome_dialog()
                    return
                channels, vod_items, series_items = PlaylistParser.parse_m3u_file(url, force_refresh=force_refresh)
            elif saved_playlist.get('type') == 'Xtream':
                server = saved_playlist.get('server', '')
                username = saved_playlist.get('username', '')
                password = saved_playlist.get('password', '')
                if not all([server, username, password]):
                    logger.warning("Xtream credentials incomplete")
                    self.show_welcome_dialog()
                    return
                channels, vod_items, series_items = PlaylistParser.parse_xtream_codes(server, username, password, force_refresh=force_refresh)
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
            
            # Update menu button counts
            self.update_menu_counts()
            
            status_msg = f"Lista učitana: {len(channels)} kanala, {len(vod_items)} filmova, {len(series_items)} serija"
            if force_refresh:
                status_msg += " (osveženo)"
            self.status_bar.showMessage(status_msg)
            
            logger.info(f"Successfully loaded playlist with {len(channels)} channels, {len(vod_items)} VOD items, {len(series_items)} series (force_refresh={force_refresh})")
            
            # Show menu after loading
            self.show_menu()
            
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
            dialog.refresh_requested.connect(self.on_refresh_requested)  # NOVO
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
        
        # Update menu button counts
        self.update_menu_counts()
        
        self.status_bar.showMessage(f"Lista učitana: {len(channels)} kanala, {len(vod_items)} filmova, {len(series_items)} serija")
        
        # Show menu after adding playlist
        self.show_menu()
    
    def on_refresh_requested(self):
        """Handle refresh playlist request from settings"""
        saved_playlist = self.db.get_last_playlist()
        if saved_playlist:
            logger.info("Refreshing playlist...")
            self.status_bar.showMessage("Osvežavanje liste...")
            QTimer.singleShot(100, lambda: self.load_saved_playlist(saved_playlist, force_refresh=True))
        else:
            QMessageBox.warning(self, "Greška", "Nema aktivne playliste za osvežavanje.")
    
    def play_channel(self, channel: Channel):
        """Play selected channel"""
        logger.info(f"Playing channel: {channel.name}")
        
        # Save current mode for TV playback
        self.previous_mode = self.current_mode
        
        self.player_widget.play_url(channel.url)
        self.status_bar.showMessage(f"Reprodukcija: {channel.name}")
    
    def play_vod(self, vod_item: VODItem):
        """Play selected VOD item - show detail dialog"""
        logger.info(f"Opening VOD detail: {vod_item.name}")
        
        from ui.vod_detail_dialog import VODDetailDialog
        
        dialog = VODDetailDialog(vod_item, self.vod_widget.image_cache, self.db, self)
        dialog.play_clicked.connect(lambda: self.start_vod_playback(vod_item, dialog))
        dialog.favorite_changed.connect(self.vod_widget.refresh_favorites)
        
        # Save dialog reference and show as modeless (non-blocking) dialog
        self.current_detail_dialog = dialog
        dialog.show()
    
    def start_vod_playback(self, vod_item: VODItem, dialog=None):
        """Start VOD playback"""
        logger.info(f"Playing VOD: {vod_item.name}")

        # Save current mode at the moment when user clicks Play
        self.previous_mode = self.current_mode
        
        # Switch to player widget
        self.stacked_widget.setCurrentIndex(0)  # Show player

        # Play video
        self.player_widget.play_url(vod_item.url)
        self.status_bar.showMessage(f"Reprodukcija: {vod_item.name}")
        self.db.mark_vod_watched(vod_item.stream_id, vod_item.name)

        # Enter fullscreen automatically after short delay
        QTimer.singleShot(500, self.player_widget.enter_fullscreen)
    
    def play_series(self, series_name: str, episodes: list):
        """Play selected series - show season/episode selection dialog"""
        logger.info(f"Opening series detail: {series_name}")
        
        from ui.series_detail_dialog import SeriesDetailDialog
        
        dialog = SeriesDetailDialog(series_name, episodes, self.series_widget.image_cache, self.db, self)
        dialog.play_episode_clicked.connect(lambda ep: self.start_series_playback(ep, dialog))
        dialog.favorite_changed.connect(self.series_widget.refresh_favorites)
        
        # Save dialog reference and show as modeless (non-blocking) dialog
        self.current_detail_dialog = dialog
        dialog.show()
        
    def start_series_playback(self, episode: SeriesItem, dialog=None):
        """Start series episode playback"""
        logger.info(f"Playing series episode: {episode.name}")
        
        # Save current mode at the moment when user clicks Play
        self.previous_mode = self.current_mode
        
        # Switch to player widget
        self.stacked_widget.setCurrentIndex(0)  # Show player
        
        # Play video
        self.player_widget.play_url(episode.url)
        self.status_bar.showMessage(f"Reprodukcija: {episode.name}")
        self.db.mark_series_watched(episode.stream_id, episode.name)
        
        # Enter fullscreen automatically after short delay
        QTimer.singleShot(500, self.player_widget.enter_fullscreen)
    
    def play_next(self):
        """Play next channel/item"""
        if self.current_mode == 'tv':
            self.live_tv_widget.select_next_channel()
    
    def play_previous(self):
        """Play previous channel/item"""
        if self.current_mode == 'tv':
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
            if hasattr(self, 'series_widget'):
                logger.info("Cleaning up SeriesWidget...")
                self.series_widget.cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up SeriesWidget: {e}")
        
        event.accept()
        logger.info("Application closed successfully")