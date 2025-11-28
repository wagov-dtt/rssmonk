"""
Test Feed API endpoints
- /api/feeds
"""

import time
from http import HTTPStatus
from multiprocessing import Process
import requests
from requests.auth import HTTPBasicAuth
import uvicorn

from rssmonk.types import FEED_ACCOUNT_PREFIX
from .mock_feed_gen import external_app

from tests.conftest import LISTMONK_URL, RSSMONK_URL, UnitTestLifecyclePhase, ListmonkClientTestBase, make_admin_session


class TestRSSMonkFeeds(ListmonkClientTestBase):
    @classmethod
    def setUpClass(cls):
        """Start external FastAPI server on port 10000 before tests."""
        config = uvicorn.Config(external_app, host="0.0.0.0", port=10000, log_level="info")
        cls.server = uvicorn.Server(config)
        cls.process = Process(target=cls.server.run)
        cls.process.start()
        time.sleep(2)  # Blocking wait to give server time to start

    @classmethod
    def tearDownClass(cls):
        """Stop external server after tests."""
        cls.process.terminate()
        cls.process.join()

        
    def _insert_example_rss(self):
        create_feed_data = {
            "feed_url": "https://example.com/rss/example",
            "email_base_url": "https://example.com/media",
            "poll_frequencies": ["instant", "daily"],
            "name": "Example Media Statements"
        }
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert (response.status_code == HTTPStatus.CREATED), "Set up failed: "+response.text
        create_feed_data = {
            "feed_url": "https://abc.net.example/rss/example",
            "email_base_url": "https://abc.net.example/subscribe",
            "poll_frequencies": ["instant", "daily"],
            "name": "Example ABC Net"
        }
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert (response.status_code == HTTPStatus.CREATED),  "Set up failed: "+response.text
        create_feed_data = {
            "feed_url": "https://bbc.co.uk.example/rss/example",
            "email_base_url": "https://bbc.co.uk.example/subscribe",
            "poll_frequencies": ["instant", "daily"],
            "name": "Example BBC Co."
        }
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert (response.status_code == HTTPStatus.CREATED),  "Set up failed: "+response.text


    def _make_feed_account(self, feed_url: str):
        """
        These are called when required and should be called after insert_example_rss()
        """

        return ""


    # -------------------------
    # GET /api/feeds
    # -------------------------
    def test_get_feeds_no_credentials(self):
        response = requests.get(RSSMONK_URL+"/api/feeds", auth=None)
        assert response.status_code == HTTPStatus.UNAUTHORIZED


    def test_get_feeds_unauthorized_user(self):
        response = requests.get(RSSMONK_URL+"/api/feeds", auth=HTTPBasicAuth("no-one", "pawword"))
        assert response.status_code == HTTPStatus.UNAUTHORIZED


    def test_get_feeds_non_admin_credentials(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_SUBSCRIBED)
        user, pwd = next(iter(init_data.accounts.items()))

        response = requests.get(RSSMONK_URL+"/api/feeds", auth=HTTPBasicAuth(user, pwd))
        assert response.status_code == HTTPStatus.OK


    def test_get_feeds_admin_credentials(self):
        response = requests.get(RSSMONK_URL+"/api/feeds", auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.OK


    def test_list_feeds_unauthorized_user(self):
        response = requests.get(RSSMONK_URL+"/api/feeds", auth=HTTPBasicAuth("no-one", "pawword"))
        assert response.status_code == HTTPStatus.UNAUTHORIZED


    def test_list_feeds_admin_success(self):
        self._insert_example_rss() # Add example rss

        response = requests.get(RSSMONK_URL+"/api/feeds", auth=self.ADMIN_AUTH)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["feeds"]) == 3 

        assert data["feeds"][0]["feed_url"] == "https://bbc.co.uk.example/rss/example"
        assert data["feeds"][1]["feed_url"] == "https://abc.net.example/rss/example"
        assert data["feeds"][2]["feed_url"] == "https://example.com/rss/example"


    def test_list_feeds_feed_account_success(self):
        self._insert_example_rss() # Add example rss

        feed_auth = HTTPBasicAuth("admin", "admin123")
        response = requests.get(RSSMONK_URL+"/api/feeds", auth=feed_auth)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3


    def test_list_feeds_empty_list(self):
        response = requests.get(RSSMONK_URL+"/api/feeds", auth=self.ADMIN_AUTH)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["feeds"] == []

    #-------------------------
    # POST /api/feeds - Create RSS Feed (admin only)
    # - Combinations of url, name (optional), frequency and list_visibility with no pre-existing feed
    # - Already exists with incoming frequencies being a subset of existing
    # - Already exists with incoming frequencies being a subset of existing
    # - Already exists with incoming frequencies having no overlap with existing
    # - Already exists with incoming frequencies having partial overlap with existing
    # - Invalid url, frequency and list_visibility
    # - Correct details, no credentials
    # - Correct details, non admin credentials
    #-------------------------
    def test_create_feed_incorrect_auth(self):
        # - No credentials, correct details
        create_feed_data = {
            "feed_url": "https://very-different-example.com/rss/example",
            "email_base_url": "https://very-different-example.com/media",
            "poll_frequencies": ["instant"]
        }
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=None, json=create_feed_data)
        assert (response.status_code == HTTPStatus.UNAUTHORIZED), f"{response.status_code}: {response.text}"

        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
        user, pwd = next(iter(init_data.accounts.items()))
        # - Non admin credentials, correct details
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=HTTPBasicAuth(user, pwd), json=create_feed_data)
        assert (response.status_code == HTTPStatus.UNAUTHORIZED), f"{response.status_code}: {response.text}"

    
    def test_create_feed_no_credentials(self):
        # - No account
        create_feed_data = {}
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=None, json=create_feed_data)
        assert (response.status_code == HTTPStatus.UNAUTHORIZED), f"{response.status_code}: {response.text}"


    def test_create_feed_invalid_credentials(self):
        # - Invalid credentials
        create_feed_data = {}
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=HTTPBasicAuth("false", "account"), json=create_feed_data)
        assert (response.status_code == HTTPStatus.UNAUTHORIZED), f"{response.status_code}: {response.text}"


    def test_create_feed_non_admin_failures(self):
        # - Invalid credentials (active account, not admin)
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
        user, pwd = next(iter(init_data.accounts.items()))
        create_feed_data = {}
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=HTTPBasicAuth(user, pwd), json=create_feed_data)
        assert (response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT), f"{response.status_code}: {response.text}"


    def test_create_feed_admin_not_full_object(self):
        # - Empty object
        create_feed_data = {}
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert (response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT), f"{response.status_code}: {response.text}"

        # - feed_url only
        create_feed_data = {"feed_url": "https://example.com/rss/example"}
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert (response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT), f"{response.status_code}: {response.text}"

        # - email_base_url only
        create_feed_data = {"email_base_url": "https://example.com/media"}
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert (response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT), f"{response.status_code}: {response.text}"

        # - poll_frequencies
        create_feed_data = {"poll_frequencies": ["instant"]}
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert (response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT), f"{response.status_code}: {response.text}"

        # - list_visibility
        create_feed_data = {"list_visibility": "public"}
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert (response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT), f"{response.status_code}: {response.text}"


    def test_create_feed_admin_not_valid_data(self):
        # - invalid url
        create_feed_data = {
            "feed_url": "not_a_real_url",
            "email_base_url": "https://example.com/media",
            "poll_frequencies": ["instant"]
        }
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert (response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT), f"{response.status_code}: {response.text}"

        # - invalid poll frequency
        create_feed_data = {
            "feed_url": "https://example.com/rss/example",
            "email_base_url": "https://example.com/media",
            "poll_frequencies": ["5min"]
        }
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert (response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT), f"{response.status_code}: {response.text}"

        # - list_visibility
        create_feed_data = {
            "feed_url": "https://example.com/rss/example",
            "email_base_url": "https://example.com/media",
            "poll_frequencies": ["protected"]
        }
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert (response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT), f"{response.status_code}: {response.text}"


    def test_create_feeds(self):
        """
        POST /api/feeds - Create RSS Feed (admin only)
        - Successful actions which create a feed list
        """
        # - feed_url, email_base_url, poll_frequencies (accessible to fetch name)
        create_feed_data = {
            "feed_url": "https://localhost:10000/feed-1",
            "email_base_url": "https://example.com/media",
            "poll_frequencies": ["instant"]
        }
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert (response.status_code == HTTPStatus.CREATED), f"{response.status_code}: {response.text}"
        response_json = response.json()
        assert isinstance(response_json, dict)
        assert response_json["feed_url"] == "https://localhost:10000/feed-1", response_json
        assert response_json["email_base_url"] == "https://example.com/media", response_json
        assert response_json["poll_frequencies"] == ["instant"], response_json
        assert response_json["name"] == "https://localhost:10000/feed-1", response_json
        assert response_json["url_hash"] == "019b873a9357ba2e1a51963aec30bcb911e9f92aff7c21835f0eb187707f35da", response_json


    def test_create_feeds_no_title_in_feed(self):
        # - Feed creation, feed_url, email_base_url, poll_frequencies (not accessible to fetch name)
        create_feed_data = {
            "feed_url": "https://example.com/rss/example",
            "email_base_url": "https://example.com/media",
            "poll_frequencies": ["instant"]
        }
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert (response.status_code == HTTPStatus.CREATED), f"{response.status_code}: {response.text}"
        response_json = response.json()
        assert isinstance(response_json, dict)
        assert response_json["feed_url"] == "https://example.com/rss/example", response_json
        assert response_json["name"] == "https://example.com/rss/example", response_json
        assert "url_hash" in response_json, response_json
        assert response_json["url_hash"] == "091886d9077436f1ef717ac00a5e2034469bfc011699d0f46f88da90269fb180", response_json


    def test_create_feeds_name_supplied(self):
        # - Feed creation, feed_url, email_base_url, poll_frequencies, name
        create_feed_data = {
            "feed_url": "https://example.com/rss/example",
            "email_base_url": "https://example.com/media",
            "poll_frequencies": ["instant"],
            "name": "Random name"
        }
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert (response.status_code == HTTPStatus.CREATED), f"{response.status_code}: {response.text}"
        response_json = response.json()
        assert isinstance(response_json, dict)
        assert response_json["feed_url"] == "https://example.com/rss/example"
        assert response_json["name"] == "Random name"
        assert "url_hash" in response_json and "091886d9077436f1ef717ac00a5e2034469bfc011699d0f46f88da90269fb180" == response_json["url_hash"]


    # -------------------------
    # GET /api/feeds/by-url
    # -------------------------

    def test_get_feed_by_url_no_feed_no_credentials(self):
        # No credentials, no feed
        get_feed_data = {"feed_url": "https://unknownn.com/rss"}
        response = requests.get(RSSMONK_URL+"/api/feeds/by-url", auth=None, params=get_feed_data)
        assert (response.status_code == HTTPStatus.UNAUTHORIZED), f"{response.status_code}: {response.text}"


    def test_get_feed_by_url_no_feed_non_admin(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
        user, pwd = next(iter(init_data.accounts.items()))

        # Non admin credentials, no feed
        get_feed_data = {"feed_url": "https://unknownn.com/rss"}
        response = requests.get(RSSMONK_URL+"/api/feeds/by-url", auth=HTTPBasicAuth(user, pwd), params=get_feed_data)
        assert (response.status_code == HTTPStatus.NOT_FOUND), f"{response.status_code}: {response.text}"



    def test_get_feed_by_url_no_feed_admin(self):
        # Admin credentials, no feed
        get_feed_data = {"feed_url": "https://unknownn.com/rss"}
        response = requests.get(RSSMONK_URL+"/api/feeds/by-url", auth=self.ADMIN_AUTH, params=get_feed_data)
        assert (response.status_code == HTTPStatus.NOT_FOUND), f"{response.status_code}: {response.text}"


    def test_get_feed_by_url_feed_no_credentials(self):
        self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)

        # No credentials, existing feed
        get_feed_data = {"feed_url": "https://example.com/rss/example"}
        response = requests.get(RSSMONK_URL+"/api/feeds/by-url", auth=None, params=get_feed_data)
        assert (response.status_code == HTTPStatus.UNAUTHORIZED), f"{response.status_code}: {response.text}"


    def test_get_feed_by_url_non_feed_non_admin(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
        user, pwd = next(iter(init_data.accounts.items()))

        # Non admin credentials, non existing feed
        get_feed_data = {"feed_url": "https://feed-does-not-exist.com/rss"}
        response = requests.get(RSSMONK_URL+"/api/feeds/by-url", auth=HTTPBasicAuth(user, pwd), params=get_feed_data)
        assert (response.status_code == HTTPStatus.NOT_FOUND), f"{response.status_code}: {response.text}"


    def test_get_feed_by_url_feed_non_admin(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
        user, pwd = next(iter(init_data.accounts.items()))

        # Non admin credentials, unaccessible but existing feed
        get_feed_data = {"feed_url": self.FEED_TWO_FEED_URL}
        response = requests.get(RSSMONK_URL+"/api/feeds/by-url", auth=HTTPBasicAuth(user, pwd), params=get_feed_data)
        assert (response.status_code == HTTPStatus.NOT_FOUND), f"{response.status_code}: {response.text}"

        # Non admin credentials, accessible existing feed
        get_feed_data = {"feed_url": self.FEED_ONE_FEED_URL}
        response = requests.get(RSSMONK_URL+"/api/feeds/by-url", auth=HTTPBasicAuth(user, pwd), params=get_feed_data)
        assert (response.status_code == HTTPStatus.OK), f"{response.status_code}: {response.text}"
        data = response.json()
        assert "email_base_url" in data and data["email_base_url"] == "https://example.com/media-statements"
        assert "name" in data and data["name"] ==  "Example Media Statements"


    def test_get_feed_by_url_feed_admin(self):
        self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)

        # Admin credentials, no existing feed
        get_feed_data = {"feed_url": "https://example.com/rss/example"}
        response = requests.get(RSSMONK_URL+"/api/feeds/by-url", auth=self.ADMIN_AUTH, params=get_feed_data)
        assert (response.status_code == HTTPStatus.NOT_FOUND), f"{response.status_code}: {response.text}"

        self._insert_example_rss()
        # Admin credentials, existing feed
        response = requests.get(RSSMONK_URL+"/api/feeds/by-url", auth=self.ADMIN_AUTH, params=get_feed_data)
        assert (response.status_code == HTTPStatus.OK), f"{response.status_code}: {response.text}"
        response_json = response.json()
        assert isinstance(response_json, dict)


    # -------------------------
    # DELETE /api/feeds/by-url
    # -------------------------

    def test_delete_feed_by_url_no_credentials(self):
        response = requests.delete(RSSMONK_URL+"/api/feeds/by-url", auth=None)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"


    def test_delete_feed_by_url_non_admin_credentials(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
        user, pwd = next(iter(init_data.accounts.items()))

        response = requests.delete(RSSMONK_URL+"/api/feeds/by-url", auth=HTTPBasicAuth(user, pwd))
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"


    def test_delete_feed_by_url_admin_no_feed(self):
        # - Delete non existing feed
        delete_feed_data = {"feed_url": "https://example.com/rss/example"}
        response = requests.delete(RSSMONK_URL+"/api/feeds/by-url", auth=self.ADMIN_AUTH, json=delete_feed_data)
        assert (response.status_code == HTTPStatus.NOT_FOUND), f"{response.status_code}: {response.text}"


    def test_delete_feed_by_url_admin_success(self):
        self.initialise_system(UnitTestLifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)
        # Delete existing feed
        delete_feed_data = {"feed_url": self.FEED_ONE_FEED_URL}
        response = requests.delete(RSSMONK_URL+"/api/feeds/by-url", auth=self.ADMIN_AUTH, json=delete_feed_data)
        assert (response.status_code == HTTPStatus.OK), f"{response.status_code}: {response.text}"
        response_json = response.json()
        assert isinstance(response_json, dict)

        # - Check the requested list is removed
        admin_session = make_admin_session()
        response = admin_session.get(f"{LISTMONK_URL}/api/lists?minimal=true&per_page=all")
        lists_data = response.json()["data"]["results"] if "results" in response.json()["data"] else []
        assert len(lists_data) == 1, lists_data
        assert self.FEED_ONE_FEED_URL not in lists_data

        # - Check the subscriber is no longer subscribed to the list (or has been deleted)
        response = admin_session.get(f"{LISTMONK_URL}/api/subscribers?list_id=&search=&query=&page=1&subscription_status=&order_by=id&order=desc")
        subs_data = response.json().get("data", {}).get("results", [])
        # Deletion of feed will remove users who only had the one feed as a subscription
        assert len(subs_data) == 1, subs_data
        assert self.FEED_ONE_FEED_URL not in subs_data

        # - Check the user role for the list is removed
        response = admin_session.get(f"{LISTMONK_URL}/api/roles/lists")
        role_lists_data = response.json()["data"]
        assert len(lists_data) == 1, role_lists_data
        for list_data in role_lists_data:
            assert self.FEED_HASH_ONE not in list_data["name"]

        # - Check the users if left with only admin (only role left)
        response = admin_session.get(f"{LISTMONK_URL}/api/users")
        users_data = response.json()["data"]
        assert len(users_data) == 2, users_data
        for list_data in users_data:
            assert self.FEED_HASH_ONE not in list_data["name"]

        # - Check the list templates is removed
        response = admin_session.get(f"{LISTMONK_URL}/api/templates")
        template_list_data = response.json()["data"]
        for list_data in template_list_data:
            assert self.FEED_HASH_ONE not in list_data["name"]


    # -------------------------
    # GET /api/feeds/subscribe-preferences
    # -------------------------
    def test_get_subscribe_preferences_no_credentials(self):
        response = requests.get(RSSMONK_URL+"/api/feeds/subscribe-preferences", auth=None)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"


    def test_get_subscribe_preferences_non_admin_credentials(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)
        user = FEED_ACCOUNT_PREFIX + self.FEED_HASH_ONE
        pwd = init_data.accounts[user]

        response = requests.get(RSSMONK_URL+"/api/feeds/subscribe-preferences", auth=HTTPBasicAuth(user, pwd))
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Field required" in response.text


    def test_get_subscribe_preferences_admin_credentials(self):
        response = requests.get(RSSMONK_URL+"/api/feeds/subscribe-preferences", auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Field required" in response.text


    # TODO - Still unsure what to do with these endpoints
    # -------------------------
    # GET /api/feeds/configurations
    # -------------------------

    def test_get_feed_configurations_no_credentials(self):
        response = requests.get(RSSMONK_URL+"/api/feeds/configurations", auth=None)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"


    def test_get_feed_configurations_non_admin_credentials(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
        user, pwd = next(iter(init_data.accounts.items()))

        response = requests.get(RSSMONK_URL+"/api/feeds/configurations", auth=HTTPBasicAuth(user, pwd))
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Field required" in response.text

        # TODO - Get feed configuration with actual data


    def test_get_feed_configurations_admin_credentials(self):
        response = requests.get(RSSMONK_URL+"/api/feeds/configurations", auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Field required" in response.text
        
        # TODO - Get feed configuration with actual data


    # -------------------------
    # PUT /api/feeds/configurations
    # -------------------------
    def test_put_feed_configurations_no_credentials(self):
        response = requests.put(RSSMONK_URL+"/api/feeds/configurations", auth=None)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"


    def test_put_feed_configurations_non_admin_credentials(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
        user, pwd = next(iter(init_data.accounts.items()))

        response = requests.put(RSSMONK_URL+"/api/feeds/configurations", auth=HTTPBasicAuth(user, pwd))
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Field required" in response.text

    # TODO - Put feed configuration with actual data


    def test_put_feed_configurations_admin_credentials(self):
        response = requests.put(RSSMONK_URL+"/api/feeds/configurations", auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Field required" in response.text

    # TODO - Put feed configuration with actual data
