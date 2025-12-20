import sys
import logging
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont, QFontDatabase
from ui.main_window import MainWindow
from core.video_player import VideoPlayer
from core.database import Database

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migecast.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def setup_directories():
    """Create necessary directories"""
    directories = ['data', 'cache', 'logs']
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)


def get_system_font():
    """Get system font that supports Serbian letters"""
    # Preferred fonts that support Cyrillic
    preferred_fonts = [
        'Segoe UI',
        'Arial',
        'Tahoma',
        'Verdana',
        'Calibri'
    ]
    
    available_fonts = QFontDatabase.families()
    
    for font_name in preferred_fonts:
        if font_name in available_fonts:
            return font_name
    
    # Fallback to default
    return QApplication.font().family()


def main():
    """Main application entry point"""
    logger.info("="*60)
    logger.info("Starting MigeCast IPTV Application")
    logger.info("="*60)
    
    # Setup directories
    try:
        setup_directories()
        logger.info("Directories created successfully")
    except Exception as e:
        logger.error(f"Failed to setup directories: {e}", exc_info=True)
    
    # Initialize database
    try:
        db = Database()
        logger.info(f"Database initialized (Singleton): {db.db_path}")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
        logger.error("Cannot continue without database - exiting")
        return
    
    # Create application
    try:
        app = QApplication(sys.argv)
        logger.info("Qt Application created")
    except Exception as e:
        logger.error(f"Failed to create Qt application: {e}", exc_info=True)
        return
    
    # Set application font
    try:
        font_family = get_system_font()
        app.setFont(QFont(font_family, 10))
        logger.info(f"Using font: {font_family}")
    except Exception as e:
        logger.error(f"Failed to set application font: {e}", exc_info=True)
    
    # Initialize video player
    try:
        video_player = VideoPlayer()
        logger.info("Video player initialized")
    except Exception as e:
        logger.error(f"Failed to initialize video player: {e}", exc_info=True)
        logger.error("Video player initialization failed - continuing without video")
        video_player = None
    
    # Create main window
    try:
        window = MainWindow(video_player)
        logger.info("Main window created")
        window.show()
        logger.info("Main window displayed")
    except Exception as e:
        logger.error(f"Failed to create/show main window: {e}", exc_info=True)
        logger.error("Cannot display main window - exiting")
        return
    
    # Run application
    try:
        logger.info("Entering application main loop")
        exit_code = app.exec()
        logger.info(f"Application exited with code: {exit_code}")
        sys.exit(exit_code)
    except Exception as e:
        logger.error(f"Error in application main loop: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.error(f"Application crashed: {e}", exc_info=True)
        input("Press Enter to exit...")