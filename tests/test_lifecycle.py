# This pytest is to test the entire lifecycle of a feed, primarily as a sanity check on workflow

# - Feed creation
# - Feed account creation
# - Feed template insertions
# - Subscribe to feed
# - Confirm subscription to feed
# - Unsubscribe from feed
# - Delete feed
# Requires k3s to be running with RSSMonk, Listmonk and Postgres running
from http import HTTPStatus
import requests
from requests.auth import HTTPBasicAuth

from tests.listmonk_testbase import LISTMONK_URL, MAILPIT_URL, RSSMONK_URL, ListmonkClientTestBase, make_admin_session


class TestLifeCycleMethods(ListmonkClientTestBase):
    def test_accounts_lifecycle(self):
        """Singular test for an account from creation to destruction"""
        admin_session = make_admin_session()

        # - Feed creation, successfully
        create_feed_data = {
            "feed_url": "https://example.com/rss/example",
            "email_base_url": "https://example.com/media",
            "poll_frequencies": ["instant", "daily"],
            "name": "Example Media Statements"
        }
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
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
        response = requests.post(RSSMONK_URL+"/api/feeds/account", auth=self.ADMIN_AUTH, json=create_account)
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
        assert response.json()["unread"] == 1
        assert response.json()["messages"][0]["Subject"] == "Please confirm email preferences for WA media statements"

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
        response = requests.delete(RSSMONK_URL+"/api/feeds/by-url", auth=self.ADMIN_AUTH, json=delete_feed_data)
        assert (response.status_code == HTTPStatus.OK), response.text
        response_json = response.json()
        assert isinstance(response_json, dict)

        # - Check the lists are removed
        response = admin_session.get(f"{LISTMONK_URL}/api/lists?minimal=true&per_page=all")
        lists_data = response.json()["data"]["results"] if "results" in response.json()["data"] else []
        assert 0 == len(lists_data)

        # - Check the subscriber is no longer subscribed to the list (or has been deleted)
        response = admin_session.get(f"{LISTMONK_URL}/api/subscribers?list_id=&search=&query=&page=1&subscription_status=&order_by=id&order=desc")
        lists_data = response.json().get("data", {}).get("results", [])

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
