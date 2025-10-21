from enum import Enum
import hashlib
import traceback
from typing import Any, Optional, Tuple


# TODO - This... should be changed at somepoint to an env var
NO_REPLY = "noreply@noreply (No reply location)"


FEED_ACCOUNT_PREFIX = "user_"
ROLE_PREFIX = "list_role_"
LIST_DESC_FEED_URL = "RSS Feed:"
SUB_BASE_URL = "Subscription URL:"
ALL_FILTER = "All"
"""The keyword for every option in a filter"""
 
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

class NotificationsSubpageSuffix(str, Enum):
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

def make_url_tag_from_url(url: str) -> str:
    return make_url_tag_from_hash(make_url_hash(url))

def make_url_tag_from_hash(hash_str: str) -> str:
    return f"url:{hash_str}"

def make_url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()

def make_api_username(feed_url :str) -> str:
    return FEED_ACCOUNT_PREFIX + make_url_hash(feed_url)

def get_feed_hash_from_username(username :str) -> Optional[str]:
    return username.replace(FEED_ACCOUNT_PREFIX, "").strip() if FEED_ACCOUNT_PREFIX in username else None

def make_feed_role_name(url: str) -> str:
    return ROLE_PREFIX + make_url_hash(url)

def make_template_name(feed_hash: str, email_type: EmailType) -> str:
    return f"{feed_hash}-{email_type.value}"

def make_filter_url(data: list[str] | dict[str, list[int]]) -> str:
    """Creates a flat URL query string from a list or dictionary of filters."""
    if isinstance(data, list):
        # A flat list not part of a dict needs a default keyword
        return f"filter={",".join(str(x) for x in value)}"
    elif isinstance(data, dict):
        value_list = []
        for key, value in data.items():
            if isinstance(value, list):
                # Make string list from variable list
                value_list.append(f"{key}={",".join(str(x) for x in value)}")
        return "&".join(value_list)

    return ""

def extract_feed_hash(username: str, feed_url: Optional[str] = None) -> str:
    """
    Returns a feed hash based on the username. If no hash is found,
    it falls back to generating one from the feed URL.

    Should be called after validation of feed visibility.
    """
    value = get_feed_hash_from_username(username)
    if value is None:
        value = make_url_hash(feed_url) if feed_url is not None else ""
    return value
