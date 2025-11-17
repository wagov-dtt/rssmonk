"""
Test Feed API Account endpoints
- /api/feeds/account
- /api/feeds/account-reset-password)
"""

from http import HTTPStatus
import pytest
import requests
from requests.auth import HTTPBasicAuth

from tests.listmonk_testbase import RSSMONK_URL, ListmonkClientTestBase


class TestRSSMonkFeedAccount(ListmonkClientTestBase):

    # Account creation
    def test_create_feed_account_success(self):
        payload = {"feed_url": "http://example.com/rss"}
        response = requests.post(RSSMONK_URL+"/api/feeds/account", json=payload, auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.CREATED
        data = response.json()
        assert "id" in data
        assert "api_password" in data
        assert len(dict(data).get("api_password", "")) == 32

    def test_create_feed_account_conflict(self):
        # First create the account
        payload = {"feed_url": "http://example.com/rss"}
        requests.post(RSSMONK_URL+"/api/feeds/account", json=payload, auth=self.ADMIN_AUTH)

        # Second attempt should return conflict
        response = requests.post(RSSMONK_URL+"/api/feeds/account", json=payload, auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.CONFLICT
        

    def test_create_feed_account_invalid_url(self):
        payload = {"feed_url": "invalid-url"}
        response = requests.post(RSSMONK_URL+"/api/feeds/account", json=payload, auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT

    def test_create_feed_account_unauthorized(self):
        payload = {"feed_url": "http://example.com/rss"}
        response = requests.post(RSSMONK_URL+"/api/feeds/account", json=payload, auth=("wrong", "creds"))
        assert response.status_code == HTTPStatus.UNAUTHORIZED

    # Reset account password
    def test_reset_password_success(self):
        # First create an account to reset later
        create_payload = {"feed_url": "http://example.com/rss"}
        create_resp = requests.post(RSSMONK_URL+"/api/feeds/account", json=create_payload, auth=self.ADMIN_AUTH)
        assert create_resp.status_code == HTTPStatus.CREATED
        account_name = create_resp.json()["name"]

        # Reset password for the created account
        reset_payload = {"account_name": account_name}
        reset_resp = requests.post(RSSMONK_URL+"/api/feeds/account-reset-password", json=reset_payload, auth=self.ADMIN_AUTH)
        assert reset_resp.status_code == HTTPStatus.CREATED
        data = reset_resp.json()
        assert data["name"] == account_name
        assert "api_password" in data

    def test_reset_password_not_found(self):
        payload = {"account_name": "nonexistent_account"}
        response = requests.post(RSSMONK_URL+"/api/feeds/account-reset-password", json=payload, auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.NOT_FOUND

    def test_reset_password_unauthorized(self):
        payload = {"account_name": "some_account"}
        response = requests.post(RSSMONK_URL+"/api/feeds/account-reset-password", json=payload, auth=("unknown", "account"))
        assert response.status_code == HTTPStatus.UNAUTHORIZED

        # A feed is unable to reset their own account 
        payload = {"account_name": "some_account"}
        response = requests.post(RSSMONK_URL+"/api/feeds/account-reset-password", json=payload, auth=("unknown", "account"))
        assert response.status_code == HTTPStatus.UNAUTHORIZED

    def test_reset_password_bad_request(self):
        # Simulate invalid account name format
        payload = {"account_name": ""}
        response = requests.post(RSSMONK_URL+"/api/feeds/account-reset-password", json=payload, auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.BAD_REQUEST
