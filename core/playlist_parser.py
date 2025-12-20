import logging
import re
import requests
from typing import List, Tuple
from models.channel import Channel
from models.vod_item import VODItem
from models.series_item import SeriesItem
from core.tmdb_service import TMDBService

logger = logging.getLogger(__name__)


class PlaylistParser:
    """Parser for M3U and Xtream Codes playlists"""
    
    @staticmethod
    def parse_m3u_file(file_path: str) -> Tuple[List[Channel], List[VODItem], List[SeriesItem]]:
        """
        Parse M3U file and extract channels, movies, and series
        
        Args:
            file_path: Path to M3U file
            
        Returns:
            Tuple of (channels, vod_items, series_items)
        """
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
                
                # Extract name (after last comma)
                name_match = re.search(r',(.+)$', info_line)
                name = name_match.group(1).strip() if name_match else "Unknown"
                
                # Extract logo
                logo_match = re.search(r'tvg-logo="([^"]+)"', info_line)
                logo = logo_match.group(1) if logo_match else None
                
                # Extract category/group
                group_match = re.search(r'group-title="([^"]+)"', info_line)
                category = group_match.group(1) if group_match else "Uncategorized"
                
                # Extract ID
                id_match = re.search(r'tvg-id="([^"]+)"', info_line)
                item_id = id_match.group(1) if id_match else str(hash(url))
                
                # Determine type: Live TV, Movie, or Series
                is_series = any([
                    re.search(r'\bS\d{1,2}\b', name),  # S01, S1, etc.
                    re.search(r'\bS\d{1,2}E\d{1,2}\b', name),  # S01E01
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
                    # Extract season and episode
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
                    # Live TV Channel
                    channel = Channel(
                        channel_id=item_id,
                        name=name,
                        url=url,
                        logo=logo,
                        category=category
                    )
                    channels.append(channel)
            
            # Fetch TMDB data for movies (batch)
            # NOTE: Disabled in pilot version - ratings not needed
            # if vod_items:
            #     logger.info(f"Fetching TMDB data for {len(vod_items)} movies...")
            #     PlaylistParser._enrich_vod_with_tmdb(vod_items)
            
            logger.info(f"Parsed {len(channels)} channels, {len(vod_items)} movies, and {len(series_items)} series")
            return channels, vod_items, series_items
        
        except Exception as e:
            logger.error(f"Failed to parse M3U file: {e}")
            raise
    
    @staticmethod
    def parse_xtream_codes(server_url: str, username: str, password: str) -> Tuple[List[Channel], List[VODItem], List[SeriesItem]]:
        """
        Parse Xtream Codes API and extract channels, movies, and series
        
        Args:
            server_url: Xtream server URL
            username: Username
            password: Password
            
        Returns:
            Tuple of (channels, vod_items, series_items)
        """
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
            
            # Get VOD streams (movies)
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
            
            # Get Series streams
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
            
            # Fetch TMDB data for movies (batch)
            # NOTE: Disabled in pilot version - ratings not needed
            # if vod_items:
            #     logger.info(f"Fetching TMDB data for {len(vod_items)} movies...")
            #     PlaylistParser._enrich_vod_with_tmdb(vod_items)
            
            logger.info(f"Parsed {len(channels)} channels, {len(vod_items)} movies, and {len(series_items)} series from Xtream Codes")
            return channels, vod_items, series_items
        
        except Exception as e:
            logger.error(f"Failed to parse Xtream Codes: {e}")
            raise
    
    @staticmethod
    def _enrich_vod_with_tmdb(vod_items: List[VODItem]):
        """
        Enrich VOD items with TMDB metadata (batch operation)
        
        Args:
            vod_items: List of VOD items to enrich
        """
        try:
            tmdb = TMDBService()
            
            # Get cached ratings first (1 DB query)
            ratings = tmdb.batch_fetch_ratings(vod_items)
            
            # Apply ratings to items
            for item in vod_items:
                if item.stream_id in ratings:
                    rating_data = ratings[item.stream_id]
                    item.tmdb_rating = rating_data.get('rating')
                    item.tmdb_vote_count = rating_data.get('vote_count')
            
            logger.info(f"Enriched {len(vod_items)} VOD items with TMDB data")
            
        except Exception as e:
            logger.error(f"Failed to enrich VOD with TMDB: {e}")