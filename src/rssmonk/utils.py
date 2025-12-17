import hashlib
from typing import Optional, Tuple

from rssmonk.types import FEED_ACCOUNT_PREFIX, ROLE_PREFIX, EmailPhaseType


def numberfy_subbed_lists(subs : list[dict]):
    subbed_lists : list[int] = []
    for sub_list in subs:
        if "id" in sub_list:
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
    return username.replace(FEED_ACCOUNT_PREFIX, "").strip() if username.startswith(FEED_ACCOUNT_PREFIX) else None

def make_list_role_name_by_url(url: str) -> str:
    return ROLE_PREFIX + make_url_hash(url)

def make_list_role_name(hash: str) -> str:
    return ROLE_PREFIX + hash

def make_template_name(feed_hash: str, email_type: EmailPhaseType) -> str:
    return f"{feed_hash}-{email_type.value}"

def make_filter_url(data: list | dict[str, list[int]]) -> str:
    """Creates a flat URL query string from a list or dictionary of filters."""
    if isinstance(data, list):
        # A flat list not part of a dict needs a default keyword
        return f"filter={",".join(str(x) for x in data)}" if len(data) > 0 else ""
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
    if value is not None:
        return value
    return make_url_hash(feed_url) if feed_url else ""

def expand_filter_identifiers(filter_freq_data: dict) -> Tuple[list[str], list[str]]:
    expanded_topics: list[str] = []
    topic_categories_list: list[str] = []
    for key, item in filter_freq_data.items():
        if isinstance(item, str) and item == "all":
            topic_categories_list.append(key)
        elif isinstance(item, list):
            expanded_topics.extend([f"{key} {point}" for point in item])
    return topic_categories_list, expanded_topics


def matches_filter(categories_list: list[str], individual_topics_list: list[str], article_identifiers: list[str]) -> bool:
    # Check if any category is present in article identifiers
    category_match = any(
        any(article.startswith(category) for article in article_identifiers)
        for category in categories_list
    )

    # Check if any individual topic matches exactly
    individual_match = bool(set(individual_topics_list) & set(article_identifiers))
    return category_match or individual_match
