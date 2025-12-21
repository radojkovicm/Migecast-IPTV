import logging
import sys
import time
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSlider, QLabel, QFrame, QApplication
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPoint
from PyQt6.QtGui import QKeyEvent, QMouseEvent, QCursor
from core.video_player import VideoPlayer

logger = logging.getLogger(__name__)


class SeekableSlider(QSlider):
    """Custom slider with YouTube-style click-to-seek"""
    
    seek_requested = pyqtSignal(int)
    
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setMouseTracking(True)
        self.is_seeking = False
    
    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press - instant seek to clicked position"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_seeking = True
            self._seek_to_position(event.position().x())
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle drag - continuous seek while dragging"""
        if self.is_seeking and (event.buttons() & Qt.MouseButton.LeftButton):
            self._seek_to_position(event.position().x())
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release - finalize seek"""
        if event.button() == Qt.MouseButton.LeftButton and self.is_seeking:
            self.is_seeking = False
            self._seek_to_position(event.position().x())
        super().mouseReleaseEvent(event)
    
    def _seek_to_position(self, click_x: float):
        """Calculate and emit seek position from click coordinates"""
        try:
            width = self.width()
            if width <= 0:
                return
            
            # Calculate position (0-1000 range)
            position = int((click_x / width) * self.maximum())
            position = max(self.minimum(), min(position, self.maximum()))
            
            # Update slider value
            self.setValue(position)
            
            # Emit seek request
            self.seek_requested.emit(position)
            
            logger.debug(f"Seek: x={click_x:.1f}, width={width}, position={position}")
        except Exception as e:
            logger.error(f"Error in _seek_to_position: {e}", exc_info=True)

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
        
        self.timeline_slider = SeekableSlider(Qt.Orientation.Horizontal)
        self.timeline_slider.setRange(0, 1000)
        self.timeline_slider.setValue(0)
        self.timeline_slider.setStyleSheet("QSlider { background-color: transparent; }")
        # self.timeline_slider.seek_requested.connect(lambda val: self.position_changed.emit(val))
        # Enable click on slider to seek
        self.timeline_slider.seek_requested.connect(lambda val: self.position_changed.emit(val))
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
        
        self.volume_icon = QLabel("🔊")
        self.volume_icon.setStyleSheet("font-size: 20pt; color: white;")
        self.volume_icon.setCursor(Qt.CursorShape.PointingHandCursor)
        control_layout.addWidget(self.volume_icon)

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
    
    def set_position(self, time_ms: int, length_ms: int):
        """Update position display in fullscreen controls"""
        try:
            if length_ms <= 0:
                return
            
            # Update slider position (convert ms to 0-1000 range)
            position = int((time_ms / length_ms) * 1000)
            self.timeline_slider.blockSignals(True)
            self.timeline_slider.setValue(position)
            self.timeline_slider.blockSignals(False)
            
            # Update time labels
            time_min = time_ms // 60000
            time_sec = (time_ms // 1000) % 60
            self.time_label.setText(f"{time_min:02d}:{time_sec:02d}")
            
            length_min = length_ms // 60000
            length_sec = (length_ms // 1000) % 60
            self.duration_label.setText(f"{length_min:02d}:{length_sec:02d}")
        except Exception as e:
            logger.error(f"Error in FullscreenControls.set_position: {e}", exc_info=True)
    
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
        player_widget = self.parent()
        while player_widget and not hasattr(player_widget, 'content_type'):
            player_widget = player_widget.parent()

        # Ako NISMO u TV modu, ignoriši double-click logiku potpuno
        if not player_widget or player_widget.content_type != 'tv':
            super().mousePressEvent(event)
            return

        # TV MOD: omogući double-click za fullscreen toggle
        logger.info(f"🖱️ VideoFrame MOUSE PRESS (TV mode) - button={event.button()}")

        if event.button() == Qt.MouseButton.LeftButton:
            if self.click_timer.isActive():
                logger.info("🖱️🖱️ DOUBLE CLICK DETECTED (TV mode)")
                self.click_timer.stop()
                self.pending_click = False
                self.double_clicked.emit()
            else:
                self.pending_click = True
                self.click_timer.start(300)
        
        super().mousePressEvent(event)

    def _emit_single_click(self):
        if self.pending_click:
            logger.info("🖱️ Single click CONFIRMED (timeout) - emitting single_clicked")
            self.pending_click = False
            self.single_clicked.emit()

    
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
    playback_exited = pyqtSignal()  # Emitted when user exits playback
    
    def __init__(self, video_player: VideoPlayer, parent=None):
        super().__init__(parent)
        self.video_player = video_player
        self.is_fullscreen = False
        self.is_playing = False
        self.fullscreen_window = None
        self.content_type = 'vod'
        
        self.position_timer = QTimer()
        self.position_timer.timeout.connect(self.update_position)
        self.position_timer.setInterval(200)
        
        self.cursor_timer = QTimer()
        self.cursor_timer.setSingleShot(True)
        self.cursor_timer.timeout.connect(self._hide_cursor)
        
        self.mouse_poll_timer = QTimer()
        self.mouse_poll_timer.timeout.connect(self._poll_mouse)
        self.mouse_poll_timer.setInterval(50)
        self.last_mouse_pos = QPoint()
        
        self.mouse_was_pressed = False
        self.click_times = []
        
        self.init_ui()
        self._setup_vlc_output()
        
        # ← DODAJ OVDE (POSLE init_ui):
        # Double-click timer za video_frame (VLC mouse workaround)
        self.video_click_timer = QTimer()
        self.video_click_timer.setSingleShot(True)
        self.video_click_timer.timeout.connect(self._video_single_click_action)
        
        # Install na OVERLAY, ne video_frame
        QTimer.singleShot(200, lambda: self.click_overlay.installEventFilter(self))
        
        # DODAJ: Flag za non-fullscreen double click
        self.normal_click_times = []
        
        # PROMENI: Pokreni mouse polling UVEK (ne samo u fullscreen)
        self.mouse_poll_timer.start()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Video frame container
        video_container = QWidget()
        video_container_layout = QVBoxLayout(video_container)
        video_container_layout.setContentsMargins(0, 0, 0, 0)

        self.video_frame = VideoFrame()
        self.video_frame.setMinimumSize(640, 480)
        video_container_layout.addWidget(self.video_frame)

        # Transparent click overlay OVER video
        self.click_overlay = QLabel(video_container)
        self.click_overlay.setStyleSheet("background: transparent;")
        self.click_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.click_overlay.raise_()

        layout.addWidget(video_container)
        
        layout.addWidget(self.video_frame)
        
        # Fullscreen controls
        self.fullscreen_controls = FullscreenControls()
        self.fullscreen_controls.hide()
        self.fullscreen_controls.volume_icon.mousePressEvent = self._on_volume_icon_click
        self.fullscreen_controls.previous_clicked.connect(self._on_previous)
        self.fullscreen_controls.play_pause_clicked.connect(self.toggle_play_pause)
        self.fullscreen_controls.stop_clicked.connect(self.stop)
        self.fullscreen_controls.next_clicked.connect(self._on_next)
        self.fullscreen_controls.volume_changed.connect(self.set_volume)
        self.fullscreen_controls.position_changed.connect(self.set_position)
        self.fullscreen_controls.exit_fullscreen_clicked.connect(self._exit_fullscreen_and_stop)
        
        # Control bar
        self.control_bar = QWidget()
        control_layout = QVBoxLayout(self.control_bar)
        control_layout.setContentsMargins(10, 5, 10, 5)
        control_layout.setSpacing(5)
        
        timeline_layout = QHBoxLayout()
        
        self.time_label = QLabel("00:00")
        self.time_label.setStyleSheet("font-size: 10pt; color: #999;")
        timeline_layout.addWidget(self.time_label)
        
        self.timeline_slider = SeekableSlider(Qt.Orientation.Horizontal)
        self.timeline_slider.setRange(0, 1000)
        self.timeline_slider.setValue(0)
        self.timeline_slider.seek_requested.connect(self.set_position)
        # Enable click on slider to seek
        # self.timeline_slider.seek_requested.connect(self.set_position)
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
        
        self.volume_icon = QLabel("🔊")
        self.volume_icon.setStyleSheet("font-size: 14pt;")
        self.volume_icon.setCursor(Qt.CursorShape.PointingHandCursor)
        self.volume_icon.mousePressEvent = self._on_volume_icon_click  # ← OVO
        button_layout.addWidget(self.volume_icon)

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
        QTimer.singleShot(200, lambda: self.click_overlay.installEventFilter(self))
    
    def _set_vlc_output_internal(self):
        if not self.video_player.media_player:
            return
        
        try:
            # DISABLE VLC mouse/keyboard handling - KRITIČNO!
            self.video_player.media_player.video_set_mouse_input(False)
            self.video_player.media_player.video_set_key_input(False)
            
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
        """Poll mouse position and detect clicks"""
        current_pos = QCursor.pos()
        is_pressed = bool(QApplication.mouseButtons() & Qt.MouseButton.LeftButton)
        
        # Fullscreen handling
        if self.is_fullscreen and self.fullscreen_window:
            if current_pos != self.last_mouse_pos:
                self.last_mouse_pos = current_pos
                self._show_cursor()
                self.fullscreen_controls.show_with_timer()
            
            # ✅ DODAJ PROVERU: samo u TV modu reaguj na double-click
            if self.content_type == 'tv':  # ← NOVO!
                if is_pressed and not self.mouse_was_pressed:
                    controls_rect = self.fullscreen_controls.geometry()
                    local_pos = self.fullscreen_window.mapFromGlobal(current_pos)
                    
                    if not controls_rect.contains(local_pos) or not self.fullscreen_controls.isVisible():
                        self._on_fullscreen_click()
        
        # Normal mode double-click detection (već ima TV proveru)
        else:
            if is_pressed and not self.mouse_was_pressed:
                if self.video_frame.isVisible():
                    local_pos = self.video_frame.mapFromGlobal(current_pos)
                    if self.video_frame.rect().contains(local_pos):
                        self._on_normal_video_click()  # ← OVO JE VEĆ OK
        
        self.mouse_was_pressed = is_pressed
        
    def _on_normal_video_click(self):
        """Handle click on video in normal (non-fullscreen) mode - ONLY TV MODE"""
        # ONLY allow double-click fullscreen toggle in TV mode
        if self.content_type != 'tv':
            return

        current_time = time.time()
        self.normal_click_times = [t for t in self.normal_click_times if current_time - t < 0.4]
        self.normal_click_times.append(current_time)

        logger.info(f"🖱️ Normal video click (TV mode), count: {len(self.normal_click_times)}")

        if len(self.normal_click_times) >= 2:
            logger.info("🖱️🖱️ DOUBLE CLICK (TV mode) - entering fullscreen")
            self.normal_click_times.clear()
            self.enter_fullscreen()
          
    def _on_fullscreen_click(self):
        """Handle click in fullscreen mode with double-click detection"""
        current_time = time.time()
        
        # Remove old clicks (older than 400ms)
        self.click_times = [t for t in self.click_times if current_time - t < 0.4]
        self.click_times.append(current_time)
        
        logger.debug(f"Fullscreen click detected, click_times count: {len(self.click_times)}")
        
        if len(self.click_times) >= 2:
            # Double click detected
            self.click_times.clear()
            
            # ONLY exit fullscreen on double-click in TV mode
            if self.content_type == 'tv':
                logger.info("Double click detected (TV mode) - exiting fullscreen")
                self.exit_fullscreen()
            else:
                logger.debug(f"Double click ignored (content_type={self.content_type})")
        else:
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
    
    def _on_back_clicked(self):
        logger.info("Back requested from playback")
        self.stop()
        self.playback_exited.emit()
    
    def _on_video_click(self):
        if self.is_fullscreen:
            self._show_cursor()
            self.fullscreen_controls.show_with_timer()
    
    def _on_video_mouse_move(self):
        if self.is_fullscreen:
            self._show_cursor()
            self.fullscreen_controls.show_with_timer()
    
    def toggle_fullscreen(self):
        logger.info(f"🔄 toggle_fullscreen called - current state: is_fullscreen={self.is_fullscreen}")
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
        """Handle keyboard input in fullscreen mode"""
        key = event.key()
        
        if key == Qt.Key.Key_Escape or key == Qt.Key.Key_F:
            logger.info(f"🔑 ESC pressed - current content_type: '{self.content_type}'")

            # Different behavior based on content type
            if self.content_type == 'tv':
                # TV mode: Just exit fullscreen, keep playing
                logger.info("ESC/F pressed in TV mode - exiting fullscreen (playback continues)")
                self.exit_fullscreen()
            else:
                # VOD/Series mode: Stop and exit
                logger.info("ESC/F pressed in VOD/Series mode - stopping player and exiting fullscreen")
                self.stop()
                self.exit_fullscreen()
                self.playback_exited.emit()
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
        elif key == Qt.Key.Key_Left:
            # Seek backward 10 seconds
            current_pos = self.timeline_slider.value()
            new_pos = max(0, current_pos - 10)
            self.set_position(new_pos)
        elif key == Qt.Key.Key_Right:
            # Seek forward 10 seconds
            current_pos = self.timeline_slider.value()
            new_pos = min(1000, current_pos + 10)
            self.set_position(new_pos)
    
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
    
    def _exit_fullscreen_and_stop(self):
        """Exit fullscreen - behavior depends on content type"""
        if self.content_type == 'tv':
            # TV mode: Just exit fullscreen, keep playing
            logger.info("Exit fullscreen button clicked (TV mode) - exiting fullscreen (playback continues)")
            self.exit_fullscreen()
        else:
            # VOD/Series mode: Stop and exit
            logger.info("Exit fullscreen button clicked (VOD/Series mode) - stopping player and exiting fullscreen")
            self.stop()
            self.exit_fullscreen()
            self.playback_exited.emit()
    
    def play_url(self, url: str, content_type: str = 'vod'):
        """
        Play URL with specified content type
        
        Args:
            url: Media URL to play
            content_type: 'tv', 'vod', or 'series' - determines ESC behavior in fullscreen
        """
        
        # Postavi referencu ka MainWindow (za volume klik)
        if self.parent() and hasattr(self.parent(), 'on_video_mute_toggle'):
            self.main_window = self.parent()

        if not url:
            logger.warning("play_url called with empty URL")
            self.status_label.setText("Greška: Nema URL-a")
            return
        
        # Store content type for ESC handling
        self.content_type = content_type
        logger.info(f"▶️ Playing URL with content_type: '{self.content_type}'")

        try:
            self._set_vlc_output_internal()
            
            # DODAJ OVO - svaki put kad se pušta novi video
            if self.video_player.media_player:
                self.video_player.media_player.video_set_mouse_input(False)
                self.video_player.media_player.video_set_key_input(False)
            
            # Reset UI
            self.timeline_slider.blockSignals(True)
            self.timeline_slider.setValue(0)
            self.timeline_slider.blockSignals(False)
            self.time_label.setText("00:00")
            self.duration_label.setText("00:00")
            
            self.video_player.play(url)
            self.is_playing = True
            self.play_btn.setText("⏸")
            self.fullscreen_controls.set_playing(True)
            self.status_label.setText("Reprodukcija...")
            self.position_timer.start()
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
            logger.info("⏹ Stopping playback")
            self.video_player.stop()
            self.is_playing = False
            self.play_btn.setText("▶")
            self.fullscreen_controls.set_playing(False)
            self.status_label.setText("Zaustavljeno")
            self.position_timer.stop()
            self.timeline_slider.setValue(0)
            self.time_label.setText("00:00")
        except Exception as e:
            logger.error(f"Error stopping player: {e}", exc_info=True)
        
    def set_volume(self, volume: int):
        self.video_player.set_volume(volume)
        self.volume_slider.blockSignals(True)
        self.volume_slider.setValue(volume)
        self.volume_slider.blockSignals(False)
        self.fullscreen_controls.volume_slider.blockSignals(True)
        self.fullscreen_controls.volume_slider.setValue(volume)
        self.fullscreen_controls.volume_slider.blockSignals(False)
    
    def set_position(self, position: int):
        """Set playback position from slider (0-1000 range)"""
        try:
            if not self.video_player or not self.video_player.media_player:
                logger.warning("media_player not available for seek")
                return
            
            # Convert slider position (0-1000) to VLC position (0.0-1.0)
            position_fraction = position / 1000.0
            
            # Perform seek
            self.video_player.media_player.set_position(position_fraction)
            
            # Update time labels immediately for instant feedback
            length = self.video_player.media_player.get_length()
            if length > 0:
                time_ms = int(length * position_fraction)
                
                time_min = time_ms // 60000
                time_sec = (time_ms // 1000) % 60
                self.time_label.setText(f"{time_min:02d}:{time_sec:02d}")
                
                # Update fullscreen controls if active
                if self.is_fullscreen and self.fullscreen_controls:
                    self.fullscreen_controls.set_position(time_ms, length)
            
            logger.info(f"Seeked to position: {position}/1000 ({position_fraction:.2%})")
        except Exception as e:
            logger.error(f"Error in set_position: {e}", exc_info=True)
    
    def debug_vlc_state(self):
        """Debug VLC state"""
        if not self.video_player or not self.video_player.media_player:
            print("❌ No media player")
            return
        
        mp = self.video_player.media_player
        length = mp.get_length()
        time_ms = mp.get_time()
        position = mp.get_position()
        state = mp.get_state()
        is_playing = mp.is_playing()
        
        print("=" * 50)
        print(f"🎬 VLC DEBUG:")
        print(f"  State: {state}")
        print(f"  Is playing: {is_playing}")
        print(f"  Length: {length}ms ({length/1000:.1f}s)")
        print(f"  Time: {time_ms}ms ({time_ms/1000:.1f}s)")
        print(f"  Position: {position}")
        print(f"  Media: {mp.get_media()}")
        print("=" * 50)
    
    def update_position(self):
        """Update position display from VLC playback"""
        if not self.video_player.media_player:
            return
        
        try:
            # Check if media is actually playing
            if not self.video_player.media_player.is_playing() and not self.is_playing:
                return
            
            length = self.video_player.media_player.get_length()
            time_ms = self.video_player.media_player.get_time()
            
            # Debug logging (možeš kasnije ukloniti)
            if length <= 0:
                logger.debug(f"VLC not ready: length={length}, time={time_ms}")
                return
            
            # Calculate and update slider position
            position = int((time_ms / length) * 1000)
            
            self.timeline_slider.blockSignals(True)
            self.timeline_slider.setValue(position)
            self.timeline_slider.blockSignals(False)
            
            # Update time labels
            time_min = time_ms // 60000
            time_sec = (time_ms // 1000) % 60
            self.time_label.setText(f"{time_min:02d}:{time_sec:02d}")
            
            length_min = length // 60000
            length_sec = (length // 1000) % 60
            self.duration_label.setText(f"{length_min:02d}:{length_sec:02d}")
            
            # Update fullscreen controls
            if self.is_fullscreen:
                self.fullscreen_controls.set_position(time_ms, length)
                
        except Exception as e:
            logger.error(f"Error updating position: {e}", exc_info=True)
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.is_fullscreen and self.fullscreen_window:
            self._setup_fullscreen_controls()
        
        # Resize overlay to cover video
        if hasattr(self, 'click_overlay') and hasattr(self, 'video_frame'):
            self.click_overlay.setGeometry(0, 0, self.video_frame.width(), self.video_frame.height())
            
    def _on_volume_icon_click(self, event):
        """Mute/unmute na klik volume icon - pamti poslednji volume"""
        current_vol = self.volume_slider.value()
        
        if current_vol > 0:
            # Mute: sačuvaj trenutni volume i postavi na 0
            self.last_volume = current_vol  # ← NOVO: pamti poslednji
            self.set_volume(0)
            self.volume_icon.setText("🔇")  # ← KOSA CRTA
            logger.debug(f"Muted: saved {current_vol}%, now 0")
        else:
            # Unmute: vrati na poslednji volume (ili default 70)
            restore_vol = getattr(self, 'last_volume', 70)
            self.set_volume(restore_vol)
            self.volume_icon.setText("🔊")  # ← NORMALNO
            logger.debug(f"Unmuted: restored {restore_vol}%")
            
    def set_volume(self, volume: int):
        """Set volume i ažuriraj ikonu"""
        self.video_player.set_volume(volume)
        self.volume_slider.blockSignals(True)
        self.volume_slider.setValue(volume)
        self.volume_slider.blockSignals(False)
        self.fullscreen_controls.volume_slider.blockSignals(True)
        self.fullscreen_controls.volume_slider.setValue(volume)
        self.fullscreen_controls.volume_slider.blockSignals(False)
        
        # Ažuriraj ikonu prema volume-u
        if volume == 0:
            self.volume_icon.setText("🔇")
        else:
            self.volume_icon.setText("🔊")
            self.last_volume = volume
            
        if hasattr(self.fullscreen_controls, 'volume_icon'):
            self.fullscreen_controls.volume_icon.setText("🔇" if volume == 0 else "🔊")
            
    def _on_double_click_detected(self):
        """VideoFrame double click detected - only for TV mode"""
        if self.content_type != 'tv':
            logger.debug(f"Double-click ignored (content_type={self.content_type})")
            return
        
        logger.info(f"🖱️ Double click - toggling fullscreen (TV mode)")
        self.toggle_fullscreen()

    def eventFilter(self, obj, event):
        """Catch mouse events from click_overlay - ONLY TV MODE"""
        if obj == self.click_overlay:
            if event.type() == event.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    if self.content_type != 'tv':
                        logger.debug(f"Click ignored (content_type={self.content_type})")
                        return False  # ← Propusti event dalje
                    
                    logger.info(f"🖱️ Click overlay LEFT CLICK detected (TV mode)")
                    
                    if self.video_click_timer.isActive():
                        logger.info("🖱️🖱️ DOUBLE CLICK (TV mode) - toggling fullscreen")
                        self.video_click_timer.stop()
                        self.toggle_fullscreen()
                        return True
                    else:
                        self.video_click_timer.start(300)
                        return False
        
        return super().eventFilter(obj, event)

    def _video_single_click_action(self):
        """Single click action (after timeout)"""
        logger.debug("Single click confirmed - showing controls")
        if self.is_fullscreen:
            self._show_cursor()
            self.fullscreen_controls.show_with_timer()
