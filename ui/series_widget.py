import logging
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QLabel, QLineEdit, QComboBox, QScrollArea, QPushButton, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap
from models.series_item import SeriesItem
from core.database import Database
from utils.image_cache import ImageCache

logger = logging.getLogger(__name__)


class SeriesPosterWidget(QWidget):
    """Widget for displaying Series poster"""
    
    clicked = pyqtSignal(SeriesItem)
    
    def __init__(self, series_item: SeriesItem):
        super().__init__()
        self.series_item = series_item
        self.image_cache = ImageCache()
        self.setFixedSize(160, 260)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.init_ui()
        
        # Connect to image ready signal
        self.image_cache.image_ready.connect(self.on_image_ready)
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Poster
        self.poster_label = QLabel()
        self.poster_label.setFixedSize(150, 225)
        self.poster_label.setScaledContents(True)
        self.poster_label.setStyleSheet("border: 2px solid #555; border-radius: 5px;")
        
        if self.series_item.cover:
            pixmap = self.image_cache.get_image(self.series_item.cover, (150, 225))
            self.poster_label.setPixmap(pixmap)
        else:
            self.poster_label.setText("📺")
            self.poster_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.poster_label.setStyleSheet("border: 2px solid #555; border-radius: 5px; font-size: 48pt;")
        
        layout.addWidget(self.poster_label)
        
        # Title
        title_label = QLabel(self.series_item.name)
        title_label.setWordWrap(True)
        title_label.setMaximumHeight(30)
        title_label.setStyleSheet("font-size: 10pt; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
    
    def on_image_ready(self, url: str, pixmap: QPixmap):
        """Update poster when image is downloaded"""
        if url == self.series_item.cover:
            self.poster_label.setPixmap(pixmap)
            self.poster_label.setStyleSheet("border: 2px solid #555; border-radius: 5px;")
    
    def mousePressEvent(self, event):
        """Handle mouse press"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.series_item)


class SeriesWidget(QWidget):
    """Series widget with grid view"""
    
    series_selected = pyqtSignal(SeriesItem)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.series_items = []
        self.filtered_items = []
        self.db = Database()
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        
        # Top controls
        controls_layout = QHBoxLayout()
        
        # Search
        search_label = QLabel("🔍 Pretraga:")
        search_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        controls_layout.addWidget(search_label)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Pretražite serije...")
        self.search_input.setStyleSheet("font-size: 14pt; padding: 8px;")
        self.search_input.textChanged.connect(self.filter_items)
        controls_layout.addWidget(self.search_input)
        
        # Category filter
        category_label = QLabel("📁 Kategorija:")
        category_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        controls_layout.addWidget(category_label)
        
        self.category_combo = QComboBox()
        self.category_combo.setStyleSheet("font-size: 14pt; padding: 8px; min-width: 250px;")
        self.category_combo.currentTextChanged.connect(self.filter_items)
        controls_layout.addWidget(self.category_combo)
        
        layout.addLayout(controls_layout)
        
        # Scroll area with grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(10)
        
        scroll.setWidget(self.grid_container)
        layout.addWidget(scroll)
        
        # Info label
        self.info_label = QLabel("Učitajte IPTV listu iz podešavanja")
        self.info_label.setStyleSheet("font-size: 10pt; color: #666; padding: 5px;")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.info_label)
    
    def load_series_items(self, series_items: list):
        """Load Series items"""
        if not series_items:
            logger.warning("load_series_items called with empty list")
            self.info_label.setText("Nema dostupnih serija")
            return
        
        self.series_items = series_items
        
        # Extract unique categories
        categories = set()
        for item in series_items:
            if item.category:
                categories.add(item.category)
        
        # Populate category combo
        self.category_combo.clear()
        self.category_combo.addItem("⭐ Favoriti")
        self.category_combo.addItem("📺 Sve Serije")
        for category in sorted(categories):
            self.category_combo.addItem(category)
        
        # Set default to Favoriti (check if there are favorites first)
        try:
            favorite_count = sum(1 for item in series_items if self.db.is_series_favorite(item.stream_id))
        except Exception as e:
            logger.error(f"Error checking series favorites: {e}")
            favorite_count = 0
        
        if favorite_count > 0:
            self.category_combo.setCurrentIndex(0)  # Favoriti
        else:
            self.category_combo.setCurrentIndex(1)  # Sve Serije
        
        # Filter and display
        self.filter_items()
        
        logger.info(f"Loaded {len(series_items)} series items")
    
    def filter_items(self):
        """Filter series items based on search and category"""
        search_text = self.search_input.text().lower()
        selected_category = self.category_combo.currentText()
        
        # Get favorite series IDs
        favorite_ids = set()
        for item in self.series_items:
            if self.db.is_series_favorite(item.stream_id):
                favorite_ids.add(item.stream_id)
        
        # Filter items
        self.filtered_items = []
        for item in self.series_items:
            # Category filter
            if selected_category == "⭐ Favoriti":
                if item.stream_id not in favorite_ids:
                    continue
            elif selected_category != "📺 Sve Serije":
                if item.category != selected_category:
                    continue
            
            # Search filter
            if search_text and search_text not in item.name.lower():
                continue
            
            self.filtered_items.append(item)
        
        # Limit to first 200 items for performance
        display_items = self.filtered_items[:200]
        
        # Clear grid
        for i in reversed(range(self.grid_layout.count())):
            widget = self.grid_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        # Update info label
        if not display_items:
            self.info_label.setText("Nema serija koje odgovaraju kriterijumima")
            self.info_label.show()
            return
        
        total_count = len(self.filtered_items)
        if total_count > 200:
            self.info_label.setText(f"Prikazano {len(display_items)} od {total_count} serija")
            self.info_label.show()
        else:
            self.info_label.hide()
        
        # Populate grid (5 columns)
        columns = 5
        for index, item in enumerate(display_items):
            row = index // columns
            col = index % columns
            
            poster = SeriesPosterWidget(item)
            poster.clicked.connect(self.on_series_clicked)
            self.grid_layout.addWidget(poster, row, col)
    
    def on_series_clicked(self, series_item: SeriesItem):
        """Handle series click"""
        self.series_selected.emit(series_item)