from enum import Enum
import hashlib
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

def map_id_to_name(mapping: dict, ident: int) -> str:
    return mapping[ident] if ident in mapping else f"Unknown ({ident})"

def make_filter_url(data: Any) -> str:
    """Creates a flat url """
    return ""

def create_email_filter_list(data: Any, mapping: dict[int, str] = None) -> Tuple[list[str], dict]:
    """
    Converts a filter into a flatter structure into a pre determined list of strings (to preserve order)
    Only allow one layer of dictionary and convert to a flat string

    Can accept numbers in the data which will need to be mapped to a string with the help of the map.
    TODO
    """
    # This can be unbounded. Ensure API access is from trusted modules
    data_type = type(data)
    return_list = []
    return_dict = {} # This will be filled if there is a mapping system
    if data_type == list:
        for item in data:
            if isinstance(item, int):
                # Numbered filter requires a 
                category, mapped_name = map_id_to_name(mapping, item)
                if category not in return_dict:
                    return_dict[category] = []

                return_dict[category].append(mapped_name)
                return_list.append(mapped_name)
            else:
                # Assume str, but also, assume no translation possible, numbers for translation only
                return_list.append(str(item))
    elif data_type == dict:
        for key, value in dict(data).items():
            if type(value) == dict:
                raise ValueError("Only one sublevel of dictionary is permitted")
            elif type(value) != list:
                raise ValueError("Sublevel data type for %s must be an array", str(key))

            if str(key) not in return_dict:
                return_dict[str(key)] = []
            # Value here is a known list, attempt to map in case it is list[int]
            temp_list, _ = create_email_filter_list(value, mapping)
            return_dict[str(key)].append(temp_list)
    else:
        raise ValueError("Data type must be either be an array or object")
    return return_list, return_dict


# Should be called after validation of feed visibility
def extract_feed_hash(username: str, feed_url: Optional[str] = None) -> str:
    value = get_feed_hash_from_username(username)
    if value is None:
        value = make_url_hash(feed_url) if feed_url is not None else ""
    return value