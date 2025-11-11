"""Test Feed API endpoints (/apit/feeds/*)."""

import requests

from tests.listmonk_testbase import RSSMONK_URL, ListmonkClientTestBase



class TestRSSMonkFeeds(ListmonkClientTestBase):
    def test_get_root(self):
        """
        Tests create feed endpoint. POST /api/feeds

        """
        response = requests.get(RSSMONK_URL+"/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "RSS Monk API"
        assert data["version"] == "2.0.0"


    def test_get_feeds(self):
        """GET /api/feeds - List RSS Feeds
        - No acess
        """
        response = requests.get(RSSMONK_URL+"/api/feeds")
        assert response.status_code == 401
        data = response.json()


    def test_create_feed(self):
        """POST /api/feeds - Create RSS Feed (admin only)
        - Create feed with permutations of url, name (optional), frequency and list_visibility with no pre-existing feed
        - Create feed that already exists with incoming frequencies being a subset of existing
        - Create feed with already exists with incoming frequencies having no overlap with existing
        - Create feed with already exists with incoming frequencies having partial overlap with existing
        - Create feed with invalid url, frequency and list_visibility
        """
        pass


    def test_create_feed_templates(self):
        """POST /api/feeds/templates - Create email templates (admin only)
        - Create feed template
        """
        pass


    def test_create_account_feed(self):
        """POST /api/feeds/account - Create account RSS Feed (admin only)
        - Create feed account. Ensure list role and account have been created with limited role
        """

        pass


    def test_reset_account_password(self):
        """POST /api/feeds/account-reset-password - Reset RSS Feed account password (admin only)"""
        pass


    def test_get_feed_by_url(self):
        """GET /api/feeds/by-url - Get Feed by URL"""
        pass


    def test_delete_feed_by_url(self):
        """DELETE /api/feeds/by-url - Delete Feed by URL (admin only)

        - Delete non existing feed
        - Delete existing feed. Ensure feed, user account, list role, templates are removed
        """
        pass


    def test_get_configurations(self):
        """GET /api/feeds/configurations - Get URL Configurations"""
        pass


    def test_update_configurations(self):
        """PUT /api/feeds/configurations - Update Feed Configuration"""
        pass


    def test_get_subscribe_preferences(self):
        """GET /api/feeds/subscribe-preferences - Get Feed preferences"""
        pass


    def test_subscribe_to_feed(self):
        """POST /api/feeds/subscribe - Subscribe to a Feed"""
        pass


    def test_confirm_subscription(self):
        """POST /api/feeds/subscribe-confirm - Confirm subscription to a Feed"""
        pass


    def test_unsubscribe_from_feed(self):
        """POST /api/feeds/unsubscribe - Unsubscribe from a Feed"""
        pass