import logging
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QScrollArea, QWidget, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from models.vod_item import VODItem
from utils.image_cache import ImageCache
from core.database import Database

logger = logging.getLogger(__name__)


class VODDetailDialog(QDialog):
    """Dialog for displaying VOD item details"""
    
    play_clicked = pyqtSignal()
    resume_clicked = pyqtSignal(int)  # Emituj poziciju u sekundama
    favorite_changed = pyqtSignal()
    
    def __init__(self, vod_item: VODItem, image_cache: ImageCache, db: Database, parent=None):
        super().__init__(parent)
        self.vod_item = vod_item
        self.image_cache = image_cache
        self.db = db
        self.is_favorite = self.db.is_vod_favorite(vod_item.stream_id)
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        self.setWindowTitle(self.vod_item.name)
        self.setMinimumSize(700, 600)
        self.setStyleSheet("background-color: #1a1a1a;")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(15)
        
        # Top section: Poster + Info
        top_layout = QHBoxLayout()
        
        # Poster
        poster_frame = QFrame()
        poster_frame.setFixedSize(300, 450)
        poster_frame.setStyleSheet("background-color: #2a2a2a; border-radius: 10px;")
        poster_layout = QVBoxLayout(poster_frame)
        poster_layout.setContentsMargins(0, 0, 0, 0)
        
        self.poster_label = QLabel()
        self.poster_label.setFixedSize(300, 450)
        self.poster_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.poster_label.setStyleSheet("background-color: #333; border-radius: 10px;")
        
        if self.vod_item.cover:
            pixmap = self.image_cache.get_image(self.vod_item.cover, (300, 450))
            if pixmap and not pixmap.isNull():
                self.poster_label.setPixmap(pixmap)
            else:
                self.poster_label.setText("🎬")
                self.poster_label.setStyleSheet("font-size: 80pt; color: #666; background-color: #333; border-radius: 10px;")
        else:
            self.poster_label.setText("🎬")
            self.poster_label.setStyleSheet("font-size: 80pt; color: #666; background-color: #333; border-radius: 10px;")
        
        poster_layout.addWidget(self.poster_label)
        top_layout.addWidget(poster_frame)
        
        # Connect to image ready signal
        self.image_cache.image_ready.connect(self.on_image_ready)
        
        # Info section
        info_layout = QVBoxLayout()
        info_layout.setSpacing(10)
        
        # Title
        title_label = QLabel(self.vod_item.name)
        title_label.setWordWrap(True)
        title_label.setStyleSheet("font-size: 24pt; font-weight: bold; color: white;")
        info_layout.addWidget(title_label)
        
        # Rating + Year
        meta_layout = QHBoxLayout()
        
        if self.vod_item.rating:
            rating_label = QLabel(f"⭐ {self.vod_item.rating}/10")
            rating_label.setStyleSheet("font-size: 16pt; color: #FFD700;")
            meta_layout.addWidget(rating_label)
        
        if self.vod_item.year:
            year_label = QLabel(f"📅 {self.vod_item.year}")
            year_label.setStyleSheet("font-size: 16pt; color: #999;")
            meta_layout.addWidget(year_label)
        
        if self.vod_item.duration:
            duration_label = QLabel(f"⏱ {self.vod_item.duration}")
            duration_label.setStyleSheet("font-size: 16pt; color: #999;")
            meta_layout.addWidget(duration_label)
        
        meta_layout.addStretch()
        info_layout.addLayout(meta_layout)
        
        # Genre
        if self.vod_item.genre:
            genre_label = QLabel(f"🎭 {self.vod_item.genre}")
            genre_label.setStyleSheet("font-size: 14pt; color: #4CAF50;")
            info_layout.addWidget(genre_label)
        
        # Category
        if self.vod_item.category:
            category_label = QLabel(f"📁 {self.vod_item.category}")
            category_label.setStyleSheet("font-size: 14pt; color: #2196F3;")
            info_layout.addWidget(category_label)
        
        # Director
        if self.vod_item.director:
            director_label = QLabel(f"🎬 Režija: {self.vod_item.director}")
            director_label.setStyleSheet("font-size: 13pt; color: #ccc;")
            info_layout.addWidget(director_label)
        
        # Cast
        if self.vod_item.cast:
            cast_label = QLabel(f"👥 Glumci: {self.vod_item.cast}")
            cast_label.setWordWrap(True)
            cast_label.setStyleSheet("font-size: 13pt; color: #ccc;")
            info_layout.addWidget(cast_label)
        
        info_layout.addStretch()
        
        top_layout.addLayout(info_layout, stretch=1)
        scroll_layout.addLayout(top_layout)
        
        # Plot/Description
        if self.vod_item.plot:
            plot_frame = QFrame()
            plot_frame.setStyleSheet("background-color: #2a2a2a; border-radius: 10px; padding: 15px;")
            plot_layout = QVBoxLayout(plot_frame)
            
            plot_title = QLabel("📖 Opis:")
            plot_title.setStyleSheet("font-size: 16pt; font-weight: bold; color: white;")
            plot_layout.addWidget(plot_title)
            
            plot_text = QLabel(self.vod_item.plot)
            plot_text.setWordWrap(True)
            plot_text.setStyleSheet("font-size: 13pt; color: #ddd; line-height: 1.5;")
            plot_layout.addWidget(plot_text)
            
            scroll_layout.addWidget(plot_frame)
        
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)
        
        # Bottom buttons - organized in two rows
        buttons_container = QVBoxLayout()
        buttons_container.setSpacing(10)

        # Check watch progress
        self.watch_progress = self.db.get_watch_progress(str(self.vod_item.stream_id))

        # Top row - Continue Watching buttons (if watch progress exists)
        if self.watch_progress and self.watch_progress.position_seconds > 60:
            continue_watching_layout = QHBoxLayout()
            continue_watching_layout.setSpacing(10)

            # Resume button
            progress_percent = self.watch_progress.progress_percent
            resume_time = self.format_time(self.watch_progress.position_seconds)

            resume_btn = QPushButton(f"▶ Nastavi ({resume_time}) - {progress_percent}%")
            resume_btn.setStyleSheet("""
                QPushButton {
                    font-size: 16pt;
                    padding: 12px 30px;
                    background-color: #2196F3;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #0b7dda;
                }
                QPushButton:pressed {
                    background-color: #0069c0;
                }
            """)
            resume_btn.clicked.connect(self.on_resume_clicked)
            continue_watching_layout.addWidget(resume_btn)

            # Mark as Watched button
            mark_watched_btn = QPushButton("✓ Označi kao Odgledano")
            mark_watched_btn.setStyleSheet("""
                QPushButton {
                    font-size: 14pt;
                    padding: 12px 20px;
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
            mark_watched_btn.clicked.connect(self.on_mark_watched_clicked)
            continue_watching_layout.addWidget(mark_watched_btn)

            buttons_container.addLayout(continue_watching_layout)

        # Bottom row - Standard buttons
        standard_buttons_layout = QHBoxLayout()
        standard_buttons_layout.setSpacing(10)

        # Play button (od početka)
        play_btn = QPushButton("▶ Pusti od Početka" if self.watch_progress else "▶ Pusti Film")
        play_btn.setStyleSheet("""
            QPushButton {
                font-size: 16pt;
                padding: 12px 30px;
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
        play_btn.clicked.connect(self.on_play_clicked)
        standard_buttons_layout.addWidget(play_btn)

        # Favorite button
        self.fav_btn = QPushButton("⭐ Ukloni iz Favorita" if self.is_favorite else "☆ Dodaj u Favorite")
        self.fav_btn.setStyleSheet("""
            QPushButton {
                font-size: 16pt;
                padding: 12px 30px;
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:pressed {
                background-color: #E65100;
            }
        """)
        self.fav_btn.clicked.connect(self.on_favorite_clicked)
        standard_buttons_layout.addWidget(self.fav_btn)

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
        standard_buttons_layout.addWidget(back_btn)

        buttons_container.addLayout(standard_buttons_layout)
        main_layout.addLayout(buttons_container)
    
    def on_image_ready(self, url: str, pixmap: QPixmap):
        """Update poster when image is downloaded"""
        if url == self.vod_item.cover and not pixmap.isNull():
            self.poster_label.setPixmap(pixmap)
            self.poster_label.setStyleSheet("background-color: #333; border-radius: 10px;")
    
    def on_play_clicked(self):
        """Handle play button click"""
        self.play_clicked.emit()
        self.close()

    def on_resume_clicked(self):
        """Handle resume button click - play from saved position"""
        if self.watch_progress:
            self.resume_clicked.emit(self.watch_progress.position_seconds)
            self.close()

    def format_time(self, seconds: int) -> str:
        """Format seconds to MM:SS or HH:MM:SS"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"

    def on_favorite_clicked(self):
        """Handle favorite button click"""
        if self.is_favorite:
            # Remove from favorites
            self.db.remove_vod_favorite(self.vod_item.stream_id)
            self.is_favorite = False
            self.fav_btn.setText("☆ Dodaj u Favorite")
            logger.info(f"Removed from favorites: {self.vod_item.name}")
        else:
            # Add to favorites
            self.db.add_vod_favorite(self.vod_item.stream_id, self.vod_item.name)
            self.is_favorite = True
            self.fav_btn.setText("⭐ Ukloni iz Favorita")
            logger.info(f"Added to favorites: {self.vod_item.name}")

        # Notify parent to refresh
        self.favorite_changed.emit()

    def on_mark_watched_clicked(self):
        """Mark as watched - resets to initial state (removes Resume button)"""
        logger.info(f"Marking as watched (resetting progress): {self.vod_item.name}")
        # Delete watch progress completely to return to initial state
        self.db.delete_watch_progress(str(self.vod_item.stream_id))
        # Refresh buttons to show updated state
        self.refresh_buttons()

    def refresh_buttons(self):
        """Refresh button layout to show updated watch progress"""
        logger.info(f"Refreshing buttons for: {self.vod_item.name}")

        # Re-check watch progress
        self.watch_progress = self.db.get_watch_progress(str(self.vod_item.stream_id))

        # Find and remove old button container
        main_layout = self.layout()
        if main_layout and main_layout.count() >= 2:
            # Last item should be buttons_container
            old_buttons_item = main_layout.takeAt(main_layout.count() - 1)
            if old_buttons_item:
                # Delete all widgets in old container
                self._clear_layout(old_buttons_item.layout())
                old_buttons_item.layout().deleteLater()

        # Rebuild button container
        buttons_container = QVBoxLayout()
        buttons_container.setSpacing(10)

        # Top row - Continue Watching buttons (if watch progress exists)
        if self.watch_progress and self.watch_progress.position_seconds > 60:
            continue_watching_layout = QHBoxLayout()
            continue_watching_layout.setSpacing(10)

            # Resume button
            progress_percent = self.watch_progress.progress_percent
            resume_time = self.format_time(self.watch_progress.position_seconds)

            resume_btn = QPushButton(f"▶ Nastavi ({resume_time}) - {progress_percent}%")
            resume_btn.setStyleSheet("""
                QPushButton {
                    font-size: 16pt;
                    padding: 12px 30px;
                    background-color: #2196F3;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #0b7dda;
                }
                QPushButton:pressed {
                    background-color: #0069c0;
                }
            """)
            resume_btn.clicked.connect(self.on_resume_clicked)
            continue_watching_layout.addWidget(resume_btn)

            # Mark as Watched button
            mark_watched_btn = QPushButton("✓ Označi kao Odgledano")
            mark_watched_btn.setStyleSheet("""
                QPushButton {
                    font-size: 14pt;
                    padding: 12px 20px;
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
            mark_watched_btn.clicked.connect(self.on_mark_watched_clicked)
            continue_watching_layout.addWidget(mark_watched_btn)

            buttons_container.addLayout(continue_watching_layout)

        # Bottom row - Standard buttons
        standard_buttons_layout = QHBoxLayout()
        standard_buttons_layout.setSpacing(10)

        # Play button (od početka)
        play_btn = QPushButton("▶ Pusti od Početka" if self.watch_progress else "▶ Pusti Film")
        play_btn.setStyleSheet("""
            QPushButton {
                font-size: 16pt;
                padding: 12px 30px;
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
        play_btn.clicked.connect(self.on_play_clicked)
        standard_buttons_layout.addWidget(play_btn)

        # Favorite button (update reference)
        self.fav_btn = QPushButton("⭐ Ukloni iz Favorita" if self.is_favorite else "☆ Dodaj u Favorite")
        self.fav_btn.setStyleSheet("""
            QPushButton {
                font-size: 16pt;
                padding: 12px 30px;
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:pressed {
                background-color: #E65100;
            }
        """)
        self.fav_btn.clicked.connect(self.on_favorite_clicked)
        standard_buttons_layout.addWidget(self.fav_btn)

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
        standard_buttons_layout.addWidget(back_btn)

        buttons_container.addLayout(standard_buttons_layout)
        main_layout.addLayout(buttons_container)

    def _clear_layout(self, layout):
        """Helper to recursively clear layout"""
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def closeEvent(self, event):
        """Handle dialog close event"""
        logger.info(f"Closing VOD detail dialog: {self.vod_item.name}")
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