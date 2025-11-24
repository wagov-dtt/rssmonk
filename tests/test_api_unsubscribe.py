
import time
from http import HTTPStatus
import requests
from requests.auth import HTTPBasicAuth

from tests.conftest import LISTMONK_URL, MAILPIT_URL, RSSMONK_URL, LifecyclePhase, ListmonkClientTestBase, make_admin_session


class TestRSSMonkUnsubscribe(ListmonkClientTestBase):
    # -------------------------
    # POST /api/feeds/unsubscribe
    # -------------------------
    def test_post_unsubscribe_no_credentials(self):
        # No credentials, no feed, no object
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=None)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"

        self.initialise_system(LifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)
        # No credentials, no feed UnsubscribeRequest object
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=None)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"

        #  No credentials, no feed UnsubscribeAdminRequest object
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=None)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"


    def test_post_unsubscribe_non_admin_unsubscribe_request(self):
        accounts = self.initialise_system(LifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)
        user, pwd = next(iter(accounts.items()))

        # Non admin credentials, feed existing, no object
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd))
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"

        # Non admin credentials, feed existing, empty object
        unsub_data = {}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd), json=unsub_data)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Field required" in response.text

        # Non admin credentials, feed existing, UnsubscribeRequest object, empty values
        unsub_data = {"id": "", "token": ""}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd), json=unsub_data)
        assert response.status_code == HTTPStatus.BAD_REQUEST, f"{response.status_code}: {response.text}"


    def test_post_unsubscribe_non_admin_unsubscribe_request_invalid_data(self):
        accounts = self.initialise_system(LifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)
        user, pwd = next(iter(accounts.items()))

        # Non admin credentials, feed existing, UnsubscribeRequest object, ID value, empty token
        unsub_data = {"id": "00000000-0000-0000-0000-000000000000", "token": ""}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd), json=unsub_data)
        assert response.status_code == HTTPStatus.BAD_REQUEST, f"{response.status_code}: {response.text}"

        # Non admin credentials, feed existing, UnsubscribeRequest object, ID value, token that does not exist
        unsub_data = {"id": "00000000-0000-0000-0000-000000000000", "token": "00000000000000000000000000000000"}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd), json=unsub_data)
        assert response.status_code == HTTPStatus.BAD_REQUEST, f"{response.status_code}: {response.text}"


    def test_post_unsubscribe_non_admin_unsubscribe_request_valid_data(self):
        accounts = self.initialise_system(LifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)
        user, pwd = next(iter(accounts.items()))

        # Non admin credentials, feed existing, UnsubscribeRequest object, ID value, valid token
        unsub_data = {"id": "00000000-0000-0000-0000-000000000000", "token": "21286da0cb7c4f8083ca5846e5627c41"}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd), json=unsub_data)
        assert response.status_code == HTTPStatus.OK, f"{response.status_code}: {response.text}"
        # TODO - Check email
        # TODO - Check to see if user exists (should have been removed)


    def test_post_unsubscribe_non_admin_unsubscribe_request(self):
        accounts = self.initialise_system(LifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)
        user, pwd = next(iter(accounts.items()))

        # Non admin credentials, feed existing, UnsubscribeRequest object, empty values
        unsub_data = {"id": "", "token": ""}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd), json=unsub_data)
        assert response.status_code == HTTPStatus.BAD_REQUEST, f"{response.status_code}: {response.text}"


    def test_post_unsubscribe_non_admin_unsubscribe_admin_request(self):
        accounts = self.initialise_system(LifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)
        user, pwd = next(iter(accounts.items()))

        # Non admin credentials, feed existing, UnsubscribeAdminRequest object
        unsub_data = {"email": "", "feed_url": "", "bypass_confirmation" : True}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd), json=unsub_data)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "UnsubscribeRequest" in response.text # Looking for the UnsubscribeRequest object


    def test_post_unsubscribe_admin_unsubscribe_request(self):
        self.initialise_system(LifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)

        unsub_data = {}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=self.ADMIN_AUTH, json=unsub_data)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Field required" in response.text

        # Admin credentials, feed existing, UnsubscribeRequest object
        unsub_data = {"id": "", "token": ""}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=self.ADMIN_AUTH, json=unsub_data)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"


    def test_post_unsubscribe_admin_unsubscribe_admin_request(self):
        self.initialise_system(LifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)
        
        # Admin credentials, feed existing, empty UnsubscribeAdminRequest object
        unsub_data = {"email": "", "feed_url": "", "bypass_confirmation" : True}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=self.ADMIN_AUTH, json=unsub_data)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"

        # Admin credentials, feed existing, UnsubscribeAdminRequest object - unknown feed
        unsub_data = {"email": "john@example.com", "feed_url": "http://www.abc.net.au/news", "bypass_confirmation" : True}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=self.ADMIN_AUTH, json=unsub_data)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"

        # Admin credentials, feed existing, valid UnsubscribeAdminRequest object
        unsub_data = {"email": "", "feed_url": "", "bypass_confirmation" : True}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=self.ADMIN_AUTH, json=unsub_data)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"


    def test_post_unsubscribe_admin_unsubscribe_request_invalid_data(self):
        self.initialise_system(LifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)

        # Admin credentials, feed existing, valid UnsubscribeAdminRequest object
        unsub_data = {"email": "", "feed_url": "", "bypass_confirmation" : True}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=self.ADMIN_AUTH, json=unsub_data)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"


    def test_post_unsubscribe_admin_unsubscribe_request_valid_data(self):
        self.initialise_system(LifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)

        # Admin credentials, feed existing, valid UnsubscribeAdminRequest object
        unsub_data = {"email": "", "feed_url": "", "bypass_confirmation" : True}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=self.ADMIN_AUTH, json=unsub_data)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        # TODO - Check email
        # TODO - Check to see if user exists (should have been removed)