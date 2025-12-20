import logging
import sys
import time
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSlider, QLabel, QFrame, QApplication
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPoint
from PyQt6.QtGui import QKeyEvent, QMouseEvent, QCursor
from core.video_player import VideoPlayer

logger = logging.getLogger(__name__)


class FullscreenControls(QWidget):
    """Fullscreen controls overlay"""
    
    previous_clicked = pyqtSignal()
    play_pause_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    next_clicked = pyqtSignal()
    volume_changed = pyqtSignal(int)
    position_changed = pyqtSignal(int)
    exit_fullscreen_clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 200);")
        self.init_ui()
        
        self.hide_timer = QTimer()
        self.hide_timer.timeout.connect(self.hide)
        self.hide_timer.setSingleShot(True)
    
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 10, 20, 10)
        main_layout.setSpacing(10)
        
        timeline_layout = QHBoxLayout()
        
        self.time_label = QLabel("00:00")
        self.time_label.setStyleSheet("font-size: 14pt; color: white;")
        timeline_layout.addWidget(self.time_label)
        
        self.timeline_slider = QSlider(Qt.Orientation.Horizontal)
        self.timeline_slider.setRange(0, 1000)
        self.timeline_slider.setValue(0)
        self.timeline_slider.setStyleSheet("QSlider { background-color: transparent; }")
        self.timeline_slider.sliderMoved.connect(self.position_changed.emit)
        timeline_layout.addWidget(self.timeline_slider)
        
        self.duration_label = QLabel("00:00")
        self.duration_label.setStyleSheet("font-size: 14pt; color: white;")
        timeline_layout.addWidget(self.duration_label)
        
        main_layout.addLayout(timeline_layout)
        
        control_layout = QHBoxLayout()
        
        prev_btn = QPushButton("⏮")
        prev_btn.setStyleSheet("font-size: 24pt; padding: 10px 20px; background-color: #333; color: white; border: none; border-radius: 5px;")
        prev_btn.clicked.connect(self.previous_clicked.emit)
        control_layout.addWidget(prev_btn)
        
        self.play_pause_btn = QPushButton("⏸")
        self.play_pause_btn.setStyleSheet("font-size: 24pt; padding: 10px 20px; background-color: #4CAF50; color: white; border: none; border-radius: 5px;")
        self.play_pause_btn.clicked.connect(self.play_pause_clicked.emit)
        control_layout.addWidget(self.play_pause_btn)
        
        stop_btn = QPushButton("⏹")
        stop_btn.setStyleSheet("font-size: 24pt; padding: 10px 20px; background-color: #f44336; color: white; border: none; border-radius: 5px;")
        stop_btn.clicked.connect(self.stop_clicked.emit)
        control_layout.addWidget(stop_btn)
        
        next_btn = QPushButton("⏭")
        next_btn.setStyleSheet("font-size: 24pt; padding: 10px 20px; background-color: #333; color: white; border: none; border-radius: 5px;")
        next_btn.clicked.connect(self.next_clicked.emit)
        control_layout.addWidget(next_btn)
        
        control_layout.addStretch()
        
        volume_label = QLabel("🔊")
        volume_label.setStyleSheet("font-size: 20pt; color: white;")
        control_layout.addWidget(volume_label)
        
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.setFixedWidth(150)
        self.volume_slider.setStyleSheet("QSlider { background-color: transparent; }")
        self.volume_slider.valueChanged.connect(self.volume_changed.emit)
        control_layout.addWidget(self.volume_slider)
        
        exit_btn = QPushButton("⛶ Izađi (ESC)")
        exit_btn.setStyleSheet("font-size: 16pt; padding: 10px 20px; background-color: #333; color: white; border: none; border-radius: 5px;")
        exit_btn.clicked.connect(self.exit_fullscreen_clicked.emit)
        control_layout.addWidget(exit_btn)
        
        main_layout.addLayout(control_layout)
    
    def set_playing(self, is_playing: bool):
        self.play_pause_btn.setText("⏸" if is_playing else "▶")
    
    def set_position(self, position: int, duration: int):
        self.timeline_slider.blockSignals(True)
        self.timeline_slider.setValue(position)
        self.timeline_slider.blockSignals(False)
        
        pos_min = position // 60000
        pos_sec = (position // 1000) % 60
        self.time_label.setText(f"{pos_min:02d}:{pos_sec:02d}")
        
        dur_min = duration // 60000
        dur_sec = (duration // 1000) % 60
        self.duration_label.setText(f"{dur_min:02d}:{dur_sec:02d}")
    
    def show_with_timer(self):
        self.show()
        self.raise_()
        self.hide_timer.stop()
        self.hide_timer.start(4000)


class VideoFrame(QFrame):
    """Video frame for VLC rendering"""
    
    double_clicked = pyqtSignal()
    single_clicked = pyqtSignal()
    mouse_moved = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: black;")
        self.setMouseTracking(True)
        
        self.click_timer = QTimer()
        self.click_timer.setSingleShot(True)
        self.click_timer.timeout.connect(self._emit_single_click)
        self.pending_click = False
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.click_timer.isActive():
                self.click_timer.stop()
                self.pending_click = False
                self.double_clicked.emit()
            else:
                self.pending_click = True
                self.click_timer.start(300)
        super().mousePressEvent(event)
    
    def _emit_single_click(self):
        if self.pending_click:
            self.pending_click = False
            self.single_clicked.emit()
    
    def mouseMoveEvent(self, event):
        self.mouse_moved.emit()
        super().mouseMoveEvent(event)


class PlayerWidget(QWidget):
    """Video player widget with controls"""
    
    previous_requested = pyqtSignal()
    next_requested = pyqtSignal()
    
    def __init__(self, video_player: VideoPlayer, parent=None):
        super().__init__(parent)
        self.video_player = video_player
        self.is_fullscreen = False
        self.is_playing = False
        self.fullscreen_window = None
        
        self.position_timer = QTimer()
        self.position_timer.timeout.connect(self.update_position)
        self.position_timer.setInterval(1000)
        
        # Cursor hide timer for fullscreen
        self.cursor_timer = QTimer()
        self.cursor_timer.setSingleShot(True)
        self.cursor_timer.timeout.connect(self._hide_cursor)
        
        # Mouse polling timer for fullscreen
        self.mouse_poll_timer = QTimer()
        self.mouse_poll_timer.timeout.connect(self._poll_mouse)
        self.mouse_poll_timer.setInterval(50)  # Faster polling for better click detection
        self.last_mouse_pos = QPoint()
        
        # Click detection state
        self.mouse_was_pressed = False
        self.click_times = []  # List of recent click timestamps
        
        self.init_ui()
        self._setup_vlc_output()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Video frame
        self.video_frame = VideoFrame()
        self.video_frame.setMinimumSize(640, 480)
        self.video_frame.double_clicked.connect(self.toggle_fullscreen)
        self.video_frame.single_clicked.connect(self._on_video_click)
        self.video_frame.mouse_moved.connect(self._on_video_mouse_move)
        
        layout.addWidget(self.video_frame)
        
        # Fullscreen controls
        self.fullscreen_controls = FullscreenControls()
        self.fullscreen_controls.hide()
        self.fullscreen_controls.previous_clicked.connect(self._on_previous)
        self.fullscreen_controls.play_pause_clicked.connect(self.toggle_play_pause)
        self.fullscreen_controls.stop_clicked.connect(self.stop)
        self.fullscreen_controls.next_clicked.connect(self._on_next)
        self.fullscreen_controls.volume_changed.connect(self.set_volume)
        self.fullscreen_controls.position_changed.connect(self.set_position)
        self.fullscreen_controls.exit_fullscreen_clicked.connect(self.exit_fullscreen)
        
        # Control bar
        self.control_bar = QWidget()
        control_layout = QVBoxLayout(self.control_bar)
        control_layout.setContentsMargins(10, 5, 10, 5)
        control_layout.setSpacing(5)
        
        timeline_layout = QHBoxLayout()
        
        self.time_label = QLabel("00:00")
        self.time_label.setStyleSheet("font-size: 10pt; color: #999;")
        timeline_layout.addWidget(self.time_label)
        
        self.timeline_slider = QSlider(Qt.Orientation.Horizontal)
        self.timeline_slider.setRange(0, 1000)
        self.timeline_slider.setValue(0)
        self.timeline_slider.sliderMoved.connect(self.set_position)
        timeline_layout.addWidget(self.timeline_slider)
        
        self.duration_label = QLabel("00:00")
        self.duration_label.setStyleSheet("font-size: 10pt; color: #999;")
        timeline_layout.addWidget(self.duration_label)
        
        control_layout.addLayout(timeline_layout)
        
        button_layout = QHBoxLayout()
        
        prev_btn = QPushButton("⏮")
        prev_btn.setStyleSheet("font-size: 16pt; padding: 5px 15px;")
        prev_btn.clicked.connect(self._on_previous)
        button_layout.addWidget(prev_btn)
        
        self.play_btn = QPushButton("▶")
        self.play_btn.setStyleSheet("font-size: 16pt; padding: 5px 15px;")
        self.play_btn.clicked.connect(self.toggle_play_pause)
        button_layout.addWidget(self.play_btn)
        
        self.stop_btn = QPushButton("⏹")
        self.stop_btn.setStyleSheet("font-size: 16pt; padding: 5px 15px;")
        self.stop_btn.clicked.connect(self.stop)
        button_layout.addWidget(self.stop_btn)
        
        next_btn = QPushButton("⏭")
        next_btn.setStyleSheet("font-size: 16pt; padding: 5px 15px;")
        next_btn.clicked.connect(self._on_next)
        button_layout.addWidget(next_btn)
        
        volume_label = QLabel("🔊")
        volume_label.setStyleSheet("font-size: 14pt;")
        button_layout.addWidget(volume_label)
        
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.valueChanged.connect(self.set_volume)
        button_layout.addWidget(self.volume_slider)
        
        button_layout.addStretch()
        
        fullscreen_btn = QPushButton("⛶ Fullscreen")
        fullscreen_btn.setStyleSheet("font-size: 14pt; padding: 5px 15px; background-color: #333; color: white;")
        fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        button_layout.addWidget(fullscreen_btn)
        
        self.status_label = QLabel("Spremno")
        self.status_label.setStyleSheet("font-size: 12pt; color: #666;")
        button_layout.addWidget(self.status_label)
        
        control_layout.addLayout(button_layout)
        layout.addWidget(self.control_bar)
        
        self.set_volume(70)
    
    def _setup_vlc_output(self):
        QTimer.singleShot(100, self._set_vlc_output_internal)
    
    def _set_vlc_output_internal(self):
        if not self.video_player.media_player:
            return
        
        try:
            win_id = int(self.video_frame.winId())
            if sys.platform.startswith('linux'):
                self.video_player.media_player.set_xwindow(win_id)
            elif sys.platform == 'win32':
                self.video_player.media_player.set_hwnd(win_id)
            elif sys.platform == 'darwin':
                self.video_player.media_player.set_nsobject(win_id)
            logger.info(f"VLC output set to video_frame (winId: {win_id})")
        except Exception as e:
            logger.error(f"Failed to set VLC output: {e}")
    
    def _poll_mouse(self):
        """Poll mouse position and detect clicks for fullscreen mode"""
        if not self.is_fullscreen or not self.fullscreen_window:
            return
        
        current_pos = QCursor.pos()
        is_pressed = bool(QApplication.mouseButtons() & Qt.MouseButton.LeftButton)
        
        # Detect mouse movement
        if current_pos != self.last_mouse_pos:
            self.last_mouse_pos = current_pos
            self._show_cursor()
            self.fullscreen_controls.show_with_timer()
        
        # Detect click (transition from not pressed to pressed)
        if is_pressed and not self.mouse_was_pressed:
            # Check if click is on video area (not on controls)
            controls_rect = self.fullscreen_controls.geometry()
            local_pos = self.fullscreen_window.mapFromGlobal(current_pos)
            
            if not controls_rect.contains(local_pos) or not self.fullscreen_controls.isVisible():
                self._on_fullscreen_click()
        
        self.mouse_was_pressed = is_pressed
    
    def _on_fullscreen_click(self):
        """Handle click in fullscreen mode with double-click detection"""
        current_time = time.time()
        
        # Remove old clicks (older than 400ms)
        self.click_times = [t for t in self.click_times if current_time - t < 0.4]
        
        # Add current click
        self.click_times.append(current_time)
        
        logger.debug(f"Fullscreen click detected, click_times count: {len(self.click_times)}")
        
        if len(self.click_times) >= 2:
            # Double click detected - exit fullscreen
            logger.info("Double click detected - exiting fullscreen")
            self.click_times.clear()
            self.exit_fullscreen()
        else:
            # Single click - show controls (with delay to allow for double click)
            QTimer.singleShot(400, self._check_single_click)
    
    def _check_single_click(self):
        """Check if it was a single click (no second click came)"""
        if len(self.click_times) == 1:
            logger.debug("Single click confirmed - showing controls")
            self._show_cursor()
            self.fullscreen_controls.show_with_timer()
            self.click_times.clear()
    
    def _hide_cursor(self):
        if self.is_fullscreen and self.fullscreen_window:
            self.fullscreen_window.setCursor(Qt.CursorShape.BlankCursor)
    
    def _show_cursor(self):
        if self.is_fullscreen and self.fullscreen_window:
            self.fullscreen_window.setCursor(Qt.CursorShape.ArrowCursor)
            self.cursor_timer.stop()
            self.cursor_timer.start(3000)
    
    def _on_previous(self):
        logger.debug("Previous requested")
        self.previous_requested.emit()
    
    def _on_next(self):
        logger.debug("Next requested")
        self.next_requested.emit()
    
    def _on_video_click(self):
        if self.is_fullscreen:
            self._show_cursor()
            self.fullscreen_controls.show_with_timer()
    
    def _on_video_mouse_move(self):
        if self.is_fullscreen:
            self._show_cursor()
            self.fullscreen_controls.show_with_timer()
    
    def toggle_fullscreen(self):
        if self.is_fullscreen:
            self.exit_fullscreen()
        else:
            self.enter_fullscreen()
    
    def enter_fullscreen(self):
        if self.is_fullscreen:
            return
        
        logger.info("Entering fullscreen...")
        self.is_fullscreen = True
        
        # Create fullscreen window
        self.fullscreen_window = QWidget(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.fullscreen_window.setStyleSheet("background-color: black;")
        self.fullscreen_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.fullscreen_window.setMouseTracking(True)
        
        fs_layout = QVBoxLayout(self.fullscreen_window)
        fs_layout.setContentsMargins(0, 0, 0, 0)
        fs_layout.setSpacing(0)
        
        # Move video frame to fullscreen
        self.video_frame.setParent(self.fullscreen_window)
        fs_layout.addWidget(self.video_frame)
        
        # Setup controls
        self.fullscreen_controls.setParent(self.fullscreen_window)
        
        # Show fullscreen
        self.fullscreen_window.showFullScreen()
        
        # Position controls
        QTimer.singleShot(100, self._setup_fullscreen_controls)
        
        # Keyboard handler
        self.fullscreen_window.keyPressEvent = self._fullscreen_key_press
        self.fullscreen_window.setFocus()
        
        # Start mouse polling
        self.last_mouse_pos = QCursor.pos()
        self.mouse_was_pressed = False
        self.click_times.clear()
        self.mouse_poll_timer.start()
        
        logger.info("Fullscreen entered")
    
    def _setup_fullscreen_controls(self):
        if not self.fullscreen_window:
            return
        
        w = self.fullscreen_window.width()
        h = self.fullscreen_window.height()
        controls_height = 120
        
        self.fullscreen_controls.setGeometry(0, h - controls_height, w, controls_height)
        self.fullscreen_controls.raise_()
        self.fullscreen_controls.show_with_timer()
    
    def _fullscreen_key_press(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key.Key_Escape or key == Qt.Key.Key_F:
            self.exit_fullscreen()
        elif key == Qt.Key.Key_Space:
            self.toggle_play_pause()
        elif key == Qt.Key.Key_PageUp:
            self._on_previous()
        elif key == Qt.Key.Key_PageDown:
            self._on_next()
        elif key == Qt.Key.Key_Up:
            self.set_volume(min(100, self.volume_slider.value() + 5))
        elif key == Qt.Key.Key_Down:
            self.set_volume(max(0, self.volume_slider.value() - 5))
    
    def exit_fullscreen(self):
        if not self.is_fullscreen:
            return
        
        logger.info("Exiting fullscreen...")
        self.is_fullscreen = False
        
        # Stop timers
        self.cursor_timer.stop()
        self.mouse_poll_timer.stop()
        self.click_times.clear()
        
        # Hide controls
        self.fullscreen_controls.hide()
        self.fullscreen_controls.hide_timer.stop()
        
        # Move video frame back
        self.video_frame.setParent(self)
        self.layout().insertWidget(0, self.video_frame)
        
        # Move controls back
        self.fullscreen_controls.setParent(self)
        
        # Close fullscreen window
        if self.fullscreen_window:
            self.fullscreen_window.close()
            self.fullscreen_window = None
        
        logger.info("Fullscreen exited")
    
    def play_url(self, url: str):
        if not url:
            logger.warning("play_url called with empty URL")
            self.status_label.setText("Greška: Nema URL-a")
            return
        
        try:
            self._set_vlc_output_internal()
            
            self.video_player.play(url)
            self.is_playing = True
            self.play_btn.setText("⏸")
            self.fullscreen_controls.set_playing(True)
            self.status_label.setText("Reprodukcija...")
            self.position_timer.start()
            logger.info(f"Playing: {url}")
        except Exception as e:
            logger.error(f"Error playing URL: {e}", exc_info=True)
            self.status_label.setText("Greška pri reprodukciji")
            self.is_playing = False
    
    def toggle_play_pause(self):
        try:
            if self.is_playing:
                self.video_player.pause()
                self.is_playing = False
                self.play_btn.setText("▶")
                self.fullscreen_controls.set_playing(False)
                self.status_label.setText("Pauzirano")
                self.position_timer.stop()
            else:
                self.video_player.resume()
                self.is_playing = True
                self.play_btn.setText("⏸")
                self.fullscreen_controls.set_playing(True)
                self.status_label.setText("Reprodukcija...")
                self.position_timer.start()
        except Exception as e:
            logger.error(f"Error in toggle_play_pause: {e}")
    
    def stop(self):
        try:
            self.video_player.stop()
            self.is_playing = False
            self.play_btn.setText("▶")
            self.fullscreen_controls.set_playing(False)
            self.status_label.setText("Zaustavljeno")
            self.position_timer.stop()
            self.timeline_slider.setValue(0)
            self.time_label.setText("00:00")
        except Exception as e:
            logger.error(f"Error in stop: {e}")
    
    def set_volume(self, volume: int):
        self.video_player.set_volume(volume)
        self.volume_slider.blockSignals(True)
        self.volume_slider.setValue(volume)
        self.volume_slider.blockSignals(False)
        self.fullscreen_controls.volume_slider.blockSignals(True)
        self.fullscreen_controls.volume_slider.setValue(volume)
        self.fullscreen_controls.volume_slider.blockSignals(False)
    
    def set_position(self, position: int):
        if self.video_player.media_player:
            self.video_player.media_player.set_position(position / 1000.0)
    
    def update_position(self):
        if not self.video_player.media_player or not self.is_playing:
            return
        
        try:
            length = self.video_player.media_player.get_length()
            time_ms = self.video_player.media_player.get_time()
            
            if length > 0:
                position = int((time_ms / length) * 1000)
                
                self.timeline_slider.blockSignals(True)
                self.timeline_slider.setValue(position)
                self.timeline_slider.blockSignals(False)
                
                time_min = time_ms // 60000
                time_sec = (time_ms // 1000) % 60
                self.time_label.setText(f"{time_min:02d}:{time_sec:02d}")
                
                length_min = length // 60000
                length_sec = (length // 1000) % 60
                self.duration_label.setText(f"{length_min:02d}:{length_sec:02d}")
                
                if self.is_fullscreen:
                    self.fullscreen_controls.set_position(time_ms, length)
        except Exception as e:
            logger.error(f"Error updating position: {e}")
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.is_fullscreen and self.fullscreen_window:
            self._setup_fullscreen_controls()