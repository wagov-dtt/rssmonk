"""
Test Feed API endpoints
- /api/feeds/templates
"""

from http import HTTPStatus
import requests
from requests.auth import HTTPBasicAuth

from tests.listmonk_testbase import RSSMONK_URL, ListmonkClientTestBase


class TestRSSMonkFeedTemplates(ListmonkClientTestBase):    
    def test_create_feed_templates(self):
        """POST /api/feeds/templates - Create email templates (admin only)
        - Create feed template
        """
        assert False

    def test_replace_feed_templates(self):
        """POST /api/feeds/templates - Create email templates (admin only)
        - Replace an existing feed template
        """
        assert False

    def test_delete_feed_templates(self):
        """DELETE /api/feeds/templates - Delete email template (admin only)
        - Delete feed template
        """
        # TODO - need delete by query
        assert False