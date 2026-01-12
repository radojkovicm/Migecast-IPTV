"""Theme definitions for MigeCast application"""

# Theme color schemes
THEMES = {
    'dark': {
        'name': 'Tamna (podrazumevano)',
        'background': '#1e1e1e',
        'background_secondary': '#2a2a2a',
        'background_hover': '#333333',
        'text': '#ffffff',
        'text_secondary': '#cccccc',
        'accent': '#4CAF50',
        'accent_hover': '#45a049',
        'button_bg': '#2a2a2a',
        'button_hover': '#333333',
        'border': '#444444',
        'error': '#f44336',
        'warning': '#ff9800',
        'success': '#4CAF50',
    },
    'light': {
        'name': 'Svetla',
        'background': '#ffffff',
        'background_secondary': '#f5f5f5',
        'background_hover': '#e0e0e0',
        'text': '#000000',
        'text_secondary': '#666666',
        'accent': '#4CAF50',
        'accent_hover': '#45a049',
        'button_bg': '#f0f0f0',
        'button_hover': '#e0e0e0',
        'border': '#cccccc',
        'error': '#f44336',
        'warning': '#ff9800',
        'success': '#4CAF50',
    },
    'high_contrast': {
        'name': 'Visok kontrast',
        'background': '#000000',
        'background_secondary': '#1a1a1a',
        'background_hover': '#2a2a2a',
        'text': '#ffff00',  # Yellow on black for maximum contrast
        'text_secondary': '#ffffff',
        'accent': '#ffffff',
        'accent_hover': '#f0f0f0',
        'button_bg': '#1a1a1a',
        'button_hover': '#333333',
        'border': '#ffffff',
        'error': '#ff0000',
        'warning': '#ffff00',
        'success': '#00ff00',
    },
}


def generate_stylesheet(theme_name: str, font_size: int = 16) -> str:
    """
    Generate PyQt6 stylesheet for given theme

    Args:
        theme_name: Name of theme ('dark', 'light', 'high_contrast')
        font_size: Base font size in points

    Returns:
        Complete stylesheet string
    """
    theme = THEMES.get(theme_name, THEMES['dark'])

    return f"""
    /* Global Styles */
    * {{
        font-size: {font_size}pt;
        font-family: 'Segoe UI', Arial, sans-serif;
    }}

    QMainWindow, QWidget {{
        background-color: {theme['background']};
        color: {theme['text']};
    }}

    /* Buttons */
    QPushButton {{
        background-color: {theme['button_bg']};
        color: {theme['text']};
        border: 2px solid {theme['border']};
        border-radius: 8px;
        padding: 10px 20px;
        min-height: 40px;
    }}

    QPushButton:hover {{
        background-color: {theme['button_hover']};
        border-color: {theme['accent']};
    }}

    QPushButton:pressed {{
        background-color: {theme['accent']};
        color: {theme['background']};
    }}

    QPushButton:disabled {{
        background-color: {theme['background_secondary']};
        color: {theme['text_secondary']};
        border-color: {theme['border']};
    }}

    /* Accent Buttons */
    QPushButton#accent_button {{
        background-color: {theme['accent']};
        color: {theme['background']};
        font-weight: bold;
    }}

    QPushButton#accent_button:hover {{
        background-color: {theme['accent_hover']};
    }}

    /* Labels */
    QLabel {{
        color: {theme['text']};
        background-color: transparent;
    }}

    /* Line Edit */
    QLineEdit {{
        background-color: {theme['background_secondary']};
        color: {theme['text']};
        border: 2px solid {theme['border']};
        border-radius: 5px;
        padding: 8px;
        min-height: 30px;
    }}

    QLineEdit:focus {{
        border-color: {theme['accent']};
    }}

    /* Combo Box */
    QComboBox {{
        background-color: {theme['background_secondary']};
        color: {theme['text']};
        border: 2px solid {theme['border']};
        border-radius: 5px;
        padding: 8px;
        min-height: 30px;
    }}

    QComboBox:hover {{
        border-color: {theme['accent']};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 30px;
    }}

    QComboBox::down-arrow {{
        image: none;
        border: 2px solid {theme['text']};
        width: 10px;
        height: 10px;
    }}

    /* List Widget */
    QListWidget {{
        background-color: {theme['background']};
        color: {theme['text']};
        border: 2px solid {theme['border']};
        border-radius: 5px;
    }}

    QListWidget::item {{
        padding: 10px;
        border-bottom: 1px solid {theme['border']};
    }}

    QListWidget::item:hover {{
        background-color: {theme['background_hover']};
    }}

    QListWidget::item:selected {{
        background-color: {theme['accent']};
        color: {theme['background']};
    }}

    /* Scroll Bar */
    QScrollBar:vertical {{
        background-color: {theme['background_secondary']};
        width: 16px;
        margin: 0;
    }}

    QScrollBar::handle:vertical {{
        background-color: {theme['border']};
        min-height: 30px;
        border-radius: 8px;
    }}

    QScrollBar::handle:vertical:hover {{
        background-color: {theme['accent']};
    }}

    QScrollBar:horizontal {{
        background-color: {theme['background_secondary']};
        height: 16px;
        margin: 0;
    }}

    QScrollBar::handle:horizontal {{
        background-color: {theme['border']};
        min-width: 30px;
        border-radius: 8px;
    }}

    QScrollBar::handle:horizontal:hover {{
        background-color: {theme['accent']};
    }}

    /* Slider */
    QSlider::groove:horizontal {{
        background-color: {theme['background_secondary']};
        height: 8px;
        border-radius: 4px;
    }}

    QSlider::handle:horizontal {{
        background-color: {theme['accent']};
        width: 20px;
        height: 20px;
        margin: -6px 0;
        border-radius: 10px;
    }}

    QSlider::handle:horizontal:hover {{
        background-color: {theme['accent_hover']};
    }}

    /* Progress Bar */
    QProgressBar {{
        background-color: {theme['background_secondary']};
        border: 2px solid {theme['border']};
        border-radius: 5px;
        text-align: center;
        color: {theme['text']};
        min-height: 25px;
    }}

    QProgressBar::chunk {{
        background-color: {theme['accent']};
        border-radius: 3px;
    }}

    /* Tab Widget */
    QTabWidget::pane {{
        border: 2px solid {theme['border']};
        background-color: {theme['background']};
    }}

    QTabBar::tab {{
        background-color: {theme['background_secondary']};
        color: {theme['text']};
        padding: 10px 20px;
        margin-right: 2px;
        border: 2px solid {theme['border']};
        border-bottom: none;
        border-top-left-radius: 5px;
        border-top-right-radius: 5px;
    }}

    QTabBar::tab:selected {{
        background-color: {theme['accent']};
        color: {theme['background']};
    }}

    QTabBar::tab:hover {{
        background-color: {theme['background_hover']};
    }}

    /* Dialog */
    QDialog {{
        background-color: {theme['background']};
        color: {theme['text']};
    }}

    /* Message Box */
    QMessageBox {{
        background-color: {theme['background']};
        color: {theme['text']};
    }}

    QMessageBox QPushButton {{
        min-width: 80px;
    }}

    /* Group Box */
    QGroupBox {{
        border: 2px solid {theme['border']};
        border-radius: 5px;
        margin-top: 10px;
        padding-top: 10px;
        font-weight: bold;
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px;
    }}
    """


def get_theme_names():
    """Get list of available theme names"""
    return [(key, theme['name']) for key, theme in THEMES.items()]
