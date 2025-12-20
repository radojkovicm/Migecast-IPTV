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


class TMDBCache(Base):
    """TMDB metadata cache table"""
    __tablename__ = 'tmdb_cache'
    
    id = Column(Integer, primary_key=True)
    stream_id = Column(String, unique=True, nullable=False)  # VOD stream_id
    title = Column(String)
    tmdb_id = Column(Integer)
    rating = Column(Float)  # TMDB rating (0-10)
    vote_count = Column(Integer)
    overview = Column(Text)  # Description
    genres = Column(String)  # Comma-separated genres
    release_date = Column(String)
    runtime = Column(Integer)  # Duration in minutes
    director = Column(String)
    cast = Column(Text)  # Comma-separated cast (top 5)
    poster_path = Column(String)  # TMDB poster URL
    backdrop_path = Column(String)  # TMDB backdrop URL
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
        """
        Batch fetch all favorite VOD IDs.
        This is MUCH faster than calling is_vod_favorite() in a loop.
        
        Performance: 1 DB query instead of N queries for N items.
        """
        try:
            favorites = self.session.query(FavoriteVOD.stream_id).all()
            return {fav[0] for fav in favorites}
        except Exception as e:
            logger.error(f"Failed to fetch favorite VOD IDs: {e}")
            return set()
    
    def toggle_vod_favorite(self, stream_id: str, name: str = "") -> bool:
        """
        Toggle VOD favorite status.
        Returns True if added, False if removed.
        """
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
    
    def get_all_series_favorite_ids(self) -> set:
        """Batch fetch all favorite series IDs"""
        try:
            favorites = self.session.query(FavoriteSeries.series_id).all()
            return {fav[0] for fav in favorites}
        except Exception as e:
            logger.error(f"Failed to fetch favorite series IDs: {e}")
            return set()
    
    # ============================================================
    # WATCHED VOD (OPTIMIZED WITH BATCH)
    # ============================================================
    
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
            
            self.session.commit()
            logger.info(f"Saved playlist: {name}")
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to save playlist: {e}")
    
    def get_last_playlist(self):
        """Get last active playlist"""
        playlist = self.session.query(SavedPlaylist).filter_by(is_active=True).first()
        if playlist:
            return {
                'name': playlist.name,
                'type': playlist.type,
                'url': playlist.url,
                'server': playlist.server,
                'username': playlist.username,
                'password': playlist.password
            }
        return None
    
    def get_all_playlists(self):
        """Get all saved playlists"""
        return self.session.query(SavedPlaylist).all()
    
    def delete_playlist(self, playlist_id: int):
        """Delete playlist"""
        try:
            playlist = self.session.query(SavedPlaylist).filter_by(id=playlist_id).first()
            if playlist:
                self.session.delete(playlist)
                self.session.commit()
                logger.info(f"Deleted playlist: {playlist_id}")
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to delete playlist: {e}")
    
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
            # Check if exists
            cache = self.session.query(TMDBCache).filter_by(stream_id=stream_id).first()
            
            if cache:
                # Update existing
                for key, value in tmdb_data.items():
                    setattr(cache, key, value)
                cache.cached_at = datetime.now()
            else:
                # Create new
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
        """Batch fetch all TMDB ratings for quick display"""
        try:
            ratings = self.session.query(TMDBCache.stream_id, TMDBCache.rating, TMDBCache.vote_count).all()
            return {r[0]: {'rating': r[1], 'vote_count': r[2]} for r in ratings}
        except Exception as e:
            logger.error(f"Failed to fetch TMDB ratings: {e}")
            return {}
    # ============================================================
    # TMDB CACHE
    # ============================================================
    
    # ... (postojeće metode) ...

    def get_all_tmdb_cache(self) -> dict:
        """Batch fetch all TMDB cached data for quick lookup"""
        try:
            all_cache = self.session.query(TMDBCache).all()
            return {cache.stream_id: cache.to_dict() for cache in all_cache}
        except Exception as e:
            logger.error(f"Failed to fetch all TMDB cache: {e}")
            return {}