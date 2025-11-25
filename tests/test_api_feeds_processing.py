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
from .mock_feed_gen import external_app

from tests.conftest import RSSMONK_URL, UnitTestLifecyclePhase, ListmonkClientTestBase


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

    #-------------------------
    # POST /api/feeds/process/ - Process RSS Feed (admin only)
    #-------------------------
    def test_feeds_process_no_feed_no_credentials(self):
        # No credentials, process feed that does not exist
        assert False


    def test_feeds_process_no_feed_non_admin(self):
        # Non admin, process feed that does not exist
        assert False


    def test_feeds_process_no_feed_admin(self):
        # Admin, process feed that does not exist
        assert False


    def test_feeds_process_feed_no_credentials(self):
        # No credentials, process existing feed
        assert False


    def test_feeds_process_feed_non_admin(self):
        # Non admin, process existing feed
        assert False


    def test_feeds_process_feed_admin(self):
        # Admin, process existing feed
        assert False


    #-------------------------
    # POST /api/feeds/process/bulk/{frequency} - Process all RSS Feed by frequency (admin only)
    #-------------------------
    def test_feeds_bulk_process_no_feed_no_credentials(self):
        # No credentials, process feed that does not exist
        assert False


    def test_feeds_bulk_process_no_feed_non_admin(self):
        # Non admin, process feed that does not exist
        assert False


    def test_feeds_bulk_process_no_feed_admin(self):
        # Admin, process feed that does not exist
        assert False


    def test_feeds_bulk_process_feed_no_credentials(self):
        # No credentials, process existing feed
        assert False


    def test_feeds_bulk_process_feed_non_admin(self):
        # Non admin, process existing feed
        assert False


    def test_feeds_bulk_process_feed_admin(self):
        # Admin, process existing feed
        assert False
