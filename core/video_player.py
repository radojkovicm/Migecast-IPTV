import logging
import vlc
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

logger = logging.getLogger(__name__)


class VideoPlayer(QObject):
    """VLC-based video player with auto-reconnect and mouse events"""
    
    state_changed = pyqtSignal(str)  # playing, paused, stopped, error
    mouse_clicked = pyqtSignal()     # VLC detected mouse click
    mouse_moved = pyqtSignal()       # VLC detected mouse move
    error_occurred = pyqtSignal()    # Error occurred (thread-safe signal)
    
    def __init__(self):
        super().__init__()
        
        self._is_destroyed = False  # ← Track destruction state
        
        try:
            # VLC instance with optimized options
            vlc_args = [
                '--network-caching=2000',
                '--clock-jitter=0',
                '--clock-synchro=0',
                '--no-video-title-show',
                '--no-stats',
                '--no-osd',
                '--quiet'
            ]
            
            self.instance = vlc.Instance(' '.join(vlc_args))
            self.media_player = self.instance.media_player_new()
            
            # Reconnect settings
            self.max_reconnect_attempts = 3
            self.reconnect_attempt = 0
            self.current_url = None
            
            # Auto-reconnect timer
            self.reconnect_timer = QTimer()
            self.reconnect_timer.timeout.connect(self.attempt_reconnect)
            self.reconnect_timer.setSingleShot(True)
            
            # Connect error signal to timer start (thread-safe)
            self.error_occurred.connect(self._handle_error_reconnect)
            
            # Event manager - state events
            self.event_manager = self.media_player.event_manager()
            self.event_manager.event_attach(vlc.EventType.MediaPlayerEncounteredError, self.on_error)
            self.event_manager.event_attach(vlc.EventType.MediaPlayerPlaying, self.on_playing)
            self.event_manager.event_attach(vlc.EventType.MediaPlayerPaused, self.on_paused)
            self.event_manager.event_attach(vlc.EventType.MediaPlayerStopped, self.on_stopped)
            
            logger.info("VideoPlayer initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize VideoPlayer: {e}", exc_info=True)
            self.instance = None
            self.media_player = None
            self.event_manager = None
            self.reconnect_timer = None
            
    def cleanup(self):
        """Cleanup VLC resources"""
        if self._is_destroyed:
            return
        
        logger.info("Cleaning up VideoPlayer...")
        self._is_destroyed = True
        
        try:
            # Stop reconnect timer
            if self.reconnect_timer:
                self.reconnect_timer.stop()
                self.reconnect_timer = None
            
            # Stop playback
            if self.media_player:
                try:
                    if self.media_player.is_playing():
                        self.media_player.stop()
                except:
                    pass
                
                # Release media player
                try:
                    self.media_player.release()
                except Exception as e:
                    logger.error(f"Error releasing media_player: {e}")
                self.media_player = None
            
            # Release instance
            if self.instance:
                try:
                    self.instance.release()
                except Exception as e:
                    logger.error(f"Error releasing VLC instance: {e}")
                self.instance = None
            
            logger.info("VideoPlayer cleanup complete")
        except Exception as e:
            logger.error(f"Error during VideoPlayer cleanup: {e}")
    
    def __del__(self):
        """Destructor - ensure cleanup"""
        self.cleanup()
    
    def play(self, url: str):
        """Play media from URL"""
        if not self.media_player:
            logger.error("VideoPlayer not properly initialized")
            self.state_changed.emit('error')
            return
        
        self.current_url = url
        self.reconnect_attempt = 0
        
        try:
            media = self.instance.media_new(url)
            
            # Add HTTP headers for IPTV streams (required by many servers)
            media.add_option("http-user-agent=VLC/3.0.0")
            media.add_option("http-referrer=http://example.com")
            
            # media.parse()
            self.media_player.set_media(media)
            self.media_player.play()
            
            logger.info(f"Playing URL: {url}")
        
        except Exception as e:
            logger.error(f"Failed to play URL: {e}", exc_info=True)
            self.state_changed.emit('error')
    
    def pause(self):
        """Pause playback"""
        if self.media_player and self.media_player.is_playing():
            self.media_player.pause()
            logger.info("Playback paused")
    
    def resume(self):
        """Resume playback"""
        if self.media_player and not self.media_player.is_playing():
            self.media_player.play()
            logger.info("Playback resumed")
    
    def stop(self):
        """Stop playback"""
        if self.media_player:
            try:
                if self.media_player.is_playing():
                    self.media_player.stop()
            except Exception as e:
                logger.error(f"Error while stopping media player: {e}")
        self.current_url = None
        if self.reconnect_timer:
            self.reconnect_timer.stop()
        logger.debug("Playback stopped")

    def set_volume(self, volume: int):
        """Set volume (0-100)"""
        if self.media_player:
            self.media_player.audio_set_volume(volume)
    
    def on_error(self, event):
        """Handle player error"""
        logger.error("VLC player encountered an error")
        self.state_changed.emit('error')
        
        # Emit signal to trigger reconnect in main thread
        # Only reconnect if we haven't exceeded max attempts yet
        if self.current_url and self.reconnect_attempt < self.max_reconnect_attempts:
            self.error_occurred.emit()
        else:
            logger.warning(f"Reconnection failed after {self.reconnect_attempt} attempts")
            self.reconnect_attempt = 0
    
    def _handle_error_reconnect(self):
        """Handle error reconnect in main thread (slot)"""
        if self.reconnect_timer:
            # Stop any existing timer first
            self.reconnect_timer.stop()
            self.reconnect_timer.setSingleShot(True)
            self.reconnect_timer.start(2000)
    
    def attempt_reconnect(self):
        """Attempt to reconnect"""
        self.reconnect_attempt += 1
        logger.info(f"Reconnecting... Attempt {self.reconnect_attempt}/{self.max_reconnect_attempts}")
        
        if self.current_url:
            self.play(self.current_url)
    
    def on_playing(self, event):
        """Handle playing state"""
        self.state_changed.emit('playing')
        self.reconnect_attempt = 0
    
    def on_paused(self, event):
        """Handle paused state"""
        self.state_changed.emit('paused')
    
    def on_stopped(self, event):
        """Handle stopped state"""
        self.state_changed.emit('stopped')