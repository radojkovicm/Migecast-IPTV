## 22. **DEVELOPER.md**

```markdown
# MigeCast IPTV - Developer Documentation

## 🏗️ Architecture Overview

iptv_app/
├── main.py # Application entry point
├── ui/ # User interface components
│ ├── main_window.py # Main application window
│ ├── live_tv_widget.py # Live TV channels view
│ ├── vod_widget.py # VOD grid and detail views
│ ├── player_widget.py # Video player controls
│ └── settings_dialog.py # Settings dialog
├── core/ # Business logic
│ ├── playlist_parser.py # M3U/Xtream parser
│ ├── epg_manager.py # EPG data management
│ ├── video_player.py # VLC player wrapper
│ ├── stream_manager.py # Stream health monitoring
│ └── database.py # SQLite database operations
├── models/ # Data models
│ ├── channel.py # Channel model
│ ├── vod_item.py # VOD item model
│ └── playlist.py # Playlist model
└── utils/ # Utility functions
├── image_cache.py # Image caching system
└── config.py # Configuration manager


---

## 🔧 Technology Stack

- **UI Framework**: PyQt6 6.7.0
- **Video Engine**: LibVLC (python-vlc 3.0.18122)
- **HTTP Client**: requests, aiohttp
- **XML Parsing**: lxml
- **Image Processing**: Pillow
- **Database**: SQLAlchemy (SQLite backend)

---

## 🎯 Key Components

### 1. Video Player (`core/video_player.py`)
- Wraps LibVLC for video playback
- Auto-reconnect logic with configurable retry attempts
- Hardware acceleration support
- Event-driven architecture with PyQt signals

### 2. Playlist Parser (`core/playlist_parser.py`)
- Parses M3U Extended format
- Supports Xtream Codes API
- Detects timeshift/catch-up capabilities
- Separates live channels from VOD content

### 3. EPG Manager (`core/epg_manager.py`)
- Parses XMLTV format
- Provides current/next program info
- Time-based program lookup

### 4. Image Cache (`utils/image_cache.py`)
- Downloads and caches channel logos and VOD posters
- URL-based hash for cache keys
- Automatic cache size management

### 5. Database (`core/database.py`)
- SQLite database for persistence
- Favorites tracking
- Watched status for VOD
- Playlist management

---

## 🚀 Building Executable

### Using PyInstaller

```bash
# Install PyInstaller
pip install pyinstaller

# Create executable
pyinstaller --name="MigeCast IPTV" \
            --windowed \
            --icon=resources/icon.ico \
            --add-data "resources;resources" \
            --hidden-import PyQt6 \
            --hidden-import vlc \
            main.py

# Output will be in dist/MigeCast IPTV/
Using Inno Setup (Installer)
Install Inno Setup
Create installer script (example in installer.iss)
Compile to create setup.exe
🧪 Testing
Manual Testing Checklist
 M3U parsing with various formats
 Xtream Codes API connection
 Live stream playback (10+ channels)
 VOD playback (2h+ movies)
 Timeshift forward/rewind
 Auto-reconnect on stream failure
 Multi-playlist management
 EPG display
 Search functionality
 Favorites persistence
 Watched tracking
 Settings save/load
 Keyboard shortcuts
 High DPI display support
📊 Performance Optimization
Image Loading
Lazy loading: Images load only when visible
Async downloading with aiohttp (future improvement)
LRU cache for frequently accessed images
Video Streaming
Pre-buffer 5-10 seconds before playback
Hardware decoding (DXVA2/NVDEC/VAAPI)
Adaptive bitrate (if stream supports)
UI Responsiveness
Background threads for EPG refresh
Async playlist loading
Debounced search input
🔐 Security Considerations
Xtream Codes credentials stored in local JSON (config.json)
No telemetry or data collection
Local-only data storage
⚠️ Warning: In production, consider encrypting stored credentials.

🐛 Known Issues / Future Improvements
Current Limitations
EPG data must be in XMLTV format
No subtitle customization UI
Parental control not implemented
No multi-monitor support for fullscreen
Future Enhancements
 Add PIP (Picture-in-Picture) mode
 Recording functionality
 Custom playlist creation
 Advanced EPG timeline visualization
 Multi-language support
 Themes (dark mode)
 Cloud sync for favorites
📚 Code Style
PEP 8 compliance
Type hints where applicable
Docstrings for all public methods
Comments in English
Serbian UI text in strings
🤝 Contributing
Fork the repository
Create feature branch (git checkout -b feature/amazing-feature)
Commit changes (git commit -m 'Add amazing feature')
Push to branch (git push origin feature/amazing-feature)
Open Pull Request
📞 Support
For developer questions or bug reports, please open an issue on GitHub.

Happy Coding! 🚀