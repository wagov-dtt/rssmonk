
from http import HTTPStatus
import requests
from requests.auth import HTTPBasicAuth

from tests.listmonk_testbase import RSSMONK_URL, LifecyclePhase, ListmonkClientTestBase


class TestRSSMonkSubscriptions(ListmonkClientTestBase):

    # -------------------------
    # POST /api/feeds/subscribe
    # -------------------------
    def test_post_subscribe_no_feed(self):
        # No credential, no feed, no object
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=None)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"


    def test_post_subscribe_no_credentials(self):
        self.initialise_system(LifecyclePhase.FEED_TEMPLATES)

		# No credential, feed exist, no object
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=None)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"

		# No credential, feed exist, SubscribeRequest object
        sub_req = {
            "email": "email@example.com",
            "filter": {"instant": {"region": [1, 2]}},
            "display_text": {"instant": {"region": ["Verbose region 1", "Verbose region 2"]}}
        }
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=None, json=sub_req)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"

		# No credential, feed exist, SubscribeAdminRequest object
        sub_req = {
            "email": "email@example.com",
            "filter": {"instant": {"region": [1, 2]}},
            "display_text": {"instant": {"region": ["Verbose region 1", "Verbose region 2"]}}
        }
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=None)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"


    def test_post_subscribe_non_admin_no_object(self):
        accounts = self.initialise_system(LifecyclePhase.FEED_TEMPLATES)
        user, pwd = next(iter(accounts.items()))

        # Non admin credential, feed exist, no object
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=HTTPBasicAuth(user, pwd))
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"


    def test_post_subscribe_non_admin_subscribe_request(self):
        accounts = self.initialise_system(LifecyclePhase.FEED_TEMPLATES)
        user, pwd = next(iter(accounts.items()))

		# Non admin credential, feed exist, SubscribeRequest object
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=HTTPBasicAuth(user, pwd))
        assert response.status_code == HTTPStatus.OK, f"{response.status_code}: {response.text}"


    def test_post_subscribe_non_admin_subscribe_admin_request(self):
        accounts = self.initialise_system(LifecyclePhase.FEED_TEMPLATES)
        user, pwd = next(iter(accounts.items()))

		# Non admin credential, feed exist, SubscribeAdminRequest object
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=HTTPBasicAuth(user, pwd))
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"


    def test_post_subscribe_admin_no_object(self):
        self.initialise_system(LifecyclePhase.FEED_TEMPLATES)

        # Admin credential, feed exist, no object
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"


    def test_post_subscribe_admin_subscribe_request(self):
        self.initialise_system(LifecyclePhase.FEED_TEMPLATES)

		# Admin credential, feed exist, SubscribeRequest object
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.OK, f"{response.status_code}: {response.text}"


    def test_post_subscribe_admin_subscribe_admin_request(self):
        self.initialise_system(LifecyclePhase.FEED_TEMPLATES)

		# Admin credential, feed exist, SubscribeAdminRequest object
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.OK, f"{response.status_code}: {response.text}"


    # -------------------------
    # POST /api/feeds/subscribe-confirm
    # -------------------------
    def test_post_subscribe_confirm_no_credentials(self):
        self.initialise_system(LifecyclePhase.FEED_TEMPLATES)
        # No credentials, no object
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe-confirm", auth=None)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"


    def test_post_subscribe_confirm_non_admin_credentials(self):
        accounts = self.initialise_system(LifecyclePhase.FEED_TEMPLATES)
        user, pwd = next(iter(accounts.items()))

        # Non admin, SubscribeConfirmRequest object
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe-confirm", auth=HTTPBasicAuth(user, pwd))
        assert response.status_code == HTTPStatus.OK, f"{response.status_code}: {response.text}"


    def test_post_subscribe_confirm_admin_credentials(self):
        accounts = self.initialise_system(LifecyclePhase.FEED_TEMPLATES)

        # Admin, SubscribeConfirmRequest object
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe-confirm", auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.OK, f"{response.status_code}: {response.text}"


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
		# UnsubscribeRequest object	
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd))
        assert response.status_code == HTTPStatus.NOT_IMPLEMENTED, f"{response.status_code}: {response.text}"


    def test_post_unsubscribe_non_admin_unsubscribe_admin_request(self):
        accounts = self.initialise_system(LifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)
        user, pwd = next(iter(accounts.items()))
		# UnsubscribeAdminRequest object
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd))
        assert response.status_code == HTTPStatus.NOT_IMPLEMENTED, f"{response.status_code}: {response.text}"


    def test_post_unsubscribe_admin_unsubscribe_request(self):
        accounts = self.initialise_system(LifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)
		# UnsubscribeRequest object
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.NOT_IMPLEMENTED, f"{response.status_code}: {response.text}"


    def test_post_unsubscribe_admin_unsubscribe_admin_request(self):
        accounts = self.initialise_system(LifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)
		# UnsubscribeAdminRequest object
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"

