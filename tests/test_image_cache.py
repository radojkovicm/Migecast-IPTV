"""Image loading: worker threads, de-duplication, failures, disk cache,
and a responsive GUI thread while many posters download."""
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QTimer
from PyQt6.QtGui import QColor, QImage

from utils.image_cache import DiskImageCache, ImageLoader

HITS = {}


def _png_bytes():
    image = QImage(40, 60, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(data)


class Handler(BaseHTTPRequestHandler):
    png = None

    def log_message(self, *args):
        pass

    def do_GET(self):
        HITS[self.path] = HITS.get(self.path, 0) + 1
        if self.path.startswith("/slow"):
            time.sleep(0.4)
        if self.path.startswith("/broken"):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"not an image")
            return
        if self.path.startswith("/missing"):
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.end_headers()
        self.wfile.write(Handler.png)


@pytest.fixture(scope="module")
def server(qapp):
    Handler.png = _png_bytes()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def wait_until(qapp, predicate, timeout=10.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_download_dedup_and_disk_cache(qapp, server, tmp_path):
    loader = ImageLoader(folder=tmp_path / "img", max_parallel=2, max_disk_mb=10)
    ready = []
    loader.image_ready.connect(ready.append)
    url = server + "/poster/1.png"
    assert loader.pixmap(url, 100, 150) is None
    loader.request(url)
    loader.request(url)
    assert wait_until(qapp, lambda: url in ready)
    assert HITS["/poster/1.png"] == 1
    pixmap = loader.pixmap(url, 100, 150)
    assert pixmap is not None and pixmap.height() <= 150
    loader.cleanup()

    # A new loader (= program restart) reads from disk, no network request.
    second = ImageLoader(folder=tmp_path / "img", max_parallel=2, max_disk_mb=10)
    ready2 = []
    second.image_ready.connect(ready2.append)
    second.request(url)
    assert wait_until(qapp, lambda: url in ready2)
    assert HITS["/poster/1.png"] == 1
    second.cleanup()


@pytest.mark.parametrize("path", ["/broken/a.png", "/missing/a.png"])
def test_failed_images_are_not_retried(qapp, server, tmp_path, path):
    loader = ImageLoader(folder=tmp_path / "img", max_parallel=2, max_disk_mb=10)
    failed = []
    loader.image_failed.connect(failed.append)
    url = server + path
    loader.request(url)
    assert wait_until(qapp, lambda: url in failed)
    assert loader.has_failed(url)
    before = HITS[path]
    loader.request(url)
    qapp.processEvents()
    assert HITS[path] == before
    loader.cleanup()


def test_non_http_urls_are_ignored(qapp, tmp_path):
    loader = ImageLoader(folder=tmp_path / "img", max_disk_mb=10)
    loader.request("file:///etc/passwd")
    loader.request("")
    assert loader.pending_count() == 0
    loader.cleanup()


def test_parallel_limit_and_cancel(qapp, server, tmp_path):
    loader = ImageLoader(folder=tmp_path / "img", max_parallel=3, max_disk_mb=10)
    for i in range(30):
        loader.request(f"{server}/slow/{i}.png")
    assert len(loader._inflight) == 3
    assert loader.pending_count() == 30
    loader.cancel_queued()
    assert loader.pending_count() == 3
    loader.cleanup()


def test_gui_stays_responsive_while_downloading(qapp, server, tmp_path):
    loader = ImageLoader(folder=tmp_path / "img", max_parallel=6, max_disk_mb=10)
    ticks = []
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(time.monotonic()))
    timer.start(20)
    for i in range(60):
        loader.request(f"{server}/slow/r{i}.png")
    wait_until(qapp, lambda: loader.pending_count() == 0, timeout=20)
    timer.stop()
    gaps = [b - a for a, b in zip(ticks, ticks[1:])]
    assert loader.pending_count() == 0
    assert max(gaps) < 0.25, f"GUI thread blocked for {max(gaps):.2f}s"
    loader.cleanup()


def test_disk_cache_prune(tmp_path):
    cache = DiskImageCache(tmp_path / "d", max_bytes=10_000)
    for i in range(20):
        cache.put(f"http://x/{i}", b"x" * 1000)
        time.sleep(0.002)
    assert cache.size_bytes() == 20_000
    removed = cache.prune()
    assert removed > 0 and cache.size_bytes() <= 8_000
    assert cache.get("http://x/19") is not None  # newest kept
    assert cache.get("http://x/0") is None       # oldest removed
