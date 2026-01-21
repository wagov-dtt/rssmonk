"""Caching system using diskcache for RSS feeds and templates."""

import hashlib
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Optional, Tuple
import httpx
import feedparser
from diskcache import Cache

from rssmonk.types import FEED_URL_RSSMONK_QUERY, FeedItem

from .logging_config import get_logger

logger = get_logger(__name__)

# Cache directory - use environment variable or default to /tmp for containerised environments
CACHE_DIR = os.environ.get("RSSMONK_CACHE_DIR", "/tmp/rssmonk-cache")

# Global diskcache instance
_cache: Optional[Cache] = None


def get_cache() -> Cache:
    """Get or create the global diskcache instance."""
    global _cache
    if _cache is None:
        _cache = Cache(CACHE_DIR, size_limit=100 * 1024 * 1024)  # 100MB limit
        logger.info(f"Initialised diskcache at {CACHE_DIR}")
    return _cache


def close_cache():
    """Close the cache connection."""
    global _cache
    if _cache is not None:
        _cache.close()
        _cache = None


@dataclass
class CachedFeed:
    """Cached RSS feed data."""

    url: str
    url_hash: str
    content_hash: str
    etag: Optional[str]
    last_modified: Optional[str]
    articles: list[dict]  # Serialised FeedItem dicts for diskcache
    cached_at: str  # ISO format for serialisation
    expires_at: str  # ISO format for serialisation
    feed_title: Optional[str] = None

    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return datetime.now() > datetime.fromisoformat(self.expires_at)

    def is_fresh(self, max_age_minutes: int = 60) -> bool:
        """Check if cache is still fresh within max age."""
        cached_at = datetime.fromisoformat(self.cached_at)
        return datetime.now() < cached_at + timedelta(minutes=max_age_minutes)

    def get_articles(self) -> list[FeedItem]:
        """Convert stored dicts back to FeedItem objects."""
        return [FeedItem(**article) for article in self.articles]

    @staticmethod
    def from_dict(data: dict) -> "CachedFeed":
        """Create CachedFeed from dict (deserialisation)."""
        return CachedFeed(**data)

    def to_dict(self) -> dict:
        """Convert to dict for serialisation."""
        return asdict(self)


class FeedCache:
    """RSS feed cache using diskcache."""

    CACHE_PREFIX = "feed:"

    def __init__(self, default_ttl_minutes: int = 60):
        self.default_ttl_minutes = default_ttl_minutes

    def _generate_content_hash(self, content: str) -> str:
        """Generate hash of RSS feed content."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _get_cache_key(self, url: str) -> str:
        """Get cache key for URL."""
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        return f"{self.CACHE_PREFIX}{url_hash}"

    def _get_cached(self, url: str) -> Optional[CachedFeed]:
        """Get cached feed if available."""
        cache = get_cache()
        key = self._get_cache_key(url)
        data = cache.get(key)
        if data:
            return CachedFeed.from_dict(data)
        return None

    def _set_cached(self, url: str, cached_feed: CachedFeed):
        """Store feed in cache."""
        cache = get_cache()
        key = self._get_cache_key(url)
        # Set with TTL in seconds (4 hours max to allow stale fallback)
        cache.set(key, cached_feed.to_dict(), expire=4 * 60 * 60)

    async def get_feed(self, url: str, user_agent: str, timeout: float = 30.0) -> Tuple[list[FeedItem], Optional[str]]:
        """Get RSS feed with intelligent caching."""
        cached_feed = self._get_cached(url)

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
                    cached_feed.expires_at = (datetime.now() + timedelta(minutes=self.default_ttl_minutes)).isoformat()
                    self._set_cached(url, cached_feed)
                    return cached_feed.get_articles(), cached_feed.feed_title

                response.raise_for_status()

                # Parse feed content
                content = response.text
                content_hash = self._generate_content_hash(content)

                # Check if content actually changed
                if cached_feed and cached_feed.content_hash == content_hash:
                    logger.info(f"Feed content unchanged: {url}")
                    cached_feed.expires_at = (datetime.now() + timedelta(minutes=self.default_ttl_minutes)).isoformat()
                    self._set_cached(url, cached_feed)
                    return cached_feed.get_articles(), cached_feed.feed_title

                # Parse new content
                feed_data: feedparser.FeedParserDict = feedparser.parse(content)

                if feed_data.bozo:
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

                # Create cache entry - store articles as dicts for serialisation
                now = datetime.now()
                # Get feed title safely
                feed_title = url
                if feed_data.feed:
                    feed_title = feed_data.feed.get("title", url)  # type: ignore[union-attr]

                new_cached = CachedFeed(
                    url=url,
                    url_hash=hashlib.sha256(url.encode()).hexdigest(),
                    content_hash=content_hash,
                    etag=response.headers.get("ETag"),
                    last_modified=response.headers.get("Last-Modified"),
                    articles=[asdict(a) for a in articles],
                    cached_at=now.isoformat(),
                    expires_at=(now + timedelta(minutes=self.default_ttl_minutes)).isoformat(),
                    feed_title=feed_title,
                )

                self._set_cached(url, new_cached)
                logger.info(f"Cached feed: {url} ({len(articles)} articles)")
                return articles, new_cached.feed_title

        except Exception as e:
            logger.error(f"Error fetching feed {url}: {e}")

            # Return cached data if available and not too old
            if cached_feed and cached_feed.is_fresh(max_age_minutes=240):  # 4 hours fallback
                logger.info(f"Using stale cache for failed fetch: {url}")
                return cached_feed.get_articles(), cached_feed.feed_title

            return [], None

    def invalidate_url(self, url: str):
        """Invalidate cache for specific URL."""
        cache = get_cache()
        key = self._get_cache_key(url)
        if cache.delete(key):
            logger.info(f"Invalidated feed cache: {url}")

    def clear(self):
        """Clear all feed cache entries."""
        cache = get_cache()
        count = 0
        for key in list(cache):
            if isinstance(key, str) and key.startswith(self.CACHE_PREFIX):
                cache.delete(key)
                count += 1
        logger.info(f"Cleared {count} feed cache entries")

    def get_stats(self) -> dict:
        """Get cache statistics."""
        cache = get_cache()
        feed_keys = [k for k in cache if isinstance(k, str) and k.startswith(self.CACHE_PREFIX)]
        fresh_count = 0
        expired_count = 0

        for key in feed_keys:
            data = cache.get(key)
            if data:
                cached = CachedFeed.from_dict(data)
                if cached.is_expired():
                    expired_count += 1
                else:
                    fresh_count += 1

        return {
            "total_entries": len(feed_keys),
            "fresh_entries": fresh_count,
            "expired_entries": expired_count,
            "cache_directory": CACHE_DIR,
        }


class TemplateCache:
    """Template cache using diskcache."""

    CACHE_PREFIX = "template:"
    DEFAULT_TTL_SECONDS = 300  # 5 minutes - templates change infrequently

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self.ttl_seconds = ttl_seconds

    def _get_cache_key(self, feed_hash: str, phase_type: str) -> str:
        """Get cache key for template."""
        return f"{self.CACHE_PREFIX}{feed_hash}:{phase_type}"

    def get(self, feed_hash: str, phase_type: str) -> Optional[dict]:
        """Get cached template."""
        cache = get_cache()
        key = self._get_cache_key(feed_hash, phase_type)
        return cache.get(key)

    def set(self, feed_hash: str, phase_type: str, template_data: dict):
        """Cache a template."""
        cache = get_cache()
        key = self._get_cache_key(feed_hash, phase_type)
        cache.set(key, template_data, expire=self.ttl_seconds)
        logger.debug(f"Cached template: {feed_hash}:{phase_type}")

    def invalidate(self, feed_hash: str, phase_type: Optional[str] = None):
        """Invalidate cached template(s) for a feed.

        If phase_type is None, invalidates all templates for the feed.
        """
        cache = get_cache()
        if phase_type:
            key = self._get_cache_key(feed_hash, phase_type)
            if cache.delete(key):
                logger.info(f"Invalidated template cache: {feed_hash}:{phase_type}")
        else:
            # Invalidate all templates for this feed
            count = 0
            prefix = f"{self.CACHE_PREFIX}{feed_hash}:"
            for key in list(cache):
                if isinstance(key, str) and key.startswith(prefix):
                    cache.delete(key)
                    count += 1
            if count:
                logger.info(f"Invalidated {count} template cache entries for feed {feed_hash}")

    def clear(self):
        """Clear all template cache entries."""
        cache = get_cache()
        count = 0
        for key in list(cache):
            if isinstance(key, str) and key.startswith(self.CACHE_PREFIX):
                cache.delete(key)
                count += 1
        logger.info(f"Cleared {count} template cache entries")

    def get_stats(self) -> dict:
        """Get template cache statistics."""
        cache = get_cache()
        template_keys = [k for k in cache if isinstance(k, str) and k.startswith(self.CACHE_PREFIX)]
        return {
            "total_entries": len(template_keys),
            "ttl_seconds": self.ttl_seconds,
            "cache_directory": CACHE_DIR,
        }


# Global cache instances
feed_cache = FeedCache()
template_cache = TemplateCache()
