"""Application wide themes.

One stylesheet is applied to the whole ``QApplication`` so every page and
dialog shares fonts, colors, borders and button sizes. Widgets pick a look
with the dynamic ``role`` property (``primary``, ``secondary``, ``danger``,
``tile``, ``nav``, ``toggle``) instead of inline style sheets.
"""

THEMES = {
    "dark": {
        "name": "Tamna",
        "bg": "#15171a", "surface": "#1f2226", "surface2": "#2a2e33", "hover": "#343940",
        "text": "#f2f2f2", "muted": "#b3b8bf", "border": "#3d434a",
        "accent": "#3fae5a", "accent_hover": "#4cc56a", "accent_text": "#ffffff",
        "secondary": "#3a4048", "danger": "#d9453b", "warning": "#f0a030", "focus": "#ffd24a",
        "star": "#ffcc33",
    },
    "light": {
        "name": "Svetla",
        "bg": "#f4f5f7", "surface": "#ffffff", "surface2": "#e8eaee", "hover": "#dde1e6",
        "text": "#141414", "muted": "#4a4f57", "border": "#b8bec6",
        "accent": "#1e7a36", "accent_hover": "#23913f", "accent_text": "#ffffff",
        "secondary": "#d5d9df", "danger": "#c0332a", "warning": "#b36b00", "focus": "#0060d0",
        "star": "#c98a00",
    },
    "high_contrast": {
        "name": "Visok kontrast",
        "bg": "#000000", "surface": "#000000", "surface2": "#141414", "hover": "#262626",
        "text": "#ffff00", "muted": "#ffffff", "border": "#ffffff",
        "accent": "#ffff00", "accent_hover": "#ffffff", "accent_text": "#000000",
        "secondary": "#1a1a1a", "danger": "#ff3030", "warning": "#ffff00", "focus": "#00ffff",
        "star": "#ffff00",
    },
}

_current = "dark"


def current_name() -> str:
    return _current


def current() -> dict:
    return THEMES.get(_current, THEMES["dark"])


def set_current(name: str) -> dict:
    global _current
    _current = name if name in THEMES else "dark"
    return current()


def get_theme_names():
    return [(key, value["name"]) for key, value in THEMES.items()]


def generate_stylesheet(theme_name: str, font_size: int = 15) -> str:
    t = THEMES.get(theme_name, THEMES["dark"])
    return f"""
* {{ font-family: 'Segoe UI', Arial, sans-serif; font-size: {font_size}pt; }}
QMainWindow, QWidget#Root, QWidget#Page {{ background: {t['bg']}; color: {t['text']}; }}
QWidget {{ color: {t['text']}; }}
QLabel {{ background: transparent; color: {t['text']}; }}
QLabel[role="muted"] {{ color: {t['muted']}; }}
QLabel[role="title"] {{ font-size: {font_size + 13}pt; font-weight: 700; }}
QLabel[role="h2"] {{ font-size: {font_size + 4}pt; font-weight: 700; }}
QLabel[role="error"] {{ color: {t['danger']}; font-weight: 600; }}
QLabel[role="ok"] {{ color: {t['accent']}; font-weight: 600; }}
QWidget#Header {{ background: {t['surface']}; border-bottom: 2px solid {t['border']}; }}
QLabel#AppTitle {{ font-size: {font_size + 7}pt; font-weight: 800; }}
QLabel#Breadcrumb {{ font-size: {font_size + 1}pt; color: {t['muted']}; }}
QLabel[role="poster"] {{ background: {t['surface2']}; color: {t['muted']}; border-radius: 14px; font-size: 64pt; }}
QFrame[role="card"] {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 14px; }}

QPushButton {{
    background: {t['secondary']}; color: {t['text']}; border: 2px solid {t['border']};
    border-radius: 12px; padding: 10px 22px; min-height: 40px; font-weight: 600;
}}
QPushButton:hover {{ background: {t['hover']}; border-color: {t['accent']}; }}
QPushButton:pressed {{ background: {t['surface2']}; }}
QPushButton:focus {{ border-color: {t['focus']}; }}
QPushButton:disabled {{ color: {t['muted']}; background: {t['surface2']}; border-color: {t['surface2']}; }}
QPushButton[role="primary"] {{ background: {t['accent']}; color: {t['accent_text']}; border-color: {t['accent']}; }}
QPushButton[role="primary"]:hover {{ background: {t['accent_hover']}; border-color: {t['accent_hover']}; }}
QPushButton[role="danger"] {{ background: {t['danger']}; color: #ffffff; border-color: {t['danger']}; }}
QPushButton[role="nav"] {{ font-size: {font_size + 1}pt; min-height: 52px; padding: 6px 22px; }}
QPushButton[role="exit"] {{ font-size: {font_size + 1}pt; min-height: 52px; padding: 6px 22px;
    background: {t['danger']}; color: #ffffff; border-color: {t['danger']}; }}
QPushButton[role="tile"] {{
    font-size: {font_size + 9}pt; font-weight: 700; min-width: 240px; min-height: 240px;
    border-radius: 24px; background: {t['surface2']}; border: 3px solid {t['border']};
}}
QPushButton[role="tile"]:hover {{ background: {t['accent']}; color: {t['accent_text']}; border-color: {t['accent']}; }}
QPushButton[role="toggle"] {{ text-align: left; padding: 12px 18px; min-height: 48px; }}
QPushButton[role="toggle"]:checked {{ background: {t['accent']}; color: {t['accent_text']}; border-color: {t['accent']}; }}

QLineEdit, QComboBox, QSpinBox {{
    background: {t['surface']}; color: {t['text']}; border: 2px solid {t['border']};
    border-radius: 10px; padding: 8px 12px; min-height: 36px; selection-background-color: {t['accent']};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: {t['focus']}; }}
QComboBox::drop-down {{ width: 40px; border: none; }}
QComboBox QAbstractItemView {{
    background: {t['surface']}; color: {t['text']}; border: 2px solid {t['border']};
    selection-background-color: {t['accent']}; selection-color: {t['accent_text']}; outline: 0;
}}
QComboBox QAbstractItemView::item {{ min-height: 44px; padding: 4px 10px; }}
QCheckBox, QRadioButton {{ spacing: 12px; min-height: 40px; }}
QCheckBox::indicator, QRadioButton::indicator {{ width: 26px; height: 26px; }}

QListView, QListWidget {{ background: {t['bg']}; border: none; outline: 0; }}
QListWidget::item {{ min-height: 56px; padding: 6px 12px; border-radius: 10px; margin: 3px 4px; }}
QListWidget::item:hover {{ background: {t['hover']}; }}
QListWidget::item:selected {{ background: {t['accent']}; color: {t['accent_text']}; }}

QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: {t['surface']}; width: 22px; margin: 0; border-radius: 11px; }}
QScrollBar::handle:vertical {{ background: {t['border']}; min-height: 60px; border-radius: 11px; }}
QScrollBar::handle:vertical:hover {{ background: {t['accent']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ height: 0; }}

QProgressBar {{ background: {t['surface2']}; border: none; border-radius: 8px; height: 16px; text-align: center; }}
QProgressBar::chunk {{ background: {t['accent']}; border-radius: 8px; }}
QSlider::groove:horizontal {{ height: 10px; background: {t['surface2']}; border-radius: 5px; }}
QSlider::handle:horizontal {{ width: 24px; margin: -8px 0; border-radius: 12px; background: {t['accent']}; }}
QSlider::sub-page:horizontal {{ background: {t['accent']}; border-radius: 5px; }}

QWidget#Overlay {{ background: rgba(0, 0, 0, 170); }}
QFrame#OverlayBox, QFrame#DialogBox {{ background: {t['surface']}; border: 3px solid {t['accent']}; border-radius: 20px; }}
QLabel#OverlayText {{ font-size: {font_size + 7}pt; font-weight: 700; }}
QFrame#Toast {{ background: {t['surface']}; border: 2px solid {t['accent']}; border-radius: 14px; }}
QToolTip {{ background: {t['surface']}; color: {t['text']}; border: 1px solid {t['border']}; padding: 6px; }}
"""
