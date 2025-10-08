from enum import Enum
import hashlib
from typing import Any

from pydantic import BaseModel

FEED_ACCOUNT_PREFIX = "user_"
ROLE_PREFIX = "list_role_"
LIST_DESC_FEED_URL = "RSS Feed:"
SUB_BASE_URL = "Subscription URL:"
 
# Enables different filters per frequency. Default to false to only have one frequency type in the filter
MULTIPLE_FREQ = "Multiple freq:" # TODO - Currently not in use

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

class NOTIFICATIONS_SUBPAGE_SUFFIX(str, Enum):
    """Standardised URL patterns to append to base urls to perform actions"""
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    EDIT_PREFERENCES = "preferences" # This should be used sparingly

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

def email_filter_capitalise(data: Any, top_level: bool = False) -> Any:
    """
    Converts a filter into a flatter structure into a pre determined list of strings (to preserve order)
    Only allow one layer of dictionary and convert to a flat string
    TODO
    """
    # This can be unbound. Mitigated with API access only from known modules
    data_type = type(data)
    if data_type == str:
        return str(data).capitalize()
    elif data_type == list:
        
        return ", ".join(list(data))
    elif data_type == dict:
        new_dict = []
        for key, value in dict(data).items():
            new_dict[email_filter_capitalise(key)] = email_filter_capitalise(value)
        return new_dict
    elif data_type == set:
        new_set = set()
        for item in set(data):
            new_set.add(item)
        return new_set
    else:
        return data
