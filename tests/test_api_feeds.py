"""
Test Feed API endpoints
- /api/feeds
"""

from http import HTTPStatus
import requests
from requests.auth import HTTPBasicAuth

from rssmonk.types import FEED_ACCOUNT_PREFIX
from tests.conftest import LISTMONK_URL, RSSMONK_URL, UnitTestLifecyclePhase, ListmonkClientTestBase, make_admin_session


class TestRSSMonkFeeds(ListmonkClientTestBase):
    # -------------------------
    # GET /api/feeds
    # -------------------------
    def test_get_feeds_no_credentials(self):
        response = requests.get(RSSMONK_URL + "/api/feeds", auth=None)
        assert response.status_code == HTTPStatus.UNAUTHORIZED

    def test_get_feeds_unauthorized_user(self):
        response = requests.get(RSSMONK_URL + "/api/feeds", auth=HTTPBasicAuth("no-one", "pawword"))
        assert response.status_code == HTTPStatus.UNAUTHORIZED

    def test_get_feeds_non_admin_credentials(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_SUBSCRIBED)
        user, pwd = next(iter(init_data.accounts.items()))

        response = requests.get(RSSMONK_URL + "/api/feeds", auth=HTTPBasicAuth(user, pwd))
        assert response.status_code == HTTPStatus.OK

    def test_get_feeds_admin_credentials(self):
        response = requests.get(RSSMONK_URL + "/api/feeds", auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.OK

    def test_list_feeds_unauthorized_user(self):
        response = requests.get(RSSMONK_URL + "/api/feeds", auth=HTTPBasicAuth("no-one", "pawword"))
        assert response.status_code == HTTPStatus.UNAUTHORIZED

    def test_list_feeds_admin_success(self):
        self.initialise_system(UnitTestLifecyclePhase.FEED_LIST)

        response = requests.get(RSSMONK_URL + "/api/feeds", auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["total"] == 3
        assert len(data["feeds"]) == 3

        # Listmonk will return reverse order
        assert data["feeds"][0]["feed_url"] == self.FEED_THREE_FEED_URL, data
        assert data["feeds"][1]["feed_url"] == self.FEED_TWO_FEED_URL, data
        assert data["feeds"][2]["feed_url"] == self.FEED_ONE_FEED_URL, data

    def test_list_feeds_feed_account_success(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_ACCOUNT)
        user, pwd = next(iter(init_data.accounts.items()))

        feed_auth = HTTPBasicAuth(user, pwd)
        response = requests.get(RSSMONK_URL + "/api/feeds", auth=feed_auth)
        assert response.status_code == HTTPStatus.OK, f"{response.status_code}: {response.text}"
        data = response.json()
        assert data["total"] == 1  # Feed account only sees its own feed

    def test_list_feeds_empty_list(self):
        response = requests.get(RSSMONK_URL + "/api/feeds", auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["total"] == 0
        assert data["feeds"] == []

    # -------------------------
    # POST /api/feeds - Create RSS Feed (admin only)
    # - Combinations of url, name (optional), frequency and list_visibility with no pre-existing feed
    # - Already exists with incoming frequencies being a subset of existing
    # - Already exists with incoming frequencies being a subset of existing
    # - Already exists with incoming frequencies having no overlap with existing
    # - Already exists with incoming frequencies having partial overlap with existing
    # - Invalid url, frequency and list_visibility
    # - Correct details, no credentials
    # - Correct details, non admin credentials
    # -------------------------
    def test_create_feed_incorrect_auth(self):
        # - No credentials, correct details
        create_feed_data = {
            "feed_url": "https://very-different-example.com/rss/example",
            "email_base_url": "https://very-different-example.com/media",
            "poll_frequencies": ["instant"],
        }
        response = requests.post(RSSMONK_URL + "/api/feeds", auth=None, json=create_feed_data)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"

        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
        user, pwd = next(iter(init_data.accounts.items()))
        # - Non admin credentials, correct details
        response = requests.post(RSSMONK_URL + "/api/feeds", auth=HTTPBasicAuth(user, pwd), json=create_feed_data)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"

    def test_create_feed_no_credentials(self):
        # - No account
        create_feed_data = {}
        response = requests.post(RSSMONK_URL + "/api/feeds", auth=None, json=create_feed_data)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"

    def test_create_feed_invalid_credentials(self):
        # - Invalid credentials with valid body
        create_feed_data = {
            "feed_url": "https://example.com/rss",
            "email_base_url": "https://example.com/media",
            "poll_frequencies": ["instant"],
        }
        response = requests.post(
            RSSMONK_URL + "/api/feeds", auth=HTTPBasicAuth("false", "account"), json=create_feed_data
        )
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"

    def test_create_feed_non_admin_failures(self):
        # - Invalid credentials (active account, not admin)
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
        user, pwd = next(iter(init_data.accounts.items()))
        create_feed_data = {}
        response = requests.post(RSSMONK_URL + "/api/feeds", auth=HTTPBasicAuth(user, pwd), json=create_feed_data)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"

    def test_create_feed_admin_not_full_object(self):
        # - Empty object
        create_feed_data = {}
        response = requests.post(RSSMONK_URL + "/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"

        # - feed_url only
        create_feed_data = {"feed_url": "https://example.com/rss"}
        response = requests.post(RSSMONK_URL + "/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"

        # - email_base_url only
        create_feed_data = {"email_base_url": "https://example.com/media"}
        response = requests.post(RSSMONK_URL + "/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"

        # - poll_frequencies
        create_feed_data = {"poll_frequencies": ["instant"]}
        response = requests.post(RSSMONK_URL + "/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"

        # - list_visibility
        create_feed_data = {"list_visibility": "public"}
        response = requests.post(RSSMONK_URL + "/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"

    def test_create_feed_admin_not_valid_data(self):
        # - invalid url
        create_feed_data = {
            "feed_url": "not_a_real_url",
            "email_base_url": "https://example.com/media",
            "poll_frequencies": ["instant"],
        }
        response = requests.post(RSSMONK_URL + "/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"

        # - invalid poll frequency
        create_feed_data = {
            "feed_url": "https://example.com/rss",
            "email_base_url": "https://example.com/media",
            "poll_frequencies": ["5min"],
        }
        response = requests.post(RSSMONK_URL + "/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"

        # - invalid poll frequency (protected is not valid)
        create_feed_data = {
            "feed_url": "https://example.com/rss",
            "email_base_url": "https://example.com/media",
            "poll_frequencies": ["protected"],
        }
        response = requests.post(RSSMONK_URL + "/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"

    def test_create_feeds(self):
        """
        POST /api/feeds - Create RSS Feed (admin only)
        - Successful actions which create a feed list
        """
        # - feed_url, email_base_url, poll_frequencies (accessible to fetch name)
        create_feed_data = {
            "feed_url": self.TEST_FEED_URL,
            "email_base_url": "https://example.com/media",
            "poll_frequencies": ["instant"],
        }
        response = requests.post(RSSMONK_URL + "/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert response.status_code == HTTPStatus.CREATED, f"{response.status_code}: {response.text}"
        response_json = response.json()
        assert isinstance(response_json, dict)
        assert response_json["feed_url"] == self.TEST_FEED_URL, response_json
        assert response_json["email_base_url"] == "https://example.com/media", response_json
        assert response_json["poll_frequencies"] == ["instant"], response_json
        assert "url_hash" in response_json, response_json

    def test_create_feeds_empty_frequency(self):
        # - Feed creation, feed_url, email_base_url, poll_frequencies, name
        create_feed_data = {
            "feed_url": "https://example.com/rss",
            "email_base_url": "https://example.com/media",
            "poll_frequencies": [],
            "name": "Random name",
        }
        response = requests.post(RSSMONK_URL + "/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "poll_frequencies" in response.text
        assert "List should have at least 1 item after validation" in response.text

    def test_create_feeds_name_supplied(self):
        # - Feed creation with explicit name (doesn't need to fetch feed)
        create_feed_data = {
            "feed_url": self.TEST_FEED_URL,
            "email_base_url": "https://example.com/media",
            "poll_frequencies": ["instant"],
            "name": "Custom Feed Name",
        }
        response = requests.post(RSSMONK_URL + "/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert response.status_code == HTTPStatus.CREATED, f"{response.status_code}: {response.text}"
        response_json = response.json()
        assert isinstance(response_json, dict)
        assert response_json["feed_url"] == self.TEST_FEED_URL
        assert response_json["name"] == "Custom Feed Name"
        assert "url_hash" in response_json, response_json

    # -------------------------
    # GET /api/feeds/by-url
    # -------------------------

    def test_get_feed_by_url_no_feed_no_credentials(self):
        # No credentials, no feed
        get_feed_data = {"feed_url": ""}
        response = requests.get(RSSMONK_URL + "/api/feeds/by-url", auth=None, params=get_feed_data)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"

    def test_get_feed_by_url_no_feed_non_admin(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
        user, pwd = next(iter(init_data.accounts.items()))

        # Non admin credentials, no feed
        get_feed_data = {"feed_url": ""}
        response = requests.get(RSSMONK_URL + "/api/feeds/by-url", auth=HTTPBasicAuth(user, pwd), params=get_feed_data)
        assert response.status_code == HTTPStatus.NOT_FOUND, f"{response.status_code}: {response.text}"

    def test_get_feed_by_url_no_feed_admin(self):
        # Admin credentials, no feed
        get_feed_data = {"feed_url": ""}
        response = requests.get(RSSMONK_URL + "/api/feeds/by-url", auth=self.ADMIN_AUTH, params=get_feed_data)
        assert response.status_code == HTTPStatus.NOT_FOUND, f"{response.status_code}: {response.text}"

    def test_get_feed_by_url_feed_no_credentials(self):
        self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)

        # No credentials, existing feed
        get_feed_data = {"feed_url": self.FEED_ONE_FEED_URL}
        response = requests.get(RSSMONK_URL + "/api/feeds/by-url", auth=None, params=get_feed_data)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"

    def test_get_feed_by_url_non_feed_non_admin(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
        user, pwd = next(iter(init_data.accounts.items()))

        # Non admin credentials, non existing feed
        get_feed_data = {"feed_url": "https://feed-does-not-exist.com/rss"}
        response = requests.get(RSSMONK_URL + "/api/feeds/by-url", auth=HTTPBasicAuth(user, pwd), params=get_feed_data)
        assert response.status_code == HTTPStatus.NOT_FOUND, f"{response.status_code}: {response.text}"

    def test_get_feed_by_url_feed_non_admin(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
        user, pwd = next(iter(init_data.accounts.items()))

        # Non admin credentials, unaccessible but existing feed
        response = requests.get(
            RSSMONK_URL + "/api/feeds/by-url",
            auth=HTTPBasicAuth(user, pwd),
            params={"feed_url": self.FEED_TWO_FEED_URL},
        )
        assert response.status_code == HTTPStatus.NOT_FOUND, f"{response.status_code}: {response.text}"

        # Same as above, but with admin credentials to catch errors in setup
        response = requests.get(
            RSSMONK_URL + "/api/feeds/by-url", auth=self.ADMIN_AUTH, params={"feed_url": self.FEED_TWO_FEED_URL}
        )
        assert response.status_code == HTTPStatus.OK, "Setup out of sync"

        # Non admin credentials, accessible existing feed
        response = requests.get(
            RSSMONK_URL + "/api/feeds/by-url",
            auth=HTTPBasicAuth(user, pwd),
            params={"feed_url": self.FEED_ONE_FEED_URL},
        )
        assert response.status_code == HTTPStatus.OK, f"{response.status_code}: {response.text}"
        data = response.json()
        assert "email_base_url" in data and data["email_base_url"] == "https://example.com/subscribe"
        assert "name" in data and data["name"] == "Example Media Statements"

    def test_get_feed_by_url_feed_admin(self):
        # Admin credentials, no existing feed
        get_feed_data = {"feed_url": self.FEED_THREE_FEED_URL}
        response = requests.get(RSSMONK_URL + "/api/feeds/by-url", auth=self.ADMIN_AUTH, params=get_feed_data)
        assert response.status_code == HTTPStatus.NOT_FOUND, f"{response.status_code}: {response.text}"

        self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
        # Admin credentials, existing feed
        response = requests.get(RSSMONK_URL + "/api/feeds/by-url", auth=self.ADMIN_AUTH, params=get_feed_data)
        assert response.status_code == HTTPStatus.OK, f"{response.status_code}: {response.text}"
        response_json = response.json()
        assert isinstance(response_json, dict)

    # -------------------------
    # DELETE /api/feeds/by-url
    # -------------------------

    def test_delete_feed_by_url_no_credentials(self):
        response = requests.delete(RSSMONK_URL + "/api/feeds/by-url", auth=None)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"

    def test_delete_feed_by_url_non_admin_credentials(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
        user, pwd = next(iter(init_data.accounts.items()))

        response = requests.delete(RSSMONK_URL + "/api/feeds/by-url", auth=HTTPBasicAuth(user, pwd))
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"

    def test_delete_feed_by_url_admin_no_feed(self):
        # - Delete non existing feed
        delete_feed_data = {"feed_url": "https://example.com/nonexistent.xml"}
        response = requests.delete(RSSMONK_URL + "/api/feeds/by-url", auth=self.ADMIN_AUTH, json=delete_feed_data)
        assert response.status_code == HTTPStatus.NOT_FOUND, f"{response.status_code}: {response.text}"

    def test_delete_feed_by_url_admin_success(self):
        self.initialise_system(UnitTestLifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)
        # Delete existing feed
        delete_feed_data = {"feed_url": self.FEED_ONE_FEED_URL}
        response = requests.delete(RSSMONK_URL + "/api/feeds/by-url", auth=self.ADMIN_AUTH, json=delete_feed_data)
        assert response.status_code == HTTPStatus.OK, f"{response.status_code}: {response.text}"
        response_json = response.json()
        assert isinstance(response_json, dict)

        # - Check the requested list is removed
        admin_session = make_admin_session()
        response = admin_session.get(f"{LISTMONK_URL}/api/lists?minimal=true&per_page=all")
        lists_data = response.json()["data"]["results"] if "results" in response.json()["data"] else []
        assert len(lists_data) == 2, lists_data
        for list_item in lists_data:
            assert isinstance(list_item, dict)
            assert self.FEED_ONE_FEED_URL not in list_item

        # - Check the subscriber is no longer subscribed to the list (or has been deleted)
        response = admin_session.get(
            f"{LISTMONK_URL}/api/subscribers?list_id=&search=&query=&page=1&subscription_status=&order_by=id&order=desc"
        )
        subs_data = response.json().get("data", {}).get("results", [])
        # Subscribers who were only subscribed to FEED_ONE should be deleted
        # Note: Due to how Listmonk handles cascading list deletions, all subscribers
        # may be cleaned up depending on their list membership state
        for sub in subs_data:
            # Any remaining subscriber should not have FEED_ONE in their attribs
            assert self.FEED_ONE_HASH not in sub.get("attribs", {})

        # - Check the user role for the list is removed
        response = admin_session.get(f"{LISTMONK_URL}/api/roles/lists")
        role_lists_data = response.json()["data"]
        assert len(lists_data) == 2, role_lists_data
        for list_data in role_lists_data:
            assert self.FEED_ONE_HASH not in list_data["name"]

        # - Check the users - FEED_ONE user should be deleted
        response = admin_session.get(f"{LISTMONK_URL}/api/users")
        users_data = response.json()["data"]
        # At minimum: admin + rssmonk-api. feed_two user may or may not remain.
        assert len(users_data) >= 2, users_data
        for list_data in users_data:
            assert self.FEED_ONE_HASH not in list_data["name"]

        # - Check the list templates is removed
        response = admin_session.get(f"{LISTMONK_URL}/api/templates")
        template_list_data = response.json()["data"]
        for list_data in template_list_data:
            assert self.FEED_ONE_HASH not in list_data["name"]

    # -------------------------
    # GET /api/feeds/subscribe-preferences
    # -------------------------
    def test_get_subscribe_preferences_no_credentials(self):
        response = requests.get(RSSMONK_URL + "/api/feeds/subscribe-preferences", auth=None)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"

    def test_get_subscribe_preferences_non_admin_credentials(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)
        user = FEED_ACCOUNT_PREFIX + self.FEED_ONE_HASH
        pwd = init_data.accounts[user]

        response = requests.get(RSSMONK_URL + "/api/feeds/subscribe-preferences", auth=HTTPBasicAuth(user, pwd))
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Field required" in response.text

    def test_get_subscribe_preferences_admin_credentials(self):
        response = requests.get(RSSMONK_URL + "/api/feeds/subscribe-preferences", auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Field required" in response.text

    # TODO - Still unsure what to do with these endpoints
    # -------------------------
    # GET /api/feeds/configurations
    # -------------------------

    def test_get_feed_configurations_no_credentials(self):
        response = requests.get(RSSMONK_URL + "/api/feeds/configurations", auth=None)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"

    def test_get_feed_configurations_non_admin_credentials(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
        user, pwd = next(iter(init_data.accounts.items()))

        response = requests.get(RSSMONK_URL + "/api/feeds/configurations", auth=HTTPBasicAuth(user, pwd))
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Field required" in response.text

    def test_get_feed_configurations_admin_credentials(self):
        response = requests.get(RSSMONK_URL + "/api/feeds/configurations", auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Field required" in response.text

    def test_get_feed_configurations_with_existing_feed(self):
        """Test GET /api/feeds/configurations with a feed that exists."""
        self.initialise_system(UnitTestLifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)

        # Get configurations for FEED_ONE which has both instant and daily frequencies
        response = requests.get(
            RSSMONK_URL + "/api/feeds/configurations",
            params={"feed_url": self.FEED_ONE_FEED_URL},
            auth=self.ADMIN_AUTH,
        )
        assert response.status_code == HTTPStatus.OK, f"{response.status_code}: {response.text}"

        data = response.json()
        assert "url" in data
        assert "configurations" in data
        assert "total_configurations" in data
        assert data["total_configurations"] >= 1

        # Verify configuration structure
        for config in data["configurations"]:
            assert "id" in config
            assert "name" in config
            assert "url" in config
            assert "frequency" in config
            assert "url_hash" in config

    def test_get_feed_configurations_nonexistent_feed(self):
        """Test GET /api/feeds/configurations with a feed that does not exist."""
        self.initialise_system(UnitTestLifecyclePhase.FEED_LIST)

        response = requests.get(
            RSSMONK_URL + "/api/feeds/configurations",
            params={"feed_url": "https://nonexistent.example.com/rss"},
            auth=self.ADMIN_AUTH,
        )
        assert response.status_code == HTTPStatus.OK, f"{response.status_code}: {response.text}"

        data = response.json()
        assert data["total_configurations"] == 0
        assert data["configurations"] == []

    # -------------------------
    # PUT /api/feeds/configurations
    # -------------------------
    def test_put_feed_configurations_no_credentials(self):
        response = requests.put(RSSMONK_URL + "/api/feeds/configurations", auth=None)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"

    def test_put_feed_configurations_non_admin_credentials(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
        user, pwd = next(iter(init_data.accounts.items()))

        response = requests.put(RSSMONK_URL + "/api/feeds/configurations", auth=HTTPBasicAuth(user, pwd))
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Field required" in response.text

    def test_put_feed_configurations_admin_credentials(self):
        response = requests.put(RSSMONK_URL + "/api/feeds/configurations", auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Field required" in response.text

    def test_put_feed_configurations_add_new_frequency(self):
        """Test PUT /api/feeds/configurations to add a new frequency configuration."""
        self.initialise_system(UnitTestLifecyclePhase.FEED_LIST)

        # FEED_TWO only has instant frequency, try to add daily
        update_data = {
            "feed_url": self.FEED_TWO_FEED_URL,
            "email_base_url": "https://example.com/subscribe",
            "poll_frequencies": ["daily"],
            "name": "Example Media Statements 2 - Daily",
        }

        response = requests.put(
            RSSMONK_URL + "/api/feeds/configurations",
            json=update_data,
            auth=self.ADMIN_AUTH,
        )
        assert response.status_code == HTTPStatus.OK, f"{response.status_code}: {response.text}"

        data = response.json()
        assert "action" in data
        assert data["action"] == "updated"
        assert "new_feed" in data
        assert "message" in data

    def test_put_feed_configurations_no_change_same_frequency(self):
        """Test PUT /api/feeds/configurations with same frequency returns no_change."""
        self.initialise_system(UnitTestLifecyclePhase.FEED_LIST)

        # FEED_TWO has instant frequency, try to add instant again
        update_data = {
            "feed_url": self.FEED_TWO_FEED_URL,
            "email_base_url": "https://example.com/subscribe",
            "poll_frequencies": ["instant"],
            "name": "Example Media Statements 2",
        }

        response = requests.put(
            RSSMONK_URL + "/api/feeds/configurations",
            json=update_data,
            auth=self.ADMIN_AUTH,
        )
        assert response.status_code == HTTPStatus.OK, f"{response.status_code}: {response.text}"

        data = response.json()
        assert data["action"] == "no_change"
        assert "existing_feeds" in data

    def test_put_feed_configurations_nonexistent_feed(self):
        """Test PUT /api/feeds/configurations with a feed that does not exist."""
        self.initialise_system(UnitTestLifecyclePhase.FEED_LIST)

        update_data = {
            "feed_url": "https://nonexistent.example.com/rss",
            "email_base_url": "https://example.com/subscribe",
            "poll_frequencies": ["instant"],
            "name": "Nonexistent Feed",
        }

        response = requests.put(
            RSSMONK_URL + "/api/feeds/configurations",
            json=update_data,
            auth=self.ADMIN_AUTH,
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST, f"{response.status_code}: {response.text}"
        assert "No existing feed found" in response.text
