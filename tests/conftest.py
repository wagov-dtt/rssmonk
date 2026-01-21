"""
Test Configuration - Grugbrain Edition

Simple test infrastructure that provides:
- Service URLs and credentials
- ListmonkClientTestBase for class-based tests with initialise_system()
- Helper functions for common operations
- Fixtures for API server lifecycle

Tests connect to:
- RSS Monk API at localhost:8000 (started by this fixture)
- Listmonk at localhost:9000 (running in k3d)
- Mailpit at localhost:8025 (running in k3d)
"""

import os
import signal
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import pytest
import requests
from requests.auth import HTTPBasicAuth

from rssmonk.utils import make_url_hash

# ---------------------------------------------------------------------------
# URLs - where services live
# ---------------------------------------------------------------------------
RSSMONK_URL = "http://localhost:8000"
LISTMONK_URL = "http://localhost:9000"
MAILPIT_URL = "http://localhost:8025"

# ---------------------------------------------------------------------------
# Timeouts
# ---------------------------------------------------------------------------
REQUEST_TIMEOUT = 5

# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------
# Listmonk admin (for session-based auth to Listmonk admin UI)
LISTMONK_ADMIN_USER = "admin"
LISTMONK_ADMIN_PASSWORD = "admin123"

# RSS Monk API user (created fresh each test session)
RSSMONK_API_USERNAME = "rssmonk-api"

# Populated by api_server fixture
API_USERNAME = ""
API_PASSWORD = ""

# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------
PID_FILE = Path("/tmp/rssmonk-api.pid")
LOG_FILE = Path("/tmp/rssmonk-api.log")


# ---------------------------------------------------------------------------
# Test Feed URLs - using the built-in test feed endpoint
# ---------------------------------------------------------------------------
TEST_FEED_URL = f"{RSSMONK_URL}/test/feed"
TEST_FEED_HASH = make_url_hash(TEST_FEED_URL)


# ===========================================================================
# LIFECYCLE PHASES - controls what test data is set up
# ===========================================================================


class UnitTestLifecyclePhase(Enum):
    """Phases of test data setup. Each phase includes all previous phases."""

    CLEAN = "clean"  # Just clean state
    FEED_LIST = "feed_list"  # Create feed lists
    FEED_ACCOUNT = "feed_account"  # Create feed accounts
    FEED_TEMPLATES = "feed_templates"  # Create feed templates
    FEED_SUBSCRIBED = "feed_subscribed"  # Subscribe users (unconfirmed)
    FEED_SUBSCRIBE_CONFIRMED = "feed_subscribe_confirmed"  # Confirm subscriptions


@dataclass
class InitialisedData:
    """Data returned from initialise_system()."""

    accounts: dict[str, str] = field(default_factory=dict)  # username -> password
    subscribers: dict[str, dict] = field(default_factory=dict)  # subscriber_uuid -> {feed_hash: guid}


# ===========================================================================
# HELPER FUNCTIONS
# ===========================================================================


def wait_for(condition_fn, timeout=30, interval=0.5, desc="condition"):
    """Wait for condition_fn() to return True. Simple polling."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if condition_fn():
                return True
        except Exception:
            pass
        time.sleep(interval)
    return False


def wait_for_service(url, timeout=30, timeout_seconds=None):
    """Wait for a service to be ready.

    Args:
        url: URL to check
        timeout: Timeout in seconds (default 30)
        timeout_seconds: Alias for timeout (for backwards compatibility)
    """
    if timeout_seconds is not None:
        timeout = timeout_seconds
    return wait_for(lambda: service_ready(url), timeout=timeout, desc=f"service at {url}")


def service_ready(url):
    """Check if a service is responding."""
    try:
        r = requests.get(url, timeout=2)
        return r.status_code in (200, 401, 403)
    except Exception:
        return False


def api_auth():
    """Get HTTPBasicAuth for the RSS Monk API."""
    return HTTPBasicAuth(API_USERNAME, API_PASSWORD)


def make_admin_session():
    """Create a fresh authenticated session to Listmonk admin.

    This is an alias for listmonk_session() for backwards compatibility.
    """
    return listmonk_session()


def listmonk_session():
    """Create a fresh authenticated session to Listmonk admin."""
    session = requests.Session()
    session.get(f"{LISTMONK_URL}/admin/login", timeout=REQUEST_TIMEOUT)
    nonce = session.cookies.get("nonce")
    if not nonce:
        raise RuntimeError("Failed to get nonce from Listmonk")

    resp = session.post(
        f"{LISTMONK_URL}/admin/login",
        data={
            "username": LISTMONK_ADMIN_USER,
            "password": LISTMONK_ADMIN_PASSWORD,
            "nonce": nonce,
            "next": "/admin",
        },
        allow_redirects=False,
        timeout=REQUEST_TIMEOUT,
    )
    if resp.status_code != 302:
        raise RuntimeError(f"Failed to login to Listmonk: {resp.status_code}")
    return session


def clear_listmonk():
    """Delete all test data from Listmonk. Call this in setUp if needed."""
    session = listmonk_session()

    # Delete in order: subscribers -> lists -> templates -> roles -> users
    # (respecting foreign key dependencies)

    # Subscribers
    resp = session.get(f"{LISTMONK_URL}/api/subscribers?per_page=1000", timeout=REQUEST_TIMEOUT)
    for sub in resp.json().get("data", {}).get("results") or []:
        session.delete(f"{LISTMONK_URL}/api/subscribers/{sub['id']}", timeout=REQUEST_TIMEOUT)

    # Lists
    resp = session.get(f"{LISTMONK_URL}/api/lists?per_page=1000", timeout=REQUEST_TIMEOUT)
    for lst in resp.json().get("data", {}).get("results") or []:
        session.delete(f"{LISTMONK_URL}/api/lists/{lst['id']}", timeout=REQUEST_TIMEOUT)

    # Templates (keep id=1 which is the default)
    resp = session.get(f"{LISTMONK_URL}/api/templates", timeout=REQUEST_TIMEOUT)
    for tpl in resp.json().get("data") or []:
        if tpl["id"] != 1:
            session.delete(f"{LISTMONK_URL}/api/templates/{tpl['id']}", timeout=REQUEST_TIMEOUT)

    # List roles
    resp = session.get(f"{LISTMONK_URL}/api/roles/lists", timeout=REQUEST_TIMEOUT)
    for role in resp.json().get("data") or []:
        session.delete(f"{LISTMONK_URL}/api/roles/{role['id']}", timeout=REQUEST_TIMEOUT)

    # User roles (keep id=1 which is Super Admin)
    resp = session.get(f"{LISTMONK_URL}/api/roles/users", timeout=REQUEST_TIMEOUT)
    for role in resp.json().get("data") or []:
        if role["id"] != 1:
            session.delete(f"{LISTMONK_URL}/api/roles/{role['id']}", timeout=REQUEST_TIMEOUT)

    # Users (keep id=1 which is admin, and keep rssmonk-api)
    resp = session.get(f"{LISTMONK_URL}/api/users", timeout=REQUEST_TIMEOUT)
    for user in resp.json().get("data") or []:
        if user["id"] != 1 and user.get("username") != RSSMONK_API_USERNAME:
            session.delete(f"{LISTMONK_URL}/api/users/{user['id']}", timeout=REQUEST_TIMEOUT)


def clear_mailpit():
    """Delete all emails from Mailpit."""
    requests.delete(f"{MAILPIT_URL}/api/v1/messages", timeout=REQUEST_TIMEOUT)


def mailpit_message_count():
    """Get number of messages in Mailpit."""
    resp = requests.get(f"{MAILPIT_URL}/api/v1/messages", timeout=REQUEST_TIMEOUT)
    return resp.json().get("total", 0)


def wait_for_email(expected_count=1, timeout=10):
    """Wait for Mailpit to have at least expected_count messages."""
    return wait_for(
        lambda: mailpit_message_count() >= expected_count,
        timeout=timeout,
        desc=f"mailpit to have {expected_count} emails",
    )


def wait_for_mailpit_messages(expected_count=1, timeout_seconds=10):
    """Wait for Mailpit to have at least expected_count messages.

    This is an alias for wait_for_email() for backwards compatibility.
    """
    return wait_for_email(expected_count=expected_count, timeout=timeout_seconds)


# ===========================================================================
# API SETUP HELPERS
# ===========================================================================


def create_feed(feed_url=TEST_FEED_URL, name="Test Feed", email_base_url="http://example.com"):
    """Create a feed via the API. Returns the response JSON."""
    resp = requests.post(
        f"{RSSMONK_URL}/api/feeds",
        json={
            "feed_url": feed_url,
            "email_base_url": email_base_url,
            "poll_frequencies": ["instant"],
            "name": name,
        },
        auth=api_auth(),
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def create_account(feed_url=TEST_FEED_URL):
    """Create a feed account via the API. Returns (username, password)."""
    resp = requests.post(
        f"{RSSMONK_URL}/api/feeds/account",
        json={"feed_url": feed_url},
        auth=api_auth(),
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["name"], data["api_password"]


def create_template(feed_url=TEST_FEED_URL, template_type="subscribe"):
    """Create a template via the API. Returns the response JSON."""
    resp = requests.post(
        f"{RSSMONK_URL}/api/feeds/templates",
        json={
            "feed_url": feed_url,
            "template_type": template_type,
            "name": f"Test {template_type}",
            "subject": f"Test {template_type} subject",
            "body": f"<p>Test {template_type} body</p>",
        },
        auth=api_auth(),
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


# ===========================================================================
# LISTMONK CLIENT TEST BASE
# ===========================================================================


class ListmonkClientTestBase:
    """Base class for tests that need Listmonk setup.

    Provides:
    - ADMIN_AUTH: HTTPBasicAuth for admin API access
    - admin_session: Authenticated requests.Session to Listmonk
    - FEED_ONE_*, FEED_TWO_*, FEED_THREE_*: Test feed URLs and hashes
    - TEST_FEED_URL, TEST_FEED_HASH: Built-in test feed endpoint
    - initialise_system(phase): Sets up test data to a specific lifecycle phase
    """

    # Test feed URLs (external feeds for testing)
    FEED_ONE_FEED_URL = "https://example.com/media/rss/example"
    FEED_TWO_FEED_URL = "https://example.com/media/rss/example2"
    FEED_THREE_FEED_URL = "https://example.com/media/rss/example3"

    # Computed hashes
    FEED_ONE_HASH = make_url_hash(FEED_ONE_FEED_URL)
    FEED_TWO_HASH = make_url_hash(FEED_TWO_FEED_URL)
    FEED_THREE_HASH = make_url_hash(FEED_THREE_FEED_URL)

    # Built-in test feed (served by the API itself)
    TEST_FEED_URL = TEST_FEED_URL
    TEST_FEED_HASH = TEST_FEED_HASH

    # Set up in setup_method()
    ADMIN_AUTH: HTTPBasicAuth
    admin_session: requests.Session

    # Tracking for subscribers
    one_feed_subscriber_uuid: str = ""
    two_feed_subscriber_uuid: str = ""

    @classmethod
    def setUpClass(cls):
        """Class-level setup for unittest compatibility."""
        pass

    def setup_method(self, method=None):
        """Set up admin auth and clean state before each test (pytest style)."""
        self.ADMIN_AUTH = api_auth()
        self.admin_session = make_admin_session()
        clear_listmonk()
        clear_mailpit()

    def setUp(self):
        """Set up admin auth and clean state before each test (unittest style)."""
        self.setup_method()

    def initialise_system(self, phase: UnitTestLifecyclePhase) -> InitialisedData:
        """Set up test data to a specific lifecycle phase.

        Each phase includes all previous phases:
        - CLEAN: Just clean state
        - FEED_LIST: Create feed lists
        - FEED_ACCOUNT: Create feed accounts
        - FEED_TEMPLATES: Create feed templates
        - FEED_SUBSCRIBED: Subscribe users (unconfirmed)
        - FEED_SUBSCRIBE_CONFIRMED: Confirm subscriptions
        """
        # Always start clean
        clear_listmonk()
        clear_mailpit()

        data = InitialisedData()

        if phase == UnitTestLifecyclePhase.CLEAN:
            return data

        # FEED_LIST and above: Create feed lists
        self._create_feed_lists()

        if phase == UnitTestLifecyclePhase.FEED_LIST:
            return data

        # FEED_ACCOUNT and above: Create feed accounts
        data.accounts = self._create_feed_accounts()

        if phase == UnitTestLifecyclePhase.FEED_ACCOUNT:
            return data

        # FEED_TEMPLATES and above: Create feed templates
        self._create_feed_templates(data.accounts)

        if phase == UnitTestLifecyclePhase.FEED_TEMPLATES:
            return data

        # FEED_SUBSCRIBED and above: Subscribe users (unconfirmed)
        data.subscribers = self._subscribe_users(data.accounts)

        if phase == UnitTestLifecyclePhase.FEED_SUBSCRIBED:
            return data

        # FEED_SUBSCRIBE_CONFIRMED: Confirm subscriptions
        self._confirm_subscriptions(data.accounts, data.subscribers)

        # Clear mailpit after all setup is done so tests start with clean inbox
        clear_mailpit()

        return data

    def _create_feed_lists(self):
        """Create the three test feed lists."""
        feeds = [
            {
                "feed_url": self.FEED_ONE_FEED_URL,
                "email_base_url": "https://example.com/subscribe",
                "poll_frequencies": ["instant", "daily"],
                "name": "Example Media Statements",
            },
            {
                "feed_url": self.FEED_TWO_FEED_URL,
                "email_base_url": "https://example.com/subscribe",
                "poll_frequencies": ["instant"],
                "name": "Example Media Statements 2",
            },
            {
                "feed_url": self.FEED_THREE_FEED_URL,
                "email_base_url": "https://example.com/subscribe",
                "poll_frequencies": ["daily"],
                "name": "Example Media Statements 3",
            },
        ]
        for feed_data in feeds:
            resp = requests.post(
                f"{RSSMONK_URL}/api/feeds",
                json=feed_data,
                auth=self.ADMIN_AUTH,
                timeout=REQUEST_TIMEOUT,
            )
            assert resp.status_code == 201, f"Failed to create feed: {resp.text}"

    def _create_feed_accounts(self) -> dict[str, str]:
        """Create feed accounts for FEED_ONE and FEED_TWO only.

        Tests expect only 2 feed accounts (not 3).
        Returns {username: password}.
        """
        accounts = {}
        for feed_url in [self.FEED_ONE_FEED_URL, self.FEED_TWO_FEED_URL]:
            resp = requests.post(
                f"{RSSMONK_URL}/api/feeds/account",
                json={"feed_url": feed_url},
                auth=self.ADMIN_AUTH,
                timeout=REQUEST_TIMEOUT,
            )
            assert resp.status_code == 201, f"Failed to create account: {resp.text}"
            data = resp.json()
            accounts[data["name"]] = data["api_password"]
        return accounts

    def _create_feed_templates(self, accounts: dict[str, str]):
        """Create subscribe and unsubscribe templates for FEED_ONE only.

        Tests expect only FEED_ONE to have templates (5 total: 1 default + 2 sub/unsub + 2 digest).
        """
        from rssmonk.types import FEED_ACCOUNT_PREFIX

        feed_url = self.FEED_ONE_FEED_URL
        feed_hash = self.FEED_ONE_HASH
        username = FEED_ACCOUNT_PREFIX + feed_hash
        password = accounts[username]
        auth = HTTPBasicAuth(username, password)

        # Subscribe template
        resp = requests.post(
            f"{RSSMONK_URL}/api/feeds/templates",
            json={
                "feed_url": feed_url,
                "template_type": "tx",
                "phase_type": "subscribe",
                "subject": "Please confirm your subscription",
                "body": '<p>Click <a href="{{ .Tx.Data.confirmation_link }}">here</a> to confirm.</p>',
            },
            auth=auth,
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 201, f"Failed to create subscribe template: {resp.text}"

        # Unsubscribe template
        resp = requests.post(
            f"{RSSMONK_URL}/api/feeds/templates",
            json={
                "feed_url": feed_url,
                "template_type": "tx",
                "phase_type": "unsubscribe",
                "subject": "Please confirm unsubscription",
                "body": '<p>Click <a href="{{ .Tx.Data.confirmation_link }}">here</a> to unsubscribe.</p>',
            },
            auth=auth,
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 201, f"Failed to create unsubscribe template: {resp.text}"

        # Digest template (instant)
        resp = requests.post(
            f"{RSSMONK_URL}/api/feeds/templates",
            json={
                "feed_url": feed_url,
                "template_type": "tx",
                "phase_type": "instant_digest",
                "subject": "Instant digest",
                "body": "<p>Here are your instant updates.</p>",
            },
            auth=auth,
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 201, f"Failed to create instant digest template: {resp.text}"

        # Digest template (daily)
        resp = requests.post(
            f"{RSSMONK_URL}/api/feeds/templates",
            json={
                "feed_url": feed_url,
                "template_type": "tx",
                "phase_type": "daily_digest",
                "subject": "Daily digest",
                "body": "<p>Here are your daily updates.</p>",
            },
            auth=auth,
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 201, f"Failed to create daily digest template: {resp.text}"

    def _subscribe_users(self, accounts: dict[str, str]) -> dict[str, dict]:
        """Subscribe test users. Returns {subscriber_uuid: {feed_hash: guid}}.

        Creates:
        - one_feed_user (example@example.com) subscribed to FEED_ONE only
        - two_feed_user (two_feed_user@test.com) subscribed to FEED_ONE and FEED_TWO
        """
        from rssmonk.types import FEED_ACCOUNT_PREFIX

        subscribers = {}
        clear_mailpit()  # Clear any emails from template creation

        # Subscribe one_feed_user to feed one only
        # Uses example@example.com as expected by unsubscribe tests
        username = FEED_ACCOUNT_PREFIX + self.FEED_ONE_HASH
        password = accounts[username]
        auth = HTTPBasicAuth(username, password)

        resp = requests.post(
            f"{RSSMONK_URL}/api/feeds/subscribe",
            json={
                "email": "example@example.com",
                "filter": {"instant": {"region": [1, 2]}},
                "display_text": {"instant": {"region": ["Region 1", "Region 2"]}},
            },
            auth=auth,
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 200, f"Failed to subscribe one_feed_user: {resp.text}"

        # Get subscriber UUID and guid for one_feed_user
        resp = self.admin_session.get(
            f"{LISTMONK_URL}/api/subscribers",
            params={"query": "subscribers.email='example@example.com'"},
            timeout=REQUEST_TIMEOUT,
        )
        sub = resp.json()["data"]["results"][0]
        self.one_feed_subscriber_uuid = sub["uuid"].replace("-", "")
        guid = list(sub["attribs"].get(self.FEED_ONE_HASH, {}).keys())[0]
        subscribers[self.one_feed_subscriber_uuid] = {self.FEED_ONE_HASH: guid}

        # Subscribe two_feed_user to BOTH feed one and feed two
        # First subscribe to feed one
        resp = requests.post(
            f"{RSSMONK_URL}/api/feeds/subscribe",
            json={
                "email": "two_feed_user@test.com",
                "filter": {"instant": {"region": [3, 4]}},
                "display_text": {"instant": {"region": ["Region 3", "Region 4"]}},
            },
            auth=auth,
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 200, f"Failed to subscribe two_feed_user to feed one: {resp.text}"

        # Then subscribe to feed two using admin with bypass (no template for FEED_TWO)
        resp = requests.post(
            f"{RSSMONK_URL}/api/feeds/subscribe",
            json={
                "feed_url": self.FEED_TWO_FEED_URL,
                "email": "two_feed_user@test.com",
                "filter": {"instant": {"region": [5, 6]}},
                "display_text": {"instant": {"region": ["Region 5", "Region 6"]}},
                "bypass_confirmation": True,
            },
            auth=self.ADMIN_AUTH,
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 200, f"Failed to subscribe two_feed_user to feed two: {resp.text}"

        # Get subscriber UUID and guids for two_feed_user
        resp = self.admin_session.get(
            f"{LISTMONK_URL}/api/subscribers",
            params={"query": "subscribers.email='two_feed_user@test.com'"},
            timeout=REQUEST_TIMEOUT,
        )
        sub = resp.json()["data"]["results"][0]
        self.two_feed_subscriber_uuid = sub["uuid"].replace("-", "")

        # FEED_ONE has a guid (pending confirmation)
        guid_one = list(sub["attribs"].get(self.FEED_ONE_HASH, {}).keys())[0]

        # FEED_TWO was subscribed with bypass_confirmation=True, so it already has token (no guid)
        # We'll store the token directly for FEED_TWO
        feed_two_attribs = sub["attribs"].get(self.FEED_TWO_HASH, {})
        token_two = feed_two_attribs.get("token")

        subscribers[self.two_feed_subscriber_uuid] = {
            self.FEED_ONE_HASH: guid_one,
            self.FEED_TWO_HASH: token_two,  # Store token, not guid
        }

        return subscribers

    def _confirm_subscriptions(self, accounts: dict[str, str], subscribers: dict[str, dict]):
        """Confirm subscriptions for test users.

        After confirmation, updates subscribers dict to contain tokens instead of guids.
        Note: FEED_TWO subscription was already bypassed, so only FEED_ONE needs confirmation.
        """
        from rssmonk.types import FEED_ACCOUNT_PREFIX

        # Confirm one_feed_user's subscription to feed one
        username = FEED_ACCOUNT_PREFIX + self.FEED_ONE_HASH
        password = accounts[username]
        auth = HTTPBasicAuth(username, password)
        guid = subscribers[self.one_feed_subscriber_uuid][self.FEED_ONE_HASH]

        resp = requests.post(
            f"{RSSMONK_URL}/api/feeds/subscribe-confirm",
            json={"subscriber_id": self.one_feed_subscriber_uuid, "guid": guid},
            auth=auth,
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 200, f"Failed to confirm one_feed_user subscription: {resp.text}"

        # Get the token for one_feed_user after confirmation
        resp = self.admin_session.get(
            f"{LISTMONK_URL}/api/subscribers",
            params={"query": "subscribers.email='example@example.com'"},
            timeout=REQUEST_TIMEOUT,
        )
        sub = resp.json()["data"]["results"][0]
        token = sub["attribs"].get(self.FEED_ONE_HASH, {}).get("token")
        subscribers[self.one_feed_subscriber_uuid] = {self.FEED_ONE_HASH: token}

        # Confirm two_feed_user's subscription to feed one
        guid = subscribers[self.two_feed_subscriber_uuid][self.FEED_ONE_HASH]
        resp = requests.post(
            f"{RSSMONK_URL}/api/feeds/subscribe-confirm",
            json={"subscriber_id": self.two_feed_subscriber_uuid, "guid": guid},
            auth=auth,
            timeout=REQUEST_TIMEOUT,
        )
        assert resp.status_code == 200, f"Failed to confirm two_feed_user feed one subscription: {resp.text}"

        # Get the tokens for two_feed_user after confirmation
        # Note: FEED_TWO was subscribed with bypass_confirmation=True, so it already has a token
        resp = self.admin_session.get(
            f"{LISTMONK_URL}/api/subscribers",
            params={"query": "subscribers.email='two_feed_user@test.com'"},
            timeout=REQUEST_TIMEOUT,
        )
        sub = resp.json()["data"]["results"][0]
        token_one = sub["attribs"].get(self.FEED_ONE_HASH, {}).get("token")
        token_two = sub["attribs"].get(self.FEED_TWO_HASH, {}).get("token")
        subscribers[self.two_feed_subscriber_uuid] = {
            self.FEED_ONE_HASH: token_one,
            self.FEED_TWO_HASH: token_two,
        }


# ===========================================================================
# PYTEST FIXTURES
# ===========================================================================


def stop_api():
    """Stop any running API server."""
    subprocess.run(["pkill", "-f", "uvicorn.*rssmonk.api"], capture_output=True)
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, signal.SIGTERM)
        except (ValueError, ProcessLookupError):
            pass
        PID_FILE.unlink(missing_ok=True)
    # Wait for it to actually stop
    wait_for(lambda: not service_ready(f"{RSSMONK_URL}/health"), timeout=5)


def start_api(api_password):
    """Start the API server."""
    stop_api()

    # Write .env file
    Path(".env").write_text(f'''# Test credentials
LISTMONK_URL="{LISTMONK_URL}"
LISTMONK_ADMIN_USER="{RSSMONK_API_USERNAME}"
LISTMONK_ADMIN_PASSWORD="{api_password}"
''')

    env = os.environ.copy()
    env["RSSMONK_TESTING"] = "1"
    env["LISTMONK_URL"] = LISTMONK_URL
    env["LISTMONK_ADMIN_USER"] = RSSMONK_API_USERNAME
    env["LISTMONK_ADMIN_PASSWORD"] = api_password

    with open(LOG_FILE, "w") as log:
        proc = subprocess.Popen(
            ["uv", "run", "fastapi", "run", "src/rssmonk/api.py", "--port", "8000", "--workers", "2"],
            env=env,
            stdout=log,
            stderr=log,
            start_new_session=True,
            cwd=Path(__file__).parent.parent,
        )

    PID_FILE.write_text(str(proc.pid))

    # Wait for API to be ready
    if not wait_for(lambda: service_ready(f"{RSSMONK_URL}/health"), timeout=30):
        raise RuntimeError("API failed to start. Check /tmp/rssmonk-api.log")


def get_or_create_api_token(session):
    """Create API user in Listmonk and return the token."""
    # Delete existing user if present
    resp = session.get(f"{LISTMONK_URL}/api/users", timeout=REQUEST_TIMEOUT)
    for user in resp.json().get("data") or []:
        if user.get("username") == RSSMONK_API_USERNAME:
            session.delete(f"{LISTMONK_URL}/api/users/{user['id']}", timeout=REQUEST_TIMEOUT)
            break

    # Create new API user
    resp = session.post(
        f"{LISTMONK_URL}/api/users",
        json={
            "username": RSSMONK_API_USERNAME,
            "email": "",
            "name": "RSS Monk API",
            "type": "api",
            "status": "enabled",
            "password": None,
            "password_login": False,
            "user_role_id": 1,  # Super Admin
            "list_role_id": None,
        },
        timeout=REQUEST_TIMEOUT,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to create API user: {resp.text}")

    return resp.json()["data"]["password"]


def configure_listmonk_smtp(session):
    """Configure Listmonk to use Mailpit for SMTP."""
    # Get current settings and update SMTP
    resp = session.get(f"{LISTMONK_URL}/api/settings", timeout=REQUEST_TIMEOUT)
    settings = resp.json().get("data", {})

    # Update only the SMTP part
    settings["smtp"] = [
        {
            "name": "",
            "uuid": "585c1139-ec96-4279-8be0-ba918db272f0",
            "enabled": True,
            "host": "mailpit.rssmonk.svc.cluster.local",
            "port": 1025,
            "auth_protocol": "none",
            "username": "",
            "password": "",
            "email_headers": [],
            "max_conns": 20,
            "max_msg_retries": 2,
            "idle_timeout": "15s",
            "wait_timeout": "5s",
            "tls_type": "none",
            "tls_skip_verify": False,
            "strEmailHeaders": "[]",
        }
    ]

    resp = session.put(f"{LISTMONK_URL}/api/settings", json=settings, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to configure SMTP: {resp.text}")


@pytest.fixture(scope="session", autouse=True)
def api_server():
    """Start API server for the test session."""
    global API_USERNAME, API_PASSWORD

    # Wait for Listmonk
    if not wait_for(lambda: service_ready(f"{LISTMONK_URL}/api/health"), timeout=60):
        pytest.fail("Listmonk not running. Start with: just start")

    # Get authenticated session to Listmonk
    session = listmonk_session()

    # Configure SMTP to use Mailpit
    configure_listmonk_smtp(session)

    # Create API token
    API_PASSWORD = get_or_create_api_token(session)
    API_USERNAME = RSSMONK_API_USERNAME

    # Start API server
    start_api(API_PASSWORD)

    yield

    # Cleanup
    stop_api()


@pytest.fixture
def clean_state():
    """Fixture to clean Listmonk state before a test. Use explicitly when needed."""
    clear_listmonk()
    clear_mailpit()
    yield
