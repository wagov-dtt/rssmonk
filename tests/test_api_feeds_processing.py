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
from .mock_feed_gen import external_mock_app

from tests.conftest import RSSMONK_URL, UnitTestLifecyclePhase, ListmonkClientTestBase


class TestRSSMonkFeeds(ListmonkClientTestBase):
    @classmethod
    def setUpClass(cls):
        """Start external FastAPI server on port 10000 before tests."""
        config = uvicorn.Config(external_mock_app, host="0.0.0.0", port=10000, log_level="info")
        cls.server = uvicorn.Server(config)
        cls.process = Process(target=cls.server.run)
        cls.process.start()
        time.sleep(2)  # Blocking wait to give server time to start


    @classmethod
    def tearDownClass(cls):
        """Stop external server after tests."""
        cls.process.terminate()
        cls.process.join()


    #-------------------------
    # POST /api/feeds/process/ - Process RSS Feed (admin only)
    #-------------------------
    def test_feeds_process_no_feed_no_credentials(self):
        # No credentials, process feed that does not exist
        process_data = {"feed_url": "http://unknown-rss.com/rss"}
        response = requests.post(RSSMONK_URL+"/api/feeds/process", auth=None, json=process_data)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"


    def test_feeds_process_no_feed_non_admin(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
        user, pwd = next(iter(init_data.accounts.items()))
        # Non admin, process feed that does not exist
        process_data = {"feed_url": self.FEED_ONE_FEED_URL}
        response = requests.post(RSSMONK_URL+"/api/feeds/process", auth=HTTPBasicAuth(user, pwd), json=process_data)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"


    def test_feeds_process_no_feed_admin(self):
        # Admin, process feed that does not exist (yet)
        process_data = {"feed_url": self.FEED_ONE_FEED_URL}
        response = requests.post(RSSMONK_URL+"/api/feeds/process", auth=self.ADMIN_AUTH, json=process_data)
        assert response.status_code == HTTPStatus.NOT_FOUND, f"{response.status_code}: {response.text}"


    def test_feeds_process_feed_no_credentials(self):
        self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
        # No credentials, process existing feed
        process_data = {"feed_url": self.FEED_ONE_FEED_URL}
        response = requests.post(RSSMONK_URL+"/api/feeds/process", auth=None, json=process_data)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"


    def test_feeds_process_feed_non_admin(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
        user, pwd = next(iter(init_data.accounts.items()))
        # Non admin, process existing feed
        process_data = {"feed_url": self.FEED_ONE_FEED_URL}
        response = requests.post(RSSMONK_URL+"/api/feeds/process", auth=HTTPBasicAuth(user, pwd), json=process_data)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"


    def test_feeds_process_feed_admin(self):
        self.initialise_system(UnitTestLifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)
        # Admin, process existing feed
        process_data = {"feed_url": self.FEED_ONE_FEED_URL}
        response = requests.post(RSSMONK_URL+"/api/feeds/process", auth=self.ADMIN_AUTH, json=process_data)
        assert response.status_code == HTTPStatus.OK, f"{response.status_code}: {response.text}"
        data = response.json()
        assert "feed_name" in data and data["feed_name"] == "Example Media Statements"


    #-------------------------
    # POST /api/feeds/process/bulk/{frequency} - Process all RSS Feed by frequency (admin only)
    #-------------------------
    def test_feeds_bulk_process_no_credentials(self):
        # No credentials, process bulk feeds
        response = requests.post(RSSMONK_URL+"/api/feeds/process/bulk/instant", auth=None)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"

        response = requests.post(RSSMONK_URL+"/api/feeds/process/bulk/daily", auth=None)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"


    def test_feeds_bulk_process_non_admin(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)
        user, pwd = next(iter(init_data.accounts.items()))
        # Non admin, process bulk feeds
        response = requests.post(RSSMONK_URL+"/api/feeds/process/bulk/instant", auth=HTTPBasicAuth(user, pwd))
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"

        response = requests.post(RSSMONK_URL+"/api/feeds/process/bulk/daily", auth=HTTPBasicAuth(user, pwd))
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"


    def test_feeds_bulk_process_no_feed_admin(self):
        # Admin, process feed that do not exist
        response = requests.post(RSSMONK_URL+"/api/feeds/process/bulk/instant", auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.OK, f"{response.status_code}: {response.text}"
        data = response.json()
        assert "frequency" in data and data["frequency"] == "instant"
        assert "feeds_processed" in data and data["feeds_processed"] == 0
        assert "total_emails_sent" in data and data["total_emails_sent"] == 0

        response = requests.post(RSSMONK_URL+"/api/feeds/process/bulk/daily", auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.OK, f"{response.status_code}: {response.text}"
        data = response.json()
        assert "frequency" in data and data["frequency"] == "daily"
        assert "feeds_processed" in data and data["feeds_processed"] == 0
        assert "total_emails_sent" in data and data["total_emails_sent"] == 0


    def test_feeds_bulk_process_feed_instant_admin(self):
        self.initialise_system(UnitTestLifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)

        # Admin, process existing feeds with instant tag
        response = requests.post(RSSMONK_URL+"/api/feeds/process/bulk/instant", auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.OK, f"{response.status_code}: {response.text}"
        data = response.json()
        assert "frequency" in data and data["frequency"] == "instant"
        assert "feeds_processed" in data and data["feeds_processed"] == 2
        assert "total_emails_sent" in data and data["total_emails_sent"] == 0
        # TODO - Check emails


    def test_feeds_bulk_process_feed_daily_admin(self):
        self.initialise_system(UnitTestLifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)

        # Admin, process existing feeds with instant tag
        response = requests.post(RSSMONK_URL+"/api/feeds/process/bulk/daily", auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.OK, f"{response.status_code}: {response.text}"
        data = response.json()
        assert "frequency" in data and data["frequency"] == "daily"
        assert "feeds_processed" in data and data["feeds_processed"] == 2
        assert "total_emails_sent" in data and data["total_emails_sent"] == 0
        # TODO - Check emails
