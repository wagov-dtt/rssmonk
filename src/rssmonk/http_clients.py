"""HTTP client utilities."""

from fastapi import HTTPException
import httpx
import feedparser

from .logging_config import get_logger

logger = get_logger(__name__)


class ListmonkClient:
    """Listmonk API client with automatic JSON handling and error logging."""

    def __init__(self, base_url: str, username: str, password: str, timeout: float = 30.0):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.timeout = timeout

        if not self.password:
            raise ValueError("Listmonk password is required")

        self._client = None

    def __enter__(self):
        self._client = httpx.Client(
            base_url=self.base_url,
            auth=(self.username, self.password),
            timeout=self.timeout,
            headers={"Content-Type": "application/json"},
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            self._client.close()

    def _make_request(self, method, path, **kwargs):
        """Make HTTP request with retry logic and error handling."""
        try:
            response = self._client.request(method, path, **kwargs)
            response.raise_for_status()
            if method == "DELETE":
                return response.status_code == 200 # TODO - This should not be assumed
            if response.content:
                data = response.json()
                return data.get("data", data)
            return True
        except httpx.HTTPError as e:
            logger.error(f"HTTP {method} {path}: {e}")
            raise

    def get(self, path, params=None):
        """GET request."""
        return self._make_request("GET", path, params=params)

    def post(self, path, json_data):
        """POST request."""
        return self._make_request("POST", path, json=json_data)

    def put(self, path, json_data):
        """PUT request."""
        return self._make_request("PUT", path, json=json_data)

    def delete(self, path):
        """DELETE request."""
        return self._make_request("DELETE", path)

    def _normalize_results(self, data):
        """Normalize API response to always return a list."""
        if isinstance(data, dict) and "results" in data:
            return data["results"]
        elif isinstance(data, list):
            return data
        else:
            return [data] if data else []

    def get_lists(self, tag=None, per_page="all"):
        """Get all lists, optionally filtered by tag."""
        params = {"per_page": per_page}
        if tag:
            params["tag"] = tag
        data = self.get("/api/lists", params=params)
        print(data)
        return self._normalize_results(data)

    def find_list_by_tag(self, tag): # TODO - Change to find list by name because it wouldn't work likethis
        """Find a single list by tag."""
        lists = self.get_lists(tag=tag, per_page="1")
        return lists[0] if lists else None

    def create_list(self, name, description, tags, list_type="public", optin="single"):
        """Create a new list."""
        payload = {
            "name": name,
            "description": description,
            "tags": tags,
            "type": list_type,
            "optin": optin,
        }
        return self.post("/api/lists", payload)

    def get_subscribers(self, query=None):
        """Get subscribers, optionally filtered by query."""
        params = {"query": query} if query else {}
        data = self.get("/api/subscribers", params=params)
        # TODO - Change to alter attributes
        print("get_subscribers")
        return self._normalize_results(data)

    def create_subscriber(self, email, name=None, status="enabled", lists=None):
        """Create a new subscriber."""
        payload = {
            "email": email,
            "name": name or email,
            "status": status, # TODO - Change to confirmed
            "lists": lists or [],
            "preconfirm_subscriptions": True,
        }
        return self.post("/api/subscribers", payload)

    def subscribe_to_lists(self, subscriber_ids, list_ids, status="confirmed"):
        """Subscribe users to lists."""
        payload = {
            "ids": subscriber_ids,
            "action": "add",
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
        # TODO - Design is to remove campaigns as they are not useful to emailing... maybe?
        raise HTTPException(status_code=404, detail="Not found")
        #return self.post("/api/campaigns", payload)

    def start_campaign(self, campaign_id):
        """Start a campaign."""
        # TODO - Leave, because there's no campaigns to kick off...?
        self.put(f"/api/campaigns/{campaign_id}/status", {"status": "running"})
        return True


def create_client():
    """Create a Listmonk client with environment config."""
    return ListmonkClient()


def fetch_feed(feed_url: str, timeout: float = 30.0, user_agent: str = "RSS Monk/2.0"):
    """Fetch and parse RSS feed with retry logic."""
    try:
        logger.info(f"Fetching feed: {feed_url}")

        with httpx.Client(timeout=timeout, headers={"User-Agent": user_agent}) as client:
            response = client.get(feed_url)

            if response.status_code == 304:
                logger.info(f"Feed unchanged (304): {feed_url}")
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
                    "published": entry.get("published", ""),
                    "author": entry.get("author", ""),
                    "guid": guid,
                }
                articles.append(article)

            logger.info(f"Found {len(articles)} articles from {feed_url}")
            return articles, latest_guid

    except Exception as e:
        logger.error(f"Error fetching feed {feed_url}: {e}")
        return [], None
