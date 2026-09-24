"""Loading playlists from files, URLs and Xtream accounts (worker threads)."""
import logging
import os
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlsplit

from core import xtream
from core.m3u import (NotAPlaylist, ParsedPlaylist, detect_xtream_url, looks_like_url,
                      normalize_server_url, parse_m3u_text)
from core.net import CancelToken, NetworkError, decode_text, fetch_bytes

logger = logging.getLogger(__name__)


class PlaylistError(Exception):
    """User facing error while loading a playlist (message in Serbian)."""


def default_name(source: dict) -> str:
    if source.get("type") == "Xtream":
        host = urlsplit(normalize_server_url(source.get("server", ""))).hostname or "Xtream"
        return f"Xtream – {host}"
    url = source.get("url", "")
    if looks_like_url(url):
        return f"Lista – {urlsplit(url).hostname or 'internet'}"
    return Path(url).stem or "Moja lista"


def source_from_user_input(text: str) -> dict:
    """Turn a pasted URL / path into a playlist source. Full Xtream
    ``get.php`` links are converted to an Xtream account automatically."""
    text = (text or "").strip().strip('"')
    if not text:
        raise PlaylistError("Unesite adresu liste ili izaberite fajl.")
    account = detect_xtream_url(text)
    if account:
        return {"type": "Xtream", "server": account.server, "username": account.username,
                "password": account.password}
    if looks_like_url(text):
        return {"type": "M3U", "url": text}
    if "://" in text:
        raise PlaylistError("Adresa nije ispravna. Adresa mora počinjati sa http:// ili https://")
    return {"type": "M3U", "url": text}


def load_playlist(source: dict, cancel: Optional[CancelToken] = None,
                  progress: Optional[Callable[[str], None]] = None) -> ParsedPlaylist:
    """Fetch and parse a playlist. Raises :class:`PlaylistError` or ``Cancelled``."""
    cancel = cancel or CancelToken()
    report = progress or (lambda message: None)
    try:
        if source.get("type") == "Xtream":
            server = source.get("server", "")
            username = source.get("username", "")
            password = source.get("password", "")
            if not (server and username and password):
                raise PlaylistError("Popunite adresu servera, korisničko ime i lozinku.")
            result = xtream.fetch_account(server, username, password, cancel=cancel, progress=report)
        else:
            location = source.get("url", "")
            if looks_like_url(location):
                report("Preuzimam listu sa interneta…")

                def on_bytes(total):
                    report(f"Preuzimam listu… {total / (1024 * 1024):.1f} MB")

                data = fetch_bytes(location, cancel=cancel, progress=on_bytes)
            else:
                path = Path(os.path.expandvars(location)).expanduser()
                if not path.is_file():
                    raise PlaylistError("Fajl nije pronađen. Izaberite ponovo fajl sa listom.")
                report("Čitam fajl…")
                data = path.read_bytes()
            cancel.check()
            report("Obrađujem listu…")
            try:
                result = parse_m3u_text(decode_text(data), check_cancel=cancel.check)
            except NotAPlaylist:
                raise PlaylistError("Sadržaj nije IPTV lista (M3U). Proverite adresu.") from None
    except NetworkError as exc:
        raise PlaylistError(str(exc)) from None
    except OSError as exc:
        logger.error("Playlist file error: %s", exc)
        raise PlaylistError("Fajl sa listom nije moguće pročitati.") from None
    if result.total == 0:
        raise PlaylistError("Lista je prazna – nema kanala, filmova ni serija.")
    return result


def resolve_stream_url(url: str, playlist: Optional[dict]) -> str:
    if url and url.startswith(xtream.XTREAM_PREFIX) and playlist:
        return xtream.resolve_url(url, playlist.get("server", ""), playlist.get("username", ""),
                                  playlist.get("password", ""))
    return url
