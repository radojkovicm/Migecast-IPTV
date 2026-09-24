"""Xtream Codes API client (blocking; call from worker threads only).

Stream URLs are cached as ``xtream:<kind>/<id>.<ext>`` without credentials;
:func:`resolve_url` builds the real URL right before playback. This keeps the
account password out of the cached playlist tables.
"""
import logging
from typing import List, Optional
from urllib.parse import urlencode

from core.m3u import ParsedPlaylist, normalize_server_url, parse_episode_info
from core.net import CancelToken, NetworkError, fetch_json
from models.channel import Channel
from models.series_item import SeriesItem
from models.vod_item import VODItem

logger = logging.getLogger(__name__)

XTREAM_PREFIX = "xtream:"


def api_url(server: str, username: str, password: str, action: Optional[str] = None, **params) -> str:
    query = {"username": username, "password": password}
    if action:
        query["action"] = action
    query.update({key: value for key, value in params.items() if value is not None})
    return f"{normalize_server_url(server)}/player_api.php?{urlencode(query)}"


def resolve_url(url: str, server: str = "", username: str = "", password: str = "") -> str:
    """Turn ``xtream:live/123.ts`` into a playable URL; other URLs pass through."""
    if not url or not url.startswith(XTREAM_PREFIX):
        return url
    kind, _, rest = url[len(XTREAM_PREFIX):].partition("/")
    return f"{normalize_server_url(server)}/{kind}/{username}/{password}/{rest}"


def _as_list(data) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return list(data.values())
    return []


def _categories(server, username, password, action, cancel) -> dict:
    try:
        data = fetch_json(api_url(server, username, password, action), cancel=cancel)
    except NetworkError as exc:
        logger.warning("Could not load %s: %s", action, exc)
        return {}
    return {str(c.get("category_id")): (c.get("category_name") or "Ostalo").strip()
            for c in _as_list(data) if isinstance(c, dict)}


def authenticate(server: str, username: str, password: str, cancel: Optional[CancelToken] = None) -> dict:
    data = fetch_json(api_url(server, username, password), cancel=cancel)
    if not isinstance(data, dict) or "user_info" not in data:
        raise NetworkError("Adresa ne izgleda kao Xtream server.", "bad_response")
    info = data.get("user_info") or {}
    if str(info.get("auth", "1")) in ("0", "False", "false"):
        raise NetworkError("Pogrešno korisničko ime ili lozinka.", "auth")
    status = str(info.get("status", "Active"))
    if status.lower() not in ("active", ""):
        raise NetworkError(f"Nalog nije aktivan (status: {status}).", "auth")
    return info


def fetch_account(server: str, username: str, password: str, cancel: Optional[CancelToken] = None,
                  progress=None) -> ParsedPlaylist:
    cancel = cancel or CancelToken()
    server = normalize_server_url(server)
    report = progress or (lambda message: None)

    report("Povezujem se sa serverom…")
    info = authenticate(server, username, password, cancel)
    formats = [str(f).lower() for f in (info.get("allowed_output_formats") or [])]
    live_ext = "ts" if (not formats or "ts" in formats) else (formats[0] or "m3u8")

    result = ParsedPlaylist()

    report("Učitavam TV kanale…")
    live_categories = _categories(server, username, password, "get_live_categories", cancel)
    for stream in _as_list(fetch_json(api_url(server, username, password, "get_live_streams"), cancel=cancel)):
        if not isinstance(stream, dict) or stream.get("stream_id") in (None, ""):
            continue
        stream_id = str(stream.get("stream_id"))
        result.channels.append(Channel(
            channel_id=stream_id,
            name=stream.get("name") or "Kanal",
            url=f"{XTREAM_PREFIX}live/{stream_id}.{live_ext}",
            logo=stream.get("stream_icon") or None,
            category=stream.get("category_name") or live_categories.get(str(stream.get("category_id")), "Ostalo"),
            epg_id=stream.get("epg_channel_id") or None,
        ))
    cancel.check()

    report("Učitavam filmove…")
    vod_categories = _categories(server, username, password, "get_vod_categories", cancel)
    for stream in _as_list(fetch_json(api_url(server, username, password, "get_vod_streams"), cancel=cancel)):
        if not isinstance(stream, dict) or stream.get("stream_id") in (None, ""):
            continue
        stream_id = str(stream.get("stream_id"))
        ext = stream.get("container_extension") or "mp4"
        result.vod_items.append(VODItem(
            stream_id=stream_id,
            name=stream.get("name") or "Film",
            url=f"{XTREAM_PREFIX}movie/{stream_id}.{ext}",
            cover=stream.get("stream_icon") or None,
            plot=stream.get("plot") or None,
            rating=str(stream.get("rating") or "") or None,
            year=str(stream.get("year") or stream.get("releasedate") or "")[:4] or None,
            genre=stream.get("genre") or None,
            duration=stream.get("duration") or None,
            director=stream.get("director") or None,
            cast=stream.get("cast") or None,
            category=stream.get("category_name") or vod_categories.get(str(stream.get("category_id")), "Ostalo"),
        ))
    cancel.check()

    report("Učitavam serije…")
    series_categories = _categories(server, username, password, "get_series_categories", cancel)
    for series in _as_list(fetch_json(api_url(server, username, password, "get_series"), cancel=cancel)):
        if not isinstance(series, dict) or series.get("series_id") in (None, ""):
            continue
        series_id = str(series.get("series_id"))
        name = (series.get("name") or "Serija").strip()
        item = SeriesItem(
            stream_id=f"xs{series_id}",
            name=name,
            url="",
            cover=series.get("cover") or None,
            plot=series.get("plot") or None,
            rating=str(series.get("rating") or "") or None,
            year=str(series.get("releaseDate") or series.get("year") or "")[:4] or None,
            genre=series.get("genre") or None,
            director=series.get("director") or None,
            cast=series.get("cast") or None,
            category=series.get("category_name") or series_categories.get(str(series.get("category_id")), "Ostalo"),
        )
        item.series_name = name
        item.xtream_series_id = series_id
        result.series_items.append(item)
    return result


def fetch_series_episodes(server: str, username: str, password: str, series: SeriesItem,
                          cancel: Optional[CancelToken] = None) -> List[SeriesItem]:
    """Load all episodes of an Xtream series (``get_series_info``)."""
    data = fetch_json(api_url(server, username, password, "get_series_info", series_id=series.xtream_series_id),
                      cancel=cancel)
    if not isinstance(data, dict):
        return []
    info = data.get("info") or {}
    episodes_by_season = data.get("episodes") or {}
    if isinstance(episodes_by_season, list):  # some panels return a flat list
        episodes_by_season = {"1": episodes_by_season}
    episodes = []
    for season_key, items in episodes_by_season.items():
        for index, episode in enumerate(_as_list(items), start=1):
            if not isinstance(episode, dict) or episode.get("id") in (None, ""):
                continue
            episode_id = str(episode.get("id"))
            ext = episode.get("container_extension") or "mp4"
            meta = episode.get("info") if isinstance(episode.get("info"), dict) else {}
            season_no = episode.get("season") or season_key
            episode_no = episode.get("episode_num") or index
            title = (episode.get("title") or "").strip()
            parsed = parse_episode_info(title)
            item = SeriesItem(
                stream_id=episode_id,
                name=title or f"{series.name} S{season_no}E{episode_no}",
                url=f"{XTREAM_PREFIX}series/{episode_id}.{ext}",
                cover=meta.get("movie_image") or series.cover or info.get("cover"),
                plot=meta.get("plot") or None,
                rating=str(meta.get("rating") or "") or None,
                category=series.category,
                season=str(season_no),
                episode=str(episode_no),
            )
            item.series_name = series.series_name or series.name
            item.episode_title = _episode_title(title, parsed)
            episodes.append(item)
    return episodes


def _episode_title(title: str, parsed) -> Optional[str]:
    if not title:
        return None
    if parsed and parsed.series_name and title.startswith(parsed.series_name):
        rest = title[len(parsed.series_name):]
        import re
        rest = re.sub(r"(?i)^[\s\-–|:.]*S\d+\s*E\d+[\s\-–|:.]*", "", rest).strip()
        return rest or None
    return title
