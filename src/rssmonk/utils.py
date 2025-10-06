from enum import Enum
import hashlib

from pydantic import BaseModel

FEED_ACCOUNT_PREFIX = "user_"
ROLE_PREFIX = "list_role_"
LIST_DESC_FEED_URL = "RSS Feed:"
SUB_BASE_URL = "Subscription URL: "

class EmailType(str, Enum):
    """Email template types."""
    SUBSCRIBE = "subscribe"
    SUBSCRIBE_CONFIRM = "sub_confirm"

    EDIT_PREFERENCES = "edit_preferences"

    UNSUBSCRIBE = "unsubscribe"
    UNSUBSCRIBE_CONFIRM = "unsub_confirm"

    INSTANT_DIGEST = "instant_digest"
    DAILY_DIGEST = "daily_digest"
    WEEKLY_DIGEST = "weekly_digest"

class ErrorMessages:
    NO_AUTH_FEED = "Not authorised to interact with this feed"

# Removes everything except for the one key in the dict, empty if the key is not present in the dict
def remove_other_keys(attr: dict, key: str) -> dict:
    if key in attr:
        return {key: attr[key]}
    return {}

def numberfy_subbed_lists(subs : list[dict]):
    subbed_lists : list[int] = []
    for sub_list in subs:
        subbed_lists.append(sub_list["id"])
    return subbed_lists

def make_url_tag(url: str) -> str:
    return f"url:{make_url_hash(url)}"

def make_url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()

def make_api_username(feed_url :str) -> str:
    return FEED_ACCOUNT_PREFIX + make_url_hash(feed_url)

def get_feed_hash_from_username(username :str) -> str:
    return username.replace(FEED_ACCOUNT_PREFIX, "").strip()

def make_feed_role_name(url: str) -> str:
    return ROLE_PREFIX + make_url_hash(url)

def make_template_name(feed_url: str, type: EmailType) -> str:
    return f"{make_url_hash(feed_url)}-{type.value}"