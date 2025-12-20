from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class Playlist:
    """Playlist configuration model"""
    id: Optional[int] = None
    name: str = ""
    type: str = "m3u"  # 'm3u' or 'xtream'
    source: str = ""  # File path or URL
    username: Optional[str] = None
    password: Optional[str] = None
    last_updated: Optional[datetime] = None
    auto_refresh: bool = True
    
    @property
    def is_xtream(self) -> bool:
        return self.type == 'xtream'
    
    @property
    def needs_credentials(self) -> bool:
        return self.is_xtream and (not self.username or not self.password)