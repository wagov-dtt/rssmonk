# This pytest is to test the entire lifecycle of a feed, primarily as a sanity check on changes
# - Feed creation
# - Feed account creation
# - Feed template insertions
# - Subscribe to feed
# - Confirm subscription to feed
# - Unsubscribe from feed
# - Delete feed
# Requires k3s to be running with a freshly created RSSMonk, Listmonk and Postgres running
import json
import time
import unittest

from http import HTTPStatus
import requests
from requests.auth import HTTPBasicAuth


admin_session = requests.Session()
admin_auth=HTTPBasicAuth("admin", "admin123") # Default k3d credentials
RSSMONK_URL = "http://localhost:8000"
LISTMONK_URL = "http://localhost:9000"
MAILPIT_URL = "http://localhost:8025"

class TestLifeCycleMethods(unittest.TestCase):
    def setUp(self):

        # Create the session into Listmonk
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
            assert False, "Failed to create prereq admin session to Listmonk"

        admin_session.delete(f"{LISTMONK_URL}/api/maintenance/subscribers/orphan")

        # Empty lists, subscribers, templates and list roles.
        # Testing purposes assume low counts
        response = admin_session.get(f"{LISTMONK_URL}/api/lists?minimal=True&per_page=all")
        data = dict(response.json()).get("data", {})
        lists_data = data.get("results", []) if isinstance(data, dict) else []
        for list_data in lists_data:
            admin_session.delete(f"{LISTMONK_URL}/api/lists/{list_data['id']}")

        response = admin_session.get(f"{LISTMONK_URL}/api/subscribers?list_id=&search=&query=&page=1&subscription_status=&order_by=id&order=desc")
        data = dict(response.json()).get("data", {})
        lists_data = data.get("results", []) if isinstance(data, dict) else []
        for list_data in lists_data:
            admin_session.delete(f"{LISTMONK_URL}/api/subscribers/{list_data['id']}")

        response = admin_session.get(f"{LISTMONK_URL}/api/templates")
        lists_data = response.json()["data"]
        for list_data in lists_data:
            admin_session.delete(f"{LISTMONK_URL}/api/templates/{list_data['id']}")

        response = admin_session.get(f"{LISTMONK_URL}/api/roles/lists")
        lists_data = response.json()["data"]
        for list_data in lists_data:
            admin_session.delete(f"{LISTMONK_URL}/api/roles/{list_data['id']}")

        # Modify settings to ensure mailpit is accessible
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
        time.sleep(5)

        # Clean up mailpit
        sessions = requests.Session()
        response = sessions.get(MAILPIT_URL)
        response = sessions.delete(MAILPIT_URL+"/api/v1/messages")


    def test_accounts_lifecycle(self):
        """Singular test for an account from creation to destruction"""


        # - Feed creation, successfully
        create_feed_data = {
            "feed_url": "https://example.com/rss/example",
            "email_base_url": "https://example.com/media",
            "frequency": ["instant", "daily"],
            "name": "Example Media Statements"
        }
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=admin_auth, json=create_feed_data)
        assert (response.status_code == HTTPStatus.CREATED), response.text
        response_json = response.json()
        assert isinstance(response_json, dict)
        # Check values reflected back
        for key, item in create_feed_data.items():
            assert key in response_json, f"{key} not found in response"
            assert item == response_json[key], f"Non matching values for {key}; in: {item}, out:{response_json[key]}"
        assert "id" in response_json
        assert "url_hash" in response_json and "091886d9077436f1ef717ac00a5e2034469bfc011699d0f46f88da90269fb180" == response_json["url_hash"]

        # - Feed account creation, successfully
        create_account = {
            "feed_url": "https://example.com/rss/example"
        }
        response = requests.post(RSSMONK_URL+"/api/feeds/account", auth=admin_auth, json=create_account)
        assert (response.status_code == HTTPStatus.CREATED), response.text
        response_json = response.json()
        assert isinstance(response_json, dict)
        assert {"id", "name", "api_password"} == set(response_json.keys())
        example_username = response_json["name"]
        example_password = response_json["api_password"]

        assert example_username == "user_091886d9077436f1ef717ac00a5e2034469bfc011699d0f46f88da90269fb180"
        assert example_password

        # Create local account
        account_auth=HTTPBasicAuth(example_username, example_password)

        # - Subscribe to feed, before subscribe template is created
        subscribe_data = {
            "email": "unsuccessful_test@test.com",
            "filter": {
                "instant": {
                    "ministers": [1, 2],
                    "region": [2, 3],
                    "portfolio": [1 ,2]
                }
            },
            "display_text": {
                "instant" : {
                    "ministers": ["Minister 1", "Minister 2"],
                    "region": ["Region 2", "Region 3"],
                    "portfolio": ["Portfolio 1", "Portfolio 2"]
                }
            }
        }
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=account_auth, json=subscribe_data)
        assert (response.status_code == HTTPStatus.BAD_REQUEST), response.text
        response_json = response.json()
        assert isinstance(response_json, dict)
        assert "Pending subscription added, but template dependancy missing for subscribe" == response_json["error"]

        # - Feed template insertions
        sub_template_data = {
            "feed_url": "https://example.com/rss/example",
            "template_type": "tx",
            "phase_type": "subscribe",
            "subject": "Please confirm email preferences for WA media statements",
            "body": "<html><body>\r\n<p>Thank you for subscribing to media statement updates from the WA Government.</p>\r\n<p>To start receiving "
                    + "updates, please verify your email address by clicking on the link below:</p>\r\n<a href=\"{{ .Tx.Data.confirmation_link }}\" "
                    + "target=\"_blank\" rel=\"noopener noreferrer\">{{ .Tx.Data.confirmation_link }}</a></p>\r\n<p>You have subscribed to the "
                    + "following statements:</p>\r\n{{ $ministers := index .Tx.Data.filter \"ministers\" }}\r\n{{ if $ministers }}\r\n<p><b>Minister(s)"
                    + "</b>\r\n<ul>\r\n {{range $val := $ministers}}\r\n <li>{{ $val }}</li>\r\n {{end}}\r\n</ul>\r\n</p>{{ end }}\r\n{{ $region := "
                    + "index .Tx.Data.filter \"region\" }}\r\n{{ if $region }}\r\n<p><b>Region(s)</b><br>\r\n<ul>\r\n {{range $val := $region}}\r\n "
                    + "<li>{{ $val }}</li>\r\n {{end}}\r\n</ul>\r\n</p>\r\n{{ end }}\r\n{{ $portfolio := index .Tx.Data.filter \"portfolio\" }}\r\n{{ "
                    + "if $portfolio }}\r\n<p><b>Portfolio(s)</b><br>\r\n<ul>\r\n {{range $val := $portfolio}}\r\n <li>{{ $val }}</li>\r\n {{end}}\r\n"
                    + "</ul>\r\n</p>\r\n{{ end }}\r\n<p>This link will expire in 24 hours for your security. If it expires, you can return to the <a"
                    + " href=\"{{ .Tx.Data.subscription_link }}\" target=\"_blank\" rel=\"noopener noreferrer\">subscription page</a> and start again."
                    + "</p>\r\n<p>If you did not make this request, please ignore this email.</p>\r\n<p>Thank you.</p>\r\n<p><b>WA Government Media "
                    + "Statement Team.</b></p>\r\n</body></html>"
        }
        response = requests.post(RSSMONK_URL+"/api/feeds/templates", auth=account_auth, json=sub_template_data)
        assert (response.status_code == HTTPStatus.CREATED), response.text
        response_json = response.json()
        assert isinstance(response_json, dict)
        # Check values reflected back, except for feed_url which has been turned into a hash
        del sub_template_data["feed_url"]
        del sub_template_data["phase_type"]
        sub_template_data["type"] = sub_template_data["template_type"]
        del sub_template_data["template_type"]
        for key, item in sub_template_data.items():
            assert key in response_json, f"{key} not found in response"
            assert item == response_json[key], f"Non matching values for {key}; in: {item}, out:{response_json[key]}"
        assert "id" in response_json
        assert "name" in response_json
        assert response_json["name"]  == "091886d9077436f1ef717ac00a5e2034469bfc011699d0f46f88da90269fb180-subscribe"

        # - Subscribe to feed, successfully
        subscribe_data = {
            "email": "test@test.com",
            "filter": {
                "instant": {
                    "ministers": [1, 2],
                    "region": [2, 3],
                    "portfolio": [1 ,2]
                }
            },
            "display_text": {
                "instant" : {
                    "ministers": ["Minister 1", "Minister 2"],
                    "region": ["Region 2", "Region 3"],
                    "portfolio": ["Portfolio 1", "Portfolio 2"]
                }
            }
        }
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=account_auth, json=subscribe_data)
        assert (response.status_code == HTTPStatus.OK), response.text
        response_json = response.json()
        assert isinstance(response_json, dict)
        assert "Subscription successful" == response_json["message"]

        # Get the guid from the subscriber attrib in feed and id is the subscriber"s uuid
        response = admin_session.get(LISTMONK_URL+"/api/subscribers", json={"query": "subscribers.email = 'test@test.com'"})
        subscriber = response.json()["data"]["results"][0]
        subscriber_uuid = str(subscriber["uuid"])
        assert "091886d9077436f1ef717ac00a5e2034469bfc011699d0f46f88da90269fb180" in subscriber["attribs"]
        feed_attribs = subscriber["attribs"]["091886d9077436f1ef717ac00a5e2034469bfc011699d0f46f88da90269fb180"]
        # Should only be a single item in here, the key is the guid.
        assert isinstance(feed_attribs, dict)
        assert "filter" not in feed_attribs
        assert "token" not in feed_attribs
        assert 1 == len(feed_attribs.keys())
        subscriber_guid = (list(feed_attribs.keys()))[0]

        # Sanity check mailpit for an email which looks like it will match what was sent out
        response = requests.get(MAILPIT_URL+"/api/v1/messages?limit=50")
        assert 1 == response.json()["unread"]
        assert "Please confirm email preferences for WA media statements" == response.json()["messages"][0]["Subject"]

        # - Confirm subscription to feed, successfully
        confirm_sub_data = {
            "id": subscriber_uuid.replace("-", ""),
            "guid": subscriber_guid
        }
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe-confirm", auth=account_auth, json=confirm_sub_data)
        assert (response.status_code == HTTPStatus.OK), response.text
        # Check the feed attribs in the subscriber to ensure the filter has been set
        response = admin_session.get(LISTMONK_URL+"/api/subscribers", json={"query": "subscribers.email = 'test@test.com'"})
        subscriber = response.json()["data"]["results"][0]
        assert "091886d9077436f1ef717ac00a5e2034469bfc011699d0f46f88da90269fb180" in subscriber["attribs"]
        feed_attribs = subscriber["attribs"]["091886d9077436f1ef717ac00a5e2034469bfc011699d0f46f88da90269fb180"]
        # Filter and token would have been set here
        assert isinstance(feed_attribs, dict)
        assert "filter" in feed_attribs
        assert "token" in feed_attribs
        assert 2 == len(feed_attribs.keys())

        # Extract the token from the filter
        filter_token = feed_attribs["token"]
        assert 32 == len(filter_token) # UUID length

        # - Unsubscribe from feed, successfully
        unsub_feed_data = {
            "id": subscriber_uuid.replace("-", ""),
            "token": filter_token
        }
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=account_auth, json=unsub_feed_data)
        assert (response.status_code == HTTPStatus.OK), response.text

        # - Delete feed
        delete_feed_data = {
            "feed_url": "https://example.com/rss/example",
            "notify": False
        }
        # Attempt self deletion, failure.
        response = requests.delete(RSSMONK_URL+"/api/feeds/by-url", auth=account_auth, json=delete_feed_data)
        assert (response.status_code == HTTPStatus.UNAUTHORIZED), response.text

        # Delete with admin, successfully
        response = requests.delete(RSSMONK_URL+"/api/feeds/by-url", auth=admin_auth, json=delete_feed_data)
        assert (response.status_code == HTTPStatus.OK), response.text
        response_json = response.json()
        assert isinstance(response_json, dict)

        # - Check the lists are removed
        response = admin_session.get(f"{LISTMONK_URL}/api/lists?minimal=True&per_page=all")
        lists_data = response.json()["data"]["results"] if "results" in response.json()["data"] else []
        assert 0 == len(lists_data)

        # - Check the subscriber is no longer subscribed to the list (or has been deleted)
        response = admin_session.get(f"{LISTMONK_URL}/api/subscribers?list_id=&search=&query=&page=1&subscription_status=&order_by=id&order=desc")
        lists_data = response.json().get("data", {}).get("results", [])
        print(lists_data)


        # - Check the templates are removed
        response = admin_session.get(f"{LISTMONK_URL}/api/templates")
        lists_data = response.json()["data"]
        for list_data in lists_data:
            assert "091886d9077436f1ef717ac00a5e2034469bfc011699d0f46f88da90269fb180" not in list_data["name"]

        # - Check the user role are removed
        response = admin_session.get(f"{LISTMONK_URL}/api/roles/lists")
        lists_data = response.json()["data"]
        assert 0 == len(lists_data)

        # - Check the users if left with only admin (only role left)
        response = admin_session.get(f"{LISTMONK_URL}/api/users")
        lists_data = response.json()["data"]
        assert 1 == len(lists_data)
