import os
import signal
import subprocess
import time
import pytest
import requests
import unittest
from datetime import datetime, timedelta, timezone
from enum import IntEnum
from http import HTTPStatus
from pathlib import Path
from requests.auth import HTTPBasicAuth

from rssmonk.utils import make_url_hash

RSSMONK_URL = "http://localhost:8000"
LISTMONK_URL = "http://localhost:9000"
MAILPIT_URL = "http://localhost:8025"

REQUEST_TIMEOUT = 5  # Fast fail timeout for test requests
SERVICE_CHECK_TIMEOUT = 2  # Faster timeout for initial service availability check

# API user created by fixture for RSS Monk API access
RSSMONK_API_USERNAME = "rssmonk-api"
PID_FILE = Path("/tmp/rssmonk-api.pid")
LOG_FILE = Path("/tmp/rssmonk-api.log")

# Runtime state - populated by api_server fixture
class ApiCredentials:
    """Holder for API credentials set by fixture."""
    username: str = ""
    password: str = ""

api_creds = ApiCredentials()

# Listmonk login credentials for session auth (k3d defaults)
LISTMONK_LOGIN_USER = "admin"
LISTMONK_LOGIN_PASSWORD = "admin123"


# Patch requests to use timeout by default
_original_request = requests.Session.request

def _request_with_timeout(self, method, url, **kwargs):
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    return _original_request(self, method, url, **kwargs)

requests.Session.request = _request_with_timeout

# Also patch the module-level functions
_original_get = requests.get
_original_post = requests.post
_original_put = requests.put
_original_delete = requests.delete

def _get_with_timeout(url, **kwargs):
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    return _original_get(url, **kwargs)

def _post_with_timeout(url, **kwargs):
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    return _original_post(url, **kwargs)

def _put_with_timeout(url, **kwargs):
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    return _original_put(url, **kwargs)

def _delete_with_timeout(url, **kwargs):
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    return _original_delete(url, **kwargs)

requests.get = _get_with_timeout
requests.post = _post_with_timeout
requests.put = _put_with_timeout
requests.delete = _delete_with_timeout


def check_service_available(url: str, name: str) -> bool:
    """Check if a service is available."""
    try:
        resp = _original_get(url, timeout=SERVICE_CHECK_TIMEOUT)
        return resp.status_code in (200, 401, 403)
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return False


def wait_for_listmonk() -> bool:
    """Wait for Listmonk to be ready."""
    for _ in range(60):
        if check_service_available(f"{LISTMONK_URL}/api/health", "Listmonk"):
            return True
        time.sleep(1)
    return False


def get_or_create_api_token(session: requests.Session) -> str:
    """Create API user in Listmonk and return the token.
    
    Listmonk only returns the API token on user creation, so if the user
    already exists, we delete and recreate to get a new token.
    """
    response = session.get(f"{LISTMONK_URL}/api/users", timeout=10)
    if response.status_code != 200:
        raise RuntimeError(f"Failed to get users: {response.text}")
    
    users = response.json().get("data", [])
    for user in users:
        if user.get("username") == RSSMONK_API_USERNAME:
            # Delete existing user to get a fresh token
            del_response = session.delete(f"{LISTMONK_URL}/api/users/{user['id']}", timeout=10)
            if del_response.status_code != 200:
                raise RuntimeError(f"Failed to delete API user: {del_response.text}")
            break
    
    # Create new API user with Super Admin role (role_id=1)
    user_data = {
        "username": RSSMONK_API_USERNAME,
        "email": "",
        "name": "RSS Monk API",
        "type": "api",
        "status": "enabled",
        "password": None,
        "password_login": False,
        "user_role_id": 1,
        "list_role_id": None
    }
    response = session.post(f"{LISTMONK_URL}/api/users", json=user_data, timeout=10)
    if response.status_code != 200:
        raise RuntimeError(f"Failed to create API user: {response.text}")
    
    return response.json()["data"]["password"]


def stop_api() -> None:
    """Stop any running API server."""
    subprocess.run(["pkill", "-f", "fastapi.*src/rssmonk/api.py"], capture_output=True)
    subprocess.run(["pkill", "-f", "uvicorn.*rssmonk"], capture_output=True)
    subprocess.run(["fuser", "-k", "8000/tcp"], capture_output=True)
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, signal.SIGTERM)
        except (ValueError, ProcessLookupError):
            pass
        PID_FILE.unlink(missing_ok=True)
    time.sleep(1)


def start_api(api_password: str) -> bool:
    """Start API server and wait for ready."""
    print(f"Starting API with user={RSSMONK_API_USERNAME}, password={api_password[:10]}...")
    stop_api()
    
    # Write credentials to .env file (API loads from .env on startup)
    env_file = Path(".env")
    env_content = f"""# Test credentials - auto-generated by conftest.py
LISTMONK_URL="{LISTMONK_URL}"
LISTMONK_ADMIN_USER="{RSSMONK_API_USERNAME}"
LISTMONK_ADMIN_PASSWORD="{api_password}"
"""
    env_file.write_text(env_content)
    
    env = os.environ.copy()
    env["RSSMONK_TESTING"] = "1"
    env["LISTMONK_URL"] = LISTMONK_URL
    env["LISTMONK_ADMIN_USER"] = RSSMONK_API_USERNAME
    env["LISTMONK_ADMIN_PASSWORD"] = api_password
    
    workspace_root = Path(__file__).parent.parent
    with open(LOG_FILE, "w") as log:
        proc = subprocess.Popen(
            ["uv", "run", "fastapi", "run", "src/rssmonk/api.py", "--port", "8000", "--workers", "2"],
            env=env,
            stdout=log,
            stderr=log,
            start_new_session=True,
            cwd=workspace_root,
        )
    
    PID_FILE.write_text(str(proc.pid))
    print(f"API process started with PID {proc.pid}")
    
    for _ in range(30):
        if check_service_available(f"{RSSMONK_URL}/health", "RSS Monk API"):
            print("API is ready")
            return True
        time.sleep(1)
    
    return False


@pytest.fixture(scope="session", autouse=True)
def api_server():
    """Start API server with fresh API token, yield credentials, then cleanup."""
    # Wait for Listmonk (k3d cluster)
    if not wait_for_listmonk():
        pytest.fail("Listmonk is not running. Start it with: just start")
    
    # Create API token via Listmonk admin session
    admin_session = make_admin_session()
    api_creds.password = get_or_create_api_token(admin_session)
    api_creds.username = RSSMONK_API_USERNAME
    
    # Start API server
    if not start_api(api_creds.password):
        pytest.fail("Failed to start API server. Check /tmp/rssmonk-api.log")
    
    yield
    
    # Cleanup
    stop_api()


def make_admin_session() -> requests.Session:
    """Create authenticated session to Listmonk using login credentials."""
    admin_session = requests.Session()

    admin_session.get(f"{LISTMONK_URL}/admin/login")
    nonce = admin_session.cookies.get("nonce")
    assert nonce, "Nonce not found in cookies"
    
    login_data = {
        "username": LISTMONK_LOGIN_USER,
        "password": LISTMONK_LOGIN_PASSWORD,
        "nonce": nonce,
        "next": "/admin"
    }
    response = admin_session.post(f"{LISTMONK_URL}/admin/login", data=login_data, allow_redirects=False, timeout=30)
    if response.status_code != 302:
        raise AssertionError("Failed to create prereq admin session to Listmonk")
    return admin_session


@pytest.fixture(scope="session")
def listmonk_setup():
    # Modify settings to ensure mailpit is the mail client for RSSMonk
    response = make_admin_session().put(LISTMONK_URL+"/api/settings", json={
        "app.site_name": "Media Statements",
        "app.root_url": LISTMONK_URL,
        "app.logo_url": "",
        "app.favicon_url": "",
        "app.from_email": "listmonk <noreply@listmonk.yoursite.com>",
        "app.notify_emails": [],
        "app.enable_public_subscription_page": True,
        "app.enable_public_archive": True,
        "app.enable_public_archive_rss_content": True,
        "app.send_optin_confirmation": True,
        "app.check_updates": True,
        "app.lang": "en",
        "app.batch_size": 1000,
        "app.concurrency": 20,
        "app.max_send_errors": 1000,
        "app.message_rate": 100,
        "app.cache_slow_queries": False,
        "app.cache_slow_queries_interval": "0 3 * * *",
        "app.message_sliding_window": False,
        "app.message_sliding_window_duration": "1h",
        "app.message_sliding_window_rate": 10000,
        "privacy.individual_tracking": False,
        "privacy.unsubscribe_header": True,
        "privacy.allow_blocklist": True,
        "privacy.allow_preferences": True,
        "privacy.allow_export": True,
        "privacy.allow_wipe": True,
        "privacy.exportable": ["profile","subscriptions","campaign_views","link_clicks"],
        "privacy.record_optin_ip": False,
        "privacy.domain_blocklist": [],
        "privacy.domain_allowlist": [],
        "security.captcha": {
            "altcha": {"enabled": False,"complexity": 300000},
            "hcaptcha": {"enabled": False,"key": "","secret": ""}
        },
        "security.oidc": {
            "enabled": False,
            "provider_url": "",
            "provider_name": "",
            "client_id": "",
            "client_secret": "",
            "auto_create_users": False,
            "default_user_role_id": None,
            "default_list_role_id": None
        },
        "upload.provider": "filesystem",
        "upload.extensions": ["jpg", "jpeg", "png", "gif", "svg", "*"],
        "upload.filesystem.upload_path": "uploads",
        "upload.filesystem.upload_uri": "/uploads",
        "upload.s3.url": "",
        "upload.s3.public_url": "",
        "upload.s3.aws_access_key_id": "",
        "upload.s3.aws_default_region": "ap-south-1",
        "upload.s3.bucket": "",
        "upload.s3.bucket_domain": "",
        "upload.s3.bucket_path": "/",
        "upload.s3.bucket_type": "public",
        "upload.s3.expiry": "167h",
        "smtp": [
            {
                "name": "",
                "uuid": "585c1139-ec96-4279-8be0-ba918db272f0",
                "enabled": True,
                "host": "mailpit.rssmonk.svc.cluster.local",
                "hello_hostname": "",
                "port": 1025,
                "auth_protocol": "none",
                "username": "username",
                "password": "",
                "email_headers": [],
                "max_conns": 20,
                "max_msg_retries": 2,
                "idle_timeout": "15s",
                "wait_timeout": "5s",
                "tls_type": "none",
                "tls_skip_verify": False,
                "strEmailHeaders": "[]"
            }
        ],
        "messengers": [],
        "bounce.enabled": False,
        "bounce.webhooks_enabled": False,
        "bounce.actions": {
            "complaint": {"count": 1, "action": "blocklist"},
            "hard": {"count": 1,"action": "blocklist"},
            "soft": {"count": 2,"action": "none"}
        },
        "bounce.ses_enabled": False,
        "bounce.sendgrid_enabled": False,
        "bounce.sendgrid_key": "",
        "bounce.postmark": {"enabled": False,"username": "","password": ""},
        "bounce.forwardemail": {"enabled": False,"key": ""},
        "bounce.mailboxes": [
            {
                "uuid": "855bd4a1-8224-425d-a6ac-0901e34fa835",
                "enabled": False,
                "type": "pop",
                "host": "pop.yoursite.com",
                "port": 995,
                "auth_protocol": "userpass",
                "return_path": "bounce@listmonk.yoursite.com",
                "username": "username",
                "password": "",
                "tls_enabled": True,
                "tls_skip_verify": False,
                "scan_interval": "15m"
            }
        ],
        "appearance.admin.custom_css": "",
        "appearance.admin.custom_js": "",
        "appearance.public.custom_css": "",
        "appearance.public.custom_js": "",
        "upload.s3.aws_secret_access_key": ""
    })
    assert response.status_code == HTTPStatus.OK
    time.sleep(5) # Listmonk will reload, so a pause is needed


class UnitTestLifecyclePhase(IntEnum):
    """
    Life cycle phase of feed setup that the system should be in.
    This helps simplify the set up each test function requires
    """
    NONE = 0
    FEED_LIST = 1
    FEED_ACCOUNT = 2
    FEED_TEMPLATES = 3
    FEED_SUBSCRIBED = 4
    FEED_SUBSCRIBE_CONFIRMED = 5
    # These would not be required
    #FEED_UNSUBSCRIBED = 6
    #FEED_DELETED = 7


class UnitTestInitialisedData:
    accounts = {} # Accounts in username + password as pair
    subscribers = {} # Subscriber's UUID + TOKEN as pair


@pytest.mark.usefixtures("api_server", "listmonk_setup")
class ListmonkClientTestBase(unittest.TestCase):
    """This is the base of the testing with RSSMonk and downstream Listmonk, setting them up and tear down."""
    # Test feed URL - served by the API at /test/feed
    TEST_FEED_URL = f"{RSSMONK_URL}/test/feed"

    # Feed URLs for multi-feed tests (FEED_ONE uses the real test feed)
    FEED_ONE_FEED_URL = TEST_FEED_URL
    FEED_ONE_HASH = make_url_hash(FEED_ONE_FEED_URL)

    FEED_TWO_FEED_URL = f"{TEST_FEED_URL}?items=2"
    FEED_TWO_HASH = make_url_hash(FEED_TWO_FEED_URL)

    FEED_THREE_FEED_URL = f"{TEST_FEED_URL}?items=5"
    FEED_THREE_HASH = make_url_hash(FEED_THREE_FEED_URL)
    
    ADMIN_AUTH: HTTPBasicAuth = None  # type: ignore[assignment]  # Set in setUpClass from env
    admin_session: requests.Session = None  # type: ignore[assignment]
    one_feed_subscriber_uuid = ""
    two_feed_subscriber_uuid = ""
    __limited_user_role_id = -1
    __feed_list_id = {}


    @classmethod
    def setUpClass(cls):
        # Set up auth from credentials set by api_server fixture
        print(f"DEBUG: api_creds.username={api_creds.username!r}, api_creds.password={api_creds.password[:10] if api_creds.password else 'EMPTY'}...")
        cls.ADMIN_AUTH = HTTPBasicAuth(api_creds.username, api_creds.password)
        # Create admin session lazily (services must be running)
        cls.admin_session = make_admin_session()
        # Empty lists, subscribers, templates and list roles.
        cls.delete_list_roles()
        cls.delete_user_roles()
        cls.delete_users()
        cls.delete_lists()
        cls.delete_subscribers()
        cls.delete_templates()
        cls.clear_mailpit_messages()
        cls.__limited_user_role_id = -1
        cls.__feed_list_id = {}

    def setUp(self):
        # Clean state before each test - use the full cleanup
        self.delete_list_roles()
        self.delete_user_roles()
        self.delete_users()
        self.delete_lists()
        self.delete_subscribers()
        self.delete_templates()
        self.clear_mailpit_messages()
        self.__limited_user_role_id = -1
        self.__feed_list_id = {}

    @classmethod
    def reset_listmonk_state(cls):
        """Reset Listmonk to clean state - optimised to minimise API calls."""
        # Delete in dependency order: subscribers -> lists -> templates -> roles -> users
        # Get all data in parallel-ish (fewer round trips)
        lists_resp = cls.admin_session.get(f"{LISTMONK_URL}/api/lists?per_page=all")
        subs_resp = cls.admin_session.get(f"{LISTMONK_URL}/api/subscribers?per_page=all")
        templates_resp = cls.admin_session.get(f"{LISTMONK_URL}/api/templates")
        list_roles_resp = cls.admin_session.get(f"{LISTMONK_URL}/api/roles/lists")
        user_roles_resp = cls.admin_session.get(f"{LISTMONK_URL}/api/roles/users")
        users_resp = cls.admin_session.get(f"{LISTMONK_URL}/api/users")

        # Delete subscribers
        for sub in (subs_resp.json().get("data", {}).get("results") or []):
            cls.admin_session.delete(f"{LISTMONK_URL}/api/subscribers/{sub['id']}")

        # Delete lists
        for lst in (lists_resp.json().get("data", {}).get("results") or []):
            cls.admin_session.delete(f"{LISTMONK_URL}/api/lists/{lst['id']}")

        # Delete templates
        for tpl in (templates_resp.json().get("data") or []):
            cls.admin_session.delete(f"{LISTMONK_URL}/api/templates/{tpl['id']}")

        # Delete list roles
        for role in (list_roles_resp.json().get("data") or []):
            cls.admin_session.delete(f"{LISTMONK_URL}/api/roles/{role['id']}")

        # Delete user roles (skip id=1 which is Super Admin)
        for role in (user_roles_resp.json().get("data") or []):
            if role["id"] != 1:
                cls.admin_session.delete(f"{LISTMONK_URL}/api/roles/{role['id']}")

        # Delete users (skip id=1 which is admin, and the rssmonk-api user)
        for user in (users_resp.json().get("data") or []):
            if user["id"] != 1 and user.get("username") != RSSMONK_API_USERNAME:
                cls.admin_session.delete(f"{LISTMONK_URL}/api/users/{user['id']}")

        # Clear mailpit
        requests.delete(f"{MAILPIT_URL}/api/v1/messages", timeout=REQUEST_TIMEOUT)

    @classmethod
    def delete_lists(cls):
        response = cls.admin_session.get(f"{LISTMONK_URL}/api/lists")
        for lst in (response.json().get("data", {}).get("results") or []):
            cls.admin_session.delete(f"{LISTMONK_URL}/api/lists/{lst['id']}")

    @classmethod
    def delete_subscribers(cls):
        cls.admin_session.delete(f"{LISTMONK_URL}/api/maintenance/subscribers/orphan")
        response = cls.admin_session.get(f"{LISTMONK_URL}/api/subscribers?per_page=all")
        for sub in (response.json().get("data", {}).get("results") or []):
            cls.admin_session.delete(f"{LISTMONK_URL}/api/subscribers/{sub['id']}")

    @classmethod
    def delete_templates(cls):
        response = cls.admin_session.get(f"{LISTMONK_URL}/api/templates")
        for tpl in (response.json().get("data") or []):
            cls.admin_session.delete(f"{LISTMONK_URL}/api/templates/{tpl['id']}")

    @classmethod
    def delete_list_roles(cls):
        response = cls.admin_session.get(f"{LISTMONK_URL}/api/roles/lists")
        for role in (response.json().get("data") or []):
            cls.admin_session.delete(f"{LISTMONK_URL}/api/roles/{role['id']}")

    @classmethod
    def delete_user_roles(cls):
        response = cls.admin_session.get(f"{LISTMONK_URL}/api/roles/users")
        for role in (response.json().get("data") or []):
            if role["id"] != 1:
                cls.admin_session.delete(f"{LISTMONK_URL}/api/roles/{role['id']}")

    @classmethod
    def delete_users(cls):
        response = cls.admin_session.get(f"{LISTMONK_URL}/api/users")
        for user in (response.json().get("data") or []):
            # Skip admin (id=1) and the rssmonk-api user used for API auth
            if user["id"] != 1 and user.get("username") != RSSMONK_API_USERNAME:
                cls.admin_session.delete(f"{LISTMONK_URL}/api/users/{user['id']}")

    @classmethod
    def clear_mailpit_messages(cls):
        requests.delete(f"{MAILPIT_URL}/api/v1/messages", timeout=REQUEST_TIMEOUT)

    #-------------------------
    # Helper functions to set up functionality
    #-------------------------
    def initialise_system(self, phase: UnitTestLifecyclePhase) -> UnitTestInitialisedData:
        # LifecyclePhase.NONE is a noop
        data = UnitTestInitialisedData()

        if phase.value >= UnitTestLifecyclePhase.FEED_LIST.value:
            self._make_feed_list()

        if phase.value >= UnitTestLifecyclePhase.FEED_ACCOUNT.value:
            data.accounts = self._make_accounts()

        if phase.value >= UnitTestLifecyclePhase.FEED_TEMPLATES.value:
            self._make_feed_templates()

        if phase.value >= UnitTestLifecyclePhase.FEED_SUBSCRIBED.value:
            data.subscribers = self._make_feed_subscriber(phase >= UnitTestLifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)

        return data


    def _make_feed_list(self):
        """Creating feeds used for testing"""
        create_feed_data = {
            "name": "Example Media Statements",
            "type": "private",
            "optin": "single",
            "tags": [
                "freq:instant",
                "freq:daily",
                "url:"+self.FEED_ONE_HASH
            ],
            "description": f"RSS Feed: {self.FEED_ONE_FEED_URL}\nSubscription URL: https://example.com/subscribe"
        }
        response = self.admin_session.post(LISTMONK_URL+"/api/lists", json=create_feed_data)
        assert (response.status_code == HTTPStatus.OK), "Set up failed. Make feed: "+response.text
        self.__feed_list_id[self.FEED_ONE_HASH] = response.json()["data"]["id"]

        create_feed_two_data = {
            "name": "Somewhere Statements",
            "type": "private",
            "optin": "single",
            "tags": [
                "freq:instant",
                "url:"+self.FEED_TWO_HASH
            ],
            "description": f"RSS Feed: {self.FEED_TWO_FEED_URL}\nSubscription URL: https://example.com/subscribe2"
        }
        response = self.admin_session.post(LISTMONK_URL+"/api/lists", json=create_feed_two_data)
        assert (response.status_code == HTTPStatus.OK), "Set up failed. Make feed: "+response.text
        self.__feed_list_id[self.FEED_TWO_HASH] = response.json()["data"]["id"]

        create_feed_three_data = {
            "name": "Live Statements",
            "type": "private",
            "optin": "single",
            "tags": [
                "freq:daily",
                "url:"+self.FEED_THREE_HASH
            ],
            "description": f"RSS Feed: {self.FEED_THREE_FEED_URL}\nSubscription URL: https://example.com/subscribe3"
        }
        response = self.admin_session.post(LISTMONK_URL+"/api/lists", json=create_feed_three_data)
        assert (response.status_code == HTTPStatus.OK), "Set up failed. Make feed: "+response.text
        self.__feed_list_id[self.FEED_THREE_HASH] = response.json()["data"]["id"]


    def _make_accounts(self) -> dict[str, dict[str, str]]:
        """Creating feeds and accounts used for testing"""
        create_limited_use_role = {
            "name": "limited-user-role",
            "permissions": [
                "subscribers:get",
                "subscribers:manage",
                "tx:send",
                "templates:get"
            ]
        }
        response = self.admin_session.post(LISTMONK_URL+"/api/roles/users", json=create_limited_use_role)
        assert (response.status_code == HTTPStatus.OK), "Set up failed. Make user role: "+response.text
        self.__limited_user_role_id = response.json()["data"]["id"]

        create_list_role = {
            "name": "list_role_"+self.FEED_ONE_HASH,
            "lists": [ {"id": self.__feed_list_id[self.FEED_ONE_HASH],
                        "permissions": ["list:get","list:manage"] } ]
        }
        response = self.admin_session.post(LISTMONK_URL+"/api/roles/lists", json=create_list_role)
        assert (response.status_code == HTTPStatus.OK), "Set up failed. Make list role: "+response.text
        list_role_id = response.json()["data"]["id"]

        create_list_two_role = {
            "name": "list_role_"+self.FEED_TWO_HASH,
            "lists": [ {"id": self.__feed_list_id[self.FEED_TWO_HASH],
                        "permissions": ["list:get","list:manage"] } ]
        }
        response = self.admin_session.post(LISTMONK_URL+"/api/roles/lists", json=create_list_two_role)
        assert (response.status_code == HTTPStatus.OK), "Set up failed. Make list role: "+response.text
        other_list_role_id = response.json()["data"]["id"]

        user_data = {
            "username": "user_"+self.FEED_ONE_HASH,
            "email": "", "name":"",
            "type": "api", "status": "enabled",
            "password": None, "password_login": False,
            "password2": None, "passwordLogin": False,
            "userRoleId": self.__limited_user_role_id, "listRoleId": list_role_id,
            "user_role_id": self.__limited_user_role_id, "list_role_id": list_role_id
        }
        response = self.admin_session.post(LISTMONK_URL+"/api/users", json=user_data)
        assert (response.status_code == HTTPStatus.OK), "Set up failed. Make user: "+response.text
        returnData = {response.json()["data"]["username"]: response.json()["data"]["password"]}

        user_two_data = {
            "username": "user_"+self.FEED_TWO_HASH,
            "email": "", "name":"",
            "type": "api", "status": "enabled",
            "password": None, "password_login": False,
            "password2": None, "passwordLogin": False,
            "userRoleId": self.__limited_user_role_id, "listRoleId": other_list_role_id,
            "user_role_id": self.__limited_user_role_id, "list_role_id": other_list_role_id
        }
        response = self.admin_session.post(LISTMONK_URL+"/api/users", json=user_two_data)
        assert (response.status_code == HTTPStatus.OK), "Set up failed. Make user: "+response.text
        returnData[response.json()["data"]["username"]] = response.json()["data"]["password"]

        # Excluding feed three

        return returnData


    def _make_feed_templates(self):
        """Creating templates used for testing. Independent of the feed list creation"""
        # Subscribe/unsubscribe templates
        template_data = {
            "name": self.FEED_ONE_HASH+"-subscribe",
            "subject": "Subject Line: You requested to be subscribed",
            "type": "tx",
            "body": "<html><body></body></html>"
        }
        response = self.admin_session.post(LISTMONK_URL+"/api/templates", json=template_data)
        assert (response.status_code == HTTPStatus.OK), "Set up failed. Make feed template: "+response.text
        template_two_data = {
            "name": self.FEED_ONE_HASH+"-unsubscribe",
            "subject": "Subject Line: You are now unsubscribed",
            "type": "tx",
            "body": "<html><body></body></html>"
        }
        response = self.admin_session.post(LISTMONK_URL+"/api/templates", json=template_two_data)
        assert (response.status_code == HTTPStatus.OK), "Set up failed. Make feed template: "+response.text

        # Digest templates required for feed processing (use underscore: instant_digest, daily_digest)
        instant_digest_data = {
            "name": self.FEED_ONE_HASH+"-instant_digest",
            "subject": "{{ .Tx.Data.subject }}",
            "type": "tx",
            "body": "<html><body>{{ .Tx.Data.item.title }}</body></html>"
        }
        response = self.admin_session.post(LISTMONK_URL+"/api/templates", json=instant_digest_data)
        assert (response.status_code == HTTPStatus.OK), "Set up failed. Make instant digest template: "+response.text

        daily_digest_data = {
            "name": self.FEED_ONE_HASH+"-daily_digest",
            "subject": "Daily Digest",
            "type": "tx",
            "body": "<html><body>{{ range .Tx.Data.items }}{{ .title }}{{ end }}</body></html>"
        }
        response = self.admin_session.post(LISTMONK_URL+"/api/templates", json=daily_digest_data)
        assert (response.status_code == HTTPStatus.OK), "Set up failed. Make daily digest template: "+response.text


    def _make_feed_subscriber(self, confirmed: bool) -> dict[str, str]:
        returnVal = {} # Returns the subscriber and either the token, or the confirmation key

        # Make subscriber that has ONE pending or has been confirmed subscription
        user_one_token_or_guid = {}
        subscriber_data = {
            "email": "example@example.com",
            "preconfirm_subscriptions": True,
            "status": "enabled",
            "lists": [self.__feed_list_id[self.FEED_ONE_HASH]]
        }

        if confirmed:
            subscriber_data["attribs"] = {
                self.FEED_ONE_HASH: {
                    "filter": {"instant": {"ministers": [1, 2], "portfolio": [1110, 1111], "region": [5, 7]}},
                    "token": "900a558ca21afbd04fc10f18aa120e0c"                              
                }
            }
            user_one_token_or_guid[self.FEED_ONE_HASH] = "900a558ca21afbd04fc10f18aa120e0c"
        else:
            subscriber_data["attribs"] = {
                self.FEED_ONE_HASH: {
                    "c870fb40d6c54cd39a2d3b9c88b7d456": {
                        "expires": int((datetime.now(timezone.utc) + timedelta(days=1)).timestamp()),
                        "filter": {"instant": {"ministers": [1, 2], "portfolio": [1110, 1111], "region": [5, 7]}},
                    }
                }
            }
            user_one_token_or_guid[self.FEED_ONE_HASH] = "c870fb40d6c54cd39a2d3b9c88b7d456"
        response = self.admin_session.post(LISTMONK_URL+"/api/subscribers", json=subscriber_data)
        assert (response.status_code == HTTPStatus.OK), "Set up failed. Make feed subscriber: "+response.text
        self.one_feed_subscriber_uuid = response.json()["data"]["uuid"]
        returnVal[self.one_feed_subscriber_uuid] = user_one_token_or_guid # Get the UUID from the response

        # Make subscriber that has TWO pending or has been confirmed subscription
        user_two_token_or_guid = {}
        subscriber_two_data = {
            "email": "two-feed-subscriber@example.com",
            "preconfirm_subscriptions": True,
            "status": "enabled",
            "lists": [self.__feed_list_id[self.FEED_ONE_HASH],
                      self.__feed_list_id[self.FEED_TWO_HASH]]
        }

        if confirmed:
            subscriber_two_data["attribs"] = {
                self.FEED_ONE_HASH: {
                    "filter": {"instant": {"ministers": [1, 2], "portfolio": [1110, 1111], "region": [5, 7]}},
                    "token": "91238e275a6c7f281ca5846e56a27c53"
                },
                self.FEED_TWO_HASH: {
                    "filter": {"instant": {"ministers": [0, 1], "portfolio": [2170, 2166], "region": [2, 3]}},
                    "token": "21286da0cb7c4f8083ca5846e5627c41"
                }
            }
            user_two_token_or_guid[self.FEED_ONE_HASH] = "91238e275a6c7f281ca5846e56a27c53"
            user_two_token_or_guid[self.FEED_TWO_HASH] = "21286da0cb7c4f8083ca5846e5627c41"
        else:
            subscriber_two_data["attribs"] = {
                self.FEED_ONE_HASH: {
                    "810c3fb40d6c54cda9a2d369c8b2d77a": {
                        "expires": int((datetime.now(timezone.utc) + timedelta(days=1)).timestamp()),
                        "filter": {"instant": {"ministers": [1, 2], "portfolio": [1110, 1111], "region": [5, 7]}}
                    }
                },
                self.FEED_TWO_HASH: {
                    "c870fb40d6c54cd39a2d3b9c88b7d456": {
                        "expires": int((datetime.now(timezone.utc) + timedelta(days=1)).timestamp()),
                        "filter": {"instant": {"ministers": [0, 1], "portfolio": [2170, 2166], "region": [2, 3]}}
                    }
                }
            }
            user_two_token_or_guid[self.FEED_ONE_HASH] = "810c3fb40d6c54cda9a2d369c8b2d77a"
            user_two_token_or_guid[self.FEED_TWO_HASH] = "c870fb40d6c54cd39a2d3b9c88b7d456"
        response = self.admin_session.post(LISTMONK_URL+"/api/subscribers", json=subscriber_two_data)
        assert (response.status_code == HTTPStatus.OK), "Set up failed. Make feed subscriber: "+response.text
        self.two_feed_subscriber_uuid = response.json()["data"]["uuid"]
        returnVal[self.two_feed_subscriber_uuid] = user_two_token_or_guid # Get the UUID from the response
        return returnVal
