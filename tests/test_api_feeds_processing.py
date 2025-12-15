"""
Test Feed API endpoints
- /api/feeds
"""

import time
from http import HTTPStatus
from multiprocessing import Process
from fastapi.security import HTTPBasicCredentials
import requests
from requests.auth import HTTPBasicAuth
import uvicorn
import unittest
from unittest.mock import patch, MagicMock

from rssmonk.core import RSSMonk
from rssmonk.models import Feed
from rssmonk.types import FeedItem, Frequency
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


class TestPerformInstantEmailCheck(unittest.TestCase):
    @patch("rssmonk.http_clients.ListmonkClient.send_transactional")
    def test_email_check_sends_correct_data(self, mock_send):
        mock_send.return_value = None  # No actual sending
        rssmonk = RSSMonk(local_creds=HTTPBasicCredentials(username="admin", password="admin123"))

        feed = Feed(email_base_url="https://example.com", url_hash="hash123")
        frequency = Frequency.INSTANT
        template_id = 101

        new_articles = [
            FeedItem(title="Article 1", link="https://example.com/1", description="Desc 1",
                     email_subject_line="Subject 1", filter_identifiers="m 0,p 143"),
            FeedItem(title="Article 2", link="https://example.com/2", description="Desc 2",
                     email_subject_line="Subject 2", filter_identifiers="m 1,p 565")
        ]

        subscribers = [
            {
                "email": "user@example.com",
                "attribs": {
                    "hash123": {
                        "filter": {
                            "instant": "all"
                        }
                    }
                }
            }
        ]

        # Act
        articles_sent, notifications_sent = rssmonk.perform_instant_email_check(feed, frequency, template_id, new_articles, subscribers)

        # Assert return values
        self.assertEqual(articles_sent, 2)
        self.assertEqual(notifications_sent, 2)

        # Assert send_transactional was called twice
        self.assertEqual(mock_send.call_count, 2)

        # Inspect arguments passed to send_transactional
        first_call_args = mock_send.call_args_list[0][0]  # Positional args of first call
        self.assertEqual(first_call_args[0], "no-reply@example.com")  # NO_REPLY_EMAIL
        self.assertEqual(first_call_args[1], template_id)
        self.assertEqual(first_call_args[2], "html")
        self.assertEqual(first_call_args[3], ["user@example.com"])  # Recipients list
        self.assertIn("item", first_call_args[4])  # Data dict contains 'item'

        # Check subject line
        self.assertEqual(first_call_args[5], "Subject 1")


class TestPerformDailyEmailCheck(unittest.TestCase):
    @patch("rssmonk.http_clients.ListmonkClient.send_transactional")
    def test_daily_email_check_sends_correct_data(self, mock_send):
        mock_send.return_value = None  # No actual sending
        rssmonk = RSSMonk(local_creds=HTTPBasicCredentials(username="admin", password="admin123"))

        feed = Feed(email_base_url="https://example.com", url_hash="hash123")
        frequency = Frequency.DAILY
        template_id = 101

        new_articles: List[FeedItem] = [
            FeedItem(title="Article 1", link="https://example.com/1", description="Desc 1",
                     email_subject_line="Subject 1", filter_identifiers="m 0,p 143"),
            FeedItem(title="Article 2", link="https://example.com/2", description="Desc 2",
                     email_subject_line="Subject 2", filter_identifiers="m 1,p 565")
        ]

        subscribers = [
            {
                "email": "user@example.com",
                "attribs": {
                    "hash123": {
                        "filter": {
                            "daily": "all"
                        }
                    }
                }
            },
            {
                "email": "filtered@example.com",
                "attribs": {
                    "hash123": {
                        "filter": {
                            "daily": {
                                "topic1": ["m 0"]
                            }
                        }
                    }
                }
            }
        ]

        # Act
        articles_sent, notifications_sent = rssmonk.perform_daily_email_check(feed, frequency, template_id, new_articles, subscribers)

        # Assert return values
        self.assertEqual(articles_sent, 2)
        self.assertEqual(notifications_sent, 3)  # 1 for filtered user + 2 for "all" user

        # Assert send_transactional was called correct number of times
        self.assertEqual(mock_send.call_count, 2)  # One for filtered user, one for all users

        # Inspect first call (filtered user)
        first_call_args = mock_send.call_args_list[0][0]
        self.assertEqual(first_call_args[0], "no-reply@example.com")  # NO_REPLY_EMAIL
        self.assertEqual(first_call_args[1], template_id)
        self.assertEqual(first_call_args[2], "html")
        self.assertEqual(first_call_args[3], ["filtered@example.com"])  # Single recipient
        self.assertIn("items", first_call_args[4])  # Data dict contains 'items'

        # Inspect second call (all users)
        second_call_args = mock_send.call_args_list[1][0]
        self.assertEqual(second_call_args[3], ["user@example.com"])  # All-inclusive list
        self.assertEqual(second_call_args[5], "Daily Digest")  # Subject line
