"""
Test Feed API endpoints
- /api/feeds
"""

from datetime import datetime, timedelta
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
        super().setUpClass()
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

        feed = Feed(email_base_url = "https://example.com", url_hash = "hash123", name = "Example",
                    feed_url = "https://example.com/rss", poll_frequencies = [Frequency.INSTANT])
        frequency = Frequency.INSTANT
        template_id = 101

        new_articles = [
            FeedItem(title = "Article 1", link = "https://example.com/1", description = "Desc 1",
                     email_subject_line = "Subject 1", filter_identifiers = "min 0,port 143",
                     published = datetime.now(), guid = "guid 1"),
            FeedItem(title = "Article 2", link = "https://example.com/2", description = "Desc 2",
                     email_subject_line = "Subject 2", filter_identifiers = "min 1,port 565",
                     published = datetime.now() - timedelta(minutes=2), guid = "guid 2"),
            FeedItem(title = "Article 3", link = "https://example.com/3", description = "Desc 3",
                     email_subject_line = "Subject 3", filter_identifiers = "port 778",
                     published = datetime.now() - timedelta(minutes=4), guid = "guid 3")
        ]

        subscribers = [
            {
                "email": "all@example.com",
                "attribs": { "hash123": { "filter": { "instant": "all" } } }
            },
            {
                "email": "one@example.com",
                "attribs": { "hash123": { "filter": { "instant": { "min" : [0] } } } }
            },
            {
                "email": "two@example.com",
                "attribs": { "hash123": { "filter": { "instant": { "min" : [1] } } } }
            },
            {
                "email": "three@example.com",
                "attribs": { "hash123": { "filter": { "instant": { "port" : "all" } } } }
            }
        ]

        # Method under test
        notifications_sent = rssmonk.perform_instant_email_check(feed, frequency, template_id, new_articles, subscribers)

        # Check notifications sent and call count
        self.assertEqual(notifications_sent, 8) 
        self.assertEqual(mock_send.call_count, 3) # Daily sending is one per each new article

        # Inspect arguments passed to send_transactional for first article
        first_call_args = mock_send.call_args_list[0][0]  # Positional args of first call
        self.assertEqual(first_call_args[0], "noreply@noreply (No reply location)")
        self.assertEqual(first_call_args[1], template_id)
        self.assertEqual(first_call_args[2], "html")
        self.assertEqual(first_call_args[3], ["all@example.com", "one@example.com", "three@example.com"])
        self.assertIn("item", first_call_args[4])
        self.assertEqual(first_call_args[5], "Subject 1")

        # Inspect second call (second article)
        second_call_args = mock_send.call_args_list[1][0]
        self.assertEqual(second_call_args[0], "noreply@noreply (No reply location)")
        self.assertEqual(second_call_args[1], template_id)
        self.assertEqual(second_call_args[2], "html")
        self.assertEqual(second_call_args[3], ["all@example.com", "two@example.com", "three@example.com"])
        self.assertIn("item", second_call_args[4])
        self.assertEqual(second_call_args[5], "Subject 2")

        # Inspect third call to send_transactional
        third_call_args = mock_send.call_args_list[2][0]
        self.assertEqual(third_call_args[0], "noreply@noreply (No reply location)")
        self.assertEqual(third_call_args[1], template_id)
        self.assertEqual(third_call_args[2], "html")
        self.assertEqual(third_call_args[3], ["all@example.com", "three@example.com"])
        self.assertIn("item", third_call_args[4])
        self.assertEqual(third_call_args[5], "Subject 3")

class TestPerformDailyEmailCheck(unittest.TestCase):
    @patch("rssmonk.http_clients.ListmonkClient.send_transactional")
    def test_daily_email_check_sends_correct_data(self, mock_send):
        mock_send.return_value = None  # No actual sending
        rssmonk = RSSMonk(local_creds=HTTPBasicCredentials(username="admin", password="admin123"))

        feed = Feed(email_base_url = "https://example.com", url_hash = "hash123", name = "Example",
                    feed_url = "https://example.com/rss", poll_frequencies = [Frequency.INSTANT])
        frequency = Frequency.DAILY
        template_id = 101

        new_articles = [
            FeedItem(title = "Article 1", link = "https://example.com/1", description = "Desc 1",
                     email_subject_line = "Subject 1", filter_identifiers = "min 0,port 143",
                     published = datetime.now(), guid = "guid 1"),
            FeedItem(title = "Article 2", link = "https://example.com/2", description = "Desc 2",
                     email_subject_line = "Subject 2", filter_identifiers = "min 1,port 565",
                     published = datetime.now() - timedelta(minutes=2), guid = "guid 2"),
            FeedItem(title = "Article 3", link = "https://example.com/3", description = "Desc 3",
                     email_subject_line = "Subject 3", filter_identifiers = "min 2,port 565",
                     published = datetime.now() - timedelta(minutes=4), guid = "guid 3")
        ]

        subscribers = [
            {
                "email": "user@example.com",
                "attribs": { "hash123": { "filter": { "daily": "all" } } }
            },
            {
                "email": "all@example.com",
                "attribs": { "hash123": { "filter": { "daily": "all" } } }
            },
            {
                "email": "one@example.com",
                "attribs": { "hash123": { "filter": { "daily": { "min" : [0] } } } }
            },
            {
                "email": "second@example.com",
                "attribs": { "hash123": { "filter": { "daily": { "port" : [143] } } } }
            },
            {
                "email": "three@example.com",
                "attribs": { "hash123": { "filter": { "daily": { "min" : [0, 1] } } } }
            },
            {
                "email": "four@example.com",
                "attribs": { "hash123": { "filter": { "daily": { "min" : "all" } } } }
            }
        ]

        # Method under test
        notifications_sent = rssmonk.perform_daily_email_check(feed, frequency, template_id, new_articles, subscribers)

        # Check notifications sent and call count
        self.assertEqual(notifications_sent, 6)  # One for each user
        self.assertEqual(mock_send.call_count, 5)  # One for each user and 1 which covers all

        # Inspect first filtered user call to send_transactional
        first_call_args = mock_send.call_args_list[0][0]
        self.assertEqual(first_call_args[0], "noreply@noreply (No reply location)")
        self.assertEqual(first_call_args[1], template_id)
        self.assertEqual(first_call_args[2], "html")
        self.assertEqual(first_call_args[3], ["one@example.com"])  # Single recipient
        self.assertIn("items", first_call_args[4])  # 'items' is present
        self.assertEqual(len(first_call_args[4]["items"]), 1, first_call_args[4]["items"]) # One article
        self.assertEqual(first_call_args[4]["items"][0]["title"], "Article 1") # Correct article that matches "min 0"

        # Inspect second filtered user call to send_transactional
        second_call_args = mock_send.call_args_list[1][0]
        self.assertEqual(second_call_args[0], "noreply@noreply (No reply location)")
        self.assertEqual(second_call_args[1], template_id)
        self.assertEqual(second_call_args[2], "html")
        self.assertEqual(second_call_args[3], ["second@example.com"])  # All-inclusive list
        self.assertIn("items", second_call_args[4])  # 'items' is present
        self.assertEqual(len(second_call_args[4]["items"]), 1, second_call_args[4]["items"]) # One article
        self.assertEqual(second_call_args[4]["items"][0]["title"], "Article 1") # Correct article that matches "port 143"

        # Inspect third filtered user call to send_transactional
        third_call_args = mock_send.call_args_list[2][0]
        self.assertEqual(third_call_args[0], "noreply@noreply (No reply location)")
        self.assertEqual(third_call_args[1], template_id)
        self.assertEqual(third_call_args[2], "html")
        self.assertEqual(third_call_args[3], ["three@example.com"])  # All-inclusive list
        self.assertIn("items", third_call_args[4])  # 'items' is present
        self.assertEqual(len(third_call_args[4]["items"]), 2, third_call_args[4]["items"]) # One article
        self.assertEqual(third_call_args[4]["items"][0]["title"], "Article 1") # Correct article that matches "min 0, min 1"
        self.assertEqual(third_call_args[4]["items"][1]["title"], "Article 2") # Correct article that matches "min 0, min 1"

        # Inspect fouth user call to send_transactional
        fourth_call_args = mock_send.call_args_list[3][0]
        self.assertEqual(fourth_call_args[0], "noreply@noreply (No reply location)")
        self.assertEqual(fourth_call_args[1], template_id)
        self.assertEqual(fourth_call_args[2], "html")
        self.assertEqual(fourth_call_args[3], ["four@example.com"])
        self.assertIn("items", fourth_call_args[4])  # 'items' is present
        self.assertEqual(len(fourth_call_args[4]["items"]), 3, fourth_call_args[4]["items"]) # Three articles for category min
        self.assertEqual(fourth_call_args[4]["items"][0]["title"], "Article 1")
        self.assertEqual(fourth_call_args[4]["items"][1]["title"], "Article 2")
        self.assertEqual(fourth_call_args[4]["items"][2]["title"], "Article 3")

        # Inspect fifth user call to send_transactional, which is for all
        fifth_call_args = mock_send.call_args_list[4][0]
        self.assertEqual(fifth_call_args[0], "noreply@noreply (No reply location)")
        self.assertEqual(fifth_call_args[1], template_id)
        self.assertEqual(fifth_call_args[2], "html")
        self.assertEqual(fifth_call_args[3], ["user@example.com", "all@example.com"])  # All-inclusive list
        self.assertIn("items", fifth_call_args[4])  # 'items' is present
        self.assertEqual(len(fifth_call_args[4]["items"]), 3, fifth_call_args[4]["items"]) # Two articles for all
        self.assertEqual(fifth_call_args[4]["items"][0]["title"], "Article 1")
        self.assertEqual(fifth_call_args[4]["items"][1]["title"], "Article 2")
        self.assertEqual(fifth_call_args[4]["items"][2]["title"], "Article 3")
