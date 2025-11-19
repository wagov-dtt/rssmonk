"""
Test Feed API Account endpoints
- /api/feeds/account
- /api/feeds/account-reset-password)
"""

from http import HTTPStatus
import pytest
import requests
from requests.auth import HTTPBasicAuth

from tests.listmonk_testbase import RSSMONK_URL, LifecyclePhase, ListmonkClientTestBase


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


    def test_create_feed_account_no_feed(self):
        # Admin credential, no existing feed, FeedAccountRequest object
        payload = {"feed_url": "http://example.com/rss"}
        response = requests.post(RSSMONK_URL+"/api/feeds/account", json=payload, auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.OK, f"{response.status_code}: {response.text}"


    def test_create_feed_account_conflict(self):
        self.initialise_system(LifecyclePhase.FEED_LIST)

        # Admin credential, existing feed, FeedAccountRequest object
        payload = {"feed_url": "https://example.com/rss/media-statements"}
        # Second attempt should return conflict
        response = requests.post(RSSMONK_URL+"/api/feeds/account", json=payload, auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.CONFLICT, f"{response.status_code}: {response.text}"
        

    def test_create_feed_account_invalid_url(self):
        # Admin credential, no feed, FeedAccountRequest object
        payload = {"feed_url": "invalid-url"}
        # Invalid url should halt creation
        response = requests.post(RSSMONK_URL+"/api/feeds/account", json=payload, auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"


    def test_create_feed_account_unauthorized(self):
        payload = {"feed_url": "http://example.com/rss"}

        # No credentials, no existing account, FeedAccountRequest object
        response = requests.post(RSSMONK_URL+"/api/feeds/account", json=payload, auth=None)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"

        # Incorrect credentials, no existing account, FeedAccountRequest object
        response = requests.post(RSSMONK_URL+"/api/feeds/account", json=payload, auth=("wrong", "creds"))
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"
        

    # Reset account password
    def test_reset_password_success(self):
        self.initialise_system(LifecyclePhase.FEED_ACCOUNT)

        # Admin credentials, existing account, FeedAccountPasswordResetRequest object
        reset_payload = {"account_name": "user_0cb1e00d5415d57f19b547084a93900a558caafbd04fc10f18aa20e0c46a02a8"}
        response = requests.post(RSSMONK_URL+"/api/feeds/account-reset-password", json=reset_payload, auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.CREATED, f"{response.status_code}: {response.text}"
        data = response.json()
        assert data["name"] == "user_0cb1e00d5415d57f19b547084a93900a558caafbd04fc10f18aa20e0c46a02a8"
        assert "api_password" in data


    def test_reset_password_not_found(self):
        # Admin credentials, no existing account, no object
        response = requests.post(RSSMONK_URL+"/api/feeds/account-reset-password", auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        
        # Admin credentials, no existing account, FeedAccountPasswordResetRequest object
        payload = {"account_name": "nonexistent_account"}
        response = requests.post(RSSMONK_URL+"/api/feeds/account-reset-password", json=payload, auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.NOT_FOUND, f"{response.status_code}: {response.text}"


    def test_reset_password_unauthorized(self):
        # Unknown credentials, existing account, FeedAccountPasswordResetRequest object
        payload = {"account_name": "some_account"}
        response = requests.post(RSSMONK_URL+"/api/feeds/account-reset-password", json=payload, auth=("unknown", "account"))
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"

        # Account credentials, existing account, FeedAccountPasswordResetRequest object
        payload = {"account_name": "some_account"}
        response = requests.post(RSSMONK_URL+"/api/feeds/account-reset-password", json=payload, auth=("unknown", "account"))
        # SHould not be able to reset their own account. Currently reserved for admin
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"


    def test_reset_password_bad_request(self):
        # Admin credentials, no existing account, FeedAccountPasswordResetRequest object
        payload = {"account_name": ""}
        response = requests.post(RSSMONK_URL+"/api/feeds/account-reset-password", json=payload, auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.BAD_REQUEST, f"{response.status_code}: {response.text}"

        # Admin credentials, no existing account, FeedAccountPasswordResetRequest object
        payload = {"account_name": "user_0000000000000000000000000000000000000000000000000000000000000000"}
        response = requests.post(RSSMONK_URL+"/api/feeds/account-reset-password", json=payload, auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.BAD_REQUEST, f"{response.status_code}: {response.text}"
