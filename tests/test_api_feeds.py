"""
Test Feed API endpoints
- /api/feeds
"""

import asyncio
from http import HTTPStatus
from multiprocessing import Process
import requests
from requests.auth import HTTPBasicAuth
import uvicorn
from .mock_feed_gen import external_app

from tests.listmonk_testbase import RSSMONK_URL, LifecyclePhase, ListmonkClientTestBase


class TestRSSMonkFeeds(ListmonkClientTestBase):
    @classmethod
    def setUpClass(cls):
        """Start external FastAPI server on port 10000 before tests."""
        config = uvicorn.Config(external_app, host="0.0.0.0", port=10000, log_level="info")
        cls.server = uvicorn.Server(config)
        cls.process = Process(target=cls.server.run)
        cls.process.start()
        asyncio.run(asyncio.sleep(1))  # Give server time to start

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

    def test_get_feeds_no_access(self):
        """
        GET /api/feeds - List RSS Feeds
        - No acesss
        """
        response = requests.get(RSSMONK_URL+"/api/feeds", auth=None)
        assert response.status_code == 401

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

        accounts = self.initialise_system(LifecyclePhase.FEED_TEMPLATES)
        user, pwd = next(iter(accounts.items()))
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
        accounts = self.initialise_system(LifecyclePhase.FEED_TEMPLATES)
        user, pwd = next(iter(accounts.items()))
        create_feed_data = {}
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=HTTPBasicAuth(user, pwd), json=create_feed_data)
        assert (response.status_code == HTTPStatus.UNAUTHORIZED), f"{response.status_code}: {response.text}"


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
        assert response_json["feed_url"] == "https://localhost:10000/feed-1"
        assert response_json["email_base_url"] == "https://example.com/media"
        assert response_json["poll_frequencies"] == ["instant"]
        assert response_json["name"] == "Media Statements"
        assert "url_hash" in response_json and "091886d9077436f1ef717ac00a5e2034469bfc011699d0f46f88da90269fb180" == response_json["url_hash"]

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
        assert response_json["feed_url"] == "https://example.com/rss/example"
        assert response_json["name"] == "https://example.com/rss/example"
        assert "url_hash" in response_json and "091886d9077436f1ef717ac00a5e2034469bfc011699d0f46f88da90269fb180" == response_json["url_hash"]


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


    def test_get_feed_by_url_no_feed_no_credentials(self):
        # No credentials, no feed
        get_feed_data = {"feed_url": "https://unknownn.com/rss"}
        response = requests.get(RSSMONK_URL+"/api/feeds/by-url", auth=None, params=get_feed_data)
        assert (response.status_code == HTTPStatus.UNAUTHORIZED), f"{response.status_code}: {response.text}"


    def test_get_feed_by_url_no_feed_non_admin(self):
        accounts = self.initialise_system(LifecyclePhase.FEED_TEMPLATES)
        user, pwd = next(iter(accounts.items()))

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
        self.initialise_system(LifecyclePhase.FEED_TEMPLATES)

        # No credentials, existing feed
        get_feed_data = {"feed_url": "https://example.com/rss/example"}
        response = requests.get(RSSMONK_URL+"/api/feeds/by-url", auth=None, params=get_feed_data)
        assert (response.status_code == HTTPStatus.UNAUTHORIZED), f"{response.status_code}: {response.text}"


    def test_get_feed_by_url_feed_non_admin(self):
        accounts = self.initialise_system(LifecyclePhase.FEED_TEMPLATES)
        user, pwd = next(iter(accounts.items()))

        # Non admin credentials, existing feed
        get_feed_data = {"feed_url": "https://somewhere.com/rss"}
        response = requests.get(RSSMONK_URL+"/api/feeds/by-url", auth=HTTPBasicAuth(user, pwd), params=get_feed_data)
        assert (response.status_code == HTTPStatus.OK), f"{response.status_code}: {response.text}"


    def test_get_feed_by_url_feed_admin(self):
        self.initialise_system(LifecyclePhase.FEED_TEMPLATES)

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


    def test_delete_feed_by_url(self):
        """
        DELETE /api/feeds/by-url - Delete Feed by URL (admin only)
        - No account access
        - No admin 
        - Delete non existing feed
        - Delete existing feed. Ensure feed, user account, list role, templates are removed
        """
        # - Delete non existing feed
        delete_feed_data = {"feed_url": "https://example.com/rss/example"}
        response = requests.delete(RSSMONK_URL+"/api/feeds/by-url", auth=self.ADMIN_AUTH, json=delete_feed_data)
        assert (response.status_code == HTTPStatus.NOT_FOUND), f"{response.status_code}: {response.text}"

        self._insert_example_rss()
        delete_feed_data = {"feed_url": "https://example.com/rss/example"}
        response = requests.delete(RSSMONK_URL+"/api/feeds/by-url", auth=self.ADMIN_AUTH, json=delete_feed_data)
        assert (response.status_code == HTTPStatus.OK), f"{response.status_code}: {response.text}"
        response_json = response.json()
        assert isinstance(response_json, dict)


    def test_get_subscribe_preferences(self):
        """
        GET /api/feeds/subscribe-preferences
        - Get Feed preferences
        """
        assert False


    # TODO - Still unsure what to do with these endpoints
    def test_get_configurations(self):
        """
        GET /api/feeds/configurations
        - Get URL Configurations
        """
        assert False

    def test_update_configurations(self):
        """
        PUT /api/feeds/configurations
        - Update Feed Configuration
        """
        assert False


