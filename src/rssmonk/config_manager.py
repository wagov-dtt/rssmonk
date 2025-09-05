"""Configuration management for RSS feed updates and migrations."""

from typing import Dict, List, Optional

from .core import Feed, RSSMonk, Frequency
from .logging_config import get_logger

logger = get_logger(__name__)


class FeedConfigManager:
    """Manages RSS feed configuration updates and migrations."""
    
    def __init__(self, rss_monk: RSSMonk):
        self.rss_monk = rss_monk
    
    def update_feed_config(self, url: str, new_frequency: Frequency, new_name: Optional[str] = None) -> Dict:
        """Update feed configuration, handling migrations and subscriber transfers."""
        try:
            # Find all existing feeds for this URL
            existing_feeds = self._find_feeds_by_url(url)
            
            if not existing_feeds:
                raise ValueError(f"No existing feed found for URL: {url}")
            
            # Check if target configuration already exists
            target_exists = any(feed.frequency == new_frequency for feed in existing_feeds)
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
    
    def replace_feed_config(self, url: str, new_frequency: Frequency, new_name: Optional[str] = None, 
                           delete_old: bool = True) -> Dict:
        """Replace feed configuration, optionally deleting old configurations."""
        try:
            # Find all existing feeds for this URL
            existing_feeds = self._find_feeds_by_url(url)
            
            if not existing_feeds:
                raise ValueError(f"No existing feed found for URL: {url}")
            
            # Create new feed configuration
            new_feed = self.rss_monk.add_feed(url, new_frequency, new_name)
            logger.info(f"Created replacement feed: {new_feed.name}")
            
            # Migrate all subscribers to new configuration
            total_migrated = 0
            for old_feed in existing_feeds:
                try:
                    migrated_count = self._migrate_subscribers(old_feed, new_feed)
                    total_migrated += migrated_count
                    logger.info(f"Migrated {migrated_count} subscribers from {old_feed.name}")
                except Exception as e:
                    logger.error(f"Failed to migrate from {old_feed.name}: {e}")
            
            # Delete old feeds if requested
            deleted_feeds = []
            if delete_old:
                for old_feed in existing_feeds:
                    try:
                        if self.rss_monk.delete_feed(old_feed.url):
                            deleted_feeds.append(old_feed.name)
                            logger.info(f"Deleted old feed: {old_feed.name}")
                    except Exception as e:
                        logger.error(f"Failed to delete old feed {old_feed.name}: {e}")
            
            return {
                "action": "replaced",
                "new_feed": self._feed_to_dict(new_feed),
                "subscribers_migrated": total_migrated,
                "deleted_feeds": deleted_feeds,
                "message": f"Replaced feed configurations with: {new_feed.name}"
            }
            
        except Exception as e:
            logger.error(f"Failed to replace feed configuration: {e}")
            raise
    
    def _find_feeds_by_url(self, url: str) -> List[Feed]:
        """Find all feeds with the given URL."""
        all_feeds = self.rss_monk.list_feeds()
        return [feed for feed in all_feeds if feed.url == url]
    
    def _migrate_subscribers(self, from_feed: Feed, to_feed: Feed) -> int:
        """Migrate subscribers from one feed to another."""
        try:
            # Get subscriber IDs from the source list
            source_list = self.rss_monk._client.get(f"/api/lists/{from_feed.id}")
            subscriber_ids = []
            
            # Get subscribers for this list
            subscribers_response = self.rss_monk._client.get("/api/subscribers", params={
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
                self.rss_monk._client.subscribe_to_lists(subscriber_ids, [to_feed.id])
                logger.info(f"Migrated {len(subscriber_ids)} subscribers from {from_feed.name} to {to_feed.name}")
                return len(subscriber_ids)
            
            return 0
            
        except Exception as e:
            logger.error(f"Failed to migrate subscribers: {e}")
            raise
    
    def _feed_to_dict(self, feed: Feed) -> Dict:
        """Convert Feed object to dictionary."""
        return {
            "id": feed.id,
            "name": feed.name,
            "url": feed.url,
            "base_url": feed.base_url,
            "frequency": feed.frequency.value,
            "url_hash": feed.url_hash
        }
    
    def get_url_configurations(self, url: str) -> Dict:
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
                subscribers_response = self.rss_monk._client.get("/api/subscribers", params={
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
