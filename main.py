import sys
import logging
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont, QFontDatabase
from ui.main_window import MainWindow
from core.video_player import VideoPlayer
from core.database import Database

# Setup logging - Change to WARNING for production, INFO for development
logging.basicConfig(
    level=logging.INFO,  # Change to logging.WARNING for production
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def setup_directories():
    """Create necessary directories"""
    directories = ['data', 'cache', 'logs']
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)


def get_system_font():
    """Get system font that supports Serbian letters"""
    preferred_fonts = ['Segoe UI', 'Arial', 'Tahoma', 'Verdana', 'Calibri']
    available_fonts = QFontDatabase.families()
    
    for font_name in preferred_fonts:
        if font_name in available_fonts:
            return font_name
    
    return QApplication.font().family()


def main():
    """Main application entry point"""
    logger.info("Starting MigeCast IPTV Application")
    
    # Setup directories
    try:
        setup_directories()
    except Exception as e:
        logger.error(f"Failed to setup directories: {e}")
        return
    
    # Initialize database
    try:
        db = Database()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return
    
    # Create application
    try:
        app = QApplication(sys.argv)
        font_family = get_system_font()
        app.setFont(QFont(font_family, 10))
    except Exception as e:
        logger.error(f"Failed to create application: {e}")
        return
    
    # Initialize video player
    try:
        video_player = VideoPlayer()
    except Exception as e:
        logger.error(f"Failed to initialize video player: {e}")
        video_player = None
    
    # Create and show main window
    try:
        window = MainWindow(video_player)
        window.showFullScreen() 
    except Exception as e:
        logger.error(f"Failed to create main window: {e}")
        return
    
    # Run application
    try:
        exit_code = app.exec()
        sys.exit(exit_code)
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.critical(f"Critical error: {e}")
        input("Press Enter to exit...")