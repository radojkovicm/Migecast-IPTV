"""Pure M3U/M3U8 parsing and classification helpers (no Qt, no database).

Keeping this logic free of side effects makes it fast and easy to test.
"""
import hashlib
import re
from dataclasses import dataclass, field
from typing import Callable, Iterable, List, Optional, Tuple
from urllib.parse import parse_qs, urlsplit

from models.channel import Channel
from models.series_item import SeriesItem
from models.vod_item import VODItem

# ---------------------------------------------------------------------------
# Stable identifiers
# ---------------------------------------------------------------------------

def url_id(url: str) -> str:
    """Deterministic ID derived from the stream URL.

    Version 1.x used Python's ``hash(url)`` which is randomised per process,
    so favorites and watch progress got lost after a refresh.
    """
    return "u" + hashlib.sha1(url.strip().encode("utf-8")).hexdigest()[:16]


LEGACY_HASH_ID_RE = re.compile(r"-?\d{15,20}")


def is_legacy_hash_id(value: str) -> bool:
    return bool(value) and bool(LEGACY_HASH_ID_RE.fullmatch(value))


# ---------------------------------------------------------------------------
# Season / episode parsing
# ---------------------------------------------------------------------------

_EPISODE_PATTERNS = [
    # S01E03, s1e3, S01 E03, S01.E03, S01_E03, S01-E03, S01 Ep03
    re.compile(r"(?i)(?<![A-Za-z0-9])S(?:ezona|eason)?\s*[._-]?\s*(\d{1,3})\s*[._\- ]?\s*(?:E|Ep|Epizoda|Episode)\s*[._-]?\s*(\d{1,4})(?!\d)"),
    # 1x03
    re.compile(r"(?i)(?<![A-Za-z0-9])(\d{1,2})x(\d{1,3})(?!\d)"),
    # Sezona 1 Epizoda 3 / Season 1 Episode 3 / Sez. 1 Ep. 3
    re.compile(r"(?i)(?:sezona|season|sez\.?)\s*(\d{1,3})\D{0,6}?(?:epizoda|episode|ep\.?)\s*(\d{1,4})"),
]
_EPISODE_ONLY = re.compile(r"(?i)(?<![A-Za-z0-9])(?:E|Ep\.?|Epizoda|Episode)\s*[._-]?\s*(\d{1,4})(?!\d)\s*$")
_SEPARATORS = " -–—|:._,/\\([)"


@dataclass
class EpisodeInfo:
    series_name: str
    season: Optional[int]
    episode: Optional[int]

    @property
    def code(self) -> str:
        return episode_code(self.season, self.episode)


def episode_code(season, episode) -> str:
    """Return a label like ``S01E03`` (or ``E03`` when season is unknown)."""
    s = _to_int(season)
    e = _to_int(episode)
    if s is not None and e is not None:
        return f"S{s:02d}E{e:02d}"
    if e is not None:
        return f"E{e:02d}"
    if s is not None:
        return f"S{s:02d}"
    return ""


def _to_int(value) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _clean_series_name(name: str) -> str:
    name = " ".join(name.split())
    name = name.strip(_SEPARATORS)
    return " ".join(name.split())


def parse_episode_info(title: str) -> Optional[EpisodeInfo]:
    """Extract series name, season and episode from an episode title."""
    if not title:
        return None
    for pattern in _EPISODE_PATTERNS:
        match = pattern.search(title)
        if match:
            name = _clean_series_name(title[:match.start()])
            if not name:
                name = _clean_series_name(title[match.end():]) or title.strip()
            return EpisodeInfo(name, int(match.group(1)), int(match.group(2)))
    match = _EPISODE_ONLY.search(title)
    if match:
        name = _clean_series_name(title[:match.start()])
        if name:
            return EpisodeInfo(name, None, int(match.group(1)))
    return None


def legacy_series_name(full_name: str) -> str:
    """Series name exactly as version 1.x computed it (for favorite migration)."""
    name = re.sub(r"\s+S\d{1,2}\s*E\d{1,2}.*$", "", full_name or "", flags=re.IGNORECASE)
    return " ".join(name.split()).strip()


def series_name_for(item: SeriesItem) -> str:
    if getattr(item, "series_name", None):
        return item.series_name
    info = parse_episode_info(item.name)
    if info:
        return info.series_name
    return _clean_series_name(item.name) or item.name


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

_SERIES_WORDS = ("series", "serij", "sezon", "tv show", "tvshow", "shows", "episod", "epizod")
_MOVIE_WORDS = ("movie", "film", "vod", "kino", "cinema", "bioskop", "4k movies")
_VIDEO_EXT = (".mp4", ".mkv", ".avi", ".mov", ".wmv", ".m4v", ".mpg", ".mpeg", ".webm", ".flv")


def classify(name: str, group: str, url: str) -> str:
    """Return ``'tv'``, ``'movie'`` or ``'series'`` for an M3U entry."""
    group_l = (group or "").lower()
    path = urlsplit(url).path.lower() if "://" in url else url.lower()

    if "/series/" in path:
        return "series"
    if "/movie/" in path or "/movies/" in path:
        return "movie"
    if "/live/" in path:
        return "tv"

    has_episode = any(pattern.search(name or "") for pattern in _EPISODE_PATTERNS)
    if has_episode or any(word in group_l for word in _SERIES_WORDS):
        return "series"
    if any(word in group_l for word in _MOVIE_WORDS):
        return "movie"
    if path.endswith(_VIDEO_EXT):
        return "movie"
    return "tv"


# ---------------------------------------------------------------------------
# Xtream URL detection
# ---------------------------------------------------------------------------

@dataclass
class XtreamAccount:
    server: str
    username: str
    password: str


def detect_xtream_url(url: str) -> Optional[XtreamAccount]:
    """Recognise ``http://host:port/get.php?username=U&password=P&type=m3u``."""
    if not url or "://" not in url:
        return None
    parts = urlsplit(url.strip())
    if not parts.netloc:
        return None
    last = parts.path.rstrip("/").rsplit("/", 1)[-1].lower()
    if last not in ("get.php", "player_api.php", "panel_api.php"):
        return None
    query = parse_qs(parts.query)
    username = (query.get("username") or [""])[0]
    password = (query.get("password") or [""])[0]
    if not username or not password:
        return None
    prefix = parts.path.rstrip("/").rsplit("/", 1)[0]
    server = f"{parts.scheme}://{parts.netloc}{prefix}"
    return XtreamAccount(server=server.rstrip("/"), username=username, password=password)


def normalize_server_url(server: str) -> str:
    server = (server or "").strip()
    if server and "://" not in server:
        server = "http://" + server
    return server.rstrip("/")


def looks_like_url(text: str) -> bool:
    text = (text or "").strip()
    return bool(re.match(r"(?i)^(https?|ftp)://[^\s/]+", text))


# ---------------------------------------------------------------------------
# M3U parsing
# ---------------------------------------------------------------------------

_ATTR_RE = re.compile(r'([A-Za-z0-9_-]+)\s*=\s*"([^"]*)"')


def _split_extinf(line: str) -> Tuple[dict, str]:
    body = line[len("#EXTINF:"):]
    in_quotes = False
    comma = -1
    for index, char in enumerate(body):
        if char == '"':
            in_quotes = not in_quotes
        elif char == "," and not in_quotes:
            comma = index
            break
    attrs_part = body if comma < 0 else body[:comma]
    title = "" if comma < 0 else body[comma + 1:].strip()
    attrs = {key.lower(): value.strip() for key, value in _ATTR_RE.findall(attrs_part)}
    return attrs, title


@dataclass
class ParsedPlaylist:
    channels: List[Channel] = field(default_factory=list)
    vod_items: List[VODItem] = field(default_factory=list)
    series_items: List[SeriesItem] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.channels) + len(self.vod_items) + len(self.series_items)


class NotAPlaylist(ValueError):
    pass


def parse_m3u_text(text: str, check_cancel: Optional[Callable[[], None]] = None) -> ParsedPlaylist:
    """Parse M3U text into channels, movies and series episodes."""
    result = ParsedPlaylist()
    if text is None:
        return result
    text = text.lstrip("﻿")
    stripped = text.lstrip()
    if stripped and not stripped.startswith("#EXTM3U") and "#EXTINF" not in text[:20000]:
        # Plain list of URLs is allowed; anything else (HTML, JSON) is not.
        first = stripped.splitlines()[0].strip()
        if not looks_like_url(first):
            raise NotAPlaylist("Sadržaj nije M3U lista.")

    used_ids = set()
    pending_attrs, pending_title, pending_group = None, None, None

    def unique_id(candidate: str, url: str) -> str:
        item_id = candidate or url_id(url)
        if item_id in used_ids:
            item_id = url_id(url)
            suffix = 1
            base = item_id
            while item_id in used_ids:
                suffix += 1
                item_id = f"{base}-{suffix}"
        used_ids.add(item_id)
        return item_id

    for count, raw in enumerate(text.splitlines()):
        if check_cancel and count % 2000 == 0:
            check_cancel()
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            pending_attrs, pending_title = _split_extinf(line)
            pending_group = None
            continue
        if line.startswith("#EXTGRP:"):
            pending_group = line[len("#EXTGRP:"):].strip()
            continue
        if line.startswith("#"):
            continue

        url = line
        attrs = pending_attrs or {}
        title = pending_title or attrs.get("tvg-name") or url.rsplit("/", 1)[-1]
        title = " ".join(title.split()) or "Bez naziva"
        group = attrs.get("group-title") or pending_group or "Ostalo"
        logo = attrs.get("tvg-logo") or attrs.get("logo") or None
        tvg_id = attrs.get("tvg-id", "").strip()
        pending_attrs, pending_title, pending_group = None, None, None

        kind = classify(title, group, url)
        if kind == "series":
            info = parse_episode_info(title)
            item = SeriesItem(
                stream_id=unique_id("", url), name=title, url=url, cover=logo, category=group,
                season=str(info.season) if info and info.season is not None else None,
                episode=str(info.episode) if info and info.episode is not None else None,
            )
            item.series_name = info.series_name if info else _clean_series_name(title)
            result.series_items.append(item)
        elif kind == "movie":
            result.vod_items.append(VODItem(stream_id=unique_id("", url), name=title, url=url,
                                            cover=logo, category=group))
        else:
            result.channels.append(Channel(channel_id=unique_id(tvg_id, url), name=title, url=url,
                                           logo=logo, category=group, epg_id=tvg_id or None))
    return result


def group_series(items: Iterable[SeriesItem]) -> dict:
    """Group episodes by series name, preserving first-seen order."""
    groups = {}
    for item in items:
        groups.setdefault(series_name_for(item), []).append(item)
    return groups


def sort_episodes(episodes: List[SeriesItem]) -> List[SeriesItem]:
    """Sort by season, then episode number, then title (stable for odd names)."""
    def key(item):
        season = _to_int(item.season)
        episode = _to_int(item.episode)
        return (season if season is not None else 0,
                episode if episode is not None else 10 ** 6,
                natural_key(item.name))
    return sorted(episodes, key=key)


def natural_key(text: str):
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", text or "")]
