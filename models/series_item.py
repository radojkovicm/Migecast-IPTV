from dataclasses import dataclass
from typing import Optional


@dataclass
class SeriesItem:
    """TV Series item model"""
    
    stream_id: str
    name: str
    url: str
    cover: Optional[str] = None  # Poster/cover image URL
    plot: Optional[str] = None  # Description
    rating: Optional[str] = None  # Rating (e.g., "8.5")
    year: Optional[str] = None  # Release year
    genre: Optional[str] = None  # Genre
    director: Optional[str] = None  # Director name
    cast: Optional[str] = None  # Cast list
    category: Optional[str] = None  # Category name
    season: Optional[str] = None  # Season number
    episode: Optional[str] = None  # Episode number
    
    def __post_init__(self):
        """Validate and process fields after initialization"""
        # Ensure stream_id is string
        if self.stream_id is not None:
            self.stream_id = str(self.stream_id)
        
        # Clean up name
        if self.name:
            self.name = self.name.strip()