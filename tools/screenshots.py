"""Render every page with synthetic data to PNG files (visual QA).

Usage:  python tools/screenshots.py <output-folder> [theme]
Uses a temporary data folder; never touches real user data.
"""
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["MIGECAST_DATA_DIR"] = tempfile.mkdtemp(prefix="migecast-shots-")


def _poster_server():
    """Local HTTP server that paints synthetic posters/logos (no real images)."""
    import threading
    import zlib
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
    from PyQt6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter

    def paint(path: str) -> bytes:
        kind, _, name = path.strip("/").partition("/")
        number = name.split(".")[0]
        hue = zlib.crc32(path.encode()) % 360
        logo = kind == "ch"
        width, height = (240, 150) if logo else (360, 540)
        image = QImage(width, height, QImage.Format.Format_RGB32)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient = QLinearGradient(0, 0, 0, height)
        gradient.setColorAt(0, QColor.fromHsv(hue, 150, 190))
        gradient.setColorAt(1, QColor.fromHsv((hue + 40) % 360, 200, 60))
        painter.fillRect(0, 0, width, height, gradient)
        painter.setPen(QColor(255, 255, 255))
        font = QFont("DejaVu Sans")
        font.setBold(True)
        if logo:
            font.setPixelSize(54)
            painter.setFont(font)
            painter.drawText(QRectF(0, 0, width, height), Qt.AlignmentFlag.AlignCenter, f"K{int(number) + 1}")
        else:
            font.setPixelSize(38)
            painter.setFont(font)
            title = "Demo\nSerija" if kind == "s" else f"Demo\nFilm {int(number) + 1}"
            painter.drawText(QRectF(20, 0, width - 40, height * 0.7), Qt.AlignmentFlag.AlignCenter, title)
            font.setPixelSize(20)
            font.setBold(False)
            painter.setFont(font)
            painter.drawText(QRectF(0, height - 70, width, 40), Qt.AlignmentFlag.AlignCenter, "MigeCast demo")
        painter.end()
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        return bytes(data)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            body = paint(self.path)
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{httpd.server_address[1]}"


def main(out: Path, theme: str = "dark"):
    from PyQt6.QtWidgets import QApplication

    from core.database import Database
    from core.m3u import parse_m3u_text
    from tools.demo_data import demo_m3u
    from utils import themes
    from utils.config import Config

    out.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv)
    image_base = _poster_server()
    config = Config()
    config.set("appearance", "theme", theme)
    config.save()
    parsed = parse_m3u_text(demo_m3u(image_base=image_base))
    db = Database()
    playlist_id = db.save_playlist("Demo lista", "M3U", url="http://list.demo.invalid/demo.m3u")
    db.replace_cached_playlist(playlist_id, parsed.channels, parsed.vod_items, parsed.series_items)
    first_movie = parsed.vod_items[3]
    db.add_vod_favorite(first_movie.stream_id, first_movie.name)
    db.update_watch_progress(first_movie.stream_id, "vod", first_movie.name, 1500, 6000)
    long_series = [e for e in parsed.series_items if e.series_name == "Duga Demo Serija"]
    db.update_watch_progress(long_series[26].stream_id, "series", long_series[26].name, 700, 2600)
    for episode in long_series[24:26]:
        db.mark_series_watched(episode.stream_id, episode.name, "Duga Demo Serija")
    db.set_series_state("Duga Demo Serija", season="2", episode_id=long_series[26].stream_id)
    db.add_series_favorite("Duga Demo Serija")
    Database.reset_instance()

    themes.set_current(theme)
    app.setStyleSheet(themes.generate_stylesheet(theme))
    from ui.main_window import HOME, SERIES, SERIES_DETAIL, SETTINGS, TV, VOD, VOD_DETAIL, MainWindow
    window = MainWindow()
    window.resize(1600, 960)
    window.show()
    window.start()

    def pump(seconds=0.6):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(0.02)

    for _ in range(100):
        pump(0.1)
        if window.parsed is not None:
            break
    pump()

    def shot(name):
        pump(2.0)  # let posters load
        window.grab().save(str(out / f"{theme}-{name}.png"))

    shot("01-home")
    window.open_section(TV)
    window.live_tv_widget.category.setCurrentIndex(1)
    shot("02-tv")
    window.open_section(VOD)
    window.vod_page.category.setCurrentIndex(2)
    shot("03-movies")
    window.open_vod(first_movie)
    shot("04-movie-detail")
    window.go(HOME)
    window.open_section(SERIES)
    window.series_page.category.setCurrentIndex(2)
    shot("05-series")
    groups = window.series_page.groups
    window.open_series(("Duga Demo Serija", groups["Duga Demo Serija"]))
    shot("06-series-detail")
    window.series_detail.search.setText("E07")
    shot("07-series-search")
    window.series_detail.search.clear()
    window.open_series(("Serija Bez Sezone", groups["Serija Bez Sezone"]))
    shot("08-series-no-season")
    window.go(SETTINGS)
    shot("09-settings")
    window.close()


if __name__ == "__main__":
    main(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else "dark")
