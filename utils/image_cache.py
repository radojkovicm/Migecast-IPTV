"""Poster / logo loading that never blocks the GUI thread.

* Network downloads and disk reads run in a small ``QThreadPool``; workers
  only touch ``QImage`` (thread-safe), never ``QPixmap``.
* Each URL is downloaded at most once at a time (de-duplication) and a failed
  URL is not retried for a while, so a dead image server cannot slow the UI.
* Requests are LIFO: what the user is looking at right now loads first.
  ``cancel_queued()`` drops requests for items that are no longer visible.
* Memory cache: LRU of scaled pixmaps. Disk cache: downscaled JPEG files with
  a size limit (oldest files are removed first).
* Views connect once to :attr:`ImageLoader.image_ready` and repaint the rows
  that use the URL (no per-widget signal connections).
"""
import hashlib
import logging
import os
import threading
import time
from collections import OrderedDict, deque
from pathlib import Path
from typing import Optional

import requests
from PyQt6.QtCore import QObject, QRunnable, QSize, Qt, QThreadPool, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap

from utils import paths

logger = logging.getLogger(__name__)

MAX_SOURCE_BYTES = 8 * 1024 * 1024
THUMB_MAX = QSize(360, 540)
FAILED_RETRY_SECONDS = 15 * 60


class DiskImageCache:
    """Size-bounded folder of cached images (pure Python, thread-safe)."""

    def __init__(self, folder: Path, max_bytes: int = 300 * 1024 * 1024):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_bytes
        self._lock = threading.Lock()

    @staticmethod
    def key(url: str) -> str:
        return hashlib.sha1(url.encode("utf-8", errors="ignore")).hexdigest()

    def path_for(self, url: str) -> Path:
        return self.folder / f"{self.key(url)}.jpg"

    def get(self, url: str) -> Optional[bytes]:
        path = self.path_for(url)
        try:
            data = path.read_bytes()
        except OSError:
            return None
        try:
            os.utime(path, None)  # mark as recently used
        except OSError:
            pass
        return data

    def put(self, url: str, data: bytes) -> None:
        path = self.path_for(url)
        tmp = path.with_suffix(f".{threading.get_ident()}.tmp")
        try:
            tmp.write_bytes(data)
            os.replace(tmp, path)
        except OSError as exc:
            logger.debug("Disk cache write failed: %s", exc)
            try:
                tmp.unlink()
            except OSError:
                pass

    def size_bytes(self) -> int:
        return sum(entry.stat().st_size for entry in self.folder.iterdir() if entry.is_file())

    def prune(self, target_ratio: float = 0.8) -> int:
        """Delete least recently used files until below ``max_bytes``."""
        with self._lock:
            try:
                entries = [(e.stat().st_mtime, e.stat().st_size, e) for e in self.folder.iterdir() if e.is_file()]
            except OSError:
                return 0
            total = sum(size for _, size, _ in entries)
            if total <= self.max_bytes:
                return 0
            removed = 0
            limit = self.max_bytes * target_ratio
            for _, size, entry in sorted(entries, key=lambda item: item[0]):
                if total <= limit:
                    break
                try:
                    entry.unlink()
                    total -= size
                    removed += 1
                except OSError:
                    pass
            logger.info("Image cache pruned: %d files removed", removed)
            return removed

    def clear(self) -> None:
        for entry in self.folder.iterdir():
            try:
                entry.unlink()
            except OSError:
                pass


class _Bridge(QObject):
    done = pyqtSignal(str, QImage)
    failed = pyqtSignal(str)


class _LoadTask(QRunnable):
    def __init__(self, url: str, disk: DiskImageCache, bridge: _Bridge):
        super().__init__()
        self.url = url
        self.disk = disk
        self.bridge = bridge
        self.setAutoDelete(True)

    def run(self):
        try:
            data = self.disk.get(self.url)
            image = QImage.fromData(data) if data else QImage()
            if image.isNull():
                image = self._download()
            if image.isNull():
                self.bridge.failed.emit(self.url)
            else:
                self.bridge.done.emit(self.url, image)
        except Exception as exc:  # never let a worker crash the app
            logger.debug("Image task error: %s", exc)
            self.bridge.failed.emit(self.url)

    def _download(self) -> QImage:
        from core.net import session
        for attempt in range(2):
            try:
                with session().get(self.url, timeout=(4, 10), stream=True) as response:
                    response.raise_for_status()
                    chunks, total = [], 0
                    for chunk in response.iter_content(64 * 1024):
                        chunks.append(chunk)
                        total += len(chunk)
                        if total > MAX_SOURCE_BYTES:
                            return QImage()
                    data = b"".join(chunks)
                break
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                if attempt == 0:
                    time.sleep(0.5)
                    continue
                return QImage()
            except requests.exceptions.RequestException:
                return QImage()
        image = QImage.fromData(data)
        if image.isNull():
            return image
        if image.width() > THUMB_MAX.width() or image.height() > THUMB_MAX.height():
            image = image.scaled(THUMB_MAX, Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
        from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
        buffer_bytes = QByteArray()
        buffer = QBuffer(buffer_bytes)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG" if image.hasAlphaChannel() else "JPG", 85)
        buffer.close()
        self.disk.put(self.url, bytes(buffer_bytes))
        return image


class ImageLoader(QObject):
    """Process wide asynchronous image loader (use :meth:`instance`)."""

    image_ready = pyqtSignal(str)
    image_failed = pyqtSignal(str)

    _instance = None

    @classmethod
    def instance(cls) -> "ImageLoader":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, folder: Optional[Path] = None, max_parallel: int = 6,
                 max_disk_mb: Optional[int] = None, memory_items: int = 600):
        super().__init__()
        if max_disk_mb is None:
            try:
                from utils.config import Config
                max_disk_mb = int(Config().get("images", "max_cache_mb", 300))
            except Exception:
                max_disk_mb = 300
        self.disk = DiskImageCache(folder or paths.image_cache_dir(), max_disk_mb * 1024 * 1024)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(max_parallel)
        self.max_parallel = max_parallel
        self.bridge = _Bridge()
        self.bridge.done.connect(self._on_done)
        self.bridge.failed.connect(self._on_failed)
        self._images = OrderedDict()   # url -> QImage (source thumbnail)
        self._scaled = OrderedDict()   # (url, w, h) -> QPixmap
        self._memory_items = memory_items
        self._queue = deque()
        self._queued = set()
        self._inflight = set()
        self._failed = {}
        self._closed = False

    # -- public API ---------------------------------------------------------

    def pixmap(self, url: Optional[str], width: int, height: int) -> Optional[QPixmap]:
        """Return a cached pixmap scaled to fit ``width``x``height`` or ``None``
        (and schedule loading). Call from the GUI thread only."""
        if not url or self._closed:
            return None
        key = (url, width, height)
        cached = self._scaled.get(key)
        if cached is not None:
            self._scaled.move_to_end(key)
            return cached
        image = self._images.get(url)
        if image is None:
            self.request(url)
            return None
        self._images.move_to_end(url)
        scaled = QPixmap.fromImage(image.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatio,
                                                Qt.TransformationMode.SmoothTransformation))
        self._scaled[key] = scaled
        while len(self._scaled) > self._memory_items:
            self._scaled.popitem(last=False)
        return scaled

    def get_image(self, url: str, size: tuple = (100, 100)) -> Optional[QPixmap]:
        """Compatibility wrapper for older call sites."""
        return self.pixmap(url, size[0], size[1])

    def has_failed(self, url: Optional[str]) -> bool:
        if not url:
            return True
        failed_at = self._failed.get(url)
        return failed_at is not None and time.monotonic() - failed_at < FAILED_RETRY_SECONDS

    def request(self, url: str) -> None:
        if (not url or self._closed or url in self._images or url in self._inflight
                or self.has_failed(url) or not url.lower().startswith(("http://", "https://"))):
            return
        if url in self._queued:
            try:
                self._queue.remove(url)
            except ValueError:
                pass
        self._queued.add(url)
        self._queue.append(url)  # LIFO: newest first
        self._pump()

    def cancel_queued(self) -> None:
        """Forget requests that have not started yet (e.g. after scrolling away)."""
        self._queue.clear()
        self._queued.clear()

    def pending_count(self) -> int:
        return len(self._queue) + len(self._inflight)

    def prune_disk_async(self) -> None:
        threading.Thread(target=self.disk.prune, name="image-cache-prune", daemon=True).start()

    def clear_cache(self) -> None:
        self._images.clear()
        self._scaled.clear()
        self._failed.clear()
        self.disk.clear()

    def cleanup(self) -> None:
        self._closed = True
        self.cancel_queued()
        self.pool.clear()
        self.pool.waitForDone(2000)

    # -- internals -------------------------------------------------------------

    def _pump(self):
        while self._queue and len(self._inflight) < self.max_parallel:
            url = self._queue.pop()
            self._queued.discard(url)
            self._inflight.add(url)
            self.pool.start(_LoadTask(url, self.disk, self.bridge))

    def _on_done(self, url: str, image: QImage):
        self._inflight.discard(url)
        if self._closed:
            return
        self._images[url] = image
        while len(self._images) > self._memory_items:
            self._images.popitem(last=False)
        self.image_ready.emit(url)
        self._pump()

    def _on_failed(self, url: str):
        self._inflight.discard(url)
        self._failed[url] = time.monotonic()
        if not self._closed:
            self.image_failed.emit(url)
            self._pump()


# Backwards compatible name used by older modules.
ImageCache = ImageLoader
