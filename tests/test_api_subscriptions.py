
import requests
from requests.auth import HTTPBasicAuth

from tests.listmonk_testbase import RSSMONK_URL, LifecyclePhase, ListmonkClientTestBase


class TestRSSMonkSubscriptions(ListmonkClientTestBase):

    # -------------------------
    # POST /api/feeds/subscribe
    # -------------------------
    def test_post_subscribe_no_credentials(self):
		# SubscribeRequest object
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=None)
        self.assertEqual(response.status_code, 401)

		# SubscribeAdminRequest object
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=None)
        self.assertEqual(response.status_code, 401)

    def test_post_subscribe_non_admin_subscribe_request(self):
        accounts = self.initialise_system(LifecyclePhase.FEED_TEMPLATES)
        user, pwd = next(iter(accounts.items()))
		# SubscribeRequest object
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=HTTPBasicAuth(user, pwd))
        self.assertEqual(response.status_code, 200)

    def test_post_subscribe_non_admin_subscribe_admin_request(self):
        accounts = self.initialise_system(LifecyclePhase.FEED_TEMPLATES)
        user, pwd = next(iter(accounts.items()))
		# SubscribeAdminRequest object
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=HTTPBasicAuth(user, pwd))
        self.assertEqual(response.status_code, 200)

    def test_post_subscribe_admin_subscribe_request(self):
		# SubscribeRequest object
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=self.ADMIN_AUTH)
        self.assertEqual(response.status_code, 200)

    def test_post_subscribe_admin_subscribe_admin_request(self):
		# SubscribeAdminRequest object
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=self.ADMIN_AUTH)
        self.assertEqual(response.status_code, 200)


    # -------------------------
    # POST /api/feeds/subscribe-confirm
    # -------------------------
    def test_post_subscribe_confirm_no_credentials(self):
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe-confirm", auth=None)
        self.assertEqual(response.status_code, 401)

    def test_post_subscribe_confirm_non_admin_credentials(self):
        accounts = self.initialise_system(LifecyclePhase.FEED_TEMPLATES)
        user, pwd = next(iter(accounts.items()))

        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe-confirm", auth=HTTPBasicAuth(user, pwd))
        self.assertEqual(response.status_code, 200)

    def test_post_subscribe_confirm_admin_credentials(self):
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe-confirm", auth=self.ADMIN_AUTH)
        self.assertEqual(response.status_code, 200)


    # -------------------------
    # POST /api/feeds/unsubscribe
    # -------------------------
    def test_post_unsubscribe_no_credentials(self):
		# UnsubscribeRequest object
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=None)
        self.assertEqual(response.status_code, 401)

		# UnsubscribeAdminRequest object
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=None)
        self.assertEqual(response.status_code, 401)


    def test_post_unsubscribe_non_admin_unsubscribe_request(self):
		# UnsubscribeRequest object	
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=NON_ADMIN_HEADERS)
        self.assertEqual(response.status_code, 200)

    def test_post_unsubscribe_non_admin_unsubscribe_admin_request(self):
		# UnsubscribeAdminRequest object
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=NON_ADMIN_HEADERS)
        self.assertEqual(response.status_code, 200)

    def test_post_unsubscribe_admin_unsubscribe_request(self):
		# UnsubscribeRequest object
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=self.ADMIN_AUTH)
        self.assertEqual(response.status_code, 200)

    def test_post_unsubscribe_admin_unsubscribe_admin_request(self):
		# UnsubscribeAdminRequest object
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=self.ADMIN_AUTH)
        self.assertEqual(response.status_code, 200)

