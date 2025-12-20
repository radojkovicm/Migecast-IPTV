import logging
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
                             QListWidgetItem, QLabel, QLineEdit, QComboBox, QPushButton)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap
from models.channel import Channel
from utils.image_cache import ImageCache
from core.database import Database
from typing import List

logger = logging.getLogger(__name__)


class ChannelListItem(QWidget):
    """Custom widget for channel list item with favorite button"""
    
    favorite_toggled = pyqtSignal(Channel)
    
    def __init__(self, channel: Channel, image_cache: ImageCache, is_favorite: bool = False):
        super().__init__()
        self.channel = channel
        self.image_cache = image_cache
        self._is_favorite = is_favorite
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        
        # Logo
        self.logo_label = QLabel()
        self.logo_label.setFixedSize(60, 40)
        self.logo_label.setScaledContents(True)
        
        if self.channel.logo:
            pixmap = self.image_cache.get_image(self.channel.logo, (60, 40))
            if pixmap and not pixmap.isNull():
                self.logo_label.setPixmap(pixmap)
            else:
                self.logo_label.setText("📺")
                self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.logo_label.setStyleSheet("font-size: 20pt;")
        else:
            self.logo_label.setText("📺")
            self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.logo_label.setStyleSheet("font-size: 20pt;")
        
        layout.addWidget(self.logo_label)
        
        # Connect to image ready signal
        self.image_cache.image_ready.connect(self.on_image_ready)
        
        # Channel info
        info_layout = QVBoxLayout()
        
        # Channel name
        name_label = QLabel(self.channel.name)
        name_label.setStyleSheet("font-size: 16pt; font-weight: bold; color: #1a1a1a;")
        info_layout.addWidget(name_label)
        
        # Category
        cat_label = QLabel(self.channel.category if self.channel.category else "Ostalo")
        cat_label.setStyleSheet("font-size: 12pt; color: #666;")
        info_layout.addWidget(cat_label)
        
        layout.addLayout(info_layout, stretch=1)
        
        # Favorite button
        self.fav_btn = QPushButton("⭐" if self._is_favorite else "☆")
        self.fav_btn.setFixedSize(40, 40)
        self.fav_btn.setStyleSheet("""
            QPushButton {
                font-size: 20pt;
                background-color: transparent;
                border: none;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
                border-radius: 5px;
            }
        """)
        self.fav_btn.clicked.connect(self.on_favorite_clicked)
        layout.addWidget(self.fav_btn)
    
    def on_image_ready(self, url: str, pixmap: QPixmap):
        """Update logo when image is downloaded"""
        if url == self.channel.logo and not pixmap.isNull():
            self.logo_label.setPixmap(pixmap)
            self.logo_label.setStyleSheet("")
    
    def on_favorite_clicked(self):
        """Handle favorite button click"""
        self.favorite_toggled.emit(self.channel)
    
    def set_favorite(self, is_favorite: bool):
        """Update favorite status"""
        self._is_favorite = is_favorite
        self.fav_btn.setText("⭐" if is_favorite else "☆")


class LiveTVWidget(QWidget):
    """Live TV channels widget with favorites"""
    
    channel_selected = pyqtSignal(Channel)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.channels: List[Channel] = []
        self.filtered_channels: List[Channel] = []
        self.favorite_ids: set = set()
        self.current_index = -1
        
        # Single shared ImageCache instance
        self.image_cache = ImageCache()
        
        # Database
        self.db = Database()
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        
        # Search and filter bar
        filter_layout = QHBoxLayout()
        
        # Search
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Pretraži kanale...")
        self.search_input.setStyleSheet("font-size: 16pt; padding: 10px;")
        self.search_input.textChanged.connect(self.filter_channels)
        filter_layout.addWidget(self.search_input, stretch=2)
        
        # Category filter
        category_label = QLabel("📁 Kategorija:")
        category_label.setStyleSheet("font-size: 16pt; font-weight: bold;")
        filter_layout.addWidget(category_label)
        
        self.category_combo = QComboBox()
        self.category_combo.setStyleSheet("""
            QComboBox {
                font-size: 16pt;
                padding: 8px 10px;
                min-width: 250px;
                background-color: white;
                border: 2px solid #4CAF50;
                border-radius: 5px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                font-size: 14pt;
                padding: 5px;
                selection-background-color: #4CAF50;
            }
        """)
        self.category_combo.currentTextChanged.connect(self.filter_channels)
        filter_layout.addWidget(self.category_combo, stretch=1)
        
        layout.addLayout(filter_layout)
        
        # Channel list
        self.channel_list = QListWidget()
        self.channel_list.setStyleSheet("""
            QListWidget {
                font-size: 14pt;
                background-color: white;
                border: 2px solid #ccc;
                border-radius: 5px;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background-color: #4CAF50;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #e8f5e9;
            }
        """)
        self.channel_list.itemClicked.connect(self.on_channel_clicked)
        layout.addWidget(self.channel_list)
    
    def load_channels(self, channels: List[Channel]):
        """Load channels"""
        try:
            if not channels:
                logger.warning("load_channels called with empty list")
                return
            
            self.channels = channels
            
            # Batch load favorite IDs
            try:
                self.favorite_ids = self.db.get_favorite_channel_ids()
                logger.info(f"Loaded {len(self.favorite_ids)} favorite channels")
            except Exception as e:
                logger.error(f"Error loading favorites: {e}")
                self.favorite_ids = set()
            
            # Extract and clean categories
            categories_raw = set()
            for ch in channels:
                if ch.category:
                    categories_raw.add(ch.category)
            
            # Clean category names
            categories_clean = {}
            for cat in categories_raw:
                clean_name = self.clean_category_name(cat)
                categories_clean[cat] = clean_name
            
            # Sort categories by clean name
            categories_sorted = sorted(categories_raw, key=lambda c: categories_clean[c])
            
            # Populate category combo
            self.category_combo.blockSignals(True)
            self.category_combo.clear()
            
            # Add special categories first
            self.category_combo.addItem("⭐ Favoriti", "FAVORITES")
            self.category_combo.addItem("📺 Svi Kanali", "ALL")
            
            # Add regular categories with clean names
            for cat in categories_sorted:
                clean_name = categories_clean[cat]
                self.category_combo.addItem(clean_name, cat)  # Display clean, store original
            
            # Set default to Favoriti if there are favorites, otherwise Svi Kanali
            if self.favorite_ids:
                self.category_combo.setCurrentIndex(0)  # Favoriti
            else:
                self.category_combo.setCurrentIndex(1)  # Svi Kanali
            
            self.category_combo.blockSignals(False)
            
            self.filter_channels()
            
            logger.info(f"Loaded {len(channels)} channels with {len(categories_raw)} categories")
        except Exception as e:
            logger.error(f"Error in load_channels: {e}", exc_info=True)
    
    def clean_category_name(self, category: str) -> str:
        """Clean and format category name for display"""
        if not category:
            return "Ostalo"
        
        # Remove leading/trailing pipes and whitespace
        clean = category.strip().strip('|').strip()
        
        # Map common prefixes to flags/icons
        country_map = {
            'RS': '🇷🇸 Srpski',
            'HR': '🇭🇷 Hrvatski',
            'BA': '🇧🇦 Bosanski',
            'SI': '🇸🇮 Slovenački',
            'MK': '🇲🇰 Makedonski',
            'ME': '🇲🇪 Crnogorski',
            'EXYU': '🌍 Ex-Yu',
            'RU': '🇷🇺 Ruski',
            'DE': '🇩🇪 Nemački',
            'UK': '🇬🇧 Britanski',
            'US': '🇺🇸 Američki',
            'IT': '🇮🇹 Italijanski',
            'FR': '🇫🇷 Francuski',
            'ES': '🇪🇸 Španski',
            'TR': '🇹🇷 Turski',
            'GR': '🇬🇷 Grčki',
            'AL': '🇦🇱 Albanski',
        }
        
        # Check if starts with country code
        for code, name in country_map.items():
            if clean.upper().startswith(code):
                # Remove code and return clean name
                rest = clean[len(code):].strip().strip('|').strip('-').strip()
                if rest:
                    return f"{name} - {rest}"
                return name
        
        # If no country code, just return cleaned
        return clean if clean else "Ostalo"
    
    def filter_channels(self):
        """Filter channels based on search and category"""
        try:
            self.channel_list.clear()
            
            search_text = self.search_input.text().lower()
            selected_category_data = self.category_combo.currentData()
            
            # Filter channels
            filtered = []
            for channel in self.channels:
                # Category filter
                if selected_category_data == "FAVORITES":
                    if channel.channel_id not in self.favorite_ids:
                        continue
                elif selected_category_data != "ALL":
                    if channel.category != selected_category_data:
                        continue
                
                # Search filter
                if search_text and search_text not in channel.name.lower():
                    continue
                
                filtered.append(channel)
            
            self.filtered_channels = filtered
            
            # Populate list (limit to first 500 for performance)
            for channel in filtered[:500]:
                item = QListWidgetItem()
                item.setSizeHint(QSize(0, 80))
                
                # Pass shared image_cache instance and favorite status
                is_favorite = channel.channel_id in self.favorite_ids
                widget = ChannelListItem(channel, self.image_cache, is_favorite)
                widget.favorite_toggled.connect(self.toggle_favorite)
                
                self.channel_list.addItem(item)
                self.channel_list.setItemWidget(item, widget)
                
                # Store channel reference
                item.setData(Qt.ItemDataRole.UserRole, channel)
            
            logger.debug(f"Filtered to {len(filtered)} channels")
        except Exception as e:
            logger.error(f"Error in filter_channels: {e}", exc_info=True)
    
    def toggle_favorite(self, channel: Channel):
        """Toggle channel favorite status"""
        try:
            if channel.channel_id in self.favorite_ids:
                # Remove from favorites
                self.db.remove_channel_favorite(channel.channel_id)
                self.favorite_ids.discard(channel.channel_id)
                logger.info(f"Removed from favorites: {channel.name}")
            else:
                # Add to favorites
                self.db.add_channel_favorite(channel.channel_id, channel.name)
                self.favorite_ids.add(channel.channel_id)
                logger.info(f"Added to favorites: {channel.name}")
            
            # Refresh display
            self.refresh_favorites()
        except Exception as e:
            logger.error(f"Error toggling favorite: {e}", exc_info=True)
    
    def refresh_favorites(self):
        """Refresh favorite status for all visible items"""
        try:
            # Reload favorite IDs from database
            self.favorite_ids = self.db.get_favorite_channel_ids()
            
            # Update all visible widgets
            for i in range(self.channel_list.count()):
                item = self.channel_list.item(i)
                widget = self.channel_list.itemWidget(item)
                if widget and hasattr(widget, 'channel'):
                    is_favorite = widget.channel.channel_id in self.favorite_ids
                    widget.set_favorite(is_favorite)
            
            logger.debug("Favorites refreshed")
        except Exception as e:
            logger.error(f"Error refreshing favorites: {e}")
    
    def on_channel_clicked(self, item: QListWidgetItem):
        """Handle channel click"""
        channel = item.data(Qt.ItemDataRole.UserRole)
        if channel:
            self.channel_selected.emit(channel)
    
    def select_next_channel(self):
        """Select next channel"""
        if not self.filtered_channels:
            return
        
        self.current_index = (self.current_index + 1) % len(self.filtered_channels)
        self.channel_list.setCurrentRow(self.current_index)
        self.channel_selected.emit(self.filtered_channels[self.current_index])
    
    def select_previous_channel(self):
        """Select previous channel"""
        if not self.filtered_channels:
            return
        
        self.current_index = (self.current_index - 1) % len(self.filtered_channels)
        self.channel_list.setCurrentRow(self.current_index)
        self.channel_selected.emit(self.filtered_channels[self.current_index])
    
    def cleanup(self):
        """Cleanup resources"""
        try:
            if hasattr(self, 'image_cache'):
                self.image_cache.cleanup()
                logger.info("LiveTVWidget image cache cleaned up")
        except Exception as e:
            logger.error(f"Error during LiveTVWidget cleanup: {e}")