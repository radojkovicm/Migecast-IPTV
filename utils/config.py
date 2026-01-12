import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class Config:
    """Configuration manager for application settings"""
    
    def __init__(self, config_file: str = 'data/config.json'):
        self.config_file = Path(config_file)
        self.settings = {}
        self.load()
    
    def load(self):
        """Load configuration from file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.settings = json.load(f)
                logger.info(f"Configuration loaded from {self.config_file}")
            except Exception as e:
                logger.error(f"Failed to load configuration: {e}")
                self.settings = {}
        else:
            # Create default settings
            self.settings = {
                'display': {
                    'max_channels': '500',
                    'max_vod': '200'
                },
                'player': {
                    'reconnect_attempts': 3,
                    'hw_acceleration': True
                }
            }
            self.save()
    
    def save(self):
        """Save configuration to file"""
        try:
            # Ensure directory exists
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
            
            logger.info(f"Configuration saved to {self.config_file}")
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
    
    def get(self, section: str, key: str = None, default=None):
        """
        Get configuration value

        Args:
            section: Section name (e.g., 'display')
            key: Key name (optional, if None returns whole section)
            default: Default value if not found
        """
        if key is None:
            # Return whole section
            return self.settings.get(section, default)

        if section in self.settings and key in self.settings[section]:
            return self.settings[section][key]
        return default

    def set(self, section: str, key: str, value):
        """Set configuration value"""
        if section not in self.settings:
            self.settings[section] = {}

        self.settings[section][key] = value

    def get_flat(self, key: str, default=None):
        """Get configuration value from root level (for backward compatibility)"""
        return self.settings.get(key, default)
