import logging
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QScrollArea, QWidget, QFrame, QComboBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from models.series_item import SeriesItem
from utils.image_cache import ImageCache
from core.database import Database

logger = logging.getLogger(__name__)


class EpisodeWidget(QWidget):
    """Widget for single episode"""

    play_clicked = pyqtSignal(SeriesItem)
    resume_clicked = pyqtSignal(SeriesItem, int)  # episode, position_seconds
    mark_watched_clicked = pyqtSignal(SeriesItem)  # episode to mark as watched

    def __init__(self, episode: SeriesItem, image_cache: ImageCache, db: Database):
        super().__init__()
        self.episode = episode
        self.image_cache = image_cache
        self.db = db
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        self.setStyleSheet("""
            QWidget {
                background-color: #2a2a2a;
                border-radius: 10px;
                padding: 15px;
            }
            QWidget:hover {
                background-color: #333;
                border: 2px solid #4CAF50;
            }
            QWidget[selected="true"] {
                border: 2px solid #4CAF50;
                background-color: #2f3d2f;
            }
        """)
        self.setFixedHeight(150)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(20)
        
        # Episode poster
        self.poster_label = QLabel()
        self.poster_label.setFixedSize(200, 120)
        self.poster_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.poster_label.setStyleSheet("background-color: #1a1a1a; border-radius: 8px; border: 2px solid #555;")
        
        if self.episode.cover:
            pixmap = self.image_cache.get_image(self.episode.cover, (200, 120))
            if pixmap and not pixmap.isNull():
                self.poster_label.setPixmap(pixmap)
            else:
                self.poster_label.setText("📺")
                self.poster_label.setStyleSheet("font-size: 48pt; color: #666; background-color: #1a1a1a; border-radius: 8px; border: 2px solid #555;")
        else:
            self.poster_label.setText("📺")
            self.poster_label.setStyleSheet("font-size: 48pt; color: #666; background-color: #1a1a1a; border-radius: 8px; border: 2px solid #555;")
        
        layout.addWidget(self.poster_label)
        
        # Connect to image ready signal
        self.image_cache.image_ready.connect(self.on_image_ready)
        
        # Episode info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(8)
        
        # Episode number
        episode_num = f"Epizoda {self.episode.episode}" if self.episode.episode else "Epizoda"
        episode_label = QLabel(f"<b>{episode_num}</b>")
        episode_label.setStyleSheet("font-size: 22pt; color: #4CAF50; background: transparent; padding: 5px;")
        info_layout.addWidget(episode_label)
        
        # Episode name
        name_label = QLabel(self.episode.name)
        name_label.setWordWrap(True)
        name_label.setStyleSheet("font-size: 14pt; color: #ccc; background: transparent;")
        info_layout.addWidget(name_label)
        
        info_layout.addStretch()
        layout.addLayout(info_layout, stretch=1)

        # Button layout - horizontal with Resume on left, Play/Mark Watched on right
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        # Check for watch progress
        watch_progress = self.db.get_watch_progress(str(self.episode.stream_id))

        if watch_progress and watch_progress.position_seconds > 60:
            # Resume button on the left
            resume_time = self.format_time(watch_progress.position_seconds)
            progress_percent = watch_progress.progress_percent

            resume_btn = QPushButton(f"▶ Nastavi {resume_time}")
            resume_btn.setFixedSize(160, 110)
            resume_btn.setStyleSheet("""
                QPushButton {
                    font-size: 14pt;
                    padding: 10px;
                    background-color: #2196F3;
                    color: white;
                    border: none;
                    border-radius: 10px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #0b7dda;
                }
                QPushButton:pressed {
                    background-color: #0069c0;
                }
            """)
            resume_btn.clicked.connect(lambda: self.resume_clicked.emit(self.episode, watch_progress.position_seconds))
            button_layout.addWidget(resume_btn)

            # Right side buttons (Play from start + Mark as Watched)
            right_buttons_layout = QVBoxLayout()
            right_buttons_layout.setSpacing(5)

            # Play from start button
            play_btn = QPushButton("⏮ Od početka")
            play_btn.setFixedSize(160, 52)
            play_btn.setStyleSheet("""
                QPushButton {
                    font-size: 12pt;
                    padding: 8px;
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
                QPushButton:pressed {
                    background-color: #3d8b40;
                }
            """)
            play_btn.clicked.connect(lambda: self.play_clicked.emit(self.episode))
            right_buttons_layout.addWidget(play_btn)

            # Mark as Watched button
            mark_watched_btn = QPushButton("✓ Odgledano")
            mark_watched_btn.setFixedSize(160, 52)
            mark_watched_btn.setStyleSheet("""
                QPushButton {
                    font-size: 11pt;
                    padding: 8px;
                    background-color: #9C27B0;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #7B1FA2;
                }
                QPushButton:pressed {
                    background-color: #6A1B9A;
                }
            """)
            mark_watched_btn.clicked.connect(lambda: self.mark_watched_clicked.emit(self.episode))
            right_buttons_layout.addWidget(mark_watched_btn)

            button_layout.addLayout(right_buttons_layout)
        else:
            # Regular play button - centered, larger
            play_btn = QPushButton("▶ Pusti")
            play_btn.setFixedSize(200, 80)
            play_btn.setStyleSheet("""
                QPushButton {
                    font-size: 18pt;
                    padding: 15px;
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    border-radius: 10px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
                QPushButton:pressed {
                    background-color: #3d8b40;
                }
            """)
            play_btn.clicked.connect(lambda: self.play_clicked.emit(self.episode))
            button_layout.addWidget(play_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # Create container widget for button layout with center alignment
        button_container = QWidget()
        button_container.setLayout(button_layout)
        layout.addWidget(button_container, alignment=Qt.AlignmentFlag.AlignCenter)
    
    def on_image_ready(self, url: str, pixmap: QPixmap):
        """Update poster when image is downloaded"""
        if url == self.episode.cover and not pixmap.isNull():
            self.poster_label.setPixmap(pixmap)
            self.poster_label.setStyleSheet("background-color: #1a1a1a; border-radius: 8px; border: 2px solid #555;")

    def format_time(self, seconds: int) -> str:
        """Format seconds to MM:SS or HH:MM:SS"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"

    def set_selected(self, value: bool):
        """Set selected state for episode widget"""
        self.setProperty("selected", value)
        self.style().unpolish(self)
        self.style().polish(self)


class SeriesDetailDialog(QDialog):
    """Dialog for displaying series details with seasons and episodes"""

    play_episode_clicked = pyqtSignal(SeriesItem)
    resume_episode_clicked = pyqtSignal(SeriesItem, int)  # episode, position_seconds
    favorite_changed = pyqtSignal()
    
    def __init__(self, series_name: str, all_episodes: list, image_cache: ImageCache, db: Database, parent=None):
        super().__init__(parent)
        self.series_name = series_name
        self.all_episodes = all_episodes
        self.image_cache = image_cache
        self.db = db
        
        # Group episodes by season
        self.seasons = {}
        for episode in all_episodes:
            season_num = episode.season or "1"
            if season_num not in self.seasons:
                self.seasons[season_num] = []
            self.seasons[season_num].append(episode)
        
        # Sort seasons
        self.season_list = sorted(self.seasons.keys(), key=lambda x: int(x) if x.isdigit() else 0)
        
        # Use first episode for series info
        self.main_episode = all_episodes[0]
        self.is_favorite = self.db.is_series_favorite(self.series_name)
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        self.setWindowTitle(self.series_name)
        self.setMinimumSize(1200, 800)
        self.setStyleSheet("background-color: #1a1a1a;")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Top section: Poster + Info + Season Selector
        top_layout = QHBoxLayout()
        
        # Poster
        poster_frame = QFrame()
        poster_frame.setFixedHeight(320)
        poster_frame.setFixedWidth(300)
        poster_frame.setStyleSheet("background-color: #2a2a2a; border-radius: 10px;")
        poster_layout = QVBoxLayout(poster_frame)
        poster_layout.setContentsMargins(0, 0, 0, 0)
        
        self.poster_label = QLabel()
        self.poster_label.setFixedSize(300, 450)
        self.poster_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.poster_label.setStyleSheet("background-color: #333; border-radius: 10px;")
        
        if self.main_episode.cover:
            pixmap = self.image_cache.get_image(self.main_episode.cover, (300, 450))
            if pixmap and not pixmap.isNull():
                self.poster_label.setPixmap(pixmap)
            else:
                self.poster_label.setText("📺")
                self.poster_label.setStyleSheet("font-size: 80pt; color: #666; background-color: #333; border-radius: 10px;")
        else:
            self.poster_label.setText("📺")
            self.poster_label.setStyleSheet("font-size: 80pt; color: #666; background-color: #333; border-radius: 10px;")
        
        poster_layout.addWidget(self.poster_label)
        top_layout.addWidget(poster_frame)
        
        # Connect to image ready signal
        self.image_cache.image_ready.connect(self.on_image_ready)
        
        # Right side: Info + Season selector
        right_layout = QVBoxLayout()
        right_layout.setSpacing(15)
        
        # Title + Favorite + Back
        title_fav_layout = QHBoxLayout()

        title_label = QLabel(self.series_name)
        title_label.setWordWrap(True)
        title_label.setStyleSheet("font-size: 26pt; font-weight: bold; color: white;")
        title_fav_layout.addWidget(title_label, stretch=1)

        # Right side (favorite + back stacked)
        fav_back_layout = QVBoxLayout()
        fav_back_layout.setSpacing(6)

        self.fav_btn = QPushButton()
        self.fav_btn.setFixedHeight(50)
        self.fav_btn.setMinimumWidth(220)
        self.fav_btn.clicked.connect(self.on_favorite_clicked)
        fav_back_layout.addWidget(self.fav_btn)

        back_btn_top = QPushButton("← Nazad")
        back_btn_top.setStyleSheet("""
            QPushButton {
                font-size: 14pt;
                padding: 8px 20px;
                background-color: #555;
                color: white;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #666;
            }
            QPushButton:pressed {
                background-color: #444;
            }
        """)
        back_btn_top.clicked.connect(self.close)
        fav_back_layout.addWidget(back_btn_top)

        title_fav_layout.addLayout(fav_back_layout)
        right_layout.addLayout(title_fav_layout)

        self.update_fav_button()
                
        # Rating + Year + Episodes
        meta_layout = QHBoxLayout()
        
        if self.main_episode.rating:
            rating_label = QLabel(f"⭐ {self.main_episode.rating}/10")
            rating_label.setStyleSheet("font-size: 16pt; color: #FFD700;")
            meta_layout.addWidget(rating_label)
        
        if self.main_episode.year:
            year_label = QLabel(f"📅 {self.main_episode.year}")
            year_label.setStyleSheet("font-size: 16pt; color: #999;")
            meta_layout.addWidget(year_label)
        
        total_episodes = len(self.all_episodes)
        episodes_label = QLabel(f"📺 {total_episodes} epizoda")
        episodes_label.setStyleSheet("font-size: 16pt; color: #999;")
        meta_layout.addWidget(episodes_label)
        
        meta_layout.addStretch()
        right_layout.addLayout(meta_layout)
        
        # Genre & Category
        if self.main_episode.genre:
            genre_label = QLabel(f"🎭 {self.main_episode.genre}")
            genre_label.setStyleSheet("font-size: 14pt; color: #4CAF50;")
            right_layout.addWidget(genre_label)
        
        if self.main_episode.category:
            category_label = QLabel(f"📁 {self.main_episode.category}")
            category_label.setStyleSheet("font-size: 14pt; color: #2196F3;")
            right_layout.addWidget(category_label)
        
        # Plot
        if self.main_episode.plot:
            plot_text = QLabel(self.main_episode.plot)
            plot_text.setWordWrap(True)
            plot_text.setStyleSheet("font-size: 12pt; color: #ddd; line-height: 1.5;")
            right_layout.addWidget(plot_text)
        
        right_layout.addStretch()
        
        # Season selector (NA VRHU!)
        season_frame = QFrame()
        season_frame.setStyleSheet("background-color: #2a2a2a; border-radius: 10px; padding: 15px;")
        season_layout = QHBoxLayout(season_frame)
        
        season_label = QLabel("🎬 Izaberi sezonu:")
        season_label.setStyleSheet("font-size: 18pt; font-weight: bold; color: white; background: transparent;")
        season_layout.addWidget(season_label)
        
        self.season_combo = QComboBox()
        self.season_combo.setStyleSheet("""
            QComboBox {
                font-size: 18pt;
                padding: 12px;
                background-color: #1a1a1a;
                color: white;
                border: 2px solid #4CAF50;
                border-radius: 8px;
                min-width: 300px;
            }
            QComboBox:hover {
                background-color: #333;
                border: 2px solid #45a049;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #333;
                color: white;
                selection-background-color: #4CAF50;
                font-size: 16pt;
                padding: 5px;
            }
        """)
        
        for season in self.season_list:
            episode_count = len(self.seasons[season])
            self.season_combo.addItem(f"Sezona {season} ({episode_count} epizoda)", season)
        
        self.season_combo.currentIndexChanged.connect(self.on_season_changed)
        season_layout.addWidget(self.season_combo)
        
        season_layout.addStretch()
        
        right_layout.addWidget(season_frame)
        
        top_layout.addLayout(right_layout, stretch=1)
        main_layout.addLayout(top_layout)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #555; height: 2px;")
        main_layout.addWidget(separator)
        
        # Episodes label
        episodes_title = QLabel("📺 Epizode:")
        episodes_title.setStyleSheet("font-size: 20pt; font-weight: bold; color: white;")
        main_layout.addWidget(episodes_title)
        
        # Episodes scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: #2a2a2a;
                width: 18px;
                border-radius: 9px;
            }
            QScrollBar::handle:vertical {
                background-color: #4CAF50;
                border-radius: 9px;
                min-height: 40px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #45a049;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        self.episodes_container = QWidget()
        self.episodes_layout = QVBoxLayout(self.episodes_container)
        self.episodes_layout.setSpacing(15)
        self.episodes_layout.setContentsMargins(5, 5, 5, 5)
        
        scroll.setWidget(self.episodes_container)
        main_layout.addWidget(scroll, stretch=1)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        button_layout.addStretch()
        
        # Back button
        back_btn = QPushButton("← Nazad")
        back_btn.setStyleSheet("""
            QPushButton {
                font-size: 16pt;
                padding: 12px 30px;
                background-color: #555;
                color: white;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #666;
            }
            QPushButton:pressed {
                background-color: #444;
            }
        """)
        back_btn.clicked.connect(self.close)
        button_layout.addWidget(back_btn)
        
        main_layout.addLayout(button_layout)
        
        # Load first season
        self.load_season(self.season_list[0])
    
    def on_image_ready(self, url: str, pixmap: QPixmap):
        """Update poster when image is downloaded"""
        if url == self.main_episode.cover and not pixmap.isNull():
            self.poster_label.setPixmap(pixmap)
            self.poster_label.setStyleSheet("background-color: #333; border-radius: 10px;")
    
    def on_season_changed(self, index: int):
        """Handle season selection change"""
        season = self.season_combo.itemData(index)
        self.load_season(season)
    
    def load_season(self, season: str):
        """Load episodes for selected season"""
        # Clear existing episodes
        for i in reversed(range(self.episodes_layout.count())):
            widget = self.episodes_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        # Load episodes for this season
        episodes = self.seasons.get(season, [])
        
        # Sort episodes by episode number
        episodes_sorted = sorted(episodes, key=lambda x: int(x.episode) if x.episode and x.episode.isdigit() else 0)
        
        # Update parent's episode list for auto-play
        if self.parent() and hasattr(self.parent(), 'current_series_episodes'):
            self.parent().current_series_episodes = episodes_sorted
        
        for episode in episodes_sorted:
            episode_widget = EpisodeWidget(episode, self.image_cache, self.db)
            episode_widget.play_clicked.connect(self.on_episode_play_clicked)
            episode_widget.resume_clicked.connect(self.on_episode_resume_clicked)
            episode_widget.mark_watched_clicked.connect(self.on_episode_mark_watched)
            self.episodes_layout.addWidget(episode_widget)
        
        self.episodes_layout.addStretch()
    
    def on_episode_play_clicked(self, episode: SeriesItem):
        """Handle episode play button click"""
        logger.info(f"Playing episode: {episode.name}")
        self.play_episode_clicked.emit(episode)
        self.close()

    def on_episode_resume_clicked(self, episode: SeriesItem, position_seconds: int):
        """Handle episode resume button click"""
        logger.info(f"Resuming episode: {episode.name} at {position_seconds}s")
        self.resume_episode_clicked.emit(episode, position_seconds)
        self.close()

    def on_episode_mark_watched(self, episode: SeriesItem):
        """Mark episode as watched - resets to initial state (removes Resume button)"""
        logger.info(f"Marking episode as watched (resetting progress): {episode.name}")
        # Delete watch progress completely to return to initial state
        self.db.delete_watch_progress(str(episode.stream_id))
        # Reload current season to update UI
        current_season = self.season_combo.currentData()
        self.load_season(current_season)

    def refresh_episodes(self):
        """Refresh episode list to show updated watch progress"""
        logger.info("Refreshing episode list")
        current_season = self.season_combo.currentData()
        self.load_season(current_season)

    def update_fav_button(self):
        if self.is_favorite:
            self.fav_btn.setText("⭐ Odstrani iz favorita")
            self.fav_btn.setStyleSheet("""
                QPushButton {
                    font-size: 16pt;
                    padding: 8px 20px;
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    border-radius: 25px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #43a047;
                }
                QPushButton:pressed {
                    background-color: #388e3c;
                }
            """)
        else:
            self.fav_btn.setText("☆ Dodaj u favorite")
            self.fav_btn.setStyleSheet("""
                QPushButton {
                    font-size: 16pt;
                    padding: 8px 20px;
                    background-color: #FF9800;
                    color: white;
                    border: none;
                    border-radius: 25px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #F57C00;
                }
                QPushButton:pressed {
                    background-color: #E65100;
                }
            """)
    
    def on_favorite_clicked(self):
        """Handle favorite button click"""
        if self.is_favorite:
            self.db.remove_series_favorite(self.series_name)

            self.is_favorite = False
            logger.info(f"Removed from favorites: {self.series_name}")
        else:
            self.db.add_series_favorite(self.series_name, self.series_name)
            self.is_favorite = True
            logger.info(f"Added to favorites: {self.series_name}")

        self.update_fav_button()
        self.favorite_changed.emit()    
    def closeEvent(self, event):
        """Handle dialog close event"""
        logger.info(f"Closing Series detail dialog: {self.series_name}")
        # Only clear reference if dialog is being explicitly closed by user
        # Not when player is active
        if self.parent():
            parent = self.parent()
            # Only clear if player is not visible (not during playback)
            if parent.stacked_widget.currentIndex() != 0:
                parent.current_detail_dialog = None
            else:
                # Ignore close event during playback
                event.ignore()
                return
        super().closeEvent(event)