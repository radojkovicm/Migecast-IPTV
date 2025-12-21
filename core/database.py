import logging
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

Base = declarative_base()


class FavoriteChannel(Base):
    """Favorite channels table"""
    __tablename__ = 'favorite_channels'
    
    id = Column(Integer, primary_key=True)
    channel_id = Column(String, unique=True, nullable=False)
    name = Column(String)
    added_at = Column(DateTime, default=datetime.now)


class FavoriteVOD(Base):
    """Favorite VOD items table"""
    __tablename__ = 'favorite_vod'
    
    id = Column(Integer, primary_key=True)
    stream_id = Column(String, unique=True, nullable=False)
    name = Column(String)
    added_at = Column(DateTime, default=datetime.now)


class FavoriteSeries(Base):
    """Favorite Series table"""
    __tablename__ = 'favorite_series'
    
    id = Column(Integer, primary_key=True)
    series_id = Column(String, unique=True, nullable=False)
    name = Column(String)
    added_at = Column(DateTime, default=datetime.now)

class WatchedSeries(Base):
    """Watched Series episodes table"""
    __tablename__ = 'watched_series'
    
    id = Column(Integer, primary_key=True)
    stream_id = Column(String, nullable=False)
    series_id = Column(String)  # ID serije (za grupisanje epizoda)
    name = Column(String)
    season = Column(String)
    episode = Column(String)
    watched_at = Column(DateTime, default=datetime.now)

class WatchedVOD(Base):
    """Watched VOD items table"""
    __tablename__ = 'watched_vod'
    
    id = Column(Integer, primary_key=True)
    stream_id = Column(String, unique=True, nullable=False)
    name = Column(String)
    watched_at = Column(DateTime, default=datetime.now)


class SavedPlaylist(Base):
    """Saved playlists table"""
    __tablename__ = 'saved_playlists'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    type = Column(String)  # 'M3U' or 'Xtream'
    url = Column(String)  # For M3U URL or Xtream server
    server = Column(String)  # For Xtream server
    username = Column(String)  # For Xtream
    password = Column(String)  # For Xtream
    is_active = Column(Boolean, default=False)
    added_at = Column(DateTime, default=datetime.now)
    last_loaded = Column(DateTime)
    last_refreshed = Column(DateTime)  # NOVO - kada je zadnji put osveženo


# ============================================================
# NOVE TABELE ZA KESIRANJE PLAYLISTE
# ============================================================

class CachedChannel(Base):
    """Cached channels from playlist"""
    __tablename__ = 'cached_channels'
    
    id = Column(Integer, primary_key=True)
    channel_id = Column(String, nullable=False)
    name = Column(String)
    url = Column(String)
    logo = Column(String)
    category = Column(String)
    playlist_id = Column(Integer, nullable=False)  # Link to SavedPlaylist


class CachedVOD(Base):
    """Cached VOD items from playlist"""
    __tablename__ = 'cached_vod'
    
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


class CachedSeries(Base):
    """Cached Series from playlist"""
    __tablename__ = 'cached_series'
    
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
    playlist_id = Column(Integer, nullable=False)


class TMDBCache(Base):
    """TMDB metadata cache table"""
    __tablename__ = 'tmdb_cache'
    
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
        """Convert to dictionary"""
        return {
            'tmdb_id': self.tmdb_id,
            'rating': self.rating,
            'vote_count': self.vote_count,
            'overview': self.overview,
            'genres': self.genres,
            'release_date': self.release_date,
            'runtime': self.runtime,
            'director': self.director,
            'cast': self.cast,
            'poster_path': self.poster_path,
            'backdrop_path': self.backdrop_path
        }


class Database:
    """Database manager with singleton pattern"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        
        # Ensure data directory exists
        Path("data").mkdir(exist_ok=True)
        
        self.db_path = "data/migecast.db"
        self.engine = create_engine(f'sqlite:///{self.db_path}')
        Base.metadata.create_all(self.engine)
        
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        logger.info(f"Database initialized (Singleton): {self.db_path}")
    
    # ============================================================
    # CHANNEL FAVORITES
    # ============================================================
    
    def add_channel_favorite(self, channel_id: str, name: str = ""):
        """Add channel to favorites"""
        try:
            if not self.is_channel_favorite(channel_id):
                favorite = FavoriteChannel(channel_id=channel_id, name=name)
                self.session.add(favorite)
                self.session.commit()
                logger.info(f"Added channel to favorites: {name}")
                return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to add channel favorite: {e}")
        return False
    
    def remove_channel_favorite(self, channel_id: str):
        """Remove channel from favorites"""
        try:
            favorite = self.session.query(FavoriteChannel).filter_by(channel_id=channel_id).first()
            if favorite:
                self.session.delete(favorite)
                self.session.commit()
                logger.info(f"Removed channel from favorites: {channel_id}")
                return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to remove channel favorite: {e}")
        return False
    
    def is_channel_favorite(self, channel_id: str) -> bool:
        """Check if channel is favorite"""
        return self.session.query(FavoriteChannel).filter_by(channel_id=channel_id).first() is not None
    
    def get_favorite_channel_ids(self) -> set:
        """Get all favorite channel IDs (batch query)"""
        favorites = self.session.query(FavoriteChannel.channel_id).all()
        return {fav[0] for fav in favorites}
    
    # ============================================================
    # VOD FAVORITES (OPTIMIZED WITH BATCH)
    # ============================================================
    
    def add_vod_favorite(self, stream_id: str, name: str = ""):
        """Add VOD to favorites"""
        try:
            if not self.is_vod_favorite(stream_id):
                favorite = FavoriteVOD(stream_id=stream_id, name=name)
                self.session.add(favorite)
                self.session.commit()
                logger.info(f"Added VOD to favorites: {name}")
                return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to add VOD favorite: {e}")
        return False
    
    def remove_vod_favorite(self, stream_id: str):
        """Remove VOD from favorites"""
        try:
            favorite = self.session.query(FavoriteVOD).filter_by(stream_id=stream_id).first()
            if favorite:
                self.session.delete(favorite)
                self.session.commit()
                logger.info(f"Removed VOD from favorites: {stream_id}")
                return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to remove VOD favorite: {e}")
        return False
    
    def is_vod_favorite(self, stream_id: str) -> bool:
        """Check if VOD is favorite"""
        return self.session.query(FavoriteVOD).filter_by(stream_id=stream_id).first() is not None
    
    def get_all_vod_favorite_ids(self) -> set:
        """Batch fetch all favorite VOD IDs"""
        try:
            favorites = self.session.query(FavoriteVOD.stream_id).all()
            return {fav[0] for fav in favorites}
        except Exception as e:
            logger.error(f"Failed to fetch favorite VOD IDs: {e}")
            return set()
    
    def toggle_vod_favorite(self, stream_id: str, name: str = "") -> bool:
        """Toggle VOD favorite status"""
        if self.is_vod_favorite(stream_id):
            self.remove_vod_favorite(stream_id)
            return False
        else:
            self.add_vod_favorite(stream_id, name)
            return True
    
    # ============================================================
    # SERIES FAVORITES (OPTIMIZED WITH BATCH)
    # ============================================================
    
    def add_series_favorite(self, series_id: str, name: str = ""):
        """Add series to favorites"""
        try:
            if not self.is_series_favorite(series_id):
                favorite = FavoriteSeries(series_id=series_id, name=name)
                self.session.add(favorite)
                self.session.commit()
                logger.info(f"Added series to favorites: {name}")
                return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to add series favorite: {e}")
        return False
    
    def remove_series_favorite(self, series_id: str):
        """Remove series from favorites"""
        try:
            favorite = self.session.query(FavoriteSeries).filter_by(series_id=series_id).first()
            if favorite:
                self.session.delete(favorite)
                self.session.commit()
                logger.info(f"Removed series from favorites: {series_id}")
                return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to remove series favorite: {e}")
        return False
    
    def is_series_favorite(self, series_id: str) -> bool:
        """Check if series is favorite"""
        return self.session.query(FavoriteSeries).filter_by(series_id=series_id).first() is not None
    
    def get_series_favorites(self) -> list:
        """Get all favorite series with their data"""
        try:
            favorites = self.session.query(FavoriteSeries).all()
            return [(fav.series_id, fav.name) for fav in favorites]
        except Exception as e:
            logger.error(f"Failed to fetch favorite series: {e}")
            return []
    
    def get_all_series_favorite_ids(self) -> set:
        """Batch fetch all favorite series IDs"""
        try:
            favorites = self.session.query(FavoriteSeries.series_id).all()
            return {fav[0] for fav in favorites}
        except Exception as e:
            logger.error(f"Failed to fetch favorite series IDs: {e}")
            return set()
        
    def mark_series_watched(self, stream_id: str, name: str = "", series_id: str = "", season: str = "", episode: str = ""):
        """Mark series episode as watched"""
        try:
            # Proveri da li već postoji
            existing = self.session.query(WatchedSeries).filter_by(stream_id=stream_id).first()
            
            if existing:
                # Ažuriraj timestamp
                existing.watched_at = datetime.now()
            else:
                # Dodaj novi
                watched = WatchedSeries(
                    stream_id=stream_id,
                    series_id=series_id,
                    name=name,
                    season=season,
                    episode=episode
                )
                self.session.add(watched)
            
            self.session.commit()
            logger.info(f"Marked series as watched: {name}")
            return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to mark series as watched: {e}")
            return False

    
    def mark_vod_watched(self, stream_id: str, name: str = ""):
        """Mark VOD as watched"""
        try:
            if not self.is_vod_watched(stream_id):
                watched = WatchedVOD(stream_id=stream_id, name=name)
                self.session.add(watched)
                self.session.commit()
                logger.info(f"Marked VOD as watched: {name}")
                return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to mark VOD as watched: {e}")
        return False
    
    def mark_vod_unwatched(self, stream_id: str):
        """Mark VOD as unwatched"""
        try:
            watched = self.session.query(WatchedVOD).filter_by(stream_id=stream_id).first()
            if watched:
                self.session.delete(watched)
                self.session.commit()
                logger.info(f"Marked VOD as unwatched: {stream_id}")
                return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to mark VOD as unwatched: {e}")
        return False
    
    def is_vod_watched(self, stream_id: str) -> bool:
        """Check if VOD is watched"""
        return self.session.query(WatchedVOD).filter_by(stream_id=stream_id).first() is not None
    
    def get_all_watched_vod_ids(self) -> set:
        """Batch fetch all watched VOD IDs"""
        try:
            watched = self.session.query(WatchedVOD.stream_id).all()
            return {w[0] for w in watched}
        except Exception as e:
            logger.error(f"Failed to fetch watched VOD IDs: {e}")
            return set()
    
    # ============================================================
    # SAVED PLAYLISTS
    # ============================================================
    
    def save_playlist(self, name: str, playlist_type: str, url: str = "", 
                     server: str = "", username: str = "", password: str = ""):
        """Save playlist to database"""
        try:
            # Deactivate all other playlists
            self.session.query(SavedPlaylist).update({SavedPlaylist.is_active: False})
            
            # Check if playlist already exists
            existing = None
            if playlist_type == 'M3U' and url:
                existing = self.session.query(SavedPlaylist).filter_by(type='M3U', url=url).first()
            elif playlist_type == 'Xtream' and server:
                existing = self.session.query(SavedPlaylist).filter_by(
                    type='Xtream', server=server, username=username
                ).first()
            
            if existing:
                # Update existing
                existing.name = name
                existing.is_active = True
                existing.last_loaded = datetime.now()
                playlist_id = existing.id
            else:
                # Create new
                playlist = SavedPlaylist(
                    name=name,
                    type=playlist_type,
                    url=url,
                    server=server,
                    username=username,
                    password=password,
                    is_active=True,
                    last_loaded=datetime.now()
                )
                self.session.add(playlist)
                self.session.flush()  # Get ID
                playlist_id = playlist.id
            
            self.session.commit()
            logger.info(f"Saved playlist: {name} (ID: {playlist_id})")
            return playlist_id
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to save playlist: {e}")
            return None
    
    def get_last_playlist(self):
        """Get last active playlist"""
        playlist = self.session.query(SavedPlaylist).filter_by(is_active=True).first()
        if playlist:
            return {
                'id': playlist.id,
                'name': playlist.name,
                'type': playlist.type,
                'url': playlist.url,
                'server': playlist.server,
                'username': playlist.username,
                'password': playlist.password,
                'last_refreshed': playlist.last_refreshed
            }
        return None
    
    def get_all_playlists(self):
        """Get all saved playlists"""
        return self.session.query(SavedPlaylist).all()
    
    def delete_playlist(self, playlist_id: int):
        """Delete playlist and its cached data"""
        try:
            # Delete cached data first
            self.clear_cached_playlist(playlist_id)
            
            # Delete playlist
            playlist = self.session.query(SavedPlaylist).filter_by(id=playlist_id).first()
            if playlist:
                self.session.delete(playlist)
                self.session.commit()
                logger.info(f"Deleted playlist: {playlist_id}")
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to delete playlist: {e}")
    
    def update_playlist_refresh_time(self, playlist_id: int):
        """Update last_refreshed timestamp"""
        try:
            playlist = self.session.query(SavedPlaylist).filter_by(id=playlist_id).first()
            if playlist:
                playlist.last_refreshed = datetime.now()
                self.session.commit()
                logger.info(f"Updated refresh time for playlist: {playlist_id}")
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to update refresh time: {e}")
    
    # ============================================================
    # PLAYLIST CACHE (NOVO!)
    # ============================================================
    
    def cache_channels(self, channels: list, playlist_id: int):
        """Cache channels to database"""
        try:
            # Clear existing cached channels for this playlist
            self.session.query(CachedChannel).filter_by(playlist_id=playlist_id).delete()
            
            # Add new channels
            for ch in channels:
                cached = CachedChannel(
                    channel_id=ch.channel_id,
                    name=ch.name,
                    url=ch.url,
                    logo=ch.logo,
                    category=ch.category,
                    playlist_id=playlist_id
                )
                self.session.add(cached)
            
            self.session.commit()
            logger.info(f"Cached {len(channels)} channels for playlist {playlist_id}")
            return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to cache channels: {e}")
            return False
    
    def cache_vod_items(self, vod_items: list, playlist_id: int):
        """Cache VOD items to database"""
        try:
            # Clear existing
            self.session.query(CachedVOD).filter_by(playlist_id=playlist_id).delete()
            
            # Add new
            for item in vod_items:
                cached = CachedVOD(
                    stream_id=item.stream_id,
                    name=item.name,
                    url=item.url,
                    cover=item.cover,
                    plot=getattr(item, 'plot', ''),
                    rating=getattr(item, 'rating', ''),
                    year=getattr(item, 'year', ''),
                    genre=getattr(item, 'genre', ''),
                    duration=getattr(item, 'duration', ''),
                    director=getattr(item, 'director', ''),
                    cast=getattr(item, 'cast', ''),
                    category=item.category,
                    playlist_id=playlist_id
                )
                self.session.add(cached)
            
            self.session.commit()
            logger.info(f"Cached {len(vod_items)} VOD items for playlist {playlist_id}")
            return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to cache VOD items: {e}")
            return False
    
    def cache_series_items(self, series_items: list, playlist_id: int):
        """Cache Series items to database"""
        try:
            # Clear existing
            self.session.query(CachedSeries).filter_by(playlist_id=playlist_id).delete()
            
            # Add new
            for item in series_items:
                cached = CachedSeries(
                    stream_id=item.stream_id,
                    name=item.name,
                    url=item.url,
                    cover=item.cover,
                    plot=getattr(item, 'plot', ''),
                    rating=getattr(item, 'rating', ''),
                    year=getattr(item, 'year', ''),
                    genre=getattr(item, 'genre', ''),
                    director=getattr(item, 'director', ''),
                    cast=getattr(item, 'cast', ''),
                    category=item.category,
                    season=getattr(item, 'season', ''),
                    episode=getattr(item, 'episode', ''),
                    playlist_id=playlist_id
                )
                self.session.add(cached)
            
            self.session.commit()
            logger.info(f"Cached {len(series_items)} series items for playlist {playlist_id}")
            return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to cache series items: {e}")
            return False
    
    def get_cached_channels(self, playlist_id: int) -> list:
        """Get cached channels from database"""
        try:
            cached = self.session.query(CachedChannel).filter_by(playlist_id=playlist_id).all()
            logger.info(f"Loaded {len(cached)} cached channels")
            return cached
        except Exception as e:
            logger.error(f"Failed to get cached channels: {e}")
            return []
    
    def get_cached_vod_items(self, playlist_id: int) -> list:
        """Get cached VOD items from database"""
        try:
            cached = self.session.query(CachedVOD).filter_by(playlist_id=playlist_id).all()
            logger.info(f"Loaded {len(cached)} cached VOD items")
            return cached
        except Exception as e:
            logger.error(f"Failed to get cached VOD items: {e}")
            return []
    
    def get_cached_series_items(self, playlist_id: int) -> list:
        """Get cached series items from database"""
        try:
            cached = self.session.query(CachedSeries).filter_by(playlist_id=playlist_id).all()
            logger.info(f"Loaded {len(cached)} cached series items")
            return cached
        except Exception as e:
            logger.error(f"Failed to get cached series items: {e}")
            return []
    
    def has_cached_playlist(self, playlist_id: int) -> bool:
        """Check if playlist has cached data"""
        try:
            channel_count = self.session.query(CachedChannel).filter_by(playlist_id=playlist_id).count()
            return channel_count > 0
        except Exception as e:
            logger.error(f"Failed to check cached playlist: {e}")
            return False
    
    def clear_cached_playlist(self, playlist_id: int):
        """Clear all cached data for playlist"""
        try:
            self.session.query(CachedChannel).filter_by(playlist_id=playlist_id).delete()
            self.session.query(CachedVOD).filter_by(playlist_id=playlist_id).delete()
            self.session.query(CachedSeries).filter_by(playlist_id=playlist_id).delete()
            self.session.commit()
            logger.info(f"Cleared cached data for playlist {playlist_id}")
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to clear cached playlist: {e}")
    
    # ============================================================
    # TMDB CACHE
    # ============================================================
    
    def get_tmdb_cache(self, stream_id: str):
        """Get cached TMDB data for VOD"""
        try:
            cache = self.session.query(TMDBCache).filter_by(stream_id=stream_id).first()
            return cache.to_dict() if cache else None
        except Exception as e:
            logger.error(f"Failed to get TMDB cache: {e}")
            return None
    
    def save_tmdb_cache(self, stream_id: str, tmdb_data: dict):
        """Save TMDB data to cache"""
        try:
            cache = self.session.query(TMDBCache).filter_by(stream_id=stream_id).first()
            
            if cache:
                for key, value in tmdb_data.items():
                    setattr(cache, key, value)
                cache.cached_at = datetime.now()
            else:
                cache = TMDBCache(stream_id=stream_id, **tmdb_data)
                self.session.add(cache)
            
            self.session.commit()
            logger.info(f"Saved TMDB cache for stream_id: {stream_id}")
            return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to save TMDB cache: {e}")
            return False
    
    def get_all_tmdb_ratings(self) -> dict:
        """Batch fetch all TMDB ratings"""
        try:
            ratings = self.session.query(TMDBCache.stream_id, TMDBCache.rating, TMDBCache.vote_count).all()
            return {r[0]: {'rating': r[1], 'vote_count': r[2]} for r in ratings}
        except Exception as e:
            logger.error(f"Failed to fetch TMDB ratings: {e}")
            return {}
    
    def get_all_tmdb_cache(self) -> dict:
        """Batch fetch all TMDB cached data"""
        try:
            all_cache = self.session.query(TMDBCache).all()
            return {cache.stream_id: cache.to_dict() for cache in all_cache}
        except Exception as e:
            logger.error(f"Failed to fetch all TMDB cache: {e}")
            return {}