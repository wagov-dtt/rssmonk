
import time
from http import HTTPStatus
import requests
from requests.auth import HTTPBasicAuth

from rssmonk.types import FEED_ACCOUNT_PREFIX
from tests.conftest import LISTMONK_URL, MAILPIT_URL, RSSMONK_URL, UnitTestLifecyclePhase, ListmonkClientTestBase, make_admin_session


class TestRSSMonkSubscribe(ListmonkClientTestBase):

    # -------------------------
    # POST /api/feeds/subscribe
    # -------------------------
    def test_post_subscribe_no_feed(self):
        # No credential, no feed, no object
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=None)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"


    def test_post_subscribe_no_credentials(self):
        self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)

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


    def test_post_subscribe_no_credentials_bad_request(self):
        # No credential, feed exist, SubscribeAdminRequest object that should fail value checks
        sub_req = {
            "email": "email@example.com",
            "filter": "everything",
            "display_text": "everything"
        }
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=None, json=sub_req)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"

        sub_req = {
            "email": "email@example.com",
            "filter": {"instant": "everything"},
            "display_text": {"instant": "everything"}
        }
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=None, json=sub_req)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"


    def test_post_subscribe_non_admin_no_object(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
        user = FEED_ACCOUNT_PREFIX + self.FEED_ONE_HASH
        pwd = init_data.accounts[user]

        # Non admin credential, feed exist, no object
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=HTTPBasicAuth(user, pwd))
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"


    def test_post_subscribe_non_admin_subscribe_request(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
        user = FEED_ACCOUNT_PREFIX + self.FEED_ONE_HASH
        pwd = init_data.accounts[user]

        # Non admin credential, feed exist, SubscribeRequest object
        sub_req = {
            "email": "email@example.com",
            "filter": {"instant": {"region": [1, 2]}},
            "display_text": {"instant": {"region": ["Verbose region 1", "Verbose region 2"]}}
        }
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=HTTPBasicAuth(user, pwd), json=sub_req)
        assert response.status_code == HTTPStatus.OK, f"{response.status_code}: {response.text}"
        # - Check listmonk for attribs feed without filter (but there's one entry in the feed dict) and no token existance
        response = self.admin_session.get(LISTMONK_URL+"/api/subscribers", params={"query": "subscribers.email='email@example.com'"})
        print(response.json()["data"]["results"])
        subscriber = response.json()["data"]["results"][0]
        assert self.FEED_ONE_HASH in subscriber["attribs"]
        feed_attribs = subscriber["attribs"][self.FEED_ONE_HASH]
        # Should only be a single item in here, the key is the guid.
        assert isinstance(feed_attribs, dict)
        assert "filter" not in feed_attribs
        assert "token" not in feed_attribs
        assert 1 == len(feed_attribs.keys())


    def test_post_subscribe_non_admin_subscribe_request_all_category(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
        user = FEED_ACCOUNT_PREFIX + self.FEED_ONE_HASH
        pwd = init_data.accounts[user]

        # Non admin credential, feed exist, SubscribeRequest object
        sub_req = {
            "email": "email@example.com",
            "filter": {"instant": {"region": "all"}},
            "display_text": {"instant": {"region": "Everything"}}
        }
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=HTTPBasicAuth(user, pwd), json=sub_req)
        assert response.status_code == HTTPStatus.OK, f"{response.status_code}: {response.text}"
        # - Check listmonk for attribs feed without filter (but there's one entry in the feed dict) and no token existance
        response = self.admin_session.get(LISTMONK_URL+"/api/subscribers", params={"query": "subscribers.email='email@example.com'"})
        print(response.json()["data"]["results"])
        subscriber = response.json()["data"]["results"][0]
        assert self.FEED_ONE_HASH in subscriber["attribs"]
        feed_attribs = subscriber["attribs"][self.FEED_ONE_HASH]
        # Should only be a single item in here, the key is the guid.
        assert isinstance(feed_attribs, dict)
        assert "filter" not in feed_attribs
        assert "token" not in feed_attribs
        assert 1 == len(feed_attribs.keys())


    def test_post_subscribe_non_admin_subscribe_request_all_filter(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
        user = FEED_ACCOUNT_PREFIX + self.FEED_ONE_HASH
        pwd = init_data.accounts[user]

        # Non admin credential, feed exist, SubscribeRequest object with the 'all' filter
        sub_req = {
            "email": "email@example.com",
            "filter": {"instant": "all"},
            "display_text": {"instant": "Everything"}
        }
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=HTTPBasicAuth(user, pwd), json=sub_req)
        assert response.status_code == HTTPStatus.OK, f"{response.status_code}: {response.text}"
        # - Check listmonk for attribs feed without filter (but there's one entry in the feed dict) and no token existance
        response = self.admin_session.get(LISTMONK_URL+"/api/subscribers", params={"query": "subscribers.email='email@example.com'"})
        print(response.json()["data"]["results"])
        subscriber = response.json()["data"]["results"][0]
        assert self.FEED_ONE_HASH in subscriber["attribs"]
        feed_attribs = subscriber["attribs"][self.FEED_ONE_HASH]
        # Should only be a single item in here, the key is the guid.
        assert isinstance(feed_attribs, dict)
        assert "filter" not in feed_attribs
        assert "token" not in feed_attribs
        assert 1 == len(feed_attribs.keys())


    def test_post_subscribe_non_admin_subscribe_admin_request(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
        user = FEED_ACCOUNT_PREFIX + self.FEED_ONE_HASH
        pwd = init_data.accounts[user]

        # Non admin credential, feed exist, SubscribeAdminRequest object
        sub_req = {
            "email": "email@example.com",
            "feed_url": self.FEED_ONE_FEED_URL,
            "filter": {"instant": {"region": [1, 2]}},
            "display_text": {"instant": {"region": ["Verbose region 1", "Verbose region 2"]}}
        }
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=HTTPBasicAuth(user, pwd),  json=sub_req)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"


    def test_post_subscribe_non_admin_bad_request(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
        user = FEED_ACCOUNT_PREFIX + self.FEED_ONE_HASH
        pwd = init_data.accounts[user]

        # Non admin credential, feed exist, SubscribeAdminRequest object that should fail value checks
        sub_req = {
            "email": "email@example.com",
            "filter": "everything",
            "display_text": "everything"
        }
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=HTTPBasicAuth(user, pwd), json=sub_req)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Input should be a valid dictionary" in response.text

        sub_req = {
            "email": "email@example.com",
            "filter": {"instant": "everything"},
            "display_text": {"instant": "everything"}
        }
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=HTTPBasicAuth(user, pwd), json=sub_req)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Value error, Filter must be a dict or 'all'" in response.text


    def test_post_subscribe_admin_no_object(self):
        self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)

        # Admin credential, feed exist, no object
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=self.ADMIN_AUTH)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Field required" in response.text


    def test_post_subscribe_admin_bad_request(self):
        self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)

        # Non admin credential, feed exist, SubscribeAdminRequest object that should fail value checks
        sub_req = {
            "email": "email@example.com",
            "filter": "everything",
            "display_text": "everything"
        }
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=self.ADMIN_AUTH, json=sub_req)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Input should be a valid dictionary" in response.text

        sub_req = {
            "email": "email@example.com",
            "filter": {"instant": "everything"},
            "display_text": {"instant": "everything"}
        }
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe", auth=self.ADMIN_AUTH, json=sub_req)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"
        assert "Value error, Filter must be a dict or 'all'" in response.text


    def test_post_subscribe_admin_subscribe_request(self):
        self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
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
        assert response.json()["unread"] == 0


    def test_post_subscribe_admin_subscribe_admin_request(self):
        self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
        subscribe_data = {
            "feed_url": self.FEED_ONE_FEED_URL,
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
        time.sleep(1)
        response = requests.get(MAILPIT_URL+"/api/v1/messages?limit=50")
        assert response.json()["unread"] == 1
        
        # - Check listmonk for attribs feed without filter (but there's one entry in the feed dict) and no token existance
        response = self.admin_session.get(LISTMONK_URL+"/api/subscribers", params={"query": "subscribers.email='john@example.com'"})
        subscriber = response.json()["data"]["results"][0]
        assert self.FEED_ONE_HASH in subscriber["attribs"]
        feed_attribs = subscriber["attribs"][self.FEED_ONE_HASH]
        # Should only be a single item in here, the key is the guid.
        assert isinstance(feed_attribs, dict)
        assert "filter" not in feed_attribs
        assert "token" not in feed_attribs
        assert len(feed_attribs.keys()) == 1


    def test_post_subscribe_admin_subscribe_admin_request_bypass(self):
        self.initialise_system(UnitTestLifecyclePhase.FEED_ACCOUNT) # Don't need templates yet
        subscribe_data = {
            "feed_url": self.FEED_ONE_FEED_URL,
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
        assert response.json()["unread"] == 0

        # - Check listmonk for attribs feed with only and token existance
        response = self.admin_session.get(LISTMONK_URL+"/api/subscribers", params={"query": "subscribers.email='john@example.com'"})
        subscriber = response.json()["data"]["results"][0]
        assert self.FEED_ONE_HASH in subscriber["attribs"]
        feed_attribs = subscriber["attribs"][self.FEED_ONE_HASH]
        # Should only be a single item in here, the key is the guid.
        assert isinstance(feed_attribs, dict)
        assert "filter" in feed_attribs
        assert "token" in feed_attribs
        assert "subscribe_query" in feed_attribs
        assert "unsubscribe_query" in feed_attribs
        assert len(feed_attribs.keys()) == 4, feed_attribs


    def test_post_subscribe_admin_subscribe_admin_request_with_bypass(self):
        self.initialise_system(UnitTestLifecyclePhase.FEED_TEMPLATES)
        subscribe_data = {
            "feed_url": self.FEED_ONE_FEED_URL,
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
        assert response.json()["unread"] == 0

        # - Check listmonk for attribs feed with only and token existance
        response = self.admin_session.get(LISTMONK_URL+"/api/subscribers", params={"query": "subscribers.email='john@example.com'"})
        subscriber = response.json()["data"]["results"][0]
        assert self.FEED_ONE_HASH in subscriber["attribs"]
        feed_attribs = subscriber["attribs"][self.FEED_ONE_HASH]
        # Should only be a single item in here, the key is the guid.
        assert isinstance(feed_attribs, dict)
        assert "filter" in feed_attribs
        assert "token" in feed_attribs
        assert "subscribe_query" in feed_attribs
        assert "unsubscribe_query" in feed_attribs
        assert len(feed_attribs.keys()) == 4, feed_attribs


    # -------------------------
    # POST /api/feeds/subscribe-confirm
    # -------------------------
    def test_post_subscribe_confirm_no_credentials(self):
        self.initialise_system(UnitTestLifecyclePhase.FEED_SUBSCRIBED)
        # No credentials, no object
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe-confirm", auth=None, json=None)
        assert response.status_code == HTTPStatus.UNAUTHORIZED, f"{response.status_code}: {response.text}"


    def test_post_subscribe_confirm_non_admin_credentials(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_SUBSCRIBED)
        user = FEED_ACCOUNT_PREFIX + self.FEED_ONE_HASH
        pwd = init_data.accounts[user]

        # Non admin, no object
        confirm_req = {}
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe-confirm", auth=HTTPBasicAuth(user, pwd), json=confirm_req)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"

        # Non admin, SubscribeConfirmRequest object, empty values
        confirm_req = {"subscriber_id": "", "guid": ""}
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe-confirm", auth=HTTPBasicAuth(user, pwd), json=confirm_req)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"

        # Non admin, SubscribeConfirmRequest object, invalid values
        confirm_req = {"subscriber_id": "", "guid": ""}
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe-confirm", auth=HTTPBasicAuth(user, pwd), json=confirm_req)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"


    def test_post_subscribe_confirm_non_admin_credentials_success(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_SUBSCRIBED)
        user = FEED_ACCOUNT_PREFIX + self.FEED_ONE_HASH
        pwd = init_data.accounts[user]

        # Non admin, SubscribeConfirmRequest object, valid values
        confirm_req = {"subscriber_id": "", "guid": ""}
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe-confirm", auth=HTTPBasicAuth(user, pwd), json=confirm_req)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"


    def test_post_subscribe_confirm_admin_credentials(self):
        init_data = self.initialise_system(UnitTestLifecyclePhase.FEED_SUBSCRIBED)

        # Admin, no object. Data models are checked first
        confirm_req = {}
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe-confirm", auth=self.ADMIN_AUTH, json=confirm_req)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"

        # Admin, SubscribeConfirmRequest object, empty values. Data models are checked first
        confirm_req = {"subscriber_id": "", "guid": ""}
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe-confirm", auth=self.ADMIN_AUTH, json=confirm_req)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT, f"{response.status_code}: {response.text}"

        sub_tokens = init_data.subscribers[self.one_feed_subscriber_uuid]
        # Admin, SubscribeConfirmRequest object, valid values - Rejected because admin should go to /api/feeds/subscribe
        confirm_req = {"subscriber_id": self.one_feed_subscriber_uuid, "guid": sub_tokens[self.FEED_ONE_HASH]}
        response = requests.post(RSSMONK_URL+"/api/feeds/subscribe-confirm", auth=self.ADMIN_AUTH, json=confirm_req)
        assert response.status_code == HTTPStatus.FORBIDDEN, f"{response.status_code}: {response.text}"
