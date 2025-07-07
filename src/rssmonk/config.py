"""Configuration and constants for RSS Monk."""

import os

# Application constants
USER_AGENT = "RSS Monk/1.0 (Feed Aggregator; +https://github.com/wagov-dtt/rssmonk)"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_WORKERS = 10
DEFAULT_CACHE_DIR = "/tmp/rss_cache"
DEFAULT_STATE_FILE = "/tmp/rssmonk_state.json"

# Feed frequency configurations
FREQUENCIES = {
    'freq:5min': {
        'interval_minutes': 5,
        'check_time': None,
        'check_day': None,
        'description': 'Every 5 minutes'
    },
    'freq:daily': {
        'interval_minutes': None,
        'check_time': (17, 0),  # 5pm
        'check_day': None,
        'description': 'Daily at 5pm'
    },
    'freq:weekly': {
        'interval_minutes': None,
        'check_time': (17, 0),  # 5pm
        'check_day': 4,         # Friday
        'description': 'Weekly on Friday at 5pm'
    }
}

# Logging configuration
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Environment configuration
class Config:
    """Application configuration from environment variables."""
    
    def __init__(self):
        self.listmonk_url = os.getenv('LISTMONK_URL', 'http://localhost:9000')
        self.listmonk_username = os.getenv('LISTMONK_APIUSER', 'api')
        self.listmonk_password = os.getenv('LISTMONK_APITOKEN')
        self.max_workers = int(os.getenv('MAX_WORKERS', str(DEFAULT_MAX_WORKERS)))
        self.auto_send = os.getenv('RSS_AUTO_SEND', 'false').lower() == 'true'
        self.cache_dir = os.getenv('RSS_CACHE_DIR', DEFAULT_CACHE_DIR)

        self.timeout = float(os.getenv('RSS_TIMEOUT', str(DEFAULT_TIMEOUT)))
    
    def validate(self) -> None:
        """Validate required configuration."""
        if not self.listmonk_password:
            raise ValueError("LISTMONK_APITOKEN environment variable is required")
        
        if not self.listmonk_url:
            raise ValueError("LISTMONK_URL environment variable is required")

# Global config instance
config = Config()
