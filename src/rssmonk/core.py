"""Simplified core models and service for RSS Monk."""

import os
import hmac
import traceback
from warnings import deprecated
import httpx
import uuid

from http import HTTPStatus
from fastapi import HTTPException
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from fastapi.security import HTTPBasicCredentials
from pydantic import Field
from pydantic_settings import BaseSettings

from rssmonk.models import EmailTemplate, Feed, Frequency, ListVisibilityType, Subscriber
from rssmonk.utils import make_list_role_name, make_template_name, make_url_hash, make_url_tag_from_hash, numberfy_subbed_lists
from rssmonk.types import AVAILABLE_FREQUENCY_SETTINGS, MULTIPLE_FREQ, SUB_BASE_URL, LIST_DESC_FEED_URL, TOPICS_TITLE, EmailPhaseType, ErrorMessages, FeedItem

from .cache import feed_cache
from .http_clients import AuthType, ListmonkClient
from .logging_config import get_logger


logger = get_logger(__name__)


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # Listmonk configuration
    listmonk_url: str = Field(default="http://localhost:9000", description="Listmonk API URL")
    listmonk_admin_username: str = Field(default="admin", alias="LISTMONK_ADMIN_USER", description="Listmonk admin username")
    listmonk_admin_password: str = Field(alias="LISTMONK_ADMIN_PASSWORD", description="Listmonk admin token/password")

    # RSS processing configuration
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
        if not self.listmonk_admin_password:
            raise ValueError("LISTMONK_ADMIN_PASSWORD environment variable is required")


    def validate_admin_auth(self, username: str, password: str) -> bool:
        # Only used as a quick check against settings (env vars) before going to work against Listmonk.
        # No real check against Listmonk. Could be done by getting user 1
        # TODO - Ping against Listmonk. Access it's own user_role and check for Super Admin as it's a reserved role.
        return hmac.compare_digest(password, self.listmonk_admin_password) and username == self.listmonk_admin_username


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
        env_content += "LISTMONK_ADMIN_PASSWORD=your-token-here\n\n"
        
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


class RSSMonk:
    """Main RSS Monk service - stateless, uses Listmonk for persistence. Should be used with"""
    def __init__(self, local_creds: Optional[HTTPBasicCredentials] = None, settings: Optional[Settings] = None):
        self.local_creds: Optional[HTTPBasicCredentials] = local_creds
        self.settings = settings or Settings()
        self.settings.validate_required()
        self._client = ListmonkClient(
            base_url=self.settings.listmonk_url,
            username=self.local_creds.username if self.local_creds is not None else "",
            password=self.local_creds.password if self.local_creds is not None else "",
            auth_type=AuthType.SESSION if self.settings.validate_admin_auth(
                self.local_creds.username if self.local_creds is not None else "",
                self.local_creds.password if self.local_creds is not None else "") else AuthType.BASIC,
            timeout=self.settings.rss_timeout
        )
        self._admin = ListmonkClient(
            base_url=self.settings.listmonk_url,
            username=self.settings.listmonk_admin_username,
            password=self.settings.listmonk_admin_password,
            auth_type=AuthType.SESSION,
            timeout=self.settings.rss_timeout
        )

    # Create two clients, local creds for access control and admin creds for use if required
    def __enter__(self):
        self._client.__enter__()
        self._admin.__enter__()
        return self

    def __exit__(self, *args):
            self._client.__exit__(*args)
            self._admin.__exit__(*args)

    def getClient(self):
        return self._client
    
    def getAdminClient(self):
        return self._admin

    def validate_feed_visibility(self, feed_hash: str | None = None):
        '''
        Check if the active credentials can see the feed's list, raises HTTP return codes otherwise.
        '''
        if not feed_hash:
            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Not permitted to interact with this feed")

        # Hash is used as a higher priority than the url
        found_feed = self._client.find_list_by_tag(tag=make_url_tag_from_hash(feed_hash))
        if found_feed is None:
            if self._client.username == self._admin.username:
                # Give actual response to admins
                raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Feed does not exist")
            else:
                raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail=ErrorMessages.NO_AUTH_FEED)


    # Account operations


    def get_user_by_name(self, api_name: str) -> dict | None:
        """Get user by name"""
        user_list = self._admin.get_users()
        if user_list is not None and isinstance(user_list, list):
            for user in user_list:
                if isinstance(user, dict) and user["username"] == api_name:
                    return user
        return None


    def create_api_user(self, api_name: str, user_role_id: int, list_role_id: int) -> dict:
        """Create API user."""
        # Pull password from secrets (would rather push up but TBD)
        data = {
            "username": api_name,
            "email": "", "name":"",
            "type": "api", "status": "enabled",
            "password": None, "password_login": False,
            "password2": None, "passwordLogin": False,
            "userRoleId": user_role_id, "listRoleId": list_role_id,
            "user_role_id": user_role_id, "list_role_id": list_role_id
        }

        try:
            response = self._admin.post("/api/users", data)
            if not isinstance(response, dict):
                raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
            
            return response
        except httpx.HTTPStatusError as e:
            if (e.response.status_code == 500 and ("already exists" in e.response.text)):
                # Already exists, return error so they can recreate account, or bail
                raise HTTPException(status_code=HTTPStatus.CONFLICT)
            else:
                raise


    def delete_api_user(self, api_name: str) -> bool: # TODO - User id and password
        """Delete API user."""
        users = self.get_user_by_name(api_name)
        if users is None:
            return True # Count as deleted

        return self._admin.delete(f"/api/users/{users["id"]}")


    def reset_api_user_password(self, username: str) -> dict:
        """Reset API user password. This function only makes a user with no roles attached to it"""
        # Currently we delete and recreate the user here.
        # In the future, Listmonk may have a reset api password functionality
        self.delete_api_user(username)
        return self.create_api_user(username)
    

    def ensure_limited_user_role_exists(self) -> int:
        """Obtains the limited user role ID. Creates the role if it does not exist"""
        role_name = "limited-user-role"
        payload= {
            "name": role_name,
            "permissions": [
                "subscribers:get",
                "subscribers:manage",
                "tx:send",
                "templates:get"
            ]
        }

        try:
            response = self._admin.post("api/roles/users", payload)
            return response["id"]
        except httpx.HTTPStatusError as e:
            # Should be 409, but quickest way
            if not (e.response.status_code == 500 and ("already exists" in e.response.text)):
                raise
            
            # User role already exists. Find the user role with the same name
            user_roles = self._admin.get("api/roles/users")
            for role in user_roles:
                if isinstance(role, dict) and role["name"] == role_name:
                    return role["id"]


    def ensure_list_role_by_url(self, url: str) -> int:
        return self.ensure_list_role_by_hash(make_url_hash(url))


    def ensure_list_role_by_hash(self, feed_hash: str) -> int:
        list_role_name = make_list_role_name(feed_hash)

        # Retrieve the list to get its ID for role creation.
        list_data = self._admin.find_list_by_tag(make_url_tag_from_hash(feed_hash))
        if list_data is None:
            raise HTTPException(status_code=HTTPStatus.UNPROCESSABLE_CONTENT, detail="List does not exist")

        # Attempt to create the role. If it exists retrieve the ID
        payload = {
            "name": list_role_name, # Name is unique
            "lists": [ {"id": list_data["id"], "permissions": ["list:get","list:manage"] } ]
        }

        try:
            response = self._admin.post("/api/roles/lists", payload)
            if isinstance(response, dict):
                return response["id"]
        except httpx.HTTPStatusError as e:
            if not (e.response.status_code == 500 and ("already exists" in e.response.text)):
                raise

            # User role already exists, fetch the ID
            return self.get_list_role_id_by_hash(feed_hash)


    def get_list_role_id_by_url(self, url: str) -> int:
        return self.get_list_role_id_by_hash(make_url_hash(url))


    def get_list_role_id_by_hash(self, feed_hash: str) -> int:
        list_role_name = make_list_role_name(feed_hash)

        list_roles = self._client.get("api/roles/lists")
        for list_role in list_roles:
            if isinstance(list_role, dict) and list_role["name"] == list_role_name:
                return list_role["id"]
        return -1


    def delete_list_role(self, url: str):
        role_id = self.get_list_role_id_by_url(url)
        if role_id > 0:
            try:
                self._client.delete(f"/api/roles/{role_id}")
            except:
                # Log on failure, will try to fix later
                logger.error("Failed to delete list role {role_id}")
        return True


    # Feed operations

    def add_feed(self, feed_url: str, email_base_url: str, new_frequency: list[Frequency], filter_groups: list[str],
                 name: Optional[str] = None, visibility: ListVisibilityType = ListVisibilityType.PRIVATE) -> Feed:
        """Add RSS feed, handling existing URLs with different frequency configurations."""
        if not name:
            name = self._get_feed_name(feed_url)

        # Create return
        feed = Feed(name=name, feed_url=feed_url, poll_frequencies=new_frequency, filter_groups=filter_groups, email_base_url=email_base_url)

        # Check for existing feed with same URL
        existing_feed = self.get_feed_by_url(feed_url)

        if existing_feed is None:
            # Create in Listmonk
            result = self._client.create_list(name=feed.name, description=feed.description, tags=feed.tags, list_type=visibility)
            feed.id = result["id"]
            
            # Invalidate cache for this URL to ensure fresh fetch
            feed_cache.invalidate_url(feed_url)
            return feed
        else:
            # No update required if the URL and frequencies are already covered
            if set(new_frequency) <= set(existing_feed.poll_frequencies):
                raise HTTPException(status_code=HTTPStatus.CONFLICT, detail=f"Feed with same URL and frequency combination already exists: {feed_url}")

            # Add new freq tags to end of the list and update
            for new_freq in new_frequency:
                if f"freq:{new_freq.value}" not in existing_feed.tags:
                    existing_feed.poll_frequencies.append(new_freq)
                    existing_feed.tags.append(f"freq:{new_freq.value}")

            payload = {
                "name": existing_feed.name,
                "description": existing_feed.description,
                "tags": existing_feed.tags,
            }
            self._client.update_list_data(existing_feed.id, payload)
            return existing_feed

    def list_feeds(self, freq: Optional[Frequency] = None) -> list[Feed]:
        """list all feeds. Optional freq to list all feeds by freq type"""
        feeds = []
        lists = self._client.get_lists(tag=f"freq:{freq.value}" if freq is not None else None)
        for lst in lists:
            try:
                feed = self._parse_feed_from_list(lst)
                feeds.append(feed)
            except Exception as e:
                logger.warning(f"Could not parse feed. Skipping {lst.get('name')}: {e}")

        # Deduplicate by ID
        return list({f.id: f for f in feeds if f.id}.values())

    def get_feed_by_url(self, url: str) -> Optional[Feed]:
        """Get feed by URL."""
        return self.get_feed_by_hash(make_url_hash(url))

    def get_feed_by_hash(self, url_hash: str) -> Optional[Feed]:
        """Get feed by URL."""
        lst = self._client.find_list_by_tag(f"url:{url_hash}")
        return self._parse_feed_from_list(lst) if lst else None

    def delete_feed(self, url: str) -> bool: # Admin only
        """Delete feed by URL."""
        feed = self.get_feed_by_url(url)
        if feed and feed.id:
            self._client.delete(f"/api/lists/{feed.id}")
            return True
        return False


    # Template operations
    # TODO - Set up map, name to template id, if there are many, for caching

    def get_template(self, feed_hash: str, phase_type: EmailPhaseType):
        """Get a template associated with a feed and template type"""
        # TODO - Future cache here
        return self._admin.find_email_template(feed_hash, phase_type)

    def add_update_template(self, feed_hash: str, phase_type: EmailPhaseType, new_template: EmailTemplate):
        """Insert or update an email template for a feed"""
        template = self._admin.find_email_template(feed_hash, phase_type)
        if template is None:
            return self._admin.create_email_template(new_template)
        else:
            return self._admin.update_email_template(template.id, new_template)

    def delete_template(self, feed_hash: str, phase_type: EmailPhaseType):
        """Delete singular templates associated with the feed"""
        template_name = make_template_name(feed_hash, phase_type)
        templates = self._admin.get_templates()
        for template in templates:
            if template_name == template["name"]:
                return self._admin.delete_email_template(template["id"])
        return False

    def delete_feed_templates(self, feed_url: str):
        """Delete all templates associated with the feed"""
        templates = self._admin.get_templates()
        url_hash = make_url_hash(str(feed_url))
        for template in templates:
            if url_hash in template["name"]:
                self._admin.delete_email_template(template["id"])


    # Subscriber operations. Data from these functions should not leak attributes 

    def add_subscriber(self, email: str, name: Optional[str] = None) -> Subscriber:
        """Add subscriber."""
        result = self._admin.create_subscriber(email=email, name=name or email)
        return Subscriber(id=result["id"], email=result["email"], name=result["name"])

    def get_subscriber_feed_filter(self, email: str) -> Optional[dict]:
        """Get existing subscriber's data block."""
        subs = self._admin.get_subscribers(query=f"subscribers.email='{email}'")
        if subs:
            s = subs[0]
            return s["attribs"]
        return None

    def get_subscriber_by_uuid(self, uuid: str) -> Optional[dict]:
        """Get existing subscriber's data block."""
        subs = self._admin.get_subscribers(query=f"subscribers.uuid = '{uuid}'")
        if subs:
            s = subs[0]
            return s["uuid"]
        return None

    def get_subscriber_uuid(self, email: str) -> str:
        """Get existing subscriber's data block."""
        subs = self._admin.get_subscribers(query=f"subscribers.email='{email}'")
        if subs:
            s = subs[0]
            return s["uuid"]
        
        logger.error("Subscriber (%s) is missing uuid", email)
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="")

    def get_or_create_subscriber(self, email: str) -> Subscriber:
        """Get existing or create new subscriber."""
        subs = self._admin.get_subscribers(query=f"subscribers.email='{email}'")
        if subs:
            s = subs[0]
            return Subscriber(id=s["id"], email=s["email"]) # Listmonk will populate name from the email
        return self.add_subscriber(email)

    def list_subscribers(self) -> list[Subscriber]:
        """list all subscribers."""
        subs = self._client.get_subscribers()
        return [Subscriber(id=s["id"], email=s["email"], name=s["name"]) for s in subs]

    def subscribe(self, email: str, feed_hash: str) -> bool:
        """Subscribe email to feed."""
        subscriber = self.get_or_create_subscriber(email)
        feed = self.get_feed_by_hash(feed_hash)
        if not feed or not feed.id:
            raise ValueError(f"Feed not found: {feed_hash}")

        self._client.subscribe_to_list([subscriber.id], [feed.id])
        return True

    def unsubscribe(self, email: str, feed_hash: Optional[str]) -> bool:
        """Subscribe email to feed."""
        subscriber = self.get_or_create_subscriber(email)
        feed = self.get_feed_by_hash(feed_hash)
        if not feed or not feed.id:
            raise ValueError(f"Feed not found: {feed_hash}")

        self._client.unsubscribe_from_list([subscriber.id], [feed.id])

        return True
    
    def update_subscriber_filter(self, email: str, sub_filter: dict, feed_hash: str,
                                 bypass_confirmation: bool = False) -> Optional[str]:
        """Adds either a pending filter, or main filter. Returns uuid of the pending filter if confirmation is required"""
        feed = self.get_feed_by_hash(feed_hash)
        sub_list = self._admin.get_subscribers(query=f"subscribers.email='{email}'")
        subs: dict = sub_list[0] if sub_list is not None else None

        if not feed or not feed.id:
            raise ValueError(f"Feed not found: {feed_hash}")
        if not subs:
            raise ValueError(f"Subscriber not found: {email}")

        # Attribs format - url-hash and uuids are permitted to be many
        # attribs: {
        #   url_hash: {
        #     active: dict
        #     uuid: {
        #       filter: dict
        #       expires: timestamp
        #     }
        #   }
        # }
        attribs = subs["attribs"]
        url_dict = attribs[feed_hash] if feed_hash in attribs else {}
        filter_uuid = uuid.uuid4().hex
        if not bypass_confirmation:
            # Add filter with 24 hours expiry
            timestamp = int((datetime.now(timezone.utc) + timedelta(days=1)).timestamp())
            url_dict[filter_uuid] = {"filter": sub_filter, "expires": timestamp}
        else:
            url_dict = {"filter": sub_filter}
            # Generate the token that will be used in email to help validate the removal of the subscription
            url_dict["token"] = uuid.uuid4().hex
        attribs[feed_hash] = url_dict

        # Have to covert the extracted lists to be a list of numbers to retain subscriptions
        subs["lists"] = numberfy_subbed_lists(subs["lists"])

        # Update the subscriber
        self._client.update_subscriber(subs["id"], subs)
        return None if bypass_confirmation else filter_uuid


    def remove_subscriber_filter(self, email: str, feed_hash: str):
        """Removes the feed hash from the attribs"""
        sub_list = self._admin.get_subscribers(query=f"subscribers.email='{email}'")
        subs: dict = sub_list[0] if sub_list is not None else None

        if not subs:
            return # Count as removed

        # Attribs format
        # attribs
        # - url_hash
        attribs = subs["attribs"]
        del attribs[feed_hash]

        # Have to covert the extracted lists to be a list of numbers to retain subscriptions
        subs["lists"] = numberfy_subbed_lists(subs["lists"])

        if len(subs["lists"]) > 0:
            # Update the subscriber
            self._client.update_subscriber(subs["id"], subs)
        else:
            self.getAdminClient().delete_subscriber(subs["id"])


    # Feed processing

    async def process_feed(self, feed: Feed, frequency: Frequency) -> Tuple[int, int]:
        """Process single feed - fetch articles and send tx  using cache."""
        try:
            # Fetch articles using cache
            articles, feed_title = await feed_cache.get_feed(
                url=feed.feed_url,
                user_agent=self.settings.rss_user_agent,
                timeout=self.settings.rss_timeout
            )

            # Get new articles (check against last poll tag)
            new_articles = self._find_new_articles(feed, articles)

            if not new_articles:
                self._update_poll_time(feed, frequency)
                return 0, 0

            feed_hash = make_url_hash(feed.feed_url)
            notifications_sent = 0 # This counts successful emails sent by unique email addresses
            subscribers = self.getClient().get_all_feed_subscribers(feed.id)

            # TODO - Generate all inclusive email case to prevent generating it continously
            # TODO - What to do with multiple instant notifications
            all_inclusive_email = ""

            # Extract list of subscribers, generate urls for the template and them email out.
            # Populate - If multiple articles exist and it is instant, ensure that one email per article is sent out
            # Send out
            for subscriber in subscribers:
                if "email" not in subscriber:
                    continue

                email = subscriber["email"]
                # If the filter_groups in the feed are present in the subscriber filter and they ask for all, then add to all_filter
                feed_hash_data = subscriber["attribs"][feed_hash]
                filter_freq_data = feed_hash_data["filter"][frequency.value]
                # TODO - The urls can be generated and stored for use later... would be better generated once
                unsub_url = feed_hash_data["unsub_segment"]
                subscription_url = feed_hash_data["filter_segment"]
                if feed.filter_groups is None: # TODO - Add or for having all marked 
                    # TODO - make dict for these urls and sent it with the data... (are there limits?)
                    pass

                notifications_sent += 1

            # Update state
            self._update_feed_state(feed, frequency, new_articles)
            return notifications_sent, new_articles

        except Exception as e:
            logger.error(f"Feed processing failed for {feed.name}: {e}")
            traceback.print_exc()
            return 0, 0


    async def process_feeds_by_frequency(self, frequency: Frequency) -> dict:
        """Process all feeds of given frequency that are due."""
        feeds = [f for f in self.list_feeds() if frequency in f.poll_frequencies]
        results = {}

        for feed in feeds:
            # TODO - Only handing instant and not the others
            if self._should_poll(frequency, feed):
                print(f"Processing {frequency.value} {feed.name}")
                results[feed.name], _ = await self.process_feed(feed, frequency)

        # TODO - Consider using for loop below if needing to handle each feed on a thread
        # Form a list of independant processings
        #tasks = {}
        #async with asyncio.TaskGroup() as tg:
        #    for feed in feeds:
        #        if self._should_poll(frequency, feed):
        #            tasks[feed.name] = tg.create_task(self.process_feed(feed))
        # Extract the results
        #for name, task in tasks.items():
        #    results[name] = asyncio.Task(task).result()

        return results

    # Helper methods

    def _get_feed_name(self, url: str) -> str:
        """Get feed name from URL if one can be found, or the URL."""
        try:
            import feedparser

            feed = feedparser.parse(url)
            return feed.get("title", url)
        except Exception:
            return url

    def _parse_feed_from_list(self, data: dict) -> Feed:
        """Parse feed from Listmonk list."""
        tags = data.get("tags", [])

        # Extract frequencies
        frequency_list: list[Frequency] = []
        for tag in tags:
            if tag.startswith("freq:"):
                try:
                    frequency_list.append(Frequency(tag.replace("freq:", "")))
                except ValueError:
                    logger.error(f"Invalid frequency in tag {tag} for list ID {data.get("id"), "unknown"}")
        if len(frequency_list) == 0:
            raise ValueError("No frequency tag found in existing list")

        # Extract details from the description
        desc = data.get("description", "")
        mult_freq = False
        url = None
        sub_url = None
        topics = None

        for line in desc.split("\n"):
            if line.startswith(LIST_DESC_FEED_URL):
                url = line.replace(LIST_DESC_FEED_URL, "").strip()
            if line.startswith(SUB_BASE_URL):
                sub_url = line.replace(SUB_BASE_URL, "").strip()
            if line.startswith(TOPICS_TITLE):
                topics = line.replace(TOPICS_TITLE, "").strip().split(',')
            if line.startswith(MULTIPLE_FREQ):
                mult_freq = (line.replace(MULTIPLE_FREQ, "").strip() == str(True))
            if url and sub_url:
                break

        # These will raise error reports up the processing chain
        if not url:
            raise ValueError("No URL in description")
        if not sub_url:
            raise ValueError("No Subscription URL in description")

        return Feed(id=data["id"], name=data["name"], feed_url=url, poll_frequencies=frequency_list,
                    filter_groups=topics, email_base_url=sub_url, mult_freq=mult_freq)


    def _find_new_articles(self, feed: Feed, articles: list[FeedItem]) -> list[FeedItem]:
        """Find new articles since last poll."""
        if not articles:
            return []

        # Get last seen GUID from tags
        lst = self._client.get(f"/api/lists/{feed.id}")
        tags = lst.get("tags", [])

        last_guid = None
        for tag in tags:
            if str(tag).startswith(f"last-guid:"):
                last_guid = str(tag).split(":", 3)[2]
                break

        if not last_guid:
            return articles

        # Find new articles (those before last seen in chronological order)
        for i, article in enumerate(articles):
            if article.get("guid", article.get("link")) == last_guid:
                return articles[:i] # Slice it up to the last guid

        return articles

    def _should_poll(self, current_frequency: Frequency, feed: Feed) -> bool:
        """Determine if a feed should be polled based on frequency settings."""
        now = datetime.now()

        config = AVAILABLE_FREQUENCY_SETTINGS().get(f"freq:{current_frequency.value}")
        if not config:
            return False

        # Get last poll time from tags
        lst = self._client.get(f"/api/lists/{feed.id}")
        tags = lst.get("tags", [])

        last_poll = None
        for tag in tags:
            if str(tag).startswith(f"last-process:{current_frequency.value}:"):
                try:
                    last_poll = datetime.fromisoformat(tag.split(":", 3)[3])
                except (ValueError, IndexError):
                    continue

        # If no last_poll data, allow polling immediately to get the data into the list
        if not last_poll:
            return True

        # Interval-based check (instant)
        if config.get("interval_minutes"):
            return now - last_poll > timedelta(minutes=config["interval_minutes"]) # Is this adding time? Should be substracting time

        # Time-based check (daily/weekly)
        if config.get("check_time"):
            target_hour, target_minute = config["check_time"]
            target_time = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)

            # Increased tolerance for negative drift
            if last_poll and last_poll > now - timedelta(weeks=1, minutes=15):
                return True


            return now >= target_time

        return False

    def _update_poll_time(self, feed: Feed, frequency: Frequency):
        """Update poll time tag."""
        self._update_feed_state(feed, frequency, [])

    def _update_feed_state(self, feed: Feed, frequency: Frequency, articles: list):
        """Update feed state in Listmonk tags."""
        lst = self._client.get(f"/api/lists/{feed.id}")
        tags = lst.get("tags", [])

        # Replace last-process tag
        now = datetime.now()
        tags = [ t for t in tags if not str(t).startswith(f"last-process:{frequency.value}:") ]
        tags.append(f"last-process:{frequency.value}:{now.isoformat()}")

        # Add latest GUID if we have articles
        # TODO - This does not create last-guid
        if articles and len(articles) > 0:
            latest_guid = articles[0].get("guid", articles[0].get("link", ""))
            # Replace last-guid guid
            tags = [ t for t in tags if not str(t).startswith(f"last-guid:") ]
            tags.append(f"last-guid:{frequency.value}:{latest_guid}")

        # Update list
        self._client.put(
            f"/api/lists/{feed.id}",
            {"name": feed.name, "description": feed.description, "tags": tags},
        )

    def _create_campaign(self, feed: Feed, article: dict) -> int:
        """Create campaign for article."""
        title = article.get("title", "No title")
        link = article.get("link", "")
        description = article.get("description", "")
        published = article.get("pubDate", "")
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
            tags=["rss", "automated", feed.poll_frequencies.value],
        )

        return result["id"]
