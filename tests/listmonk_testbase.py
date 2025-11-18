from enum import Enum
from http import HTTPStatus
import time
from typing import Optional
import unittest
from requests.auth import HTTPBasicAuth

import requests

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


class LifecyclePhase(Enum):
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
    FEED_UNSUBSCRIBED = 6
    FEED_DELETED = 7


class ListmonkClientTestBase(unittest.TestCase):
    """This is the base of the testing with RSSMonk and downstream Listmonk, setting them up and tear down. This should """
    ADMIN_AUTH = HTTPBasicAuth("admin", "admin123") # Default k3d credentials


    @classmethod
    def setUpClass(cls):
        # Empty lists, subscribers, templates and list roles.
        cls.delete_list_roles()
        cls.delete_users()
        cls.delete_lists()
        cls.delete_subscribers()
        cls.delete_templates()
        cls.clear_mailpit_messages()

        # Modify settings to ensure mailpit is the mail client for RSSMonk
        admin_session = make_admin_session()
        response = admin_session.put(LISTMONK_URL+"/api/settings", json={
            "app.site_name": "Media Statements",
            "app.root_url": "http://localhost:9000",
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


    def tearDown(self):
        # Empty lists, subscribers, templates and list roles.
        self.delete_list_roles()
        self.delete_users()
        self.delete_lists()
        self.delete_subscribers()
        self.delete_templates()
        self.clear_mailpit_messages()

    @classmethod
    def delete_lists(cls):
        admin_session = make_admin_session()
        # Testing purposes assume low counts
        response = admin_session.get(f"{LISTMONK_URL}/api/lists")
        lists_data = dict(response.json()).get("data", {}).get("results", [])
        for list_data in lists_data:
            admin_session.delete(f"{LISTMONK_URL}/api/lists/{list_data['id']}")

    @classmethod
    def delete_subscribers(cls):
        admin_session = make_admin_session()
        admin_session.delete(f"{LISTMONK_URL}/api/maintenance/subscribers/orphan")
        response = admin_session.get(f"{LISTMONK_URL}/api/subscribers?list_id=&search=&query=&page=1&subscription_status=&order_by=id&order=desc")
        lists_data = dict(response.json()).get("data", {}).get("results", [])
        for list_data in lists_data:
            admin_session.delete(f"{LISTMONK_URL}/api/subscribers/{list_data['id']}")

    @classmethod
    def delete_templates(cls):
        admin_session = make_admin_session()
        response = admin_session.get(f"{LISTMONK_URL}/api/templates")
        lists_data = response.json()["data"]
        for list_data in lists_data:
            admin_session.delete(f"{LISTMONK_URL}/api/templates/{list_data['id']}")

    @classmethod
    def delete_list_roles(cls):
        admin_session = make_admin_session()
        response = admin_session.get(f"{LISTMONK_URL}/api/roles/lists")
        lists_data = response.json()["data"]
        for list_data in lists_data:
            admin_session.delete(f"{LISTMONK_URL}/api/roles/{list_data['id']}")

    @classmethod
    def delete_list_roles(cls):
        admin_session = make_admin_session()
        response = admin_session.get(f"{LISTMONK_URL}/api/roles/users")
        lists_data = response.json()["data"]
        for list_data in lists_data:
            admin_session.delete(f"{LISTMONK_URL}/api/roles/{list_data['id']}")

    @classmethod
    def delete_users(cls):
        admin_session = make_admin_session()
        response = admin_session.get(f"{LISTMONK_URL}/api/users")
        lists_data = response.json()["data"]
        for list_data in lists_data:
            if list_data['id'] != 1:
                admin_session.delete(f"{LISTMONK_URL}/api/users/{list_data['id']}")

    @classmethod
    def clear_mailpit_messages(cls):
        # Clean up mailpit
        sessions = requests.Session()
        sessions.get(MAILPIT_URL)
        sessions.delete(MAILPIT_URL+"/api/v1/messages") # Either 200 or 302

    #-------------------------
    # Helper functions to set up functionality
    #-------------------------
    def initialise_system(self, phase: LifecyclePhase) -> dict[str, str]:
        # LifecyclePhase.NONE is a noop
        accounts = {}

        if phase.value >= LifecyclePhase.FEED_LIST.value:
            if phase.value >= LifecyclePhase.FEED_ACCOUNT.value:
                accounts = self._make_feed_list_and_accounts()
            else:
                self._make_feed_list()

        if phase.value >= LifecyclePhase.FEED_TEMPLATES.value:
            self._make_feed_templates()

        if phase.value >= LifecyclePhase.FEED_SUBSCRIBED.value:
            self._make_feed_subscriber(phase >= LifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)

        # These are needed for testing
        # LifecyclePhase.FEED_UNSUBSCRIBED
        # LifecyclePhase.FEED_DELETED
        return accounts


    def _make_feed_list(self):
        """Creating single feed used for testing"""
        create_feed_data = {
            "name": "Example Media Statements",
            "type": "private",
            "optin": "single",
            "tags": [
                "freq:instant",
                "freq:daily",
                "url:0cb1e00d5415d57f19b547084a93900a558caafbd04fc10f18aa20e0c46a02a8"
            ],
            "description": "RSS Feed: https://example.com/rss/media-statements\nSubscription URL: https://example.com/media-statements"
        }
        response = requests.post(LISTMONK_URL+"/api/lists", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert (response.status_code == HTTPStatus.OK), "Set up failed: "+response.text


    def _make_feed_list_and_accounts(self) -> dict[str, str]:
        """Creating feed and accounts used for testing"""
        create_feed_data = {
            "name": "Example Media Statements",
            "type": "private",
            "optin": "single",
            "tags": [
                "freq:instant",
                "freq:daily",
                "url:0cb1e00d5415d57f19b547084a93900a558caafbd04fc10f18aa20e0c46a02a8"
            ],
            "description": "RSS Feed: https://example.com/rss/media-statements\nSubscription URL: https://example.com/media-statements"
        }
        response = requests.post(LISTMONK_URL+"/api/lists", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert (response.status_code == HTTPStatus.OK), "Set up failed: "+response.text
        list_id = response.json()["id"]

        create_feed_data = {
            "name": "Somewhere Statements",
            "type": "private",
            "optin": "single",
            "tags": [
                "freq:instant",
                "url:a1ca7266e62dee5b39ad9622740e9a1e1275057f99a501eace02da174cf7bd14"
            ],
            "description": "RSS Feed: https://somewhere.com/rss\nSubscription URL: https://somewhere.com/media-statements"
        }
        response = requests.post(LISTMONK_URL+"/api/lists", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert (response.status_code == HTTPStatus.OK), "Set up failed: "+response.text
        other_list_id = response.json()["id"]

        payload= {
            "name": "limited-user-role",
            "permissions": [
                "subscribers:get",
                "subscribers:manage",
                "tx:send",
                "templates:get"
            ]
        }
        response = requests.post(LISTMONK_URL+"api/roles/users", json=payload)
        assert (response.status_code == HTTPStatus.CREATED), "Set up failed: "+response.text
        limited_user_role_id = response["data"]["id"]

        payload = {
            "name": "list_role_0cb1e00d5415d57f19b547084a93900a558caafbd04fc10f18aa20e0c46a02a8",
            "lists": [ {"id": list_id, "permissions": ["list:get","list:manage"] } ]
        }
        response = requests.post(LISTMONK_URL+"/api/roles/lists", json=payload)
        assert (response.status_code == HTTPStatus.CREATED), "Set up failed: "+response.text
        list_role_id = response["data"]["id"]

        payload = {
            "name": "list_role_a1ca7266e62dee5b39ad9622740e9a1e1275057f99a501eace02da174cf7bd14",
            "lists": [ {"id": other_list_id, "permissions": ["list:get","list:manage"] } ]
        }
        response = requests.post(LISTMONK_URL+"/api/roles/lists", json=payload)
        assert (response.status_code == HTTPStatus.CREATED), "Set up failed: "+response.text
        other_list_role_id = response["data"]["id"]

        user_data = {
            "username": "user_0cb1e00d5415d57f19b547084a93900a558caafbd04fc10f18aa20e0c46a02a8",
            "email": "", "name":"",
            "type": "api", "status": "enabled",
            "password": None, "password_login": False,
            "password2": None, "passwordLogin": False,
            "userRoleId": limited_user_role_id, "listRoleId": list_role_id,
            "user_role_id": limited_user_role_id, "list_role_id": list_role_id
        }
        response = requests.post(LISTMONK_URL+"/api/users", json=user_data)
        assert (response.status_code == HTTPStatus.CREATED), "Set up failed: "+response.text
        returnData = {response["data"]["username"]: response["data"]["password"]}

        user_data = {
            "username": "user_a1ca7266e62dee5b39ad9622740e9a1e1275057f99a501eace02da174cf7bd14",
            "email": "", "name":"",
            "type": "api", "status": "enabled",
            "password": None, "password_login": False,
            "password2": None, "passwordLogin": False,
            "userRoleId": other_list_role_id, "listRoleId": list_role_id,
            "user_role_id": other_list_role_id, "list_role_id": list_role_id
        }
        response = requests.post(LISTMONK_URL+"/api/users", json=user_data)
        assert (response.status_code == HTTPStatus.CREATED), "Set up failed: "+response.text
        returnData[response["data"]["username"]] = response["data"]["password"]

        return returnData


    def _make_feed_templates(self):
        """Creating templates used for testing. Independant of the feed list creation"""
        template_data = {
            "name": "0cb1e00d5415d57f19b547084a93900a558caafbd04fc10f18aa20e0c46a02a8-subscribe",
            "subject": "Subject Line",
            "type": "tx",
            "body": "<html><body></body></html>"
        }
        response = requests.post(LISTMONK_URL+"/api/templates", auth=self.ADMIN_AUTH, data=template_data)
        assert (response.status_code == HTTPStatus.OK), "Set up failed: "+response.text
        template_data = {
            "name": "0cb1e00d5415d57f19b547084a93900a558caafbd04fc10f18aa20e0c46a02a8-unsubscribe",
            "subject": "Subject Line",
            "type": "tx",
            "body": "<html><body></body></html>"
        }
        response = requests.post(LISTMONK_URL+"/api/templates", auth=self.ADMIN_AUTH, data=template_data)
        assert (response.status_code == HTTPStatus.OK), "Set up failed: "+response.text


    def _make_feed_subscriber(self, confirmed: bool):
        # Either make subscriber that is confirmation pending (bypass email), or has been confirmed
        pass

