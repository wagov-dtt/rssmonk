"""Simplified core models and service for RSS Monk."""

import hashlib
import hmac
import os
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from fastapi.security import HTTPBasicCredentials
import httpx
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from .cache import feed_cache
from .http_clients import ListmonkClient
from .logging_config import get_logger

# Feed frequency configurations
FREQUENCIES: dict[str, dict[str, Any]] = {
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

    @classmethod
    def ensure_env_file(cls) -> bool:
        """Create .env file with defaults if it doesn't exist. Returns True if created."""
        env_path = ".env"
        if os.path.exists(env_path):
            return False
            
        # Generate .env content from field definitions
        env_content = "# RSS Monk Configuration\n"
        env_content += "# Auto-generated - modify as needed\n\n"
        
        # Required fields
        env_content += "# Required - get from your Listmonk instance\n"
        env_content += "LISTMONK_APITOKEN=your-token-here\n\n"
        
        # Optional fields with defaults
        env_content += "# Optional - uncomment and modify as needed\n"
        
        # Get field info from model
        for field_name, field_info in cls.model_fields.items():
            if field_name == "listmonk_password":  # Skip - handled above
                continue
                
            alias = getattr(field_info, "alias", None) or field_name.upper()
            default = field_info.default
            description = getattr(field_info, "description", "")
            
            if default is not None:
                # Format the default value appropriately
                if isinstance(default, str):
                    default_str = f'"{default}"' if " " in default else default
                else:
                    default_str = str(default).lower() if isinstance(default, bool) else str(default)
                
                env_content += f"# {alias}={default_str}"
                if description:
                    env_content += f"  # {description}"
                env_content += "\n"
        
        try:
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(env_content)
            return True
        except OSError:
            return False


class Feed(BaseModel):
    """RSS feed model."""

    id: Optional[int] = None
    name: str
    url: str
    frequencies: list[Frequency]
    url_hash: str = ""

    def __init__(self, **data):
        super().__init__(**data)
        if not self.url_hash:
            self.url_hash = hashlib.sha256(self.url.encode()).hexdigest()

    @property
    def tags(self) -> list[str]:
        """Generate Listmonk tags."""
        return [f'freq:{x.value}' for x in self.frequencies] + [f"url:{self.url_hash}"]

    @property
    def description(self) -> str:
        """Generate Listmonk description."""
        return f"RSS Feed: {self.url}"


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
    """Main RSS Monk service - stateless, uses Listmonk for persistence. Should be used with"""
    def __init__(self, local_creds: Optional[HTTPBasicCredentials] = None, settings: Optional[Settings] = None):
        self.local_creds: Optional[HTTPBasicCredentials] = local_creds
        self.settings = settings or Settings()
        self.settings.validate_required()

    # Create two clients, local creds for access control and admin creds for use if required
    def __enter__(self):
        print(f'creds: {self.local_creds}')
        self._client = ListmonkClient(
            base_url=self.settings.listmonk_url,
            username=self.local_creds.username if self.local_creds is not None else "",
            password=self.local_creds.password if self.local_creds is not None else "",
            timeout=self.settings.rss_timeout,
        ).__enter__()
        self._admin = ListmonkClient(
            base_url=self.settings.listmonk_url,
            username=self.settings.listmonk_username,
            password=self.settings.listmonk_password,
            timeout=self.settings.rss_timeout,
        ).__enter__()
        return self

    def __exit__(self, *args):
        if hasattr(self, "_client"):
            self._client.__exit__(*args)
        if hasattr(self, "_admin"):
            self._admin.__exit__(*args)

    # Feed operations

    def add_feed(self, url: str, new_frequency: list[Frequency], name: Optional[str] = None) -> Feed:
        """Add RSS feed, handling existing URLs with different frequency configurations."""
        if not name:
            name = self._get_feed_name(url)

        # Create return
        feed = Feed(name=name, url=url, frequencies=new_frequency)

        # Check for existing feed with same URL
        existing_feed = self.get_feed_by_url(url)

        if existing_feed is None:
            # Create in Listmonk
            result = self._client.create_list(name=feed.name, description=feed.description, tags=feed.tags)
            feed.id = result["id"]
            
            # Invalidate cache for this URL to ensure fresh fetch
            feed_cache.invalidate_url(url)
        else:
            # No update required if the URL and frequencies are already covered
            if set(new_frequency) <= set(existing_feed.frequencies):
                raise ValueError(f"Feed with same URL and frequencies already exists: {url}")

            # Add new freq tags to end of the list and update
            for new_freq in new_frequency:
                if f"freq:{new_freq.value}" not in existing_feed.tags:
                    existing_feed.frequencies.append(new_freq)
                    existing_feed.tags.append(f"freq:{new_freq.value}")

            # Mandatory items
            payload = {
                "name": existing_feed.name,
                "description": existing_feed.description,
                "tags": existing_feed.tags,
            }
            self._client.update_list_data(existing_feed.id, payload)
        
        return existing_feed

    def list_feeds(self) -> list[Feed]:
        """list all feeds."""
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

    def delete_feed(self, url: str) -> bool: # Admin only
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

    def list_subscribers(self) -> list[Subscriber]:
        """list all subscribers."""
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

    async def process_feed(self, feed: Feed, auto_send: Optional[bool] = None) -> int:
        """Process single feed - fetch articles and create campaigns using cache."""
        if auto_send is None:
            auto_send = self.settings.rss_auto_send

        try:
            # Fetch articles using cache
            articles, feed_title = await feed_cache.get_feed(
                url=feed.url,
                user_agent=self.settings.rss_user_agent,
                timeout=self.settings.rss_timeout
            )

            # Get new articles (check against last poll tag)
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
        feeds = [f for f in self.list_feeds() if frequency in f.frequencies]
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

        # Extract frequency(ies)
        frequency_list: list[Frequency] = []
        for tag in tags:
            if tag.startswith("freq:"):
                frequency_list.append(Frequency(tag.replace("freq:", "")))
        if len(frequency_list) == 0:
            raise ValueError(f"No frequency tag found in existing list")

        # Extract URL from description
        desc = lst.get("description", "")
        url = None
        for line in desc.split("\n"):
            if line.startswith("RSS Feed: "):
                url = line.replace("RSS Feed: ", "").strip()
                break

        if not url:
            raise ValueError("No URL in description")

        return Feed(id=lst["id"], name=lst["name"], url=url, frequencies=frequency_list)

    def _find_new_articles(self, feed: Feed, articles: list) -> list:
        """Find new articles since last poll."""
        if not articles:
            return []

        # Get last seen GUID from tags
        lst = self._client.get(f"/api/lists/{feed.id}")
        tags = lst.get("tags", [])

        last_guid = None
        for tag in tags:
            # TODO - Figure out what this is for 
            if tag.startswith(f"last-seen:{feed.frequencies.value}:"):
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
        # TODO - Figure out what this is for 
        config = FREQUENCIES.get(f"freq:{feed.frequencies.value}")
        if not config:
            return False

        # Get last poll time from tags
        lst = self._client.get(f"/api/lists/{feed.id}")
        tags = lst.get("tags", [])

        last_poll = None
        for tag in tags:
            # TODO - Figure out what this is for 
            if tag.startswith(f"last-poll:{feed.frequencies.value}:"):
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
            # TODO - Figure out what this is for 
            if not t.startswith(f"last-poll:{feed.frequencies.value}:")
            and not t.startswith(f"last-seen:{feed.frequencies.value}:")
        ]

        # Add new poll time
        now = datetime.now()
        # TODO - Figure out what this is for 
        tags.append(f"last-poll:{feed.frequencies.value}:{now.isoformat()}")

        # Add latest GUID if we have articles
        if articles:
            latest_guid = articles[0].get("guid", articles[0].get("link", ""))
            # TODO - Figure out what this is for 
            tags.append(f"last-seen:{feed.frequencies.value}:{latest_guid}")

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
            # TODO - Figure out what this is for 
            tags=["rss", "automated", feed.frequencies.value],
        )

        return result["id"]



class RSSMonkAdmin:
    """Admin RSS Monk service. Handles users, access control and settings"""
    def __init__(self, password: str, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.settings.validate_required()
        if not hmac.compare_digest(self.settings.listmonk_password, password):
            raise ValueError("Admin authentication failed")

    # Create two clients, local creds for access control and admin creds for use if required
    def __enter__(self):
        print(f'creds: {self.local_creds}')
        self._client = ListmonkClient(
            base_url=self.settings.listmonk_url,
            username=self.local_creds.username if self.local_creds is not None else "",
            password=self.local_creds.password if self.local_creds is not None else "",
            timeout=self.settings.rss_timeout,
        ).__enter__()
        return self

    def __exit__(self, *args):
        if hasattr(self, "_client"):
            self._client.__exit__(*args)


    def find_api_user(self, username: str):
        pass


    def create_api_user(self, username: str) -> str: # TODO - User id and password
        """Create API user."""
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        lst = self._client.find_list_by_tag(f"url:{url_hash}")
        return self._parse_feed_from_list(lst) if lst else None


    def delete_api_user(self, username: str) -> str: # TODO - User id and password
        """Delete API user."""
        # TODO - Currently we delete and recreate the user here. That being said
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        lst = self._client.find_list_by_tag(f"url:{url_hash}")
        return self._parse_feed_from_list(lst) if lst else None


    def reset_api_user_password(self, username: str) -> str: # TODO - User id and password
        """Reset API user password."""
        # TODO - Currently we delete and recreate the user here.
        # In the future, Listmonk may have a reset api password functionality for us
        self.delete_api_user()
        self.create_api_user()


    def ensure_limited_role_exists(self):
        # TODO - Simple, check limited user role exists, if not, create as admin
        pass


    def ensure_list_role(self, url: str):
        # TODO - Simple, check limited list role exists for url, if not, create as admin
        pass

    def get_list_role_id_by_url(self, url: str) -> Optional[int]:
        # TODO - Check if we can query... by name... or just filter until we see the url number 
        self._client.get(f"/api/roles/lists")
        pass


    def delete_list_role(self, url: str):
        role_id = self.get_list_role_id_by_url(url)
        if role_id:
            self._client.delete(f"/api/roles/{role_id}")
            return True
        return False