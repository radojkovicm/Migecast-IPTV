import logging
import hashlib
import requests
from pathlib import Path
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import QThread, pyqtSignal, QObject, QThreadPool, QRunnable, pyqtSlot, Qt
from io import BytesIO

logger = logging.getLogger(__name__)


class ImageDownloadSignals(QObject):
    """Signals for image download runnable"""
    image_downloaded = pyqtSignal(str, QPixmap)  # url, pixmap
    download_failed = pyqtSignal(str, str)  # url, error_message


class ImageDownloadRunnable(QRunnable):
    """Runnable for downloading images in thread pool"""
    
    def __init__(self, url: str, size: tuple, cache_path: Path):
        super().__init__()
        self.url = url
        self.size = size
        self.cache_path = cache_path
        self.signals = ImageDownloadSignals()
        self.setAutoDelete(True)
    
    @pyqtSlot()
    def run(self):
        """Download and process image"""
        try:
            response = requests.get(self.url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            response.raise_for_status()
            
            # Load image
            pixmap = QPixmap()
            pixmap.loadFromData(response.content)
            
            if not pixmap.isNull():
                # Save original to disk cache (not scaled)
                try:
                    pixmap.save(str(self.cache_path), "PNG")
                    logger.debug(f"Saved to cache: {self.cache_path}")
                except Exception as e:
                    logger.warning(f"Failed to save to cache: {e}")
                
                # Scale image for display
                scaled_pixmap = pixmap.scaled(
                    self.size[0], self.size[1],
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                
                self.signals.image_downloaded.emit(self.url, scaled_pixmap)
            else:
                self.signals.download_failed.emit(self.url, "Pixmap is null after loading")
        
        except requests.exceptions.Timeout:
            self.signals.download_failed.emit(self.url, "Timeout")
        except requests.exceptions.ConnectionError:
            self.signals.download_failed.emit(self.url, "Connection error")
        except requests.exceptions.HTTPError as e:
            self.signals.download_failed.emit(self.url, f"HTTP {e.response.status_code}")
        except Exception as e:
            self.signals.download_failed.emit(self.url, str(e))


class ImageCache(QObject):
    """
    Image cache with thread pool (LIMITED concurrent downloads).
    
    CRITICAL: Uses QThreadPool to limit concurrent downloads to prevent
    system overload when loading thousands of images at once.
    """
    
    image_ready = pyqtSignal(str, QPixmap)  # url, pixmap
    
    def __init__(self, max_concurrent_downloads: int = 10):
        super().__init__()
        # Use cache/images folder to match existing structure
        self.cache_dir = Path('cache/images')
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.memory_cache = {}  # In-memory cache
        self.pending_downloads = set()  # Track pending URLs
        self.placeholder = self._create_placeholder()
        
        # Thread pool with LIMITED workers (default 10)
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(max_concurrent_downloads)
        
        # Count existing cached images
        cached_count = len(list(self.cache_dir.glob('*.png')))
        logger.info(f"ImageCache initialized with {max_concurrent_downloads} max concurrent downloads")
        logger.info(f"Found {cached_count} cached images in {self.cache_dir}")
    
    def _create_placeholder(self) -> QPixmap:
        """Create placeholder pixmap"""
        pixmap = QPixmap(100, 100)
        pixmap.fill(0xDDDDDD)  # Light gray for white background
        return pixmap
    
    def get_cache_path(self, url: str) -> Path:
        """Get cache file path for URL"""
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return self.cache_dir / f"{url_hash}.png"
    
    def get_image(self, url: str, size: tuple = (100, 100)) -> QPixmap:
        """
        Get image from cache or download it.
        Returns placeholder if image is not in cache and starts download.
        
        IMPORTANT: Uses thread pool to limit concurrent downloads.
        """
        if not url:
            return self.placeholder
        
        # Check memory cache first
        cache_key = f"{url}_{size[0]}_{size[1]}"
        if cache_key in self.memory_cache:
            return self.memory_cache[cache_key]
        
        # Check disk cache
        cache_path = self.get_cache_path(url)
        if cache_path.exists():
            try:
                pixmap = QPixmap(str(cache_path))
                if not pixmap.isNull():
                    # Scale to requested size with correct PyQt6 syntax
                    scaled_pixmap = pixmap.scaled(
                        size[0], size[1],
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    # Cache in memory
                    self.memory_cache[cache_key] = scaled_pixmap
                    logger.debug(f"Loaded from disk cache: {url}")
                    return scaled_pixmap
                else:
                    logger.warning(f"Cached image is null: {cache_path}")
            except Exception as e:
                logger.warning(f"Failed to load cached image {cache_path}: {e}")
        
        # Start download if not already downloading
        if url not in self.pending_downloads:
            self.pending_downloads.add(url)
            
            # Create runnable
            runnable = ImageDownloadRunnable(url, size, cache_path)
            runnable.signals.image_downloaded.connect(
                lambda u, p: self._on_image_downloaded(u, p, size)
            )
            runnable.signals.download_failed.connect(self._on_download_failed)
            
            # Submit to thread pool (will queue if pool is full)
            self.thread_pool.start(runnable)
            logger.debug(f"Started download for: {url}")
        
        # Return placeholder while downloading
        return self.placeholder
    
    def _on_image_downloaded(self, url: str, pixmap: QPixmap, size: tuple):
        """Handle downloaded image"""
        # Save to memory cache
        cache_key = f"{url}_{size[0]}_{size[1]}"
        self.memory_cache[cache_key] = pixmap
        
        # Remove from pending
        self.pending_downloads.discard(url)
        
        # Emit signal
        self.image_ready.emit(url, pixmap)
        
        logger.info(f"Image downloaded: {url}")
    
    def _on_download_failed(self, url: str, error: str):
        """Handle download failure"""
        self.pending_downloads.discard(url)
        logger.warning(f"Download failed for {url}: {error}")
    
    def clear_cache(self):
        """Clear all cached images"""
        self.memory_cache.clear()
        
        # Delete disk cache
        for cache_file in self.cache_dir.glob('*.png'):
            try:
                cache_file.unlink()
            except Exception as e:
                logger.error(f"Failed to delete cache file {cache_file}: {e}")
        
        logger.info("Image cache cleared")
    
    def cleanup(self):
        """Cleanup all active downloads and thread pool"""
        logger.info("Starting ImageCache cleanup...")
        
        # Clear pending downloads
        self.pending_downloads.clear()
        
        # Wait for thread pool to finish (with timeout)
        if self.thread_pool:
            logger.info(f"Waiting for {self.thread_pool.activeThreadCount()} active downloads to finish...")
            self.thread_pool.waitForDone(3000)  # Wait max 3 seconds
            
            # Force clear if still running
            if self.thread_pool.activeThreadCount() > 0:
                logger.warning(f"Force clearing {self.thread_pool.activeThreadCount()} remaining downloads")
                self.thread_pool.clear()
        
        logger.info("ImageCache cleanup completed")
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        return {
            'memory_cached': len(self.memory_cache),
            'pending_downloads': len(self.pending_downloads),
            'active_threads': self.thread_pool.activeThreadCount() if self.thread_pool else 0,
            'max_threads': self.thread_pool.maxThreadCount() if self.thread_pool else 0,
            'disk_cached': len(list(self.cache_dir.glob('*.png')))
        }