"""Structured logging configuration for RSS Monk."""

import logging
import logging.config
import sys

from .config import LOG_FORMAT, LOG_LEVEL

def setup_logging(level: str = None) -> None:
    """Setup structured logging configuration."""
    log_level = level or LOG_LEVEL
    
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': LOG_FORMAT
            },
            'detailed': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s'
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': log_level,
                'formatter': 'standard',
                'stream': sys.stdout
            },
            'error_console': {
                'class': 'logging.StreamHandler',
                'level': 'ERROR',
                'formatter': 'detailed',
                'stream': sys.stderr
            }
        },
        'loggers': {
            'rssmonk': {
                'handlers': ['console', 'error_console'],
                'level': log_level,
                'propagate': False
            },
            'httpx': {
                'handlers': ['console'],
                'level': 'WARNING',
                'propagate': False
            },
            'feedparser': {
                'handlers': ['console'],
                'level': 'WARNING',
                'propagate': False
            }
        },
        'root': {
            'handlers': ['console'],
            'level': log_level
        }
    }
    
    logging.config.dictConfig(config)

def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name."""
    return logging.getLogger(f'rssmonk.{name}')
