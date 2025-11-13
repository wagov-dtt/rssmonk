"""HTTP client utilities."""

from enum import Enum
from typing import Optional
from warnings import deprecated
from fastapi import HTTPException
from http import HTTPMethod, HTTPStatus
import httpx
import feedparser
import requests

from rssmonk.models import EmailTemplate, ListmonkTemplate
from rssmonk.utils import make_template_name
from rssmonk.types import EmailPhaseType

from .logging_config import get_logger

logger = get_logger(__name__)

class AuthType(str, Enum):
    """Authentication method type."""
    BASIC = "basic"
    SESSION = "session"

class ListmonkClient:
    """Listmonk API client with automatic JSON handling and error logging."""

    def __init__(self, base_url: str, username: str, password: str, auth_type: AuthType, timeout: float = 30.0):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.auth_type = auth_type
        self.timeout = timeout

        if not self.username:
            raise ValueError("Listmonk username is required")

        if not self.password:
            raise ValueError("Listmonk password is required")

        self._client = None


    def __enter__(self):
        if self.auth_type == AuthType.SESSION:
            self.cookies = self._init_listmonk_session()

        self._client = httpx.Client(
            base_url=self.base_url,
            auth=httpx.BasicAuth(username=self.username, password=self.password) if self.auth_type == AuthType.BASIC else None,
            cookies=self.cookies if self.auth_type == AuthType.SESSION else None,
            timeout=self.timeout,
            headers={"Content-Type": "application/json"},
        )   
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            self._client.close()
            self._client = None

    def _init_listmonk_session(self) -> dict:
        session = requests.Session()
        # Collect the nonce from the login page to satisfy CSRF protection
        response = session.get(f'{self.base_url}/admin/login')
        login_data={
            'username': self.username,
            'password': self.password,
            'nonce': session.cookies['nonce'],
            'next': '/admin'
        }

        response = session.post(f'{self.base_url}/admin/login', data=login_data, allow_redirects=False, timeout=30)
        if response.status_code == 302:
            return {
                'nonce': session.cookies['nonce'],
                'session': session.cookies['session'],
            }
        else:
            raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED)

    def _make_request(self, method, path, **kwargs):
        """Make HTTP request with error handling."""
        try:
            response = self._client.request(method, path, **kwargs)
            response.raise_for_status()
            if method == HTTPMethod.DELETE:
                return response.status_code == HTTPStatus.OK
            if response.content:
                data = response.json()
                # Listmonk idiosyncrasy
                return data.get("data", data)
            return True
        except httpx.HTTPError as e:
            logger.error("HTTP %s %s: %s", method, path, e)
            print(e.with_traceback(None))
            raise e

    def get(self, path, params=None):
        """GET request."""
        return self._make_request(HTTPMethod.GET, path, params=params)

    def post(self, path, json_data):
        """POST request."""
        return self._make_request(HTTPMethod.POST, path, json=json_data)

    def put(self, path, json_data):
        """PUT request."""
        return self._make_request(HTTPMethod.PUT, path, json=json_data)

    def delete(self, path):
        """DELETE request."""
        return self._make_request(HTTPMethod.DELETE, path)

    def _normalize_results(self, data):
        """Normalize API response to always return a list."""
        if isinstance(data, dict) and "results" in data:
            return data["results"]
        elif isinstance(data, list):
            return data
        else:
            return [data] if data else []

    def get_lists(self, name: Optional[str] = None, tag: str = None, per_page: str = "all"):
        """Get all lists, optionally filtered by tag."""
        # "minimal": True is used in urls to Listmonk to get ascending id, but does not work here.
        params = {"per_page": per_page}
        if name:
            params["query"] = name

        if tag:
            params["tag"] = tag
        data = self.get("/api/lists", params=params)
        print(params)
        return self._normalize_results(data)

    def find_list_by_name(self, name):
        """Find a single list by tag."""
        lists = self.get_lists(name=name, per_page="1")
        return lists[0] if lists else None

    def find_list_by_tag(self, tag):
        """Find a single list by tag."""
        lists = self.get_lists(tag=tag, per_page="1")
        return lists[0] if lists else None

    def create_list(self, name, description, tags:list[str], list_type="private", optin="single"):
        """Create a new list."""
        payload = {
            "name": name,
            "description": description,
            "tags": tags,
            "type": list_type,
            "optin": optin,
        }
        return self.post("/api/lists", payload)

    def update_list_data(self, ident: str, data):
        """Update a new list."""
        return self.put(f"/api/lists/{ident}", data)

    def get_subscribers(self, query=None):
        """Get subscribers, optionally filtered by query. Filters are not applied here"""
        params = {"query": query} if query else {}
        data = self.get("/api/subscribers", params=params)
        return self._normalize_results(data)

    def create_subscriber(self, email, name=None, status="enabled", lists=None):
        """Create a new subscriber."""
        payload = {
            "email": email,
            "name": name or email,
            "status": status,
            "lists": lists or [],
            "pre_subscriptions": True,
        }
        return self.post("/api/subscribers", payload)

    def update_subscriber(self, sub_id: int, body: dict):
        """Update a subscriber."""
        payload = {
            "email": body["email"],
            "name": body["name"],
            "status": body.get("status","enabled"),
            "lists": body["lists"], # Needs to be a list of numbers
            "attribs": body["attribs"],
            "preconfirm_subscriptions": True, # This API will handle confirmations
        }
        # TODO - May need to investigate if an etag system is required for attribs
        response = self.put(f"/api/subscribers/{sub_id}", payload)
        return response
    
    def delete_subscriber(self, sub_id: int):
        """Delete a subscriber."""
        response = self.delete(f"/api/subscribers/{sub_id}")
        return response

    def subscribe_to_list(self, subscriber_ids: list[int], list_ids: list[int], status="confirmed"):
        """Subscribe users to lists."""
        payload = {
            "ids": subscriber_ids,
            "action": "add",
            "target_list_ids": list_ids,
            "status": status,
        }
        self.put("/api/subscribers/lists", payload)        
        return True

    def unsubscribe_from_list(self, subscriber_ids: list[int], list_ids: list[int], status="unsubscribed"):
        """Subscribe users to lists."""
        payload = {
            "ids": subscriber_ids,
            "action": "remove",
            "target_list_ids": list_ids,
            "status": status,
        }
        self.put("/api/subscribers/lists", payload)        
        return True

    def create_campaign(self, name, subject, body, list_ids, campaign_type="regular", content_type="html", tags=None):
        """Create a new campaign."""
        payload = {
            "name": name,
            "subject": subject,
            "body": body,
            "lists": list_ids,
            "type": campaign_type,
            "content_type": content_type,
            "tags": tags or [],
        }

        # Not really required except for a mass unsubscribe
        return self.post("/api/campaigns", payload)

    def start_campaign(self, campaign_id):
        """Start a campaign."""
        self.put(f"/api/campaigns/{campaign_id}/status", {"status": "running"})
        return True

    def get_templates(self):
        """Get all templates."""
        data = self.get("/api/templates")
        return self._normalize_results(data)

    def find_email_template(self, feed_hash: str, template_type: EmailPhaseType) -> ListmonkTemplate | None:
        """Find a single email template."""
        template_name = make_template_name(feed_hash, template_type)
        templates = self.get_templates()
        for template in templates:
            if template["name"] == template_name:
                return template
        return None

    def create_email_template(self, template: EmailTemplate):
        """Create the email template"""
        payload = {
            "name": template.name,
            "type": "tx",
            "subject": template.subject,
            "body": template.body
        }
        return self.post("/api/templates", payload)

    def update_email_template(self, ident: int, template: EmailTemplate):
        """Update the email template"""
        payload = {
            "name": template.name,
            "type": "tx",
            "subject": template.subject,
            "body": template.body
        }
        return self.put(f"/api/templates/{ident}", payload)

    def delete_email_template(self, template_id: int):
        return self.delete(f"/api/templates/{template_id}")

    def send_transactional(self, reply_email: str, template_id: int, content_type: str, data: dict, subject: str | None = None):
        """Send transactional email."""
        payload = {
            "subscriber_emails": data["subscriber_emails"],
            "from_email": reply_email,
            "template_id": template_id,
            "data": data,
            "content_type": content_type
        }
        if subject is not None:
            payload["subject"] = subject

        return self.post("/api/tx", payload)

    def get_users(self) -> list | None:
        """Get the user list."""
        data = self.get("/api/users")
        return self._normalize_results(data)


@deprecated("Should not be used.")
# TODO - Why is this here?
def fetch_feed(feed_url: str, timeout: float = 30.0, user_agent: str = "RSS Monk/2.0"):
    """Deprecarted - Fetch and parse RSS feed. """
    try:
        logger.info("Fetching feed: %s", feed_url)

        with httpx.Client(timeout=timeout, headers={"User-Agent": user_agent}) as client:
            #response = client.get(feed_url + FEED_URL_RSSMONK_QUERY)
            response = client.get(feed_url)

            if response.status_code == 304:
                logger.info("Feed unchanged (304): %s", feed_url)
                return [], None

            response.raise_for_status()

            # Parse feed
            feed = feedparser.parse(response.content)

            if feed.bozo:
                logger.warning(f"Feed has issues: {feed.bozo_exception}")

            articles = []
            latest_guid = None

            for entry in feed.entries:
                guid = entry.get("id", entry.get("link", ""))
                if not latest_guid:
                    latest_guid = guid

                article = {
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "description": entry.get("description", ""),
                    "published": entry.get("pubDate", ""),
                    "guid": guid,
                    "dc:creator": entry.get("dc:creator", ""),
                    "wa:identifiers": entry.get("wa:identifiers", ""),
                }
                # TODO - RSS feed may, or may not supply old articles, this must be cleaned out to ensure duplication does not occur
                articles.append(article)

            logger.info(f"Found {len(articles)} articles from {feed_url}")
            return articles, latest_guid

    except Exception as e:
        logger.error(f"Error fetching feed {feed_url}: {e}")
        return [], None
