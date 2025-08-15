"""Simplified core models and service for RSS Monk."""

import hashlib
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from .http_clients import ListmonkClient, fetch_feed
from .logging_config import get_logger

# Feed frequency configurations
FREQUENCIES: Dict[str, Dict[str, Any]] = {
    "freq:5min": {
        "interval_minutes": 5,
        "check_time": None,
        "check_day": None,
        "description": "Every 5 minutes",
    },
    "freq:daily": {
        "interval_minutes": None,
        "check_time": (17, 0),  # 5pm
        "check_day": None,
        "description": "Daily at 5pm",
    },
    "freq:weekly": {
        "interval_minutes": None,
        "check_time": (17, 0),  # 5pm
        "check_day": 4,  # Friday
        "description": "Weekly on Friday at 5pm",
    },
}

logger = get_logger(__name__)


class Frequency(str, Enum):
    """Polling frequencies."""

    FIVE_MIN = "5min"
    DAILY = "daily"
    WEEKLY = "weekly"


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # Listmonk configuration
    listmonk_url: str = Field(default="http://localhost:9000", description="Listmonk API URL")
    listmonk_username: str = Field(default="api", alias="LISTMONK_APIUSER", description="Listmonk API username")
    listmonk_password: str = Field(alias="LISTMONK_APITOKEN", description="Listmonk API token/password")

    # RSS processing configuration
    rss_auto_send: bool = Field(
        default=False,
        alias="RSS_AUTO_SEND",
        description="Automatically send campaigns when created",
    )
    rss_timeout: float = Field(default=30.0, alias="RSS_TIMEOUT", description="HTTP timeout for RSS feed requests")
    rss_user_agent: str = Field(
        default="RSS Monk/2.0 (Feed Aggregator; +https://github.com/wagov-dtt/rssmonk)",
        alias="RSS_USER_AGENT",
        description="User agent for RSS requests",
    )

    # Logging configuration
    log_level: str = Field(default="INFO", alias="LOG_LEVEL", description="Logging level")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        alias="LOG_FORMAT",
        description="Log message format",
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }

    def validate_required(self):
        """Validate required settings."""
        if not self.listmonk_password:
            raise ValueError("LISTMONK_APITOKEN environment variable is required")


class Feed(BaseModel):
    """RSS feed model."""

    id: Optional[int] = None
    name: str
    url: str
    frequency: Frequency
    base_url: str = ""
    url_hash: str = ""

    def __init__(self, **data):
        super().__init__(**data)
        if not self.base_url:
            parsed = urlparse(self.url)
            self.base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if not self.url_hash:
            self.url_hash = hashlib.sha256(self.url.encode()).hexdigest()

    @property
    def tags(self) -> List[str]:
        """Generate Listmonk tags."""
        return [f"freq:{self.frequency.value}", f"url:{self.url_hash}"]

    @property
    def description(self) -> str:
        """Generate Listmonk description."""
        return f"RSS Feed: {self.url}\nBase URL: {self.base_url}"


class Subscriber(BaseModel):
    """Subscriber model."""

    id: Optional[int] = None
    email: str
    name: str = ""

    def __init__(self, **data):
        super().__init__(**data)
        if not self.name:
            self.name = self.email


class RSSMonk:
    """Main RSS Monk service - stateless, uses Listmonk for persistence."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.settings.validate_required()

    def __enter__(self):
        self._client = ListmonkClient(
            base_url=self.settings.listmonk_url,
            username=self.settings.listmonk_username,
            password=self.settings.listmonk_password,
            timeout=self.settings.rss_timeout,
        ).__enter__()
        return self

    def __exit__(self, *args):
        if hasattr(self, "_client"):
            self._client.__exit__(*args)

    # Feed operations

    def add_feed(self, url: str, frequency: Frequency, name: Optional[str] = None) -> Feed:
        """Add RSS feed."""
        if not name:
            name = self._get_feed_name(url)

        feed = Feed(name=name, url=url, frequency=frequency)

        # Check if exists
        if self._client.find_list_by_tag(f"url:{feed.url_hash}"):
            raise ValueError(f"Feed already exists: {url}")

        # Create in Listmonk
        result = self._client.create_list(name=feed.name, description=feed.description, tags=feed.tags)
        feed.id = result["id"]
        return feed

    def list_feeds(self) -> List[Feed]:
        """List all feeds."""
        feeds = []
        for freq in Frequency:
            lists = self._client.get_lists(tag=f"freq:{freq.value}")
            for lst in lists:
                try:
                    feed = self._parse_feed_from_list(lst)
                    feeds.append(feed)
                except Exception as e:
                    logger.warning(f"Skipping invalid feed {lst.get('name')}: {e}")

        # Deduplicate by ID
        return list({f.id: f for f in feeds if f.id}.values())

    def get_feed_by_url(self, url: str) -> Optional[Feed]:
        """Get feed by URL."""
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        lst = self._client.find_list_by_tag(f"url:{url_hash}")
        return self._parse_feed_from_list(lst) if lst else None

    def delete_feed(self, url: str) -> bool:
        """Delete feed by URL."""
        feed = self.get_feed_by_url(url)
        if feed and feed.id:
            self._client.delete(f"/api/lists/{feed.id}")
            return True
        return False

    # Subscriber operations

    def add_subscriber(self, email: str, name: Optional[str] = None) -> Subscriber:
        """Add subscriber."""
        result = self._client.create_subscriber(email=email, name=name or email)
        return Subscriber(id=result["id"], email=result["email"], name=result["name"])

    def get_or_create_subscriber(self, email: str) -> Subscriber:
        """Get existing or create new subscriber."""
        subs = self._client.get_subscribers(query=f"subscribers.email = '{email}'")
        if subs:
            s = subs[0]
            return Subscriber(id=s["id"], email=s["email"], name=s["name"])
        return self.add_subscriber(email)

    def list_subscribers(self) -> List[Subscriber]:
        """List all subscribers."""
        subs = self._client.get_subscribers()
        return [Subscriber(id=s["id"], email=s["email"], name=s["name"]) for s in subs]

    def subscribe(self, email: str, feed_url: str) -> bool:
        """Subscribe email to feed."""
        subscriber = self.get_or_create_subscriber(email)
        feed = self.get_feed_by_url(feed_url)

        if not feed or not feed.id:
            raise ValueError(f"Feed not found: {feed_url}")

        self._client.subscribe_to_lists([subscriber.id], [feed.id])
        return True

    # Feed processing

    def process_feed(self, feed: Feed, auto_send: Optional[bool] = None) -> int:
        """Process single feed - fetch articles and create campaigns."""
        if auto_send is None:
            auto_send = self.settings.rss_auto_send

        try:
            # Fetch articles
            articles, _ = fetch_feed(
                feed_url=feed.url,
                timeout=self.settings.rss_timeout,
                user_agent=self.settings.rss_user_agent,
            )

            # Get new articles (simple approach - check against last poll tag)
            new_articles = self._find_new_articles(feed, articles)

            if not new_articles:
                self._update_poll_time(feed)
                return 0

            # Create campaigns
            campaigns = 0
            for article in new_articles:
                try:
                    campaign_id = self._create_campaign(feed, article)
                    if auto_send:
                        self._client.start_campaign(campaign_id)
                    campaigns += 1
                except Exception as e:
                    logger.error(f"Campaign creation failed: {e}")

            # Update state
            self._update_feed_state(feed, new_articles)
            return campaigns

        except Exception as e:
            logger.error(f"Feed processing failed for {feed.name}: {e}")
            return 0

    def process_feeds_by_frequency(self, frequency: Frequency) -> dict:
        """Process all feeds of given frequency that are due."""
        feeds = [f for f in self.list_feeds() if f.frequency == frequency]
        results = {}

        for feed in feeds:
            if self._should_poll(feed):
                results[feed.name] = self.process_feed(feed)

        return results

    # Helper methods

    def _get_feed_name(self, url: str) -> str:
        """Get feed name from URL."""
        try:
            import feedparser

            feed = feedparser.parse(url)
            return feed.feed.get("title", url)
        except Exception:
            return url

    def _parse_feed_from_list(self, lst: dict) -> Feed:
        """Parse feed from Listmonk list."""
        tags = lst.get("tags", [])

        # Extract frequency
        freq_tag = next((t for t in tags if t.startswith("freq:")), None)
        if not freq_tag:
            raise ValueError("No frequency tag")
        frequency = Frequency(freq_tag.replace("freq:", ""))

        # Extract URL from description
        desc = lst.get("description", "")
        url = None
        for line in desc.split("\n"):
            if line.startswith("RSS Feed: "):
                url = line.replace("RSS Feed: ", "").strip()
                break

        if not url:
            raise ValueError("No URL in description")

        return Feed(id=lst["id"], name=lst["name"], url=url, frequency=frequency)

    def _find_new_articles(self, feed: Feed, articles: list) -> list:
        """Find new articles since last poll."""
        if not articles:
            return []

        # Get last seen GUID from tags
        lst = self._client.get(f"/api/lists/{feed.id}")
        tags = lst.get("tags", [])

        last_guid = None
        for tag in tags:
            if tag.startswith(f"last-seen:{feed.frequency.value}:"):
                last_guid = tag.split(":", 3)[3]
                break

        if not last_guid:
            return articles

        # Find new articles (those before last seen in chronological order)
        for i, article in enumerate(articles):
            if article.get("guid", article.get("link")) == last_guid:
                return articles[:i]

        return articles

    def _should_poll(self, feed: Feed) -> bool:
        """Check if feed should be polled."""
        config = FREQUENCIES.get(f"freq:{feed.frequency.value}")
        if not config:
            return False

        # Get last poll time from tags
        lst = self._client.get(f"/api/lists/{feed.id}")
        tags = lst.get("tags", [])

        last_poll = None
        for tag in tags:
            if tag.startswith(f"last-poll:{feed.frequency.value}:"):
                try:
                    last_poll = datetime.fromisoformat(tag.split(":", 3)[3])
                except (ValueError, IndexError):
                    continue

        now = datetime.now()

        # Interval-based check
        if config.get("interval_minutes"):
            if not last_poll:
                return True
            from datetime import timedelta

            return now - last_poll > timedelta(minutes=config["interval_minutes"])

        # Time-based check (daily/weekly)
        if config.get("check_time"):
            target_hour, target_minute = config["check_time"]

            if config.get("check_day") is not None:  # Weekly
                if now.weekday() != config["check_day"]:
                    return False
                if last_poll:
                    from datetime import timedelta

                    if last_poll > now - timedelta(weeks=1):
                        return False
            else:  # Daily
                if last_poll:
                    from datetime import timedelta

                    if last_poll > now - timedelta(days=1):
                        return False

            target_time = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
            return now >= target_time

        return False

    def _update_poll_time(self, feed: Feed):
        """Update poll time tag."""
        self._update_feed_state(feed, [])

    def _update_feed_state(self, feed: Feed, articles: list):
        """Update feed state in Listmonk tags."""
        lst = self._client.get(f"/api/lists/{feed.id}")
        tags = lst.get("tags", [])

        # Remove old state tags
        tags = [
            t
            for t in tags
            if not t.startswith(f"last-poll:{feed.frequency.value}:")
            and not t.startswith(f"last-seen:{feed.frequency.value}:")
        ]

        # Add new poll time
        now = datetime.now()
        tags.append(f"last-poll:{feed.frequency.value}:{now.isoformat()}")

        # Add latest GUID if we have articles
        if articles:
            latest_guid = articles[0].get("guid", articles[0].get("link", ""))
            tags.append(f"last-seen:{feed.frequency.value}:{latest_guid}")

        # Update list
        self._client.put(
            f"/api/lists/{feed.id}",
            {"name": feed.name, "description": feed.description, "tags": tags, "type": "public"},
        )

    def _create_campaign(self, feed: Feed, article: dict) -> int:
        """Create campaign for article."""
        title = article.get("title", "No title")
        link = article.get("link", "")
        description = article.get("description", "")
        published = article.get("published", "")
        author = article.get("author", "")

        # Create simple HTML content
        content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h1 style="color: #333; border-bottom: 2px solid #007cba; padding-bottom: 10px;">{title}</h1>
            
            <div style="margin: 20px 0; color: #666; font-size: 14px;">
                <p><strong>From:</strong> {feed.name}</p>
                {f"<p><strong>Published:</strong> {published}</p>" if published else ""}
                {f"<p><strong>Author:</strong> {author}</p>" if author else ""}
            </div>
            
            <div style="margin: 20px 0; line-height: 1.6;">
                {description}
            </div>
            
            <div style="margin: 30px 0; text-align: center;">
                <a href="{link}" style="background-color: #007cba; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; display: inline-block;">
                    Read Full Article
                </a>
            </div>
            
            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; color: #666; font-size: 12px; text-align: center;">
                <p>This email was sent automatically from RSS Monk</p>
                <p>Article URL: <a href="{link}">{link}</a></p>
            </div>
        </div>
        """

        campaign_name = f"RSS: {title[:50]}..." if len(title) > 50 else f"RSS: {title}"

        result = self._client.create_campaign(
            name=campaign_name,
            subject=title,
            body=content,
            list_ids=[feed.id],
            tags=["rss", "automated", feed.frequency.value],
        )

        return result["id"]
