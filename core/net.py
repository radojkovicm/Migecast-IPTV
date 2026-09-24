"""Network helpers with timeouts, retries and cooperative cancellation.

Everything in this module is blocking and must only be called from worker
threads, never from the Qt GUI thread.
"""
import logging
import threading
import time
from typing import Callable, Optional

import requests

from version import __version__

logger = logging.getLogger(__name__)

USER_AGENT = f"MigeCast/{__version__} (Windows; IPTV player)"
CONNECT_TIMEOUT = 8
READ_TIMEOUT = 30
MAX_PLAYLIST_BYTES = 512 * 1024 * 1024  # safety net against endless streams


class Cancelled(Exception):
    """Raised when the user cancelled the operation."""


class NetworkError(Exception):
    """Human readable network failure (message is already user friendly)."""

    def __init__(self, message: str, kind: str = "network"):
        super().__init__(message)
        self.kind = kind


class CancelToken:
    def __init__(self):
        self._event = threading.Event()

    def cancel(self):
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def check(self):
        if self._event.is_set():
            raise Cancelled()


_session_local = threading.local()


def session() -> requests.Session:
    sess = getattr(_session_local, "session", None)
    if sess is None:
        sess = requests.Session()
        sess.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})
        _session_local.session = sess
    return sess


def _classify(exc: Exception) -> NetworkError:
    if isinstance(exc, requests.exceptions.Timeout):
        return NetworkError("Server ne odgovara (isteklo vreme čekanja).", "timeout")
    if isinstance(exc, requests.exceptions.SSLError):
        return NetworkError("Greška sigurne veze (SSL) sa serverom.", "ssl")
    if isinstance(exc, requests.exceptions.ConnectionError):
        return NetworkError("Server nije dostupan. Proverite internet vezu i adresu.", "connection")
    if isinstance(exc, requests.exceptions.HTTPError):
        code = exc.response.status_code if exc.response is not None else 0
        if code in (401, 403):
            return NetworkError("Pristup odbijen. Proverite korisničko ime i lozinku.", "auth")
        if code == 404:
            return NetworkError("Adresa nije pronađena na serveru (404).", "notfound")
        return NetworkError(f"Server je vratio grešku ({code}).", "http")
    if isinstance(exc, (requests.exceptions.InvalidURL, requests.exceptions.MissingSchema,
                        requests.exceptions.InvalidSchema)):
        return NetworkError("Adresa nije ispravna.", "invalid_url")
    return NetworkError("Greška mreže.", "network")


def fetch_bytes(url: str, cancel: Optional[CancelToken] = None, retries: int = 2,
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                progress: Optional[Callable[[int], None]] = None,
                max_bytes: int = MAX_PLAYLIST_BYTES) -> bytes:
    """Download ``url`` with retries on transient errors. Honors ``cancel``."""
    cancel = cancel or CancelToken()
    attempt = 0
    while True:
        cancel.check()
        try:
            with session().get(url, stream=True, timeout=timeout) as response:
                response.raise_for_status()
                chunks = []
                total = 0
                for chunk in response.iter_content(chunk_size=256 * 1024):
                    cancel.check()
                    if not chunk:
                        continue
                    chunks.append(chunk)
                    total += len(chunk)
                    if total > max_bytes:
                        raise NetworkError("Lista je prevelika.", "too_large")
                    if progress:
                        progress(total)
                return b"".join(chunks)
        except (Cancelled, NetworkError):
            raise
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else 0
            if status >= 500 and attempt < retries:
                attempt += 1
                _sleep_cancellable(1.5 * attempt, cancel)
                continue
            raise _classify(exc) from None
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError,
                requests.exceptions.ChunkedEncodingError) as exc:
            if attempt < retries and not isinstance(exc, requests.exceptions.SSLError):
                attempt += 1
                logger.info("Network retry %d/%d (%s)", attempt, retries, type(exc).__name__)
                _sleep_cancellable(1.5 * attempt, cancel)
                continue
            raise _classify(exc) from None
        except requests.exceptions.RequestException as exc:
            raise _classify(exc) from None


def fetch_json(url: str, cancel: Optional[CancelToken] = None, retries: int = 2, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT)):
    data = fetch_bytes(url, cancel=cancel, retries=retries, timeout=timeout)
    try:
        import json
        return json.loads(data.decode("utf-8", errors="replace") or "null")
    except ValueError:
        raise NetworkError("Server nije vratio ispravne podatke. Proverite adresu servera.", "bad_response") from None


def _sleep_cancellable(seconds: float, cancel: CancelToken):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        cancel.check()
        time.sleep(0.1)


def decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1250", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")
