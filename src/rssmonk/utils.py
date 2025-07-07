"""Utility functions for RSS Monk."""

import hashlib
from typing import Optional, List
from .config import FREQUENCIES
from .logging_config import get_logger

logger = get_logger(__name__)


def create_url_tag(url: str) -> str:
    """Create a hash tag for a URL to enable efficient lookups."""
    return f"url:{hashlib.sha256(url.encode()).hexdigest()}"


def find_feed_by_url(client, url: str) -> dict:
    """Find a feed list by URL using tag-based lookup."""
    url_tag = create_url_tag(url)
    return client.find_list_by_tag(url_tag)


def extract_feed_url(description: str) -> Optional[str]:
    """Extract feed URL from list description."""
    if "RSS Feed: " in description:
        return description.split("RSS Feed: ", 1)[1].strip()
    
    for line in description.split('\n'):
        line = line.strip()
        if line.startswith('http'):
            return line
    
    return None


def get_frequency_from_tags(tags: List[str]) -> Optional[str]:
    """Extract frequency tag from list tags."""
    for tag in tags:
        if tag in FREQUENCIES:
            return tag
    return None


def create_or_get_subscriber(client, email: str) -> dict:
    """Create subscriber if doesn't exist or get existing one."""
    try:
        subscribers = client.get_subscribers(query=f"subscribers.email = '{email}'")
        if subscribers:
            return subscribers[0]
        
        return client.create_subscriber(email=email, name=email)
    except Exception as e:
        logger.error(f"Error with subscriber {email}: {e}")
        raise


def update_list_tags(client, list_id: int, tags: List[str], name: str, description: str, list_type: str = "public"):
    """Update list tags with new state."""
    try:
        update_data = {
            "name": name,
            "description": description,
            "tags": tags,
            "type": list_type
        }
        client.put(f"/api/lists/{list_id}", update_data)
        logger.debug(f"Updated tags for list {name}")
    except Exception as e:
        logger.error(f"Failed to update tags for list {name}: {e}")
        raise
