import logging
import re
import requests
from typing import List, Tuple
from models.channel import Channel
from models.vod_item import VODItem
from models.series_item import SeriesItem
from core.database import Database

logger = logging.getLogger(__name__)


class PlaylistParser:
    """Parser for M3U and Xtream Codes playlists with database caching"""
    
    @staticmethod
    def parse_m3u_file(file_path: str, force_refresh: bool = False) -> Tuple[List[Channel], List[VODItem], List[SeriesItem]]:
        """
        Parse M3U file and extract channels, movies, and series.
        Uses database cache if available and not forcing refresh.
        
        Args:
            file_path: Path to M3U file
            force_refresh: If True, ignore cache and re-parse
            
        Returns:
            Tuple of (channels, vod_items, series_items)
        """
        db = Database()
        
        # Check if we have cached data (unless forcing refresh)
        if not force_refresh:
            # Get active playlist
            saved_playlist = db.get_last_playlist()
            if saved_playlist and saved_playlist.get('url') == file_path:
                playlist_id = saved_playlist.get('id')
                
                # Check if cache exists
                if db.has_cached_playlist(playlist_id):
                    logger.info(f"Loading playlist from cache (playlist_id: {playlist_id})")
                    
                    # Load from cache
                    cached_channels = db.get_cached_channels(playlist_id)
                    cached_vod = db.get_cached_vod_items(playlist_id)
                    cached_series = db.get_cached_series_items(playlist_id)
                    
                    # Convert cached objects to model objects
                    channels = [
                        Channel(
                            channel_id=ch.channel_id,
                            name=ch.name,
                            url=ch.url,
                            logo=ch.logo,
                            category=ch.category
                        )
                        for ch in cached_channels
                    ]
                    
                    vod_items = [
                        VODItem(
                            stream_id=vod.stream_id,
                            name=vod.name,
                            url=vod.url,
                            cover=vod.cover,
                            plot=vod.plot,
                            rating=vod.rating,
                            year=vod.year,
                            genre=vod.genre,
                            duration=vod.duration,
                            director=vod.director,
                            cast=vod.cast,
                            category=vod.category
                        )
                        for vod in cached_vod
                    ]
                    
                    series_items = [
                        SeriesItem(
                            stream_id=ser.stream_id,
                            name=ser.name,
                            url=ser.url,
                            cover=ser.cover,
                            plot=ser.plot,
                            rating=ser.rating,
                            year=ser.year,
                            genre=ser.genre,
                            director=ser.director,
                            cast=ser.cast,
                            category=ser.category,
                            season=ser.season,
                            episode=ser.episode
                        )
                        for ser in cached_series
                    ]
                    
                    logger.info(f"Loaded from cache: {len(channels)} channels, {len(vod_items)} VOD, {len(series_items)} series")
                    return channels, vod_items, series_items
        
        # If no cache or forcing refresh, parse the file
        logger.info(f"Parsing M3U file: {file_path} (force_refresh={force_refresh})")
        
        channels = []
        vod_items = []
        series_items = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Split by #EXTINF lines
            entries = re.split(r'#EXTINF:', content)[1:]  # Skip header
            
            for entry in entries:
                lines = entry.strip().split('\n')
                if len(lines) < 2:
                    continue
                
                info_line = lines[0]
                url = lines[1].strip()
                
                if not url:
                    continue
                
                # Extract name
                name_match = re.search(r',(.+)$', info_line)
                name = name_match.group(1).strip() if name_match else "Unknown"
                
                # Extract logo
                logo_match = re.search(r'tvg-logo="([^"]+)"', info_line)
                logo = logo_match.group(1) if logo_match else None
                
                # Extract category
                group_match = re.search(r'group-title="([^"]+)"', info_line)
                category = group_match.group(1) if group_match else "Uncategorized"
                
                # Extract ID
                id_match = re.search(r'tvg-id="([^"]+)"', info_line)
                item_id = id_match.group(1) if id_match else str(hash(url))
                
                # Determine type
                is_series = any([
                    re.search(r'\bS\d{1,2}\b', name),
                    re.search(r'\bS\d{1,2}E\d{1,2}\b', name),
                    'series' in category.lower(),
                    'serija' in category.lower(),
                    'sezona' in category.lower()
                ])
                
                is_movie = any([
                    'movie' in category.lower(),
                    'film' in category.lower(),
                    'vod' in category.lower()
                ]) and not is_series
                
                if is_series:
                    season_match = re.search(r'S(\d{1,2})', name)
                    episode_match = re.search(r'E(\d{1,2})', name)
                    
                    series_item = SeriesItem(
                        stream_id=item_id,
                        name=name,
                        url=url,
                        cover=logo,
                        category=category,
                        season=season_match.group(1) if season_match else None,
                        episode=episode_match.group(1) if episode_match else None
                    )
                    series_items.append(series_item)
                    
                elif is_movie:
                    vod_item = VODItem(
                        stream_id=item_id,
                        name=name,
                        url=url,
                        cover=logo,
                        category=category
                    )
                    vod_items.append(vod_item)
                    
                else:
                    channel = Channel(
                        channel_id=item_id,
                        name=name,
                        url=url,
                        logo=logo,
                        category=category
                    )
                    channels.append(channel)
            
            logger.info(f"Parsed {len(channels)} channels, {len(vod_items)} movies, {len(series_items)} series")
            
            # Cache the parsed data
            saved_playlist = db.get_last_playlist()
            if saved_playlist and saved_playlist.get('url') == file_path:
                playlist_id = saved_playlist.get('id')
                logger.info(f"Caching playlist data (playlist_id: {playlist_id})")
                
                db.cache_channels(channels, playlist_id)
                db.cache_vod_items(vod_items, playlist_id)
                db.cache_series_items(series_items, playlist_id)
                db.update_playlist_refresh_time(playlist_id)
                
                logger.info("Playlist data cached successfully")
            
            return channels, vod_items, series_items
        
        except Exception as e:
            logger.error(f"Failed to parse M3U file: {e}")
            raise
    
    @staticmethod
    def parse_xtream_codes(server_url: str, username: str, password: str, force_refresh: bool = False) -> Tuple[List[Channel], List[VODItem], List[SeriesItem]]:
        """
        Parse Xtream Codes API and extract channels, movies, and series.
        Uses database cache if available and not forcing refresh.
        
        Args:
            server_url: Xtream server URL
            username: Username
            password: Password
            force_refresh: If True, ignore cache and re-fetch
            
        Returns:
            Tuple of (channels, vod_items, series_items)
        """
        db = Database()
        
        # Check if we have cached data (unless forcing refresh)
        if not force_refresh:
            saved_playlist = db.get_last_playlist()
            if saved_playlist and saved_playlist.get('server') == server_url:
                playlist_id = saved_playlist.get('id')
                
                if db.has_cached_playlist(playlist_id):
                    logger.info(f"Loading Xtream playlist from cache (playlist_id: {playlist_id})")
                    
                    cached_channels = db.get_cached_channels(playlist_id)
                    cached_vod = db.get_cached_vod_items(playlist_id)
                    cached_series = db.get_cached_series_items(playlist_id)
                    
                    channels = [
                        Channel(
                            channel_id=ch.channel_id,
                            name=ch.name,
                            url=ch.url,
                            logo=ch.logo,
                            category=ch.category
                        )
                        for ch in cached_channels
                    ]
                    
                    vod_items = [
                        VODItem(
                            stream_id=vod.stream_id,
                            name=vod.name,
                            url=vod.url,
                            cover=vod.cover,
                            plot=vod.plot,
                            rating=vod.rating,
                            year=vod.year,
                            genre=vod.genre,
                            duration=vod.duration,
                            director=vod.director,
                            cast=vod.cast,
                            category=vod.category
                        )
                        for vod in cached_vod
                    ]
                    
                    series_items = [
                        SeriesItem(
                            stream_id=ser.stream_id,
                            name=ser.name,
                            url=ser.url,
                            cover=ser.cover,
                            plot=ser.plot,
                            rating=ser.rating,
                            year=ser.year,
                            genre=ser.genre,
                            director=ser.director,
                            cast=ser.cast,
                            category=ser.category,
                            season=ser.season,
                            episode=ser.episode
                        )
                        for ser in cached_series
                    ]
                    
                    logger.info(f"Loaded from cache: {len(channels)} channels, {len(vod_items)} VOD, {len(series_items)} series")
                    return channels, vod_items, series_items
        
        # If no cache or forcing refresh, fetch from API
        logger.info(f"Fetching Xtream Codes from API: {server_url} (force_refresh={force_refresh})")
        
        channels = []
        vod_items = []
        series_items = []
        
        try:
            server_url = server_url.rstrip('/')
            
            # Get live streams
            live_url = f"{server_url}/player_api.php?username={username}&password={password}&action=get_live_streams"
            response = requests.get(live_url, timeout=10)
            response.raise_for_status()
            live_data = response.json()
            
            for stream in live_data:
                channel = Channel(
                    channel_id=str(stream.get('stream_id', '')),
                    name=stream.get('name', 'Unknown'),
                    url=f"{server_url}/live/{username}/{password}/{stream.get('stream_id')}.m3u8",
                    logo=stream.get('stream_icon', ''),
                    category=stream.get('category_name', 'Uncategorized')
                )
                channels.append(channel)
            
            # Get VOD streams
            vod_url = f"{server_url}/player_api.php?username={username}&password={password}&action=get_vod_streams"
            response = requests.get(vod_url, timeout=10)
            response.raise_for_status()
            vod_data = response.json()
            
            for stream in vod_data:
                stream_id = str(stream.get('stream_id', ''))
                container_extension = stream.get('container_extension', 'mp4')
                
                vod_item = VODItem(
                    stream_id=stream_id,
                    name=stream.get('name', 'Unknown'),
                    url=f"{server_url}/movie/{username}/{password}/{stream_id}.{container_extension}",
                    cover=stream.get('stream_icon', ''),
                    plot=stream.get('plot', ''),
                    rating=stream.get('rating', ''),
                    year=stream.get('releasedate', ''),
                    genre=stream.get('genre', ''),
                    duration=stream.get('duration', ''),
                    director=stream.get('director', ''),
                    cast=stream.get('cast', ''),
                    category=stream.get('category_name', 'Uncategorized')
                )
                vod_items.append(vod_item)
            
            # Get Series
            series_url = f"{server_url}/player_api.php?username={username}&password={password}&action=get_series"
            response = requests.get(series_url, timeout=10)
            response.raise_for_status()
            series_data = response.json()
            
            for series in series_data:
                series_id = str(series.get('series_id', ''))
                
                series_item = SeriesItem(
                    stream_id=series_id,
                    name=series.get('name', 'Unknown'),
                    url=f"{server_url}/series/{username}/{password}/{series_id}.m3u8",
                    cover=series.get('cover', ''),
                    plot=series.get('plot', ''),
                    rating=series.get('rating', ''),
                    year=series.get('releaseDate', ''),
                    genre=series.get('genre', ''),
                    director=series.get('director', ''),
                    cast=series.get('cast', ''),
                    category=series.get('category_name', 'Uncategorized')
                )
                series_items.append(series_item)
            
            logger.info(f"Parsed {len(channels)} channels, {len(vod_items)} movies, {len(series_items)} series from Xtream")
            
            # Cache the data
            saved_playlist = db.get_last_playlist()
            if saved_playlist and saved_playlist.get('server') == server_url:
                playlist_id = saved_playlist.get('id')
                logger.info(f"Caching Xtream playlist (playlist_id: {playlist_id})")
                
                db.cache_channels(channels, playlist_id)
                db.cache_vod_items(vod_items, playlist_id)
                db.cache_series_items(series_items, playlist_id)
                db.update_playlist_refresh_time(playlist_id)
                
                logger.info("Xtream playlist cached successfully")
            
            return channels, vod_items, series_items
        
        except Exception as e:
            logger.error(f"Failed to parse Xtream Codes: {e}")
            raise