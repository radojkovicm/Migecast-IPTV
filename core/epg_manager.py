import logging
import requests
from lxml import etree
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class EPGProgram:
    """EPG program data class"""
    
    def __init__(self, start: datetime, stop: datetime, title: str, description: str = ""):
        self.start = start
        self.stop = stop
        self.title = title
        self.description = description
    
    @property
    def duration_minutes(self) -> int:
        """Get program duration in minutes"""
        return int((self.stop - self.start).total_seconds() / 60)
    
    def is_current(self) -> bool:
        """Check if program is currently airing"""
        now = datetime.now()
        return self.start <= now < self.stop


class EPGManager:
    """EPG (Electronic Program Guide) manager"""
    
    def __init__(self):
        self.epg_data: Dict[str, List[EPGProgram]] = {}
        self.epg_url: Optional[str] = None
    
    def load_xmltv(self, url_or_path: str):
        """Load XMLTV EPG data"""
        try:
            logger.info(f"Loading EPG from: {url_or_path}")
            
            # Download or load file
            if url_or_path.startswith('http'):
                response = requests.get(url_or_path, timeout=30)
                xml_content = response.content
            else:
                with open(url_or_path, 'rb') as f:
                    xml_content = f.read()
            
            # Parse XML
            root = etree.fromstring(xml_content)
            
            # Parse programmes
            for programme in root.findall('programme'):
                channel_id = programme.get('channel')
                start_time = self._parse_xmltv_time(programme.get('start'))
                stop_time = self._parse_xmltv_time(programme.get('stop'))
                
                title_elem = programme.find('title')
                title = title_elem.text if title_elem is not None else "Unknown"
                
                desc_elem = programme.find('desc')
                description = desc_elem.text if desc_elem is not None else ""
                
                # Add to EPG data
                if channel_id not in self.epg_data:
                    self.epg_data[channel_id] = []
                
                self.epg_data[channel_id].append(
                    EPGProgram(start_time, stop_time, title, description)
                )
            
            logger.info(f"Loaded EPG data for {len(self.epg_data)} channels")
            
        except Exception as e:
            logger.error(f"Failed to load EPG: {e}")
    
    def get_current_program(self, channel_id: str) -> Optional[EPGProgram]:
        """Get current program for channel"""
        if channel_id not in self.epg_data:
            return None
        
        now = datetime.now()
        for program in self.epg_data[channel_id]:
            if program.start <= now < program.stop:
                return program
        
        return None
    
    def get_next_program(self, channel_id: str) -> Optional[EPGProgram]:
        """Get next program for channel"""
        current = self.get_current_program(channel_id)
        if not current or channel_id not in self.epg_data:
            return None
        
        programs = sorted(self.epg_data[channel_id], key=lambda p: p.start)
        for i, program in enumerate(programs):
            if program == current and i + 1 < len(programs):
                return programs[i + 1]
        
        return None
    
    def get_programs_for_day(self, channel_id: str, date: datetime = None) -> List[EPGProgram]:
        """Get all programs for a specific day"""
        if date is None:
            date = datetime.now()
        
        if channel_id not in self.epg_data:
            return []
        
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        
        return [
            p for p in self.epg_data[channel_id]
            if start_of_day <= p.start < end_of_day
        ]
    
    @staticmethod
    def _parse_xmltv_time(time_str: str) -> datetime:
        """Parse XMLTV timestamp format (YYYYMMDDHHmmss +0000)"""
        try:
            # Format: 20240101120000 +0000
            date_part = time_str.split()[0]
            return datetime.strptime(date_part, "%Y%m%d%H%M%S")
        except Exception as e:
            logger.warning(f"Failed to parse time: {time_str}, {e}")
            return datetime.now()