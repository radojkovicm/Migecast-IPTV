import logging
from typing import Optional, Callable
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

logger = logging.getLogger(__name__)


class StreamManager(QObject):
    """Stream connection and health monitoring manager"""
    
    # Signals
    connection_status_changed = pyqtSignal(str)  # 'connected', 'disconnected', 'reconnecting'
    
    def __init__(self):
        super().__init__()
        
        self.current_url: Optional[str] = None
        self.is_connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 3
        
        # Health check timer
        self.health_timer = QTimer()
        self.health_timer.timeout.connect(self.check_health)
        self.health_timer.setInterval(5000)  # Check every 5 seconds
    
    def start_stream(self, url: str):
        """Start monitoring stream"""
        self.current_url = url
        self.is_connected = True
        self.reconnect_attempts = 0
        self.health_timer.start()
        self.connection_status_changed.emit('connected')
        logger.info(f"Stream monitoring started: {url}")
    
    def stop_stream(self):
        """Stop monitoring stream"""
        self.health_timer.stop()
        self.current_url = None
        self.is_connected = False
        self.connection_status_changed.emit('disconnected')
        logger.info("Stream monitoring stopped")
    
    def check_health(self):
        """Check stream health"""
        # This is a placeholder for actual health checking
        # In production, you would ping the stream or check buffer status
        if self.current_url and self.is_connected:
            logger.debug(f"Stream health check: OK")
    
    def handle_connection_lost(self, reconnect_callback: Callable):
        """Handle lost connection and attempt reconnect"""
        if self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
            self.connection_status_changed.emit('reconnecting')
            logger.warning(f"Connection lost, attempting reconnect {self.reconnect_attempts}/{self.max_reconnect_attempts}")
            
            # Attempt reconnect
            if reconnect_callback:
                reconnect_callback()
        else:
            logger.error("Max reconnect attempts reached")
            self.connection_status_changed.emit('disconnected')
            self.stop_stream()