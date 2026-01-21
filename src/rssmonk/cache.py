"""RSS feed caching system for optimized polling."""

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Tuple
import httpx
import feedparser

from rssmonk.types import FEED_URL_RSSMONK_QUERY, FeedItem

from .logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class CachedFeed:
    """Cached RSS feed data."""

    url: str
    url_hash: str
    content_hash: str
    etag: Optional[str]
    last_modified: Optional[str]
    articles: list[FeedItem]
    cached_at: datetime
    expires_at: datetime
    feed_title: Optional[str] = None

    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return datetime.now() > self.expires_at

    def is_fresh(self, max_age_minutes: int = 60) -> bool:
        """Check if cache is still fresh within max age."""
        return datetime.now() < self.cached_at + timedelta(minutes=max_age_minutes)


class FeedCache:
    """In-memory RSS feed cache with smart invalidation."""

    def __init__(self, max_entries: int = 200, default_ttl_minutes: int = 60):
        self.cache: dict[str, CachedFeed] = {}
        self.max_entries = max_entries
        self.default_ttl_minutes = default_ttl_minutes

    def _generate_content_hash(self, content: str) -> str:
        """Generate hash of RSS feed content."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _get_cache_key(self, url: str) -> str:
        """Get cache key for URL."""
        return hashlib.sha256(url.encode()).hexdigest()

    def _evict_old_entries(self):
        """Remove old entries if cache is full."""
        if len(self.cache) >= self.max_entries:
            # Remove oldest 10% of entries
            remove_count = max(1, self.max_entries // 10)
            oldest_keys = sorted(self.cache.keys(), key=lambda k: self.cache[k].cached_at)[:remove_count]

            for key in oldest_keys:
                del self.cache[key]
                logger.debug(f"Evicted cache entry: {key}")

    async def get_feed(self, url: str, user_agent: str, timeout: float = 30.0) -> Tuple[list[FeedItem], Optional[str]]:
        """Get RSS feed with intelligent caching."""
        cache_key = self._get_cache_key(url)
        cached_feed = self.cache.get(cache_key)

        headers = {"User-Agent": user_agent}

        # Add conditional request headers if we have cached data
        if cached_feed and not cached_feed.is_expired():
            if cached_feed.etag:
                headers["If-None-Match"] = cached_feed.etag
            if cached_feed.last_modified:
                headers["If-Modified-Since"] = cached_feed.last_modified

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url + FEED_URL_RSSMONK_QUERY, headers=headers)

                # Handle 304 Not Modified
                if response.status_code == 304 and cached_feed:
                    logger.info(f"Feed unchanged (304): {url}")
                    # Update cache expiry but keep same content
                    cached_feed.expires_at = datetime.now() + timedelta(minutes=self.default_ttl_minutes)
                    return cached_feed.articles, cached_feed.feed_title

                response.raise_for_status()

                # Parse feed content
                content = response.text
                content_hash = self._generate_content_hash(content)

                # Check if content actually changed
                if cached_feed and cached_feed.content_hash == content_hash:
                    logger.info(f"Feed content unchanged: {url}")
                    cached_feed.expires_at = datetime.now() + timedelta(minutes=self.default_ttl_minutes)
                    return cached_feed.articles, cached_feed.feed_title

                # Parse new content
                feed_data: feedparser.FeedParserDict = feedparser.parse(content)

                if feed_data.bozo:  # From feedparser.FeedParserDict
                    logger.warning(f"Feed has issues: {feed_data.bozo_exception}")

                articles: list[FeedItem] = []
                for entry in feed_data.entries:
                    article = FeedItem(
                        title=entry.get("title", ""),
                        link=entry.get("link", ""),
                        description=entry.get("description", ""),
                        published=entry.get("pubDate", ""),
                        guid=entry.get("id", entry.get("link", "")),
                        email_subject_line=entry.get("wa:subject_line", ""),
                        filter_identifiers=entry.get("wa:identifiers", ""),
                    )
                    articles.append(article)

                # Create cache entry
                self._evict_old_entries()

                cached_feed = CachedFeed(
                    url=url,
                    url_hash=hashlib.sha256(url.encode()).hexdigest(),
                    content_hash=content_hash,
                    etag=response.headers.get("ETag"),
                    last_modified=response.headers.get("Last-Modified"),
                    articles=articles,
                    cached_at=datetime.now(),
                    expires_at=datetime.now() + timedelta(minutes=self.default_ttl_minutes),
                    feed_title=feed_data.feed.get("title", url),
                )

                self.cache[cache_key] = cached_feed

                logger.info(f"Cached feed: {url} ({len(articles)} articles)")
                return articles, cached_feed.feed_title

        except Exception as e:
            logger.error(f"Error fetching feed {url}: {e}")

            # Return cached data if available and not too old
            if cached_feed and cached_feed.is_fresh(max_age_minutes=240):  # 4 hours fallback
                logger.info(f"Using stale cache for failed fetch: {url}")
                return cached_feed.articles, cached_feed.feed_title

            return [], None

    def invalidate_url(self, url: str):
        """Invalidate cache for specific URL."""
        cache_key = self._get_cache_key(url)
        if cache_key in self.cache:
            del self.cache[cache_key]
            logger.info(f"Invalidated cache: {url}")

    def clear(self):
        """Clear all cache entries."""
        self.cache.clear()
        logger.info("Cleared all feed cache")

    def get_stats(self) -> dict:
        """Get cache statistics."""
        return {
            "total_entries": len(self.cache),
            "max_entries": self.max_entries,
            "fresh_entries": len([c for c in self.cache.values() if not c.is_expired()]),
            "expired_entries": len([c for c in self.cache.values() if c.is_expired()]),
        }


# Global cache instance
feed_cache = FeedCache()
