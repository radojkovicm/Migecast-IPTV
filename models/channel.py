from dataclasses import dataclass
from typing import Optional


@dataclass
class Channel:
    """Live TV channel model"""

    channel_id: str
    name: str
    url: str
    logo: Optional[str] = None
    category: Optional[str] = None
    epg_id: Optional[str] = None

    def __post_init__(self):
        """Validate and process fields after initialization"""
        # Ensure channel_id is string
        if self.channel_id is not None:
            self.channel_id = str(self.channel_id)

        # Clean up name
        if self.name:
            self.name = self.name.strip()