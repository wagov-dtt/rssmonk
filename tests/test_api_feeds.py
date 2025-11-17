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

from tests.listmonk_testbase import RSSMONK_URL, ListmonkClientTestBase


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
    def test_create_feed_failures_no_admin(self):
        # - No account
        create_feed_data = {}
        response = requests.post(RSSMONK_URL+"/api/feeds", json=create_feed_data)
        assert (response.status_code == HTTPStatus.UNAUTHORIZED), response.text

        # - Invalid credentials
        create_feed_data = {}
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=HTTPBasicAuth("false", "account"), json=create_feed_data)
        assert (response.status_code == HTTPStatus.UNAUTHORIZED), response.text

        # - Invalid credentials (active account, not admin)
        self.make_feed_list()
        acct_data = self.make_feed_account()
        create_feed_data = {}
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=HTTPBasicAuth(acct_data["name"], acct_data["api_password"]), json=create_feed_data)
        assert (response.status_code == HTTPStatus.UNAUTHORIZED), response.text


    def test_create_feed_failures_admin(self):
        # - No data
        create_feed_data = {}
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert (response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT), response.text

        # - feed_url only
        create_feed_data = {"feed_url": "https://example.com/rss/example"}
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert (response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT), response.text

        # - email_base_url only
        create_feed_data = {"email_base_url": "https://example.com/media"}
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert (response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT), response.text

        # - poll_frequencies
        create_feed_data = {"poll_frequencies": ["instant"]}
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert (response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT), response.text

        # - list_visibility
        create_feed_data = {"list_visibility": "public"}
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert (response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT), response.text

        # - invalid url
        create_feed_data = {
            "feed_url": "not_a_real_url",
            "email_base_url": "https://example.com/media",
            "poll_frequencies": ["instant"]
        }
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert (response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT), response.text

        # - invalid poll frequency
        create_feed_data = {
            "feed_url": "https://example.com/rss/example",
            "email_base_url": "https://example.com/media",
            "poll_frequencies": ["5min"]
        }
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert (response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT), response.text

        # - list_visibility
        create_feed_data = {
            "feed_url": "https://example.com/rss/example",
            "email_base_url": "https://example.com/media",
            "poll_frequencies": ["protected"]
        }
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert (response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT), response.text

        # - Correct details, no credentials
        create_feed_data = {
            "feed_url": "https://example.com/rss/example",
            "email_base_url": "https://example.com/media",
            "poll_frequencies": ["instant"]
        }
        response = requests.post(RSSMONK_URL+"/api/feeds", json=create_feed_data)
        assert (response.status_code == HTTPStatus.UNAUTHORIZED), response.text

        # - Correct details, non admin credentials
        # TODO - Set up non admin account for another account
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert (response.status_code == HTTPStatus.UNAUTHORIZED), response.text

    def test_create_feeds(self):
        """
        POST /api/feeds - Create RSS Feed (admin only)
        - Successful actions which create a feed list
        """
        # - feed_url, email_base_url, poll_frequencies (accessible to fetch name)
        create_feed_data = {
            "feed_url": "https://example.com/rss/example",
            "email_base_url": "https://example.com/media",
            "poll_frequencies": ["instant"]
        }
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert (response.status_code == HTTPStatus.CREATED), response.text
        response_json = response.json()
        assert isinstance(response_json, dict)
        assert response_json["feed_url"] == "https://example.com/rss/example"
        assert response_json["email_base_url"] == "https://example.com/media"
        assert response_json["poll_frequencies"] == ["instant"]
        assert response_json["name"] == ""
        assert "url_hash" in response_json and "091886d9077436f1ef717ac00a5e2034469bfc011699d0f46f88da90269fb180" == response_json["url_hash"]

        # - Feed creation, feed_url, email_base_url, poll_frequencies (not accessible to fetch name)
        create_feed_data = {
            "feed_url": "https://example.com/rss/example",
            "email_base_url": "https://example.com/media",
            "poll_frequencies": ["instant"]
        }
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert (response.status_code == HTTPStatus.CREATED), response.text
        response_json = response.json()
        assert isinstance(response_json, dict)
        assert response_json["feed_url"] == "https://example.com/rss/example"
        assert response_json["name"] == ""
        assert "url_hash" in response_json and "091886d9077436f1ef717ac00a5e2034469bfc011699d0f46f88da90269fb180" == response_json["url_hash"]

        # - Feed creation, feed_url, email_base_url, poll_frequencies, name
        create_feed_data = {
            "feed_url": "https://example.com/rss/example",
            "email_base_url": "https://example.com/media",
            "poll_frequencies": ["instant"]
        }
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=self.ADMIN_AUTH, json=create_feed_data)
        assert (response.status_code == HTTPStatus.CREATED), response.text
        response_json = response.json()
        assert isinstance(response_json, dict)
        assert response_json["feed_url"] == "https://example.com/rss/example"
        assert response_json["name"] == ""
        assert "url_hash" in response_json and "091886d9077436f1ef717ac00a5e2034469bfc011699d0f46f88da90269fb180" == response_json["url_hash"]

    def test_get_feed_by_url(self):
        """
        GET /api/feeds/by-url
        - No account access
        - Get non existing feed
        - Get existing feed
        """
        # - No account access
        get_feed_data = {"feed_url": "https://example.com/rss/example"}
        response = requests.get(RSSMONK_URL+"/api/feeds/by-url", json=get_feed_data)
        assert (response.status_code == HTTPStatus.OK), response.text

    def test_get_feed_by_url_admin(self):
        """
        GET /api/feeds/by-url
        - Get non existing feed
        - Get existing feed
        """
        # - Get non existing feed
        get_feed_data = {"feed_url": "https://example.com/rss/example"}
        response = requests.get(RSSMONK_URL+"/api/feeds/by-url", auth=self.ADMIN_AUTH, json=get_feed_data)
        assert (response.status_code == HTTPStatus.OK), response.text

        # - Get existing feed
        self._insert_example_rss()
        get_feed_data = {"feed_url": "https://example.com/rss/example"}
        response = requests.get(RSSMONK_URL+"/api/feeds/by-url", auth=self.ADMIN_AUTH, json=get_feed_data)
        assert (response.status_code == HTTPStatus.OK), response.text
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
        assert (response.status_code == HTTPStatus.NOT_FOUND), response.text

        self._insert_example_rss()
        delete_feed_data = {"feed_url": "https://example.com/rss/example"}
        response = requests.delete(RSSMONK_URL+"/api/feeds/by-url", auth=self.ADMIN_AUTH, json=delete_feed_data)
        assert (response.status_code == HTTPStatus.OK), response.text
        response_json = response.json()
        assert isinstance(response_json, dict)

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

    def test_get_subscribe_preferences(self):
        """
        GET /api/feeds/subscribe-preferences
        - Get Feed preferences
        """
        assert False
