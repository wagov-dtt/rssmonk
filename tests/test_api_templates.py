"""
Test Feed API endpoints
- /api/feeds/templates
"""

from http import HTTPStatus
import requests
from requests.auth import HTTPBasicAuth

from tests.listmonk_testbase import RSSMONK_URL, ListmonkClientTestBase


class TestRSSMonkFeedTemplates(ListmonkClientTestBase):
    def _get_standard_template(feed_url: str, phase_type: str) -> dict[str, str]:
        """Edit dict as necessary"""
        return {
            "feed_url": feed_url,
            "subject": "Subject Line",
            "phase_type": phase_type,
            "template_type": "tx",
            "body": "<html><body></body></html>"
        }

    # -------------------------
    # POST /api/feeds/templates
    # -------------------------
    def test_post_feed_templates_no_credentials(self):
        response = requests.post(RSSMONK_URL+"/api/feeds/templates",
                                 data=self._get_standard_template("subscribe"))
        self.assertEqual(response.status_code, 401)

        # - Replace an existing feed template
        pass

    def test_post_feed_templates_non_admin_credentials(self):
        # - Post new feed template
        response = requests.post(RSSMONK_URL+"/api/feeds/templates", auth=HTTPBasicAuth("not", "admin123"),
                                 data=self._get_standard_template("subscribe"))
        self.assertEqual(response.status_code, 200)

        # - Replace an existing feed template
        pass

    def test_post_feed_templates_admin_credentials(self):
        # - Post new feed template
        response = requests.post(RSSMONK_URL+"/api/feeds/templates", auth=self.ADMIN_AUTH,
                                 data=self._get_standard_template("subscribe"))
        self.assertEqual(response.status_code, 200)

        # - Replace an existing feed template
        pass


    # -------------------------
    # DELETE /api/feeds/templates
    # -------------------------
    def test_delete_feed_templates_no_credentials(self):
        # Delete non existing feed template
        response = requests.delete(RSSMONK_URL+"/api/feeds/templates", data={
            "feed_url": "https://this-should-not-exist.com", "phase_type": "subscribe"})
        self.assertEqual(response.status_code, 404)

        # Delete existing feed template
        self.make_feed_list()
        self.make_feed_templates()
        response = requests.delete(RSSMONK_URL+"/api/feeds/templates", data={
            "feed_url": "https://example.com/rss", "phase_type": "subscribe"})
        self.assertEqual(response.status_code, 404)

        pass

    def test_delete_feed_templates_non_admin_credentials(self):
        # TODO - Make feed, account
        # Delete non existing feed template 
        response = requests.delete(RSSMONK_URL+"/api/feeds/templates", NON_ADMIN_HEADERS)
        self.assertEqual(response.status_code, 200)

        self.make_feed_list()
        self.make_feed_account()
        # Delete existing template that the account does not have access to
        pass

        # Delete existing template that the account does have access to
        pass

    def test_delete_feed_templates_admin_credentials(self):
        # Delete non existing feed template
        delete_feed_data = {
            "feed_url": "https://example.com/rss/example",
            "phase_type": "subscribe"
        }
        response = requests.delete(RSSMONK_URL+"/api/feeds/templates", auth=self.ADMIN_AUTH, json=delete_feed_data)
        self.assertEqual(response.status_code, 200)
