from dataclasses import dataclass
from typing import Optional


@dataclass
class SeriesItem:
    """TV series episode (or, for Xtream accounts, a series whose episodes
    are fetched on demand - then ``xtream_series_id`` is set and ``url`` is
    empty)."""

    stream_id: str
    name: str
    url: str
    cover: Optional[str] = None
    plot: Optional[str] = None
    rating: Optional[str] = None
    year: Optional[str] = None
    genre: Optional[str] = None
    director: Optional[str] = None
    cast: Optional[str] = None
    category: Optional[str] = None
    season: Optional[str] = None
    episode: Optional[str] = None
    series_name: Optional[str] = None
    xtream_series_id: Optional[str] = None
    episode_title: Optional[str] = None

    def __post_init__(self):
        if self.stream_id is not None:
            self.stream_id = str(self.stream_id)
        if self.name:
            self.name = self.name.strip()
        if self.season is not None:
            self.season = str(self.season)
        if self.episode is not None:
            self.episode = str(self.episode)

    @property
    def is_series_stub(self) -> bool:
        return bool(self.xtream_series_id) and not self.url
