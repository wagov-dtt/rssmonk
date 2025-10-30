"""Configuration management for RSS feed updates and migrations."""

from typing import Optional
from warnings import deprecated

from .core import Feed, RSSMonk
from .types import Frequency
from .logging_config import get_logger

logger = get_logger(__name__)


class FeedConfigManager:
    """Manages RSS feed configuration updates and migrations."""
    
    def __init__(self, rss_monk: RSSMonk):
        self.rss_monk = rss_monk
    
    def update_feed_config(self, url: str, new_frequency: Frequency, new_name: Optional[str] = None) -> dict:
        """Update feed configuration, handling migrations and subscriber transfers."""
        try:
            # Find all existing feeds for this URL
            existing_feeds = self._find_feeds_by_url(url)
            
            if not existing_feeds:
                raise ValueError(f"No existing feed found for URL: {url}")
            
            # Check if target configuration already exists
            target_exists = any(feed.frequencies == new_frequency for feed in existing_feeds)
            if target_exists:
                return {
                    "action": "no_change",
                    "message": f"Feed with frequency {new_frequency.value} already exists",
                    "existing_feeds": [self._feed_to_dict(f) for f in existing_feeds]
                }
            
            # Create new feed configuration
            try:
                new_feed = self.rss_monk.add_feed(url, new_frequency, new_name)
                logger.info(f"Created new feed configuration: {new_feed.name}")
            except Exception as e:
                logger.error(f"Failed to create new feed configuration: {e}")
                raise
            
            # Migrate subscribers if requested
            migration_results = []
            for old_feed in existing_feeds:
                try:
                    migrated_count = self._migrate_subscribers(old_feed, new_feed)
                    migration_results.append({
                        "from_feed": old_feed.name,
                        "to_feed": new_feed.name,
                        "subscribers_migrated": migrated_count
                    })
                except Exception as e:
                    logger.error(f"Failed to migrate subscribers from {old_feed.name}: {e}")
                    migration_results.append({
                        "from_feed": old_feed.name,
                        "error": str(e)
                    })
            
            return {
                "action": "updated",
                "new_feed": self._feed_to_dict(new_feed),
                "existing_feeds": [self._feed_to_dict(f) for f in existing_feeds],
                "migration_results": migration_results,
                "message": f"Created new configuration: {new_feed.name}"
            }
            
        except Exception as e:
            logger.error(f"Failed to update feed configuration: {e}")
            raise
    
    def _find_feeds_by_url(self, url: str) -> list[Feed]:
        """Find all feeds with the given URL."""
        all_feeds = self.rss_monk.list_feeds()
        return [feed for feed in all_feeds if feed.feed_url == url]
    
    @deprecated("Migration between feeds is not desired as it is error prone. Method likely to be removed")
    def _migrate_subscribers(self, from_feed: Feed, to_feed: Feed) -> int:
        """Migrate subscribers from one feed to another."""
        # TODO = This one should be renamed copy and not migrate as they're left in the old one
        # TODO - Attributes are lost in this, since feed ids and urls have changed. Might be worth doing SQL here
        try:
            # Get subscriber IDs from the source list
            source_list = self.rss_monk.getClient().get(f"/api/lists/{from_feed.id}")
            subscriber_ids = []
            
            # Get subscribers for this list
            subscribers_response = self.rss_monk.getClient().get("/api/subscribers", params={
                "list_id": from_feed.id,
                "per_page": "all"
            })
            
            if isinstance(subscribers_response, dict) and "results" in subscribers_response:
                subscribers = subscribers_response["results"]
            elif isinstance(subscribers_response, list):
                subscribers = subscribers_response
            else:
                subscribers = []
            
            subscriber_ids = [sub["id"] for sub in subscribers if "id" in sub]
            
            if subscriber_ids:
                # Add subscribers to new list
                self.rss_monk.getClient().subscribe_to_list([subscriber_ids], [to_feed.id])
                logger.info(f"Migrated {len(subscriber_ids)} subscribers from {from_feed.name} to {to_feed.name}")
                return len(subscriber_ids)
            
            return 0
            
        except Exception as e:
            logger.error(f"Failed to migrate subscribers: {e}")
            raise
    
    def _feed_to_dict(self, feed: Feed) -> dict:
        """Convert Feed object to dictionary."""
        return {
            "id": feed.id,
            "name": feed.name,
            "url": feed.feed_url,
            "frequency": feed.frequencies,
            "url_hash": feed.url_hash
        }
    
    def get_url_configurations(self, url: str) -> dict:
        """Get all configurations for a given URL."""
        existing_feeds = self._find_feeds_by_url(url)
        
        if not existing_feeds:
            return {
                "url": url,
                "configurations": [],
                "total_configurations": 0
            }
        
        configurations = []
        for feed in existing_feeds:
            # Get subscriber count
            try:
                subscribers_response = self.rss_monk.getClient().get("/api/subscribers", params={
                    "list_id": feed.id,
                    "per_page": "1"
                })
                
                if isinstance(subscribers_response, dict) and "total" in subscribers_response:
                    subscriber_count = subscribers_response["total"]
                else:
                    subscriber_count = 0
                
                feed_dict = self._feed_to_dict(feed)
                feed_dict["subscriber_count"] = subscriber_count
                configurations.append(feed_dict)
                
            except Exception as e:
                logger.error(f"Failed to get subscriber count for {feed.name}: {e}")
                configurations.append(self._feed_to_dict(feed))
        
        return {
            "url": url,
            "configurations": configurations,
            "total_configurations": len(configurations)
        }
