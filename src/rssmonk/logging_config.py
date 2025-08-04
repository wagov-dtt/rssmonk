"""Structured logging configuration for RSS Monk."""

import logging
import logging.config
import sys
from typing import Optional


def setup_logging(level: str = "INFO", format_str: str = None) -> None:
    """Setup structured logging configuration."""
    if format_str is None:
        format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {"format": format_str},
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s"
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": level,
                "formatter": "standard",
                "stream": sys.stdout,
            },
            "error_console": {
                "class": "logging.StreamHandler",
                "level": "ERROR",
                "formatter": "detailed",
                "stream": sys.stderr,
            },
        },
        "loggers": {
            "rssmonk": {
                "handlers": ["console", "error_console"],
                "level": level,
                "propagate": False,
            },
            "httpx": {"handlers": ["console"], "level": "WARNING", "propagate": False},
            "feedparser": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        },
        "root": {"handlers": ["console"], "level": level},
    }

    logging.config.dictConfig(config)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name."""
    return logging.getLogger(f"rssmonk.{name}")
