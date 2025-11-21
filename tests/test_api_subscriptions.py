
from http import HTTPStatus
import requests
from requests.auth import HTTPBasicAuth

from tests.listmonk_testbase import LISTMONK_URL, MAILPIT_URL, RSSMONK_URL, LifecyclePhase, ListmonkClientTestBase


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
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=None, json=sub_req)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"


    def test_post_subscribe_non_admin_no_object(self):
        accounts = self.initialise_system(LifecyclePhase.FEED_TEMPLATES)
        user, pwd = next(iter(accounts.items()))

        # Non admin credential, feed exist, no object
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=HTTPBasicAuth(user, pwd))
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"


    def test_post_subscribe_non_admin_subscribe_request(self):
        accounts = self.initialise_system(LifecyclePhase.FEED_TEMPLATES)
        user, pwd = next(iter(accounts.items()))

		# Non admin credential, feed exist, SubscribeRequest object
        sub_req = {
            "email": "email@example.com",
            "filter": {"instant": {"region": [1, 2]}},
            "display_text": {"instant": {"region": ["Verbose region 1", "Verbose region 2"]}}
        }
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=HTTPBasicAuth(user, pwd), json=sub_req)
        assert response.status_code == HTTPStatus.OK, f"{response.status_code}: {response.text}"
        # - Check listmonk for attribs feed without filter (but there's one entry in the feed dict) and no token existance
        response = super().__admin_session.get(LISTMONK_URL+"/api/subscribers", json={"query": "subscribers.email='john@example.com'"})
        subscriber = response.json()["data"]["results"][0]
        assert "0cb1e00d5415d57f19b547084a93900a558caafbd04fc10f18aa20e0c46a02a8" in subscriber["attribs"]
        feed_attribs = subscriber["attribs"]["0cb1e00d5415d57f19b547084a93900a558caafbd04fc10f18aa20e0c46a02a8"]
        # Should only be a single item in here, the key is the guid.
        assert isinstance(feed_attribs, dict)
        assert "filter" not in feed_attribs
        assert "token" not in feed_attribs
        assert 1 == len(feed_attribs.keys())


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
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Field required" in response.text


    def test_post_subscribe_admin_subscribe_request(self):
        self.initialise_system(LifecyclePhase.FEED_TEMPLATES)
        subscribe_data = {
            "email": "john@example.com",
            "filter": {
                "instant" : {
                    "ministers": [0, 1],
                    "region": [2, 3],
                    "portfolio": [2170, 2166]
                }
            },
            "display_text": {
                "instant" : {
                    "ministers": ["Minister 1", "Minister 2"],
                    "region": ["Region 2", "Region 3"],
                    "portfolio": ["Portfolio 1", "Portfolio 2"]
                }
            }
        }
		# Admin credential, feed exist, SubscribeRequest object
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=self.ADMIN_AUTH, json=subscribe_data)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"

        # - Check mailpit for no email
        response = requests.get(MAILPIT_URL+"/api/v1/messages?limit=50")
        assert response["unread"] == 0


    def test_post_subscribe_admin_subscribe_admin_request(self):
        self.initialise_system(LifecyclePhase.FEED_TEMPLATES)
        subscribe_data = {
            "feed_url": "https://example.com/rss/media-statements",
            "email": "john@example.com",
            "filter": {
                "instant" : {
                    "ministers": [0, 1],
                    "region": [2, 3],
                    "portfolio": [2170, 2166]
                }
            },
            "display_text": {
                "instant" : {
                    "ministers": ["Minister 1", "Minister 2"],
                    "region": ["Region 2", "Region 3"],
                    "portfolio": ["Portfolio 1", "Portfolio 2"]
                }
            }
            #"bypass_confirmation": False - Field is optional and defaults to false
        }

		# Admin credential, feed exist, SubscribeAdminRequest object
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=self.ADMIN_AUTH, json=subscribe_data)
        assert response.status_code == HTTPStatus.OK, f"{response.status_code}: {response.text}"
        # - Check mailpit for email
        response = requests.get(MAILPIT_URL+"/api/v1/messages?limit=50")
        assert response["unread"] == 1
        
        # - Check listmonk for attribs feed without filter (but there's one entry in the feed dict) and no token existance
        response = super().__admin_session.get(LISTMONK_URL+"/api/subscribers", json={"query": "subscribers.email='john@example.com'"})
        subscriber = response.json()["data"]["results"][0]
        assert "0cb1e00d5415d57f19b547084a93900a558caafbd04fc10f18aa20e0c46a02a8" in subscriber["attribs"]
        feed_attribs = subscriber["attribs"]["0cb1e00d5415d57f19b547084a93900a558caafbd04fc10f18aa20e0c46a02a8"]
        # Should only be a single item in here, the key is the guid.
        assert isinstance(feed_attribs, dict)
        assert "filter" not in feed_attribs
        assert "token" not in feed_attribs
        assert 1 == len(feed_attribs.keys())


    def test_post_subscribe_admin_subscribe_admin_request_with_bypass(self):
        self.initialise_system(LifecyclePhase.FEED_TEMPLATES)
        subscribe_data = {
            "feed_url": "https://example.com/rss/media-statements",
            "email": "john@example.com",
            "filter": {
                "instant" : {
                    "ministers": [0, 1],
                    "region": [2, 3],
                    "portfolio": [2170, 2166]
                }
            },
            "display_text": {
                "instant" : {
                    "ministers": ["Minister 1", "Minister 2"],
                    "region": ["Region 2", "Region 3"],
                    "portfolio": ["Portfolio 1", "Portfolio 2"]
                }
            },
            "bypass_confirmation": True
        }

		# Admin credential, feed exist, SubscribeAdminRequest object
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=self.ADMIN_AUTH, json=subscribe_data)
        assert response.status_code == HTTPStatus.OK, f"{response.status_code}: {response.text}"
        # - Check mailpit for no email
        response = requests.get(MAILPIT_URL+"/api/v1/messages?limit=50")
        assert response["unread"] == 0

        # - Check listmonk for attribs feed with only and token existance
        response = super().__admin_session.get(LISTMONK_URL+"/api/subscribers", json={"query": "subscribers.email='john@example.com'"})
        subscriber = response.json()["data"]["results"][0]
        assert "0cb1e00d5415d57f19b547084a93900a558caafbd04fc10f18aa20e0c46a02a8" in subscriber["attribs"]
        feed_attribs = subscriber["attribs"]["0cb1e00d5415d57f19b547084a93900a558caafbd04fc10f18aa20e0c46a02a8"]
        # Should only be a single item in here, the key is the guid.
        assert isinstance(feed_attribs, dict)
        assert "filter" in feed_attribs
        assert "token" in feed_attribs
        assert 1 == len(feed_attribs.keys())


    # -------------------------
    # POST /api/feeds/subscribe-confirm
    # -------------------------
    def test_post_subscribe_confirm_no_credentials(self):
        self.initialise_system(LifecyclePhase.FEED_TEMPLATES)
        # No credentials, no object
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe-confirm", auth=None, json=None)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"


    def test_post_subscribe_confirm_non_admin_credentials(self):
        accounts = self.initialise_system(LifecyclePhase.FEED_TEMPLATES)
        user, pwd = next(iter(accounts.items()))

        # Non admin, SubscribeConfirmRequest object
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe-confirm", auth=HTTPBasicAuth(user, pwd))
        assert response.status_code == HTTPStatus.IM_A_TEAPOT, f"{response.status_code}: {response.text}"


    def test_post_subscribe_confirm_admin_credentials(self):
        accounts = self.initialise_system(LifecyclePhase.FEED_TEMPLATES)

        # Admin, SubscribeConfirmRequest object
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe-confirm", auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.IM_A_TEAPOT, f"{response.status_code}: {response.text}"


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

		# Non admin credentials, feed existing, UnsubscribeRequest object	
        unsub_data = {"id": "", "token": ""}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd), json=unsub_data)
        assert response.status_code == HTTPStatus.BAD_REQUEST, f"{response.status_code}: {response.text}"


    def test_post_unsubscribe_non_admin_unsubscribe_admin_request(self):
        accounts = self.initialise_system(LifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)
        user, pwd = next(iter(accounts.items()))

		# Non admin credentials, feed existing, UnsubscribeAdminRequest object
        unsub_data = {"email": "", "bypass_confirmation" : True, "feed_url": ""}
        response = requests.post(RSSMONK_URL+"/api/feeds/unsubscribe", auth=HTTPBasicAuth(user, pwd), json=unsub_data)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"


    def test_post_unsubscribe_admin_unsubscribe_request(self):
        self.initialise_system(LifecyclePhase.FEED_SUBSCRIBE_CONFIRMED)

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
