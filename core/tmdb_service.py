import logging
import requests
from typing import Optional, Dict, List
from core.database import Database
from models.vod_item import VODItem

logger = logging.getLogger(__name__)

# TMDB API Key (besplatno, 1000 zahteva/dan)
# Registruj se na https://www.themoviedb.org/settings/api
TMDB_API_KEY = "b08657037afffede316abcf164cee9f1"  # Replace with your API key
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"


class TMDBService:
    """TMDB API service with database caching"""
    
    def __init__(self):
        self.db = Database()
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'User-Agent': 'MigeCast/1.0'
        })
    
    def search_movie(self, title: str, year: Optional[str] = None) -> Optional[Dict]:
        """
        Search for movie on TMDB
        Returns: TMDB movie data or None
        """
        try:
            # Clean title (remove quality tags like "1080p", "BluRay", etc.)
            clean_title = self._clean_title(title)
            
            params = {
                'api_key': TMDB_API_KEY,
                'query': clean_title,
                'language': 'sr'  # Serbian language
            }
            
            if year:
                params['year'] = year
            
            response = self.session.get(f"{TMDB_BASE_URL}/search/movie", params=params, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            results = data.get('results', [])
            
            if results:
                # Get first result (best match)
                movie = results[0]
                movie_id = movie['id']
                
                # Get detailed info (includes cast, crew, etc.)
                return self._get_movie_details(movie_id)
            
            logger.debug(f"No TMDB results for: {clean_title}")
            return None
            
        except Exception as e:
            logger.error(f"TMDB search error for '{title}': {e}")
            return None
    
    def _get_movie_details(self, movie_id: int) -> Optional[Dict]:
        """Get detailed movie info including cast and crew"""
        try:
            params = {
                'api_key': TMDB_API_KEY,
                'language': 'sr',
                'append_to_response': 'credits'
            }
            
            response = self.session.get(f"{TMDB_BASE_URL}/movie/{movie_id}", params=params, timeout=5)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"TMDB details error for movie_id {movie_id}: {e}")
            return None
    
    def _clean_title(self, title: str) -> str:
        """Clean movie title from quality tags and extra info"""
        import re
        
        # Remove common quality tags
        tags = ['1080p', '720p', '480p', 'BluRay', 'WEB-DL', 'HDRip', 'BRRip', 
                'DVDRip', 'HDTV', 'WEBRip', 'x264', 'x265', 'HEVC']
        
        clean = title
        for tag in tags:
            clean = clean.replace(tag, '')
        
        # Remove year in parentheses (we'll use it separately)
        clean = re.sub(r'\(\d{4}\)', '', clean)
        
        # Remove extra spaces
        clean = ' '.join(clean.split())
        
        return clean.strip()
    
    def get_or_fetch_metadata(self, stream_id: str, title: str, year: Optional[str] = None, 
                              cached_data_map: Optional[Dict[str, Dict]] = None) -> Optional[Dict]:
        """
        Get metadata from cache or fetch from TMDB
        
        Args:
            stream_id: Unique stream ID
            title: Movie title
            year: Release year (optional)
            cached_data_map: Optional map of all cached TMDB data (stream_id -> data)
            
        Returns:
            Dictionary with TMDB data or None
        """
        # Check provided cached_data_map first (if available)
        if cached_data_map and stream_id in cached_data_map:
            logger.debug(f"TMDB cache hit (from map) for: {title}")
            return cached_data_map[stream_id]
        
        # If not in map, check individual cache (fallback)
        cached = self.db.get_tmdb_cache(stream_id)
        if cached:
            logger.debug(f"TMDB cache hit (from DB) for: {title}")
            return cached
        
        # Fetch from TMDB
        logger.info(f"Fetching TMDB data for: {title}")
        movie_data = self.search_movie(title, year)
        
        if movie_data:
            # Parse and save to cache
            parsed = self._parse_movie_data(movie_data)
            self._save_tmdb_cache(stream_id, title, parsed)
            return parsed
        
        return None
    
    def _parse_movie_data(self, movie_data: Dict) -> Dict:
        """Parse TMDB movie data into simplified format"""
        try:
            # Extract cast (first 5 actors)
            cast_list = []
            credits = movie_data.get('credits', {})
            cast = credits.get('cast', [])
            for actor in cast[:5]:
                cast_list.append(actor.get('name', ''))
            
            # Extract director
            director = None
            crew = credits.get('crew', [])
            for person in crew:
                if person.get('job') == 'Director':
                    director = person.get('name')
                    break
            
            # Extract genres
            genres = []
            for genre in movie_data.get('genres', []):
                genres.append(genre.get('name', ''))
            
            return {
                'tmdb_id': movie_data.get('id'),
                'rating': movie_data.get('vote_average'),
                'vote_count': movie_data.get('vote_count'),
                'overview': movie_data.get('overview'),
                'genres': ', '.join(genres) if genres else None,
                'cast': ', '.join(cast_list) if cast_list else None,
                'director': director,
                'poster': f"{TMDB_IMAGE_BASE}{movie_data.get('poster_path')}" if movie_data.get('poster_path') else None
            }
        except Exception as e:
            logger.error(f"Error parsing TMDB data: {e}")
            return {}
    
    def _save_tmdb_cache(self, stream_id: str, title: str, parsed: Dict):
        """Save TMDB data to database cache"""
        try:
            cache_data = {
                'title': title,
                'tmdb_id': parsed.get('tmdb_id'),
                'rating': parsed.get('rating'),
                'vote_count': parsed.get('vote_count'),
                'overview': parsed.get('overview'),
                'genres': parsed.get('genres'),
                'director': parsed.get('director'),
                'cast': parsed.get('cast'),
                'poster_path': parsed.get('poster'),
                'backdrop_path': None,
                'release_date': None,
                'runtime': None
            }
            self.db.save_tmdb_cache(stream_id, cache_data)
            logger.debug(f"Saved TMDB cache for: {title}")
        except Exception as e:
            logger.error(f"Failed to save TMDB cache: {e}")
    
    def batch_fetch_ratings(self, vod_items: List[VODItem]) -> Dict[str, Dict]:
        """
        Batch fetch ratings for multiple VOD items (optimized)
        
        Args:
            vod_items: List of VOD items
            
        Returns:
            Dictionary mapping stream_id to rating data
        """
        ratings = {}
        
        # Get all cached TMDB data first (1 DB query)
        all_cached_data = self.db.get_all_tmdb_cache()
        
        for item in vod_items:
            # Check cache
            if item.stream_id in all_cached_data:
                cached_item = all_cached_data[item.stream_id]
                ratings[item.stream_id] = {
                    'rating': cached_item.get('rating'),
                    'vote_count': cached_item.get('vote_count')
                }
                # Update VODItem with full cached data
                item.tmdb_rating = cached_item.get('rating')
                item.tmdb_vote_count = cached_item.get('vote_count')
                item.tmdb_overview = cached_item.get('overview')
                item.tmdb_genres = cached_item.get('genres')
                item.tmdb_cast = cached_item.get('cast')
                item.tmdb_director = cached_item.get('director')
                item.tmdb_poster = cached_item.get('poster_path')
                logger.debug(f"TMDB cache hit for: {item.name}")
            else:
                # Fetch from TMDB (only if not in cache)
                # Pass all_cached_data to get_or_fetch_metadata to avoid redundant DB queries
                metadata = self.get_or_fetch_metadata(item.stream_id, item.name, item.year, cached_data_map=all_cached_data)
                if metadata:
                    ratings[item.stream_id] = {
                        'rating': metadata.get('rating'),
                        'vote_count': metadata.get('vote_count')
                    }
                    # Update VODItem with fetched data
                    item.tmdb_rating = metadata.get('rating')
                    item.tmdb_vote_count = metadata.get('vote_count')
                    item.tmdb_overview = metadata.get('overview')
                    item.tmdb_genres = metadata.get('genres')
                    item.tmdb_cast = metadata.get('cast')
                    item.tmdb_director = metadata.get('director')
                    item.tmdb_poster = metadata.get('poster_path') # Corrected to 'poster_path'
        
        return ratings