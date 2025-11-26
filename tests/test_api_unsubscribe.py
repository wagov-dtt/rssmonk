
import time
from http import HTTPStatus
import requests
from requests.auth import HTTPBasicAuth

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
        user, pwd = next(iter(init_data.accounts.items()))

        # Non admin credentials, feed existing, no object
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd))
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"

        # Non admin credentials, feed existing, empty object
        unsub_request = {}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd), json=unsub_request)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Field required" in response.text

        # Non admin credentials, feed existing, UnsubscribeRequest object, empty values
        unsub_request = {"subscriber_id": "", "token": ""}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd), json=unsub_request)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Value error, badly formed hexadecimal UUID string" in response.text
        assert "Value error, Token should not be empty" in response.text

        id, token = next(iter(init_data.pending_subscriber.items()))
        # Non admin credentials, feed existing, UnsubscribeRequest object, non valid ID value, empty token
        unsub_request = {"subscriber_id": "00000000-0000-0000-0000-000000000000", "token": ""}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd), json=unsub_request)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Value error, Token should not be empty" in response.text

        # Non admin credentials, feed existing, UnsubscribeRequest object, non valid ID value, token that does not exist
        unsub_request = {"subscriber_id": "00000000-0000-0000-0000-000000000000", "token": "00000000000000000000000000000000"}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd), json=unsub_request)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Invalid subscriber details" in response.text

        # Non admin credentials, feed existing, UnsubscribeRequest object, no ID value, token is valid
        unsub_request = {"subscriber_id": "", "token": token}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd), json=unsub_request)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Value error, badly formed hexadecimal UUID string" in response.text

        # Non admin credentials, feed existing, UnsubscribeRequest object, valid ID value, empty token
        unsub_request = {"subscriber_id": id, "token": ""}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd), json=unsub_request)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Value error, Token should not be empty" in response.text

        # Non admin credentials, feed existing, UnsubscribeRequest object, ID value, token that does not exist
        unsub_request = {"subscriber_id": id, "token": "00000000000000000000000000000000"}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd), json=unsub_request)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Incorrect token" in response.text


    def test_post_unsubscribe_non_admin_unsubscribe_request_valid_data(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)
        user, pwd = next(iter(init_data.accounts.items()))
        sub_uuid, sub_token = next(iter(init_data.pending_subscriber.items()))

        # Non admin credentials, feed existing, UnsubscribeRequest object, ID value, valid token
        unsub_request = {"subscriber_id": sub_uuid, "token": sub_token}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd), json=unsub_request)
        assert response.status_code == HTTPStatus.OK, f"{response.status_code}: {response.text}"

        # Check to see if user has been removed (should have been removed)
        response = self.admin_session.get(LISTMONK_URL+"/api/subscribers", json={"query": "subscribers.email='example@example.com'"})
        assert response.json()["data"]["total"] == 0
        # TODO - Check email


    def test_post_unsubscribe_non_admin_unsubscribe_request_multiple_subscriptions(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)
        user, pwd = next(iter(init_data.accounts.items()))
        sub_uuid, sub_token = next(iter(init_data.pending_subscriber.items()))
        # TODO - Subscribe to the other subscription

        # Non admin credentials, feed existing, UnsubscribeRequest object, ID value, valid token
        unsub_request = {"subscriber_id": sub_uuid, "token": sub_token}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd), json=unsub_request)
        assert response.status_code == HTTPStatus.OK, f"{response.status_code}: {response.text}"

        # Check to see if user continues to exist
        response = self.admin_session.get(LISTMONK_URL+"/api/subscribers", json={"query": "subscribers.email='example@example.com'"})
        assert response.json()["data"]["total"] == 0
        # TODO - Check email


    def test_post_unsubscribe_non_admin_unsubscribe_request(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)
        user, pwd = next(iter(init_data.accounts.items()))

        # Non admin credentials, feed existing, UnsubscribeRequest object, empty values
        unsub_request = {"subscriber_id": "", "token": ""}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd), json=unsub_request)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Value error, badly formed hexadecimal UUID string" in response.text
        assert "Value error, Token should not be empty" in response.text


    def test_post_unsubscribe_non_admin_unsubscribe_admin_request(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)
        user, pwd = next(iter(init_data.accounts.items()))

        # Non admin credentials, feed existing, UnsubscribeAdminRequest object
        unsub_request = {"email": "", "feed_url": "", "bypass_confirmation" : True}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd), json=unsub_request)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "UnsubscribeRequest" in response.text # Looking for the UnsubscribeRequest object


    def test_post_unsubscribe_admin_unsubscribe_request(self):
        self.initialise_system(UnitTestLifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)

        unsub_request = {}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=self.ADMIN_AUTH, json=unsub_request)
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
        unsub_request = {"email": "john@example.com", "feed_url": "http://www.abc.net.au/news", "bypass_confirmation" : True}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=self.ADMIN_AUTH, json=unsub_request)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"

        # Admin credentials, feed existing, valid UnsubscribeAdminRequest object
        unsub_request = {"email": "", "feed_url": "", "bypass_confirmation" : True}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=self.ADMIN_AUTH, json=unsub_request)
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
        unsub_request = {"email": "", "feed_url": "", "bypass_confirmation" : True}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=self.ADMIN_AUTH, json=unsub_request)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        # TODO - Check email
        # TODO - Check to see if user exists (should have been removed)