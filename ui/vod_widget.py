import logging
from typing import List, Optional
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QComboBox, QScrollArea, QGridLayout)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap
from models.vod_item import VODItem
from utils.image_cache import ImageCache
from core.database import Database

logger = logging.getLogger(__name__)


class VODPosterWidget(QWidget):
    """Widget for displaying VOD poster with favorite indicator"""
    
    clicked = pyqtSignal(VODItem)
    
    def __init__(self, vod_item: VODItem, image_cache: ImageCache, is_favorite: bool = False):
        super().__init__()
        self.vod_item = vod_item
        self.image_cache = image_cache
        self._is_favorite = is_favorite
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        self.setFixedSize(220, 350)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            VODPosterWidget {
                background-color: #f0f0f0;
                border: 2px solid #ccc;
                border-radius: 8px;
            }
            VODPosterWidget:hover {
                border-color: #4CAF50;
                background-color: #e8e8e8;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Poster container with favorite indicator
        poster_container = QWidget()
        poster_container.setFixedSize(210, 300)
        poster_container.setStyleSheet("background: transparent;")
        poster_layout = QVBoxLayout(poster_container)
        poster_layout.setContentsMargins(0, 0, 0, 0)
        
        # Poster image
        self.poster_label = QLabel()
        self.poster_label.setFixedSize(210, 300)
        self.poster_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.poster_label.setStyleSheet(
            "background-color: #ddd; border-radius: 5px; border: 1px solid #bbb;"
        )
        
        # Load poster
        if self.vod_item.cover:
            pixmap = self.image_cache.get_image(self.vod_item.cover, (210, 300))
            if pixmap and not pixmap.isNull():
                self.poster_label.setPixmap(pixmap)
            else:
                self.poster_label.setText("🎬")
                self.poster_label.setStyleSheet(
                    "font-size: 56pt; color: #888; background-color: #ddd; "
                    "border-radius: 5px; border: 1px solid #bbb;"
                )
        else:
            self.poster_label.setText("🎬")
            self.poster_label.setStyleSheet(
                "font-size: 56pt; color: #888; background-color: #ddd; "
                "border-radius: 5px; border: 1px solid #bbb;"
            )
        
        poster_layout.addWidget(self.poster_label)
        
        # Favorite indicator (top-right badge)
        self.favorite_badge = QLabel("⭐")
        self.favorite_badge.setFixedSize(35, 35)
        self.favorite_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.favorite_badge.setStyleSheet("""
            background-color: rgba(0, 0, 0, 180);
            border-radius: 17px;
            font-size: 18pt;
            padding: 2px;
        """)
        self.favorite_badge.setVisible(self._is_favorite)
        
        # Position badge at top-right
        self.favorite_badge.setParent(poster_container)
        self.favorite_badge.move(170, 5)
        
        # Umesto postojećeg koda za title_label, zameni sa ovim:

        layout.addWidget(poster_container)
        
        # Title (UPPERCASE for better visibility)
        title_text = self.vod_item.name.upper()
        if len(title_text) > 40:
            title_text = title_text[:37] + "..."
        
        title_label = QLabel(title_text)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setWordWrap(True)
        title_label.setStyleSheet(
            "font-size: 11pt; font-weight: bold; color: #222; "
            "background-color: transparent;"
        )
        title_label.setMaximumHeight(40)
        layout.addWidget(title_label)
        
        # TMDB Rating (⭐ 8.5/10) - NOVO!
        rating_text = self.vod_item.get_display_rating()
        if rating_text:
            rating_label = QLabel(rating_text)
            rating_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rating_label.setStyleSheet(
                "font-size: 10pt; font-weight: bold; color: #FF9800; "
                "background-color: transparent;"
            )
            layout.addWidget(rating_label)
        
        # Connect to image ready signal
        self.image_cache.image_ready.connect(self.on_image_ready)
    
    def on_image_ready(self, url: str, pixmap: QPixmap):
        """Update poster when image is downloaded"""
        if url == self.vod_item.cover and not pixmap.isNull():
            self.poster_label.setPixmap(pixmap)
            self.poster_label.setStyleSheet(
                "background-color: #ddd; border-radius: 5px; border: 1px solid #bbb;"
            )
    
    def set_favorite(self, is_favorite: bool):
        """Update favorite status"""
        self._is_favorite = is_favorite
        self.favorite_badge.setVisible(is_favorite)
    
    def mousePressEvent(self, event):
        """Handle mouse click"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.vod_item)


class VODWidget(QWidget):
    """VOD (Movies) widget with grid view and optimized performance"""
    
    vod_selected = pyqtSignal(VODItem)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.vod_items: List[VODItem] = []
        self.filtered_items: List[VODItem] = []
        self.displayed_items: List[VODItem] = []
        self.favorite_ids: set = set()
        
        # Single shared ImageCache instance
        self.image_cache = ImageCache()
        
        # Database
        self.db = Database()
        
        # Performance settings
        self.items_per_page = 50
        self.current_page = 0
        
        # Widget cache for reuse
        self.poster_widgets: dict = {}  # stream_id -> VODPosterWidget
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        self.setStyleSheet("background-color: #ffffff;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # Top controls
        controls_widget = QWidget()
        controls_widget.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                border-radius: 10px;
            }
        """)
        controls_layout = QHBoxLayout(controls_widget)
        controls_layout.setContentsMargins(15, 15, 15, 15)
        controls_layout.setSpacing(15)
        
        # Search
        search_label = QLabel("🔍 Pretraga:")
        search_label.setStyleSheet("font-size: 14pt; font-weight: bold; color: #333; background: transparent;")
        controls_layout.addWidget(search_label)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Pretražite filmove...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                font-size: 14pt; 
                padding: 10px; 
                background-color: #fff; 
                color: #333;
                border: 2px solid #ccc;
                border-radius: 8px;
            }
            QLineEdit:focus {
                border-color: #4CAF50;
            }
        """)
        self.search_input.textChanged.connect(self.on_search_changed)
        controls_layout.addWidget(self.search_input, stretch=1)
        
        # Category filter
        category_label = QLabel("📁 Kategorija:")
        category_label.setStyleSheet("font-size: 14pt; font-weight: bold; color: #333; background: transparent;")
        controls_layout.addWidget(category_label)
        
        self.category_combo = QComboBox()
        self.category_combo.setStyleSheet("""
            QComboBox {
                font-size: 14pt; 
                padding: 10px; 
                min-width: 300px;
                background-color: #fff;
                color: #333;
                border: 2px solid #ccc;
                border-radius: 8px;
            }
            QComboBox:hover {
                border-color: #4CAF50;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 8px solid #333;
                margin-right: 10px;
            }
            QComboBox QAbstractItemView {
                background-color: #fff;
                color: #333;
                selection-background-color: #4CAF50;
                selection-color: #fff;
                border: 2px solid #ccc;
                border-radius: 5px;
                padding: 5px;
            }
            QComboBox QAbstractItemView::item {
                padding: 8px;
                min-height: 30px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #e8e8e8;
            }
        """)
        self.category_combo.currentTextChanged.connect(self.on_category_changed)
        controls_layout.addWidget(self.category_combo, stretch=2)
        
        layout.addWidget(controls_widget)
        
        # Scroll area with grid
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("""
            QScrollArea {
                background-color: #ffffff;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #f0f0f0;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #ccc;
                border-radius: 6px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #4CAF50;
            }
        """)
        
        # Connect scroll event for lazy loading
        self.scroll.verticalScrollBar().valueChanged.connect(self.on_scroll)
        
        self.grid_container = QWidget()
        self.grid_container.setStyleSheet("background-color: #ffffff;")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(15)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        
        self.scroll.setWidget(self.grid_container)
        layout.addWidget(self.scroll)
        
        # Debounce timer for search
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.filter_items)
    
    def load_vod_items(self, vod_items: List[VODItem]):
        """Load VOD items with batch optimization"""
        if not vod_items:
            logger.warning("load_vod_items called with empty list")
            return
        
        self.vod_items = vod_items
        
        # Batch fetch all favorite IDs (1 DB query instead of N)
        try:
            self.favorite_ids = self.db.get_all_vod_favorite_ids()
            logger.info(f"Loaded {len(self.favorite_ids)} favorite VODs")
        except Exception as e:
            logger.error(f"Error loading favorites: {e}")
            self.favorite_ids = set()
        
        # Extract unique categories
        categories = set()
        for item in vod_items:
            if item.category:
                categories.add(item.category)
        
        # Populate category combo
        self.category_combo.blockSignals(True)
        self.category_combo.clear()
        self.category_combo.addItem("⭐ Favoriti")
        self.category_combo.addItem("🎬 Svi Filmovi")
        for category in sorted(categories):
            self.category_combo.addItem(category)
        
        # Set default category
        if self.favorite_ids:
            self.category_combo.setCurrentIndex(0)
        else:
            self.category_combo.setCurrentIndex(1)
        
        self.category_combo.blockSignals(False)
        
        # Filter and display
        self.filter_items()
        
        logger.info(f"Loaded {len(vod_items)} VOD items with {len(categories)} categories")
    
    def on_search_changed(self):
        """Handle search input with debounce"""
        self.search_timer.stop()
        self.search_timer.start(300)
    
    def on_category_changed(self):
        """Handle category change"""
        self.filter_items()
    
    def filter_items(self):
        """Filter VOD items based on search and category"""
        search_text = self.search_input.text().lower().strip()
        selected_category = self.category_combo.currentText()
        
        # Filter items
        self.filtered_items = []
        for item in self.vod_items:
            # Category filter
            if selected_category == "⭐ Favoriti":
                if item.stream_id not in self.favorite_ids:
                    continue
            elif selected_category != "🎬 Svi Filmovi":
                if item.category != selected_category:
                    continue
            
            # Search filter
            if search_text and search_text not in item.name.lower():
                continue
            
            self.filtered_items.append(item)
        
        # Reset pagination
        self.current_page = 0
        self.displayed_items = []
        
        # Clear grid
        self.clear_grid()
        
        # Display first page
        self.load_next_page()
    
    def load_next_page(self):
        """Load next page of items (lazy loading)"""
        start_idx = self.current_page * self.items_per_page
        end_idx = start_idx + self.items_per_page
        
        page_items = self.filtered_items[start_idx:end_idx]
        
        if not page_items:
            return
        
        columns = 4  # 4 movies per row for better visibility (older users)
        
        for item in page_items:
            is_favorite = item.stream_id in self.favorite_ids
            
            # Reuse existing widget if possible
            if item.stream_id in self.poster_widgets:
                poster = self.poster_widgets[item.stream_id]
                poster.set_favorite(is_favorite)
            else:
                # Use shared image_cache instead of creating new one
                poster = VODPosterWidget(item, self.image_cache, is_favorite)
                poster.clicked.connect(self.on_vod_clicked)
                self.poster_widgets[item.stream_id] = poster
            
            # Calculate grid position
            total_displayed = len(self.displayed_items)
            row = total_displayed // columns
            col = total_displayed % columns
            
            self.grid_layout.addWidget(poster, row, col)
            self.displayed_items.append(item)
        
        self.current_page += 1
        
        logger.debug(f"Loaded page {self.current_page}, total displayed: {len(self.displayed_items)}")
    
    def on_scroll(self, value):
        """Handle scroll event for lazy loading"""
        scrollbar = self.scroll.verticalScrollBar()
        
        # Load more when scrolled to 80%
        if scrollbar.maximum() > 0:
            scroll_percentage = value / scrollbar.maximum()
            if scroll_percentage > 0.8 and len(self.displayed_items) < len(self.filtered_items):
                self.load_next_page()
    
    def clear_grid(self):
        """Clear grid layout without deleting widgets (for reuse)"""
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
    
    def on_vod_clicked(self, vod_item: VODItem):
        """Handle VOD click"""
        self.vod_selected.emit(vod_item)
    
    def refresh_favorites(self):
        """Refresh favorite status (call after adding/removing favorites)"""
        try:
            self.favorite_ids = self.db.get_all_vod_favorite_ids()
            
            # Update all visible widgets
            for stream_id, widget in self.poster_widgets.items():
                is_favorite = stream_id in self.favorite_ids
                widget.set_favorite(is_favorite)
            
            logger.info("Favorites refreshed")
        except Exception as e:
            logger.error(f"Error refreshing favorites: {e}")
    
    def cleanup(self):
        """Cleanup resources"""
        self.image_cache.cleanup()
        logger.info("VODWidget cleanup completed")