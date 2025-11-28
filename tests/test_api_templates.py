"""
Test Feed API endpoints
- /api/feeds/templates
"""

from http import HTTPStatus
import json
import requests
from requests.auth import HTTPBasicAuth

from rssmonk.types import FEED_ACCOUNT_PREFIX
from tests.conftest import RSSMONK_URL, UnitTestLifecyclePhase, ListmonkClientTestBase


class TestRSSMonkFeedTemplates(ListmonkClientTestBase):
    # -------------------------
    # POST /api/feeds/templates
    # -------------------------
    def test_post_feed_templates_no_credentials(self):
        sub_template = {
            "feed_url": "http://example.com/rss",
            "subject": "Subject Line",
            "phase_type": "subscribe",
            "template_type": "tx",
            "body": "<html><body></body></html>"
        }
        response = requests.post(RSSMONK_URL+"/api/feeds/templates", auth=None, json=sub_template)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"

        self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
        # - Replace an existing feed template
        pass

    def test_post_feed_templates_non_admin_credentials(self):
        # - Post new feed template
        sub_template = {
            "feed_url": "http://example.com/rss",
            "subject": "Subject Line",
            "phase_type": "subscribe",
            "template_type": "tx",
            "body": "<html><body></body></html>"
        }
        response = requests.post(RSSMONK_URL+"/api/feeds/templates", auth=HTTPBasicAuth("not", "admin123"), json=sub_template)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"

        # - Replace an existing feed template
        pass

    def test_post_feed_templates_admin_credentials(self):
        # - Admin credentials, no feeds, CreateTemplateRequest object
        sub_template = {
            "feed_url": "http://example.com/rss",
            "subject": "Subject Line",
            "phase_type": "subscribe",
            "template_type": "tx",
            "body": "<html><body></body></html>"
        }
        response = requests.post(RSSMONK_URL+"/api/feeds/templates", auth=self.ADMIN_AUTH, json=sub_template)
        assert response.status_code == HTTPStatus.NOT_FOUND, f"{response.status_code}: {response.text}"

        # - Replace an existing feed template
        pass


    # -------------------------
    # DELETE /api/feeds/templates
    # -------------------------
    def test_delete_feed_templates_no_credentials(self):
        # Delete non existing feed template
        response = requests.delete(RSSMONK_URL+"/api/feeds/templates", auth=None, 
                                   json={"feed_url": "https://this-should-not-exist.com", "phase_type": "subscribe"})
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"

        # Delete existing feed template
        self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
        response = requests.delete(RSSMONK_URL+"/api/feeds/templates", auth=None,
                                   json={"feed_url": "https://example.com/rss", "phase_type": "subscribe"})
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"


    def test_delete_feed_templates_non_admin_credentials_failure(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
        user = FEED_ACCOUNT_PREFIX + self.FEED_HASH_ONE
        pwd = init_data.accounts[user]

        # Delete at the end point with no payload
        response = requests.delete(RSSMONK_URL+"/api/feeds/templates", auth=HTTPBasicAuth(user, pwd))
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"

        # Delete non existing feed template
        response = requests.delete(RSSMONK_URL+"/api/feeds/templates", auth=HTTPBasicAuth(user, pwd), json={})
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"

        # Delete template of a non existant phase
        delete_non_existant_template = {"phase_type": "yearly_digest"}
        response = requests.delete(RSSMONK_URL+"/api/feeds/templates", auth=HTTPBasicAuth(user, pwd), json=delete_non_existant_template)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"

        # Delete template of a phase, which does not exist
        random_template_to_delete = {"phase_type": "random"}
        response = requests.delete(RSSMONK_URL+"/api/feeds/templates", auth=HTTPBasicAuth(user, pwd), json=random_template_to_delete)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"

        # Delete existing template that the account does not have access to (Should be bounced because this is an admin only form)
        existing_template_to_delete = {"feed_url": self.FEED_TWO_FEED_URL, "phase_type": "subscribe"}
        response = requests.delete(RSSMONK_URL+"/api/feeds/templates", auth=HTTPBasicAuth(user, pwd), json=existing_template_to_delete)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"


    def test_delete_feed_templates_non_admin_credentials_success(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
        # Non admin credentials, feed exists, DeleteTemplateRequest object
        user = FEED_ACCOUNT_PREFIX + self.FEED_HASH_ONE
        pwd = init_data.accounts[user]

        request = { "phase_type": "subscribe" }
        response = requests.delete(RSSMONK_URL+"/api/feeds/templates", auth=HTTPBasicAuth(user, pwd), json=request)
        assert response.status_code == HTTPStatus.OK, f"{response.status_code}: {response.text}"


    def test_delete_feed_templates_admin_failures(self):
        # Admin credentials, feed does not exist (does not matter here), DeleteTemplateRequest object
        delete_template_data = { "phase_type": "subscribe"}
        response = requests.delete(RSSMONK_URL+"/api/feeds/templates", auth=self.ADMIN_AUTH, json=delete_template_data)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"

        # Admin credentials, feed does not exist, DeleteTemplateAdminRequest object
        feed_not_exist_delete_template_data = {
            "feed_url": "https://unknown-example.com/rss",
            "phase_type": "subscribe"
        }
        response = requests.delete(RSSMONK_URL+"/api/feeds/templates", auth=self.ADMIN_AUTH, json=feed_not_exist_delete_template_data)
        assert response.status_code == HTTPStatus.NOT_FOUND, f"{response.status_code}: {response.text}"


    def test_delete_feed_templates_admin_success(self):
        self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
        # Admin credentials, feeds exist, DeleteTemplateAdminRequest object
        delete_template_data = {
            "feed_url": self.FEED_ONE_FEED_URL,
            "phase_type": "subscribe"
        }
        response = requests.delete(RSSMONK_URL+"/api/feeds/templates", auth=self.ADMIN_AUTH, json=delete_template_data)
        assert response.status_code == HTTPStatus.OK, f"{response.status_code}: {response.text}"
