
import json
import time
from http import HTTPStatus
import requests
from requests.auth import HTTPBasicAuth

from rssmonk.types import FEED_ACCOUNT_PREFIX
from tests.conftest import LISTMONK_URL, MAILPIT_URL, RSSMONK_URL, UnitTestLifecyclePhase, ListmonkClientTestBase, make_admin_session


class TestRSSMonkUnsubscribe(ListmonkClientTestBase):
    # -------------------------
    # POST /api/feeds/unsubscribe
    # -------------------------
    def test_post_unsubscribe_no_credentials(self):
        # No credentials, no feed, no object
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=None)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"

        self.initialise_system(UnitTestLifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)
        # No credentials, no feed UnsubscribeRequest object
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=None)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"

        #  No credentials, no feed UnsubscribeAdminRequest object
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=None)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"


    def test_post_unsubscribe_non_admin_unsubscribe_request_failures(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)
        user = FEED_ACCOUNT_PREFIX + self.FEED_HASH_ONE
        pwd = init_data.accounts[user]

        # Non admin credentials, feed existing, no object
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd))
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"

        # Non admin credentials, feed existing, empty object
        unsub_request = {}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd), json=unsub_request)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Field required" in response.text

        # Non admin credentials, feed existing, UnsubscribeRequest object, empty values
        unsub_2_request = {"subscriber_id": "", "token": ""}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd), json=unsub_2_request)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Value error, badly formed hexadecimal UUID string" in response.text
        assert "Value error, Token should not be empty" in response.text

        sub_tokens = init_data.subscribers[self.one_feed_subscriber_uuid]
        # Non admin credentials, feed existing, UnsubscribeRequest object, non valid ID value, empty token
        unsub_3_request = {"subscriber_id": "00000000-0000-0000-0000-000000000000", "token": ""}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd), json=unsub_3_request)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Value error, Token should not be empty" in response.text

        # Non admin credentials, feed existing, UnsubscribeRequest object, non valid ID value, token that does not exist
        unsub_4_request = {"subscriber_id": "00000000-0000-0000-0000-000000000000", "token": "00000000000000000000000000000000"}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd), json=unsub_4_request)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Invalid subscriber details" in response.text

        # Non admin credentials, feed existing, UnsubscribeRequest object, no ID value, token is valid
        unsub_5_request = {"subscriber_id": "", "token": sub_tokens[self.FEED_HASH_ONE]}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd), json=unsub_5_request)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Value error, badly formed hexadecimal UUID string" in response.text

        # Non admin credentials, feed existing, UnsubscribeRequest object, valid ID value, empty token
        unsub_6_request = {"subscriber_id": self.one_feed_subscriber_uuid, "token": ""}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd), json=unsub_6_request)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Value error, Token should not be empty" in response.text

        # Non admin credentials, feed existing, UnsubscribeRequest object, ID value, token that does not exist
        unsub_7_request = {"subscriber_id": self.one_feed_subscriber_uuid, "token": "00000000000000000000000000000000"}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd), json=unsub_7_request)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Incorrect token" in response.text


    def test_post_unsubscribe_non_admin_unsubscribe_request_valid_data(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)
        user = FEED_ACCOUNT_PREFIX + self.FEED_HASH_ONE
        pwd = init_data.accounts[user]
        sub_tokens = init_data.subscribers[self.one_feed_subscriber_uuid]

        # Non admin credentials, feed existing, UnsubscribeRequest object, ID value, valid token
        unsub_request = {"subscriber_id": self.one_feed_subscriber_uuid, "token": sub_tokens[self.FEED_HASH_ONE]}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd), json=unsub_request)
        assert response.status_code == HTTPStatus.OK, f"{response.status_code}: {response.text}"

        # Check to see if user has been removed (should have been removed)
        response = self.admin_session.get(LISTMONK_URL+"/api/subscribers", json={"query": "subscribers.email='example@example.com'"})
        assert response.json()["data"]["total"] == 0
        # TODO - Check email


    def test_post_unsubscribe_non_admin_unsubscribe_request_multiple_subscriptions(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)
        user = FEED_ACCOUNT_PREFIX + self.FEED_HASH_ONE
        pwd = init_data.accounts[user]
        sub_tokens = init_data.subscribers[self.two_feed_subscriber_uuid]

        # Non admin credentials, feed existing, UnsubscribeRequest object, ID value, valid token
        unsub_request = {"subscriber_id": self.two_feed_subscriber_uuid, "token": sub_tokens[self.FEED_HASH_ONE]}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd), json=unsub_request)
        assert response.status_code == HTTPStatus.OK, f"{response.status_code}: {response.text}"

        # Check to see if user continues to exist
        response = self.admin_session.get(LISTMONK_URL+"/api/subscribers", json={"query": "subscribers.email='example@example.com'"})
        assert response.json()["data"]["total"] == 1
        # TODO - Check email


    def test_post_unsubscribe_non_admin_unsubscribe_request(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)
        user = FEED_ACCOUNT_PREFIX + self.FEED_HASH_ONE
        pwd = init_data.accounts[user]

        # Non admin credentials, feed existing, UnsubscribeRequest object, empty values
        unsub_request = {"subscriber_id": "", "token": ""}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd), json=unsub_request)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Value error, badly formed hexadecimal UUID string" in response.text
        assert "Value error, Token should not be empty" in response.text


    def test_post_unsubscribe_non_admin_unsubscribe_admin_request(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)
        user = FEED_ACCOUNT_PREFIX + self.FEED_HASH_ONE
        pwd = init_data.accounts[user]

        # Non admin credentials, feed existing, UnsubscribeAdminRequest object
        unsub_request = {"email": "", "feed_url": "", "bypass_confirmation" : True}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd), json=unsub_request)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "UnsubscribeRequest" in response.text # Looking for the UnsubscribeRequest object


    def test_post_unsubscribe_admin_unsubscribe_request(self):
        self.initialise_system(UnitTestLifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)

        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=self.ADMIN_AUTH, json={})
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Field required" in response.text

        # Admin credentials, feed existing, UnsubscribeRequest object
        unsub_request = {"subscriber_id": "", "token": ""}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=self.ADMIN_AUTH, json=unsub_request)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"


    def test_post_unsubscribe_admin_unsubscribe_admin_request(self):
        self.initialise_system(UnitTestLifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)
        
        # Admin credentials, feed existing, empty UnsubscribeAdminRequest object
        unsub_request = {"email": "", "feed_url": "", "bypass_confirmation" : True}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=self.ADMIN_AUTH, json=unsub_request)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"

        # Admin credentials, feed existing, UnsubscribeAdminRequest object - unknown feed
        unsub_2_request = {"email": "john@example.com", "feed_url": "http://www.abc.net.au/news", "bypass_confirmation" : True}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=self.ADMIN_AUTH, json=unsub_2_request)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"

        # Admin credentials, feed existing, valid UnsubscribeAdminRequest object
        unsub_3_request = {"email": "", "feed_url": "", "bypass_confirmation" : True}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=self.ADMIN_AUTH, json=unsub_3_request)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"


    def test_post_unsubscribe_admin_unsubscribe_request_invalid_data(self):
        self.initialise_system(UnitTestLifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)

        # Admin credentials, feed existing, valid UnsubscribeAdminRequest object
        unsub_request = {"email": "", "feed_url": "", "bypass_confirmation" : True}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=self.ADMIN_AUTH, json=unsub_request)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"


    def test_post_unsubscribe_admin_unsubscribe_request_valid_data(self):
        self.initialise_system(UnitTestLifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)

        # Admin credentials, feed existing, valid UnsubscribeAdminRequest object
        unsub_request = {"email": "example@example.com", "feed_url": self.FEED_ONE_FEED_URL, "bypass_confirmation" : True}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=self.ADMIN_AUTH, json=unsub_request)
        assert response.status_code == HTTPStatus.OK, f"{response.status_code}: {response.text}"
        
        # Check email
        response = requests.get(MAILPIT_URL+"/api/v1/messages?limit=50")
        assert response.json()["unread"] == 0

        # Check to see if subscriber exists (should have been removed)
        response = make_admin_session().get(LISTMONK_URL+"/api/subscribers", json={"query": "subscribers.email = 'example@example.com'"})
        assert len(response.json()["data"]["results"]) == 0
