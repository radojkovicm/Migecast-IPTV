from dataclasses import dataclass
from typing import Optional


@dataclass
class VODItem:
    """Video on Demand item model"""
    
    stream_id: str
    name: str
    url: str
    cover: Optional[str] = None  # Poster/cover image URL
    plot: Optional[str] = None  # Description
    rating: Optional[str] = None  # Rating (e.g., "8.5")
    year: Optional[str] = None  # Release year
    genre: Optional[str] = None  # Genre
    duration: Optional[str] = None  # Duration (e.g., "2h 15min")
    director: Optional[str] = None  # Director name
    cast: Optional[str] = None  # Cast list
    category: Optional[str] = None  # Category name
    
    # TMDB fields
    tmdb_rating: Optional[float] = None  # TMDB rating (0-10)
    tmdb_vote_count: Optional[int] = None  # Number of votes
    tmdb_overview: Optional[str] = None  # TMDB description
    tmdb_genres: Optional[str] = None  # TMDB genres
    tmdb_cast: Optional[str] = None  # TMDB cast
    tmdb_director: Optional[str] = None  # TMDB director
    tmdb_poster: Optional[str] = None  # TMDB poster URL
    
    def __post_init__(self):
        """Validate and process fields after initialization"""
        # Ensure stream_id is string
        if self.stream_id is not None:
            self.stream_id = str(self.stream_id)
        
        # Clean up name
        if self.name:
            self.name = self.name.strip()
    
    def get_display_rating(self) -> str:
        """Get rating for display (prefer TMDB)"""
        if self.tmdb_rating and self.tmdb_vote_count:
            return f"⭐ {self.tmdb_rating:.1f}/10 ({self.tmdb_vote_count} votes)"
        elif self.rating:
            return f"⭐ {self.rating}"
        return ""
    
    def get_description(self) -> str:
        """Get description (prefer TMDB)"""
        return self.tmdb_overview or self.plot or "Nema opisa"
    
    def get_cast(self) -> str:
        """Get cast (prefer TMDB)"""
        return self.tmdb_cast or self.cast or "N/A"
    
    def get_director(self) -> str:
        """Get director (prefer TMDB)"""
        return self.tmdb_director or self.director or "N/A"