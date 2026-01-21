"""Configuration management for RSS feed updates."""

from typing import Optional

from .core import Feed, RSSMonk
from .types import Frequency
from .logging_config import get_logger

logger = get_logger(__name__)


class FeedConfigManager:
    """Manages RSS feed configuration updates."""

    def __init__(self, rss_monk: RSSMonk):
        self.rss_monk = rss_monk

    def update_feed_config(self, url: str, new_frequency: Frequency, new_name: Optional[str] = None) -> dict:
        """Update feed configuration by adding new frequency."""
        existing_feeds = self._find_feeds_by_url(url)

        if not existing_feeds:
            raise ValueError(f"No existing feed found for URL: {url}")

        target_exists = any(feed.poll_frequencies == new_frequency for feed in existing_feeds)
        if target_exists:
            return {
                "action": "no_change",
                "message": f"Feed with frequency {new_frequency.value} already exists",
                "existing_feeds": [self._feed_to_dict(f) for f in existing_feeds],
            }

        new_feed = self.rss_monk.add_feed(url, new_frequency, new_name)
        logger.info(f"Created new feed configuration: {new_feed.name}")

        return {
            "action": "updated",
            "new_feed": self._feed_to_dict(new_feed),
            "existing_feeds": [self._feed_to_dict(f) for f in existing_feeds],
            "message": f"Created new configuration: {new_feed.name}",
        }

    def _find_feeds_by_url(self, url: str) -> list[Feed]:
        """Find all feeds with the given URL."""
        all_feeds = self.rss_monk.list_feeds()
        return [feed for feed in all_feeds if feed.feed_url == url]

    def _feed_to_dict(self, feed: Feed) -> dict:
        """Convert Feed object to dictionary."""
        return {
            "id": feed.id,
            "name": feed.name,
            "url": feed.feed_url,
            "frequency": feed.poll_frequencies,
            "url_hash": feed.url_hash,
        }

    def get_url_configurations(self, url: str) -> dict:
        """Get all configurations for a given URL."""
        existing_feeds = self._find_feeds_by_url(url)

        if not existing_feeds:
            return {"url": url, "configurations": [], "total_configurations": 0}

        configurations = []
        for feed in existing_feeds:
            # Get subscriber count
            try:
                subscribers_response = self.rss_monk.get_client().get(
                    "/api/subscribers", params={"list_id": feed.id, "per_page": "1"}
                )

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

        return {"url": url, "configurations": configurations, "total_configurations": len(configurations)}
