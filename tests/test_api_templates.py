"""
Test Feed API endpoints
- /api/feeds/templates
"""

from http import HTTPStatus
import requests
from requests.auth import HTTPBasicAuth

from tests.listmonk_testbase import RSSMONK_URL, LifecyclePhase, ListmonkClientTestBase


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
        response = requests.post(RSSMONK_URL+"/api/feeds/templates", auth=None,
                                 data=self._get_standard_template("subscribe"))
        self.assertEqual(response.status_code, 401)

        self.initialise_system(LifecyclePhase.FEED_TEMPLATES)
        # - Replace an existing feed template
        pass

    def test_post_feed_templates_non_admin_credentials(self):
        # - Post new feed template
        response = requests.post(RSSMONK_URL+"/api/feeds/templates", auth=HTTPBasicAuth("not", "admin123"),
                                 data=self._get_standard_template("subscribe"))
        self.assertEqual(response.status_code, 401)

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
        response = requests.delete(RSSMONK_URL+"/api/feeds/templates", auth=None, 
                                   data={"feed_url": "https://this-should-not-exist.com", "phase_type": "subscribe"})
        self.assertEqual(response.status_code, 401)

        # Delete existing feed template
        self.initialise_system(LifecyclePhase.FEED_TEMPLATES)
        response = requests.delete(RSSMONK_URL+"/api/feeds/templates", auth=None,
                                   data={"feed_url": "https://example.com/rss", "phase_type": "subscribe"})
        self.assertEqual(response.status_code, 403)


    def test_delete_feed_templates_non_admin_credentials_failure(self):
        # Make feed, account
        accounts = self.initialise_system(LifecyclePhase.FEED_TEMPLATES)
        user, pwd = next(iter(accounts.items()))
        # Delete non existing feed template
        response = requests.delete(RSSMONK_URL+"/api/feeds/templates", auth=HTTPBasicAuth(user, pwd))
        self.assertEqual(response.status_code, 404)

        # Delete existing template that the account does not have access to
        pass

    def test_delete_feed_templates_non_admin_credentials_success(self):
        # Delete existing template that the account does have access to
        pass

    def test_delete_feed_templates_admin_credentials(self):
        # Delete non existing feed template
        delete_template_data = {
            "feed_url": "https://example.com/rss/example",
            "phase_type": "subscribe"
        }
        response = requests.delete(RSSMONK_URL+"/api/feeds/templates", auth=self.ADMIN_AUTH, json=delete_template_data)
        self.assertEqual(response.status_code, 200)
