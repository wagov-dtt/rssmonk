import json
import time
import pytest
import requests
import unittest
from datetime import datetime, timedelta, timezone
from enum import IntEnum
from http import HTTPStatus
from requests.auth import HTTPBasicAuth

RSSMONK_URL = "http://localhost:8000"
LISTMONK_URL = "http://localhost:9000"
MAILPIT_URL = "http://localhost:8025"

def make_admin_session() -> requests.Session:
    # Create the session into Listmonk
    admin_session = requests.Session()

    response = admin_session.get(f"{LISTMONK_URL}/admin/login")
    nonce = admin_session.cookies.get("nonce")
    assert nonce, "Nonce not found in cookies"
    login_data={
        "username": "admin",
        "password": "admin123", # Taken from /workspaces/rssmonk/kustomize/base/secrets.yaml
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
        "app.concurrency": 10,
        "app.max_send_errors": 1000,
        "app.message_rate": 10,
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
                "max_conns": 10,
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
    assert response.status_code == 200
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


@pytest.mark.usefixtures("listmonk_setup")
class ListmonkClientTestBase(unittest.TestCase):
    """This is the base of the testing with RSSMonk and downstream Listmonk, setting them up and tear down."""
    FEED_HASH_ONE = "0cb1e00d5415d57f19b547084a93900a558caafbd04fc10f18aa20e0c46a02a8"
    FEED_HASH_TWO = "a1ca7266e62dee5b39ad9622740e9a1e1275057f99a501eace02da174cf7bd14"
    FEED_ONE_FEED_URL = "https://example.com/rss/media-statements"
    FEED_TWO_FEED_URL = "https://somewhere.com/rss"
    
    ADMIN_AUTH = HTTPBasicAuth("admin", "admin123") # Default k3d credentials
    admin_session = make_admin_session()
    one_feed_subscriber_uuid = ""
    two_feed_subscriber_uuid = ""
    __limited_user_role_id = -1
    __feed_list_id = {}


    @classmethod
    def setUpClass(cls):
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

    def tearDown(self):
        # Empty lists, subscribers, templates and list roles.
        self.delete_list_roles()
        self.delete_user_roles()
        self.delete_users()
        self.delete_lists()
        self.delete_subscribers()
        self.delete_templates()
        self.clear_mailpit_messages()

    @classmethod
    def delete_lists(cls):
        # Testing purposes assume low counts
        response = cls.admin_session.get(f"{LISTMONK_URL}/api/lists")
        lists_data = dict(response.json()).get("data", {}).get("results", [])
        for list_data in lists_data:
            cls.admin_session.delete(f"{LISTMONK_URL}/api/lists/{list_data['id']}")

    @classmethod
    def delete_subscribers(cls):
        cls.admin_session.delete(f"{LISTMONK_URL}/api/maintenance/subscribers/orphan")
        response = cls.admin_session.get(f"{LISTMONK_URL}/api/subscribers?list_id=&search=&query=&page=1&subscription_status=&order_by=id&order=desc")
        lists_data = dict(response.json()).get("data", {}).get("results", [])
        for list_data in lists_data:
            cls.admin_session.delete(f"{LISTMONK_URL}/api/subscribers/{list_data['id']}")

    @classmethod
    def delete_templates(cls):
        response = cls.admin_session.get(f"{LISTMONK_URL}/api/templates")
        lists_data = response.json()["data"]
        for list_data in lists_data:
            cls.admin_session.delete(f"{LISTMONK_URL}/api/templates/{list_data['id']}")

    @classmethod
    def delete_list_roles(cls):
        response = cls.admin_session.get(f"{LISTMONK_URL}/api/roles/lists")
        lists_data = response.json()["data"]
        for list_data in lists_data:
            cls.admin_session.delete(f"{LISTMONK_URL}/api/roles/{list_data['id']}")

    @classmethod
    def delete_user_roles(cls):
        response = cls.admin_session.get(f"{LISTMONK_URL}/api/roles/users")
        lists_data = response.json()["data"]
        for list_data in lists_data:
            cls.admin_session.delete(f"{LISTMONK_URL}/api/roles/{list_data['id']}")

    @classmethod
    def delete_users(cls):
        response = cls.admin_session.get(f"{LISTMONK_URL}/api/users")
        lists_data = response.json()["data"]
        for list_data in lists_data:
            if list_data['id'] != 1:
                cls.admin_session.delete(f"{LISTMONK_URL}/api/users/{list_data['id']}")

    @classmethod
    def clear_mailpit_messages(cls):
        # Clean up mailpit
        sessions = requests.Session()
        sessions.get(MAILPIT_URL)
        sessions.delete(MAILPIT_URL+"/api/v1/messages") # Either 200 or 302

    #-------------------------
    # Helper functions to set up functionality
    #-------------------------
    def initialise_system(self, phase: UnitTestLifecyclePhase) -> UnitTestInitialisedData:
        # LifecyclePhase.NONE is a noop
        data = UnitTestInitialisedData()

        if phase.value >= UnitTestLifecyclePhase.FEED_LIST.value:
            if phase.value >= UnitTestLifecyclePhase.FEED_ACCOUNT.value:
                data.accounts = self._make_feed_list_and_accounts()
            else:
                self._make_feed_list()

        if phase.value >= UnitTestLifecyclePhase.FEED_TEMPLATES.value:
            self._make_feed_templates()

        if phase.value >= UnitTestLifecyclePhase.FEED_SUBSCRIBED.value:
            data.subscribers = self._make_feed_subscriber(phase >= UnitTestLifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)

        return data


    def _make_feed_list(self):
        """Creating single feed used for testing"""
        create_feed_data = {
            "name": "Example Media Statements",
            "type": "private",
            "optin": "single",
            "tags": [
                "freq:instant",
                "freq:daily",
                "url:"+self.FEED_HASH_ONE
            ],
            "description": f"RSS Feed: {self.FEED_ONE_FEED_URL}\nSubscription URL: https://example.com/media-statements"
        }
        response = self.admin_session.post(LISTMONK_URL+"/api/lists", json=create_feed_data)
        assert (response.status_code == HTTPStatus.OK), "Set up failed. Make feed: "+response.text
        self.__feed_list_id[self.FEED_HASH_ONE] = response.json()["data"]["id"]


    def _make_feed_list_and_accounts(self) -> dict[str, dict[str, str]]:
        """Creating two feeds and accounts used for testing"""
        create_feed_data = {
            "name": "Example Media Statements",
            "type": "private",
            "optin": "single",
            "tags": [
                "freq:instant",
                "freq:daily",
                "url:"+self.FEED_HASH_ONE
            ],
            "description": f"RSS Feed: {self.FEED_ONE_FEED_URL}\nSubscription URL: https://example.com/media-statements"
        }
        response = self.admin_session.post(LISTMONK_URL+"/api/lists", json=create_feed_data)
        assert (response.status_code == HTTPStatus.OK), "Set up failed. Make feed: "+response.text
        self.__feed_list_id[self.FEED_HASH_ONE] = response.json()["data"]["id"]

        create_feed_two_data = {
            "name": "Somewhere Statements",
            "type": "private",
            "optin": "single",
            "tags": [
                "freq:instant",
                "url:"+self.FEED_HASH_TWO
            ],
            "description": f"RSS Feed: {self.FEED_TWO_FEED_URL}\nSubscription URL: https://somewhere.com/media-statements"
        }
        response = self.admin_session.post(LISTMONK_URL+"/api/lists", json=create_feed_two_data)
        assert (response.status_code == HTTPStatus.OK), "Set up failed. Make feed: "+response.text
        self.__feed_list_id[self.FEED_HASH_TWO] = response.json()["data"]["id"]

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
            "name": "list_role_"+self.FEED_HASH_ONE,
            "lists": [ {"id": self.__feed_list_id[self.FEED_HASH_ONE],
                        "permissions": ["list:get","list:manage"] } ]
        }
        response = self.admin_session.post(LISTMONK_URL+"/api/roles/lists", json=create_list_role)
        assert (response.status_code == HTTPStatus.OK), "Set up failed. Make list role: "+response.text
        list_role_id = response.json()["data"]["id"]

        create_list_two_role = {
            "name": "list_role_"+self.FEED_HASH_TWO,
            "lists": [ {"id": self.__feed_list_id[self.FEED_HASH_TWO],
                        "permissions": ["list:get","list:manage"] } ]
        }
        response = self.admin_session.post(LISTMONK_URL+"/api/roles/lists", json=create_list_two_role)
        assert (response.status_code == HTTPStatus.OK), "Set up failed. Make list role: "+response.text
        other_list_role_id = response.json()["data"]["id"]

        user_data = {
            "username": "user_"+self.FEED_HASH_ONE,
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
            "username": "user_"+self.FEED_HASH_TWO,
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

        return returnData


    def _make_feed_templates(self):
        """Creating templates used for testing. Independant of the feed list creation"""
        template_data = {
            "name": self.FEED_HASH_ONE+"-subscribe",
            "subject": "Subscribed Subject Line",
            "type": "tx",
            "body": "<html><body></body></html>"
        }
        response = self.admin_session.post(LISTMONK_URL+"/api/templates", json=template_data)
        assert (response.status_code == HTTPStatus.OK), "Set up failed. Make feed template: "+response.text
        template_two_data = {
            "name": self.FEED_HASH_ONE+"-unsubscribe",
            "subject": "Unsubscribed Subject Line",
            "type": "tx",
            "body": "<html><body></body></html>"
        }
        response = self.admin_session.post(LISTMONK_URL+"/api/templates", json=template_two_data)
        assert (response.status_code == HTTPStatus.OK), "Set up failed. Make feed template: "+response.text


    def _make_feed_subscriber(self, confirmed: bool) -> dict[str, str]:
        returnVal = {} # Returns the subscriber and either the token, or the confirmation key

        # Make subscriber that has ONE pending or has been confirmed subscription
        user_one_token_or_guid = {}
        subscriber_data = {
            "email": "example@example.com",
            "preconfirm_subscriptions": True,
            "status": "enabled",
            "lists": [self.__feed_list_id[self.FEED_HASH_ONE]]
        }

        if confirmed:
            subscriber_data["attribs"] = {
                self.FEED_HASH_ONE: {
                    "filter": {"instant": {"ministers": [1, 2], "portfolio": [1110, 1111], "region": [5, 7]}},
                    "token": "900a558ca21afbd04fc10f18aa120e0c"                              
                }
            }
            user_one_token_or_guid[self.FEED_HASH_ONE] = "900a558ca21afbd04fc10f18aa120e0c"
        else:
            subscriber_data["attribs"] = {
                self.FEED_HASH_ONE: {
                    "c870fb40d6c54cd39a2d3b9c88b7d456": {
                        "expires": int((datetime.now(timezone.utc) + timedelta(days=1)).timestamp()),
                        "filter": {"instant": {"ministers": [1, 2], "portfolio": [1110, 1111], "region": [5, 7]}},
                    }
                }
            }
            user_one_token_or_guid[self.FEED_HASH_ONE] = "c870fb40d6c54cd39a2d3b9c88b7d456"
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
            "lists": [self.__feed_list_id[self.FEED_HASH_ONE],
                      self.__feed_list_id[self.FEED_HASH_TWO]]
        }

        if confirmed:
            subscriber_two_data["attribs"] = {
                self.FEED_HASH_ONE: {
                    "filter": {"instant": {"ministers": [1, 2], "portfolio": [1110, 1111], "region": [5, 7]}},
                    "token": "91238e275a6c7f281ca5846e56a27c53"
                },
                self.FEED_HASH_TWO: {
                    "filter": {"instant": {"ministers": [0, 1], "portfolio": [2170, 2166], "region": [2, 3]}},
                    "token": "21286da0cb7c4f8083ca5846e5627c41"
                }
            }
            user_two_token_or_guid[self.FEED_HASH_ONE] = "91238e275a6c7f281ca5846e56a27c53"
            user_two_token_or_guid[self.FEED_HASH_TWO] = "21286da0cb7c4f8083ca5846e5627c41"
        else:
            subscriber_two_data["attribs"] = {
                self.FEED_HASH_ONE: {
                    "810c3fb40d6c54cda9a2d369c8b2d77a": {
                        "expires": int((datetime.now(timezone.utc) + timedelta(days=1)).timestamp()),
                        "filter": {"instant": {"ministers": [1, 2], "portfolio": [1110, 1111], "region": [5, 7]}}
                    }
                },
                self.FEED_HASH_TWO: {
                    "c870fb40d6c54cd39a2d3b9c88b7d456": {
                        "expires": int((datetime.now(timezone.utc) + timedelta(days=1)).timestamp()),
                        "filter": {"instant": {"ministers": [0, 1], "portfolio": [2170, 2166], "region": [2, 3]}}
                    }
                }
            }
            user_two_token_or_guid[self.FEED_HASH_ONE] = "810c3fb40d6c54cda9a2d369c8b2d77a"
            user_two_token_or_guid[self.FEED_HASH_TWO] = "c870fb40d6c54cd39a2d3b9c88b7d456"
        response = self.admin_session.post(LISTMONK_URL+"/api/subscribers", json=subscriber_two_data)
        assert (response.status_code == HTTPStatus.OK), "Set up failed. Make feed subscriber: "+response.text
        self.two_feed_subscriber_uuid = response.json()["data"]["uuid"]
        returnVal[self.two_feed_subscriber_uuid] = user_two_token_or_guid # Get the UUID from the response
        return returnVal
