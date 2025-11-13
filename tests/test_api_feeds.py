"""
Test Feed API endpoints
- /api/feeds
"""

from http import HTTPStatus
import requests
from requests.auth import HTTPBasicAuth

from tests.listmonk_testbase import RSSMONK_URL, ListmonkClientTestBase


class TestRSSMonkFeeds(ListmonkClientTestBase):
    def test_get_root(self):
        """
        Tests create feed endpoint.
        """
        response = requests.get(RSSMONK_URL+"/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "RSS Monk API"
        assert data["version"] == "2.0.0"

class TestRSSMonkFeeds(ListmonkClientTestBase):
    def insert_example_rss(self):
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

    def make_feed_account(self, feed_url: str):

        return ""

    def test_get_feeds_no_access(self):
        """GET /api/feeds - List RSS Feeds
        - No acesss
        """
        response = requests.get(RSSMONK_URL+"/api/feeds", auth=None)
        assert response.status_code == 401

    def test_list_feeds_unauthorized_user(self):
        response = requests.get(RSSMONK_URL+"/api/feeds", auth=HTTPBasicAuth("no-one", "pawword"))
        assert response.status_code == HTTPStatus.UNAUTHORIZED

    def test_list_feeds_admin_success(self):
        self.insert_example_rss() # Add example rss

        response = requests.get(RSSMONK_URL+"/api/feeds", auth=self.ADMIN_AUTH)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["feeds"]) == 3 

        assert data["feeds"][0]["feed_url"] == "https://bbc.co.uk.example/rss/example"
        assert data["feeds"][1]["feed_url"] == "https://abc.net.example/rss/example"
        assert data["feeds"][2]["feed_url"] == "https://example.com/rss/example"

    def test_list_feeds_feed_account_success(self):
        self.insert_example_rss() # Add example rss

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

    def test_create_feed(self):
        """POST /api/feeds - Create RSS Feed (admin only)
        - Create feed with permutations of url, name (optional), frequency and list_visibility with no pre-existing feed
        - Create feed that already exists with incoming frequencies being a subset of existing
        - Create feed with already exists with incoming frequencies having no overlap with existing
        - Create feed with already exists with incoming frequencies having partial overlap with existing
        - Create feed with invalid url, frequency and list_visibility
        """
        response = requests.post(RSSMONK_URL+"/api/feeds", auth=self.ADMIN_AUTH)
        # TODO
        assert False

    def test_get_feed_by_url(self):
        """GET /api/feeds/by-url - Get Feed by URL"""
        assert False

    def test_delete_feed_by_url(self):
        """DELETE /api/feeds/by-url - Delete Feed by URL (admin only)

        - Delete non existing feed
        - Delete existing feed. Ensure feed, user account, list role, templates are removed
        """
        assert False

    def test_get_configurations(self):
        """GET /api/feeds/configurations - Get URL Configurations"""
        assert False

    def test_update_configurations(self):
        """PUT /api/feeds/configurations - Update Feed Configuration"""
        assert False

    def test_get_subscribe_preferences(self):
        """GET /api/feeds/subscribe-preferences - Get Feed preferences"""
        assert False
