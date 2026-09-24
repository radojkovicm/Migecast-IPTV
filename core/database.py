"""SQLite storage for favorites, watch progress, playlists and playlist cache.

* The database lives in ``%LOCALAPPDATA%\\MigeCast\\data\\migecast.db``.
* Sessions are thread-local (``scoped_session``) so the playlist loader
  thread and the GUI thread never share a connection.
* Schema changes are applied by numbered migrations; before migrating an
  existing database a backup copy is written to the ``backups`` folder.
"""
import logging
import shutil
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from sqlalchemy import (Boolean, Column, DateTime, Float, Index, Integer, String, Text,
                        create_engine, event, insert, select, text)
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker

from utils import paths
from utils.security import SecurityManager

logger = logging.getLogger(__name__)

Base = declarative_base()

SCHEMA_VERSION = 2
ENC_PREFIX = "enc:"


class FavoriteChannel(Base):
    __tablename__ = "favorite_channels"
    id = Column(Integer, primary_key=True)
    channel_id = Column(String, unique=True, nullable=False)
    name = Column(String)
    added_at = Column(DateTime, default=datetime.now)


class FavoriteVOD(Base):
    __tablename__ = "favorite_vod"
    id = Column(Integer, primary_key=True)
    stream_id = Column(String, unique=True, nullable=False)
    name = Column(String)
    added_at = Column(DateTime, default=datetime.now)


class FavoriteSeries(Base):
    """Series favorites are keyed by the series name (as in version 1.x)."""
    __tablename__ = "favorite_series"
    id = Column(Integer, primary_key=True)
    series_id = Column(String, unique=True, nullable=False)
    name = Column(String)
    added_at = Column(DateTime, default=datetime.now)


class WatchedSeries(Base):
    __tablename__ = "watched_series"
    id = Column(Integer, primary_key=True)
    stream_id = Column(String, nullable=False)
    series_id = Column(String)
    name = Column(String)
    season = Column(String)
    episode = Column(String)
    watched_at = Column(DateTime, default=datetime.now)


class WatchedVOD(Base):
    __tablename__ = "watched_vod"
    id = Column(Integer, primary_key=True)
    stream_id = Column(String, unique=True, nullable=False)
    name = Column(String)
    watched_at = Column(DateTime, default=datetime.now)
    __table_args__ = (Index("idx_watched_vod_time", "watched_at"),)


class SavedPlaylist(Base):
    __tablename__ = "saved_playlists"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    type = Column(String)  # 'M3U' (file or URL) or 'Xtream'
    url = Column(String)
    server = Column(String)
    username = Column(String)
    password = Column(String)
    is_active = Column(Boolean, default=False)
    added_at = Column(DateTime, default=datetime.now)
    last_loaded = Column(DateTime)
    last_refreshed = Column(DateTime)


class CachedChannel(Base):
    __tablename__ = "cached_channels"
    id = Column(Integer, primary_key=True)
    channel_id = Column(String, nullable=False)
    name = Column(String)
    url = Column(String)
    logo = Column(String)
    category = Column(String)
    epg_id = Column(String)
    playlist_id = Column(Integer, nullable=False)
    __table_args__ = (
        Index("idx_channel_playlist", "playlist_id"),
        Index("idx_channel_category", "category"),
        Index("idx_channel_name", "name"),
    )


class CachedVOD(Base):
    __tablename__ = "cached_vod"
    id = Column(Integer, primary_key=True)
    stream_id = Column(String, nullable=False)
    name = Column(String)
    url = Column(String)
    cover = Column(String)
    plot = Column(Text)
    rating = Column(String)
    year = Column(String)
    genre = Column(String)
    duration = Column(String)
    director = Column(String)
    cast = Column(Text)
    category = Column(String)
    playlist_id = Column(Integer, nullable=False)
    __table_args__ = (
        Index("idx_vod_playlist", "playlist_id"),
        Index("idx_vod_category", "category"),
        Index("idx_vod_name", "name"),
    )


class CachedSeries(Base):
    __tablename__ = "cached_series"
    id = Column(Integer, primary_key=True)
    stream_id = Column(String, nullable=False)
    name = Column(String)
    url = Column(String)
    cover = Column(String)
    plot = Column(Text)
    rating = Column(String)
    year = Column(String)
    genre = Column(String)
    director = Column(String)
    cast = Column(Text)
    category = Column(String)
    season = Column(String)
    episode = Column(String)
    series_name = Column(String)
    xtream_series_id = Column(String)
    playlist_id = Column(Integer, nullable=False)
    __table_args__ = (
        Index("idx_series_playlist", "playlist_id"),
        Index("idx_series_category", "category"),
        Index("idx_series_name", "name"),
    )


class TMDBCache(Base):
    __tablename__ = "tmdb_cache"
    id = Column(Integer, primary_key=True)
    stream_id = Column(String, unique=True, nullable=False)
    title = Column(String)
    tmdb_id = Column(Integer)
    rating = Column(Float)
    vote_count = Column(Integer)
    overview = Column(Text)
    genres = Column(String)
    release_date = Column(String)
    runtime = Column(Integer)
    director = Column(String)
    cast = Column(Text)
    poster_path = Column(String)
    backdrop_path = Column(String)
    cached_at = Column(DateTime, default=datetime.now)

    def to_dict(self):
        return {key: getattr(self, key) for key in (
            "tmdb_id", "rating", "vote_count", "overview", "genres", "release_date",
            "runtime", "director", "cast", "poster_path", "backdrop_path")}


class WatchProgress(Base):
    __tablename__ = "watch_progress"
    id = Column(Integer, primary_key=True)
    stream_id = Column(String, unique=True, nullable=False)
    content_type = Column(String, nullable=False)  # 'vod' or 'series'
    name = Column(String)
    position_seconds = Column(Integer, default=0)
    duration_seconds = Column(Integer, default=0)
    last_watched = Column(DateTime, default=datetime.now)
    completed = Column(Boolean, default=False)
    __table_args__ = (
        Index("idx_watch_progress_time", "last_watched"),
        Index("idx_watch_progress_type", "content_type"),
    )

    @property
    def progress_percent(self):
        if self.duration_seconds and self.duration_seconds > 0:
            return int((self.position_seconds / self.duration_seconds) * 100)
        return 0


class SeriesState(Base):
    """Last selected season and last played episode per series."""
    __tablename__ = "series_state"
    id = Column(Integer, primary_key=True)
    series_key = Column(String, unique=True, nullable=False)
    last_season = Column(String)
    last_episode_id = Column(String)
    updated_at = Column(DateTime, default=datetime.now)


# ---------------------------------------------------------------------------
# Migrations
# ---------------------------------------------------------------------------

def _columns(conn: sqlite3.Connection, table: str) -> set:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _tables(conn: sqlite3.Connection) -> set:
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def backup_database(db_path: Path, reason: str) -> Optional[Path]:
    """Copy the database (consistent snapshot) into the backups folder."""
    if not db_path.exists():
        return None
    target_dir = paths.backups_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = target_dir / f"migecast-{reason}-{stamp}.db"
    try:
        source = sqlite3.connect(str(db_path))
        dest = sqlite3.connect(str(target))
        with dest:
            source.backup(dest)
        source.close()
        dest.close()
    except sqlite3.Error:
        shutil.copy2(db_path, target)
    logger.info("Database backup written: %s", target.name)
    _prune_backups(target_dir, keep=10)
    return target


def _prune_backups(folder: Path, keep: int):
    backups = sorted(folder.glob("migecast-*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in backups[keep:]:
        try:
            old.unlink()
        except OSError:
            pass


def migrate_schema(db_path: Path) -> int:
    """Bring an existing database to :data:`SCHEMA_VERSION`. Returns old version."""
    if not db_path.exists():
        return SCHEMA_VERSION
    conn = sqlite3.connect(str(db_path))
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version >= SCHEMA_VERSION:
            return version
        tables = _tables(conn)
        if not tables:
            return SCHEMA_VERSION
        conn.close()
        backup_database(db_path, f"before-v{SCHEMA_VERSION}")
        conn = sqlite3.connect(str(db_path))
        with conn:
            if version < 2:
                _migrate_to_v2(conn)
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        logger.info("Database migrated from schema %s to %s", version, SCHEMA_VERSION)
        return version
    finally:
        conn.close()


def _migrate_to_v2(conn: sqlite3.Connection):
    from core.m3u import is_legacy_hash_id, url_id

    tables = _tables(conn)
    additions = {
        "cached_channels": {"epg_id": "VARCHAR"},
        "cached_series": {"series_name": "VARCHAR", "xtream_series_id": "VARCHAR"},
    }
    for table, columns in additions.items():
        if table not in tables:
            continue
        existing = _columns(conn, table)
        for column, sql_type in columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}")

    # Version 1.x used Python's randomised hash(url) as ID for M3U items
    # without tvg-id. Re-key them to a stable hash so favorites, watched
    # flags and progress survive refreshes and restarts.
    if "saved_playlists" not in tables:
        return
    m3u_ids = [row[0] for row in conn.execute("SELECT id FROM saved_playlists WHERE type = 'M3U'")]
    if not m3u_ids:
        return
    placeholders = ",".join("?" for _ in m3u_ids)
    mapping = {}
    for table, id_column in (("cached_channels", "channel_id"), ("cached_vod", "stream_id"),
                             ("cached_series", "stream_id")):
        if table not in tables:
            continue
        rows = conn.execute(
            f"SELECT id, {id_column}, url FROM {table} WHERE playlist_id IN ({placeholders})", m3u_ids).fetchall()
        for row_id, old_id, url in rows:
            if old_id and url and is_legacy_hash_id(old_id):
                new_id = url_id(url)
                mapping[old_id] = new_id
                conn.execute(f"UPDATE {table} SET {id_column} = ? WHERE id = ?", (new_id, row_id))
    if not mapping:
        return
    refs = (("favorite_channels", "channel_id"), ("favorite_vod", "stream_id"), ("watched_vod", "stream_id"),
            ("watched_series", "stream_id"), ("watch_progress", "stream_id"), ("tmdb_cache", "stream_id"))
    for table, column in refs:
        if table not in tables:
            continue
        for old_id, new_id in mapping.items():
            try:
                conn.execute(f"UPDATE {table} SET {column} = ? WHERE {column} = ?", (new_id, old_id))
            except sqlite3.IntegrityError:
                conn.execute(f"DELETE FROM {table} WHERE {column} = ?", (old_id,))
    logger.info("Re-keyed %d legacy item IDs to stable IDs", len(mapping))


# ---------------------------------------------------------------------------
# Database facade
# ---------------------------------------------------------------------------

class Database:
    """Database manager (process-wide singleton, thread-local sessions)."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                instance._initialized = False
                cls._instance = instance
        return cls._instance

    def __init__(self, db_path: Optional[Path] = None):
        with self._lock:
            if self._initialized:
                return
            self.db_path = Path(db_path) if db_path else paths.database_path()
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self.security = SecurityManager(self.db_path.parent / "secret.key")

            migrate_schema(self.db_path)
            self.engine = create_engine(
                f"sqlite:///{self.db_path}",
                connect_args={"check_same_thread": False, "timeout": 15},
            )

            @event.listens_for(self.engine, "connect")
            def _pragmas(dbapi_conn, _record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.close()

            Base.metadata.create_all(self.engine)
            with self.engine.begin() as conn:
                conn.execute(text(f"PRAGMA user_version = {SCHEMA_VERSION}"))
            self.session = scoped_session(sessionmaker(bind=self.engine, expire_on_commit=False))
            self._migrate_passwords()
            self._initialized = True
            logger.info("Database ready: %s", self.db_path.name)

    @classmethod
    def reset_instance(cls):
        """Dispose the singleton (tests and data import)."""
        with cls._lock:
            instance = cls._instance
            if instance is not None and instance._initialized:
                try:
                    instance.session.remove()
                    instance.engine.dispose()
                except Exception:
                    pass
            cls._instance = None

    def close_thread_session(self):
        """Release the session of the calling thread (call at worker exit)."""
        self.session.remove()

    # -- helpers -------------------------------------------------------------

    def _commit(self, action: str) -> bool:
        try:
            self.session.commit()
            return True
        except Exception as exc:
            self.session.rollback()
            logger.error("Database error while %s: %s", action, exc)
            return False

    # -- channel favorites ---------------------------------------------------

    def add_channel_favorite(self, channel_id: str, name: str = "") -> bool:
        if self.is_channel_favorite(channel_id):
            return False
        self.session.add(FavoriteChannel(channel_id=str(channel_id), name=name))
        return self._commit("adding channel favorite")

    def remove_channel_favorite(self, channel_id: str) -> bool:
        self.session.query(FavoriteChannel).filter_by(channel_id=str(channel_id)).delete()
        return self._commit("removing channel favorite")

    def is_channel_favorite(self, channel_id: str) -> bool:
        return self.session.query(FavoriteChannel.id).filter_by(channel_id=str(channel_id)).first() is not None

    def get_favorite_channel_ids(self) -> set:
        return {row[0] for row in self.session.query(FavoriteChannel.channel_id).all()}

    def toggle_channel_favorite(self, channel_id: str, name: str = "") -> bool:
        if self.is_channel_favorite(channel_id):
            self.remove_channel_favorite(channel_id)
            return False
        self.add_channel_favorite(channel_id, name)
        return True

    # -- VOD favorites / watched ----------------------------------------------

    def add_vod_favorite(self, stream_id: str, name: str = "") -> bool:
        if self.is_vod_favorite(stream_id):
            return False
        self.session.add(FavoriteVOD(stream_id=str(stream_id), name=name))
        return self._commit("adding VOD favorite")

    def remove_vod_favorite(self, stream_id: str) -> bool:
        self.session.query(FavoriteVOD).filter_by(stream_id=str(stream_id)).delete()
        return self._commit("removing VOD favorite")

    def is_vod_favorite(self, stream_id: str) -> bool:
        return self.session.query(FavoriteVOD.id).filter_by(stream_id=str(stream_id)).first() is not None

    def get_all_vod_favorite_ids(self) -> set:
        return {row[0] for row in self.session.query(FavoriteVOD.stream_id).all()}

    def toggle_vod_favorite(self, stream_id: str, name: str = "") -> bool:
        if self.is_vod_favorite(stream_id):
            self.remove_vod_favorite(stream_id)
            return False
        self.add_vod_favorite(stream_id, name)
        return True

    def mark_vod_watched(self, stream_id: str, name: str = "") -> bool:
        if self.is_vod_watched(stream_id):
            return False
        self.session.add(WatchedVOD(stream_id=str(stream_id), name=name))
        return self._commit("marking VOD watched")

    def mark_vod_unwatched(self, stream_id: str) -> bool:
        self.session.query(WatchedVOD).filter_by(stream_id=str(stream_id)).delete()
        return self._commit("marking VOD unwatched")

    def is_vod_watched(self, stream_id: str) -> bool:
        return self.session.query(WatchedVOD.id).filter_by(stream_id=str(stream_id)).first() is not None

    def get_all_watched_vod_ids(self) -> set:
        return {row[0] for row in self.session.query(WatchedVOD.stream_id).all()}

    # -- series favorites / watched --------------------------------------------

    def add_series_favorite(self, series_id: str, name: str = "") -> bool:
        if self.is_series_favorite(series_id):
            return False
        self.session.add(FavoriteSeries(series_id=series_id, name=name or series_id))
        return self._commit("adding series favorite")

    def remove_series_favorite(self, series_id: str) -> bool:
        self.session.query(FavoriteSeries).filter_by(series_id=series_id).delete()
        return self._commit("removing series favorite")

    def is_series_favorite(self, series_id: str) -> bool:
        return self.session.query(FavoriteSeries.id).filter_by(series_id=series_id).first() is not None

    def toggle_series_favorite(self, series_id: str) -> bool:
        if self.is_series_favorite(series_id):
            self.remove_series_favorite(series_id)
            return False
        self.add_series_favorite(series_id, series_id)
        return True

    def get_series_favorites(self) -> list:
        return [(row.series_id, row.name) for row in self.session.query(FavoriteSeries).all()]

    def get_all_series_favorite_ids(self) -> set:
        return {row[0] for row in self.session.query(FavoriteSeries.series_id).all()}

    def rename_series_favorites(self, renames: Dict[str, str]) -> int:
        """Rename favorite keys (used when series name detection improves)."""
        changed = 0
        existing = self.get_all_series_favorite_ids()
        for old, new in renames.items():
            if old in existing and old != new:
                if new in existing:
                    self.session.query(FavoriteSeries).filter_by(series_id=old).delete()
                else:
                    self.session.query(FavoriteSeries).filter_by(series_id=old).update(
                        {FavoriteSeries.series_id: new, FavoriteSeries.name: new})
                    existing.add(new)
                changed += 1
        if changed:
            self._commit("renaming series favorites")
        return changed

    def mark_series_watched(self, stream_id: str, name: str = "", series_id: str = "",
                            season: str = "", episode: str = "") -> bool:
        existing = self.session.query(WatchedSeries).filter_by(stream_id=str(stream_id)).first()
        if existing:
            existing.watched_at = datetime.now()
        else:
            self.session.add(WatchedSeries(stream_id=str(stream_id), series_id=series_id, name=name,
                                           season=season, episode=episode))
        return self._commit("marking episode watched")

    def mark_series_unwatched(self, stream_id: str) -> bool:
        self.session.query(WatchedSeries).filter_by(stream_id=str(stream_id)).delete()
        return self._commit("marking episode unwatched")

    def get_watched_series_ids(self, stream_ids: Optional[Iterable[str]] = None) -> set:
        query = self.session.query(WatchedSeries.stream_id)
        if stream_ids is not None:
            ids = [str(s) for s in stream_ids]
            if not ids:
                return set()
            query = query.filter(WatchedSeries.stream_id.in_(ids))
        return {row[0] for row in query.all()}

    # -- series state -----------------------------------------------------------

    def get_series_state(self, series_key: str) -> Optional[dict]:
        state = self.session.query(SeriesState).filter_by(series_key=series_key).first()
        if not state:
            return None
        return {"season": state.last_season, "episode_id": state.last_episode_id}

    def get_recent_series_keys(self, limit: int = 60) -> List[str]:
        rows = (self.session.query(SeriesState.series_key)
                .filter(SeriesState.last_episode_id.isnot(None))
                .order_by(SeriesState.updated_at.desc()).limit(limit).all())
        return [row[0] for row in rows]

    def set_series_state(self, series_key: str, season: Optional[str] = None,
                         episode_id: Optional[str] = None) -> bool:
        state = self.session.query(SeriesState).filter_by(series_key=series_key).first()
        if not state:
            state = SeriesState(series_key=series_key)
            self.session.add(state)
        if season is not None:
            state.last_season = str(season)
        if episode_id is not None:
            state.last_episode_id = str(episode_id)
        state.updated_at = datetime.now()
        return self._commit("saving series state")

    # -- playlists ----------------------------------------------------------------

    def _protect(self, value: str) -> str:
        if not value:
            return ""
        return ENC_PREFIX + self.security.encrypt_password(value)

    def _unprotect(self, value: str) -> str:
        if value and value.startswith(ENC_PREFIX):
            return self.security.decrypt_password(value[len(ENC_PREFIX):])
        return value or ""

    def save_playlist(self, name: str, playlist_type: str, url: str = "", server: str = "",
                      username: str = "", password: str = "") -> Optional[int]:
        """Save (or update) a playlist and make it the active one.

        Remote M3U URLs are stored encrypted because they usually contain
        the account token. Local file paths are stored as they are.
        """
        try:
            encrypted_password = self.security.encrypt_password(password) if password else ""
            is_remote = url.lower().startswith(("http://", "https://"))
            existing = None
            if playlist_type == "M3U" and url:
                for candidate in self.session.query(SavedPlaylist).filter_by(type="M3U").all():
                    if self._unprotect(candidate.url) == url:
                        existing = candidate
                        break
            elif playlist_type == "Xtream" and server:
                existing = self.session.query(SavedPlaylist).filter_by(
                    type="Xtream", server=server, username=username).first()

            self.session.query(SavedPlaylist).update({SavedPlaylist.is_active: False})
            stored_url = self._protect(url) if is_remote else url
            if existing:
                existing.name = name
                existing.url = stored_url
                existing.password = encrypted_password
                existing.is_active = True
                existing.last_loaded = datetime.now()
                playlist = existing
            else:
                playlist = SavedPlaylist(name=name, type=playlist_type, url=stored_url, server=server,
                                         username=username, password=encrypted_password,
                                         is_active=True, last_loaded=datetime.now())
                self.session.add(playlist)
            self.session.flush()
            playlist_id = playlist.id
            if not self._commit("saving playlist"):
                return None
            return playlist_id
        except Exception as exc:
            self.session.rollback()
            logger.error("Failed to save playlist: %s", exc)
            return None

    def _playlist_dict(self, playlist: SavedPlaylist) -> dict:
        return {
            "id": playlist.id,
            "name": playlist.name,
            "type": playlist.type,
            "url": self._unprotect(playlist.url),
            "server": playlist.server,
            "username": playlist.username,
            "password": self.security.decrypt_password(playlist.password) if playlist.password else "",
            "last_refreshed": playlist.last_refreshed,
            "last_loaded": playlist.last_loaded,
        }

    def get_last_playlist(self) -> Optional[dict]:
        playlist = self.session.query(SavedPlaylist).filter_by(is_active=True).first()
        return self._playlist_dict(playlist) if playlist else None

    def get_playlist(self, playlist_id: int) -> Optional[dict]:
        playlist = self.session.get(SavedPlaylist, playlist_id)
        return self._playlist_dict(playlist) if playlist else None

    def get_all_playlists(self):
        return self.session.query(SavedPlaylist).all()

    def delete_playlist(self, playlist_id: int):
        self.clear_cached_playlist(playlist_id)
        self.session.query(SavedPlaylist).filter_by(id=playlist_id).delete()
        self._commit("deleting playlist")

    def update_playlist_refresh_time(self, playlist_id: int):
        playlist = self.session.get(SavedPlaylist, playlist_id)
        if playlist:
            playlist.last_refreshed = datetime.now()
            self._commit("updating refresh time")

    # -- playlist cache --------------------------------------------------------------

    def replace_cached_playlist(self, playlist_id: int, channels: list, vod_items: list, series_items: list) -> bool:
        """Atomically replace the cached content of a playlist (bulk insert)."""
        channel_rows = [{"channel_id": c.channel_id, "name": c.name, "url": c.url, "logo": c.logo,
                         "category": c.category, "epg_id": getattr(c, "epg_id", None),
                         "playlist_id": playlist_id} for c in channels]
        vod_rows = [{"stream_id": v.stream_id, "name": v.name, "url": v.url, "cover": v.cover,
                     "plot": v.plot, "rating": v.rating, "year": v.year, "genre": v.genre,
                     "duration": v.duration, "director": v.director, "cast": v.cast,
                     "category": v.category, "playlist_id": playlist_id} for v in vod_items]
        series_rows = [{"stream_id": s.stream_id, "name": s.name, "url": s.url, "cover": s.cover,
                        "plot": s.plot, "rating": s.rating, "year": s.year, "genre": s.genre,
                        "director": s.director, "cast": s.cast, "category": s.category,
                        "season": s.season, "episode": s.episode,
                        "series_name": getattr(s, "series_name", None),
                        "xtream_series_id": getattr(s, "xtream_series_id", None),
                        "playlist_id": playlist_id} for s in series_items]
        try:
            for model in (CachedChannel, CachedVOD, CachedSeries):
                self.session.query(model).filter_by(playlist_id=playlist_id).delete()
            for model, rows in ((CachedChannel, channel_rows), (CachedVOD, vod_rows), (CachedSeries, series_rows)):
                for start in range(0, len(rows), 5000):
                    self.session.execute(insert(model), rows[start:start + 5000])
            playlist = self.session.get(SavedPlaylist, playlist_id)
            if playlist:
                playlist.last_refreshed = datetime.now()
            self.session.commit()
            logger.info("Cached playlist %s: %d channels, %d movies, %d episodes/series",
                        playlist_id, len(channel_rows), len(vod_rows), len(series_rows))
            return True
        except Exception as exc:
            self.session.rollback()
            logger.error("Failed to cache playlist: %s", exc)
            return False

    # Backward compatible single-table cache writers.
    def cache_channels(self, channels: list, playlist_id: int) -> bool:
        return self._replace_one(CachedChannel, playlist_id, channels, "channels")

    def cache_vod_items(self, vod_items: list, playlist_id: int) -> bool:
        return self._replace_one(CachedVOD, playlist_id, vod_items, "vod")

    def cache_series_items(self, series_items: list, playlist_id: int) -> bool:
        return self._replace_one(CachedSeries, playlist_id, series_items, "series")

    def _replace_one(self, model, playlist_id, items, kind) -> bool:
        current = self.load_cached_playlist(playlist_id)
        data = {"channels": current[0], "vod": current[1], "series": current[2]}
        data[kind] = items
        return self.replace_cached_playlist(playlist_id, data["channels"], data["vod"], data["series"])

    def has_cached_playlist(self, playlist_id: int) -> bool:
        for model in (CachedChannel, CachedVOD, CachedSeries):
            if self.session.query(model.id).filter_by(playlist_id=playlist_id).first() is not None:
                return True
        return False

    def load_cached_playlist(self, playlist_id: int):
        """Fast load of cached items as model objects (tuple rows, no ORM)."""
        from models.channel import Channel
        from models.series_item import SeriesItem
        from models.vod_item import VODItem

        conn = self.session.connection()
        channels = [Channel(channel_id=r[0], name=r[1] or "", url=r[2] or "", logo=r[3], category=r[4], epg_id=r[5])
                    for r in conn.execute(select(
                        CachedChannel.channel_id, CachedChannel.name, CachedChannel.url, CachedChannel.logo,
                        CachedChannel.category, CachedChannel.epg_id
                    ).where(CachedChannel.playlist_id == playlist_id).order_by(CachedChannel.id))]
        vod = [VODItem(stream_id=r[0], name=r[1] or "", url=r[2] or "", cover=r[3], plot=r[4], rating=r[5],
                       year=r[6], genre=r[7], duration=r[8], director=r[9], cast=r[10], category=r[11])
               for r in conn.execute(select(
                   CachedVOD.stream_id, CachedVOD.name, CachedVOD.url, CachedVOD.cover, CachedVOD.plot,
                   CachedVOD.rating, CachedVOD.year, CachedVOD.genre, CachedVOD.duration, CachedVOD.director,
                   CachedVOD.cast, CachedVOD.category
               ).where(CachedVOD.playlist_id == playlist_id).order_by(CachedVOD.id))]
        series = []
        for r in conn.execute(select(
                CachedSeries.stream_id, CachedSeries.name, CachedSeries.url, CachedSeries.cover, CachedSeries.plot,
                CachedSeries.rating, CachedSeries.year, CachedSeries.genre, CachedSeries.director,
                CachedSeries.cast, CachedSeries.category, CachedSeries.season, CachedSeries.episode,
                CachedSeries.series_name, CachedSeries.xtream_series_id
        ).where(CachedSeries.playlist_id == playlist_id).order_by(CachedSeries.id)):
            item = SeriesItem(stream_id=r[0], name=r[1] or "", url=r[2] or "", cover=r[3], plot=r[4], rating=r[5],
                              year=r[6], genre=r[7], director=r[8], cast=r[9], category=r[10],
                              season=r[11], episode=r[12])
            item.series_name = r[13]
            item.xtream_series_id = r[14]
            series.append(item)
        self.session.commit()
        return channels, vod, series

    def get_cached_channels(self, playlist_id: int) -> list:
        return self.load_cached_playlist(playlist_id)[0]

    def get_cached_vod_items(self, playlist_id: int) -> list:
        return self.load_cached_playlist(playlist_id)[1]

    def get_cached_series_items(self, playlist_id: int) -> list:
        return self.load_cached_playlist(playlist_id)[2]

    def clear_cached_playlist(self, playlist_id: int):
        for model in (CachedChannel, CachedVOD, CachedSeries):
            self.session.query(model).filter_by(playlist_id=playlist_id).delete()
        self._commit("clearing playlist cache")

    # -- TMDB cache -------------------------------------------------------------------

    def get_tmdb_cache(self, stream_id: str):
        cache = self.session.query(TMDBCache).filter_by(stream_id=str(stream_id)).first()
        return cache.to_dict() if cache else None

    def save_tmdb_cache(self, stream_id: str, tmdb_data: dict) -> bool:
        cache = self.session.query(TMDBCache).filter_by(stream_id=str(stream_id)).first()
        if cache:
            for key, value in tmdb_data.items():
                setattr(cache, key, value)
            cache.cached_at = datetime.now()
        else:
            self.session.add(TMDBCache(stream_id=str(stream_id), **tmdb_data))
        return self._commit("saving TMDB cache")

    def get_all_tmdb_cache(self) -> dict:
        return {c.stream_id: c.to_dict() for c in self.session.query(TMDBCache).all()}

    # -- passwords ------------------------------------------------------------------------

    def _migrate_passwords(self):
        changed = False
        for playlist in self.session.query(SavedPlaylist).all():
            if playlist.password and not self.security.is_encrypted(playlist.password):
                playlist.password = self.security.encrypt_password(playlist.password)
                changed = True
            if playlist.url and playlist.url.lower().startswith(("http://", "https://")):
                playlist.url = self._protect(playlist.url)
                changed = True
        if changed:
            self._commit("encrypting stored credentials")

    # -- watch progress ------------------------------------------------------------------------

    def update_watch_progress(self, stream_id: str, content_type: str, name: str,
                              position_seconds: int, duration_seconds: int) -> bool:
        completed = duration_seconds > 0 and (position_seconds / duration_seconds) > 0.9
        progress = self.session.query(WatchProgress).filter_by(stream_id=str(stream_id)).first()
        if progress:
            progress.position_seconds = int(position_seconds)
            progress.duration_seconds = int(duration_seconds)
            progress.last_watched = datetime.now()
            progress.completed = completed
            progress.name = name or progress.name
        else:
            self.session.add(WatchProgress(stream_id=str(stream_id), content_type=content_type, name=name,
                                           position_seconds=int(position_seconds),
                                           duration_seconds=int(duration_seconds), completed=completed))
        return self._commit("saving watch progress")

    def get_watch_progress(self, stream_id: str):
        return self.session.query(WatchProgress).filter_by(stream_id=str(stream_id)).first()

    def get_progress_map(self, stream_ids: Optional[Iterable[str]] = None) -> Dict[str, tuple]:
        """``stream_id -> (position, duration, completed)`` for many items at once."""
        query = self.session.query(WatchProgress.stream_id, WatchProgress.position_seconds,
                                   WatchProgress.duration_seconds, WatchProgress.completed)
        if stream_ids is not None:
            ids = [str(s) for s in stream_ids]
            if not ids:
                return {}
            result = {}
            for start in range(0, len(ids), 900):
                for row in query.filter(WatchProgress.stream_id.in_(ids[start:start + 900])).all():
                    result[row[0]] = (row[1] or 0, row[2] or 0, bool(row[3]))
            return result
        return {row[0]: (row[1] or 0, row[2] or 0, bool(row[3])) for row in query.all()}

    def mark_watch_progress_completed(self, stream_id: str) -> bool:
        progress = self.get_watch_progress(stream_id)
        if not progress:
            return False
        progress.completed = True
        progress.last_watched = datetime.now()
        return self._commit("completing watch progress")

    def get_continue_watching(self, limit: int = 10, content_type: Optional[str] = None) -> List[WatchProgress]:
        query = self.session.query(WatchProgress).filter_by(completed=False)
        if content_type:
            query = query.filter_by(content_type=content_type)
        items = [p for p in query.order_by(WatchProgress.last_watched.desc()).all()
                 if p.duration_seconds and 0.02 <= p.position_seconds / p.duration_seconds <= 0.95]
        return items[:limit]

    def delete_watch_progress(self, stream_id: str) -> bool:
        self.session.query(WatchProgress).filter_by(stream_id=str(stream_id)).delete()
        return self._commit("deleting watch progress")
