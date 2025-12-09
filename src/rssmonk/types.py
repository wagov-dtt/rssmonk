from datetime import datetime
import os
from enum import StrEnum
from typing import Any


# RSS Feed types

class ListVisibilityType(StrEnum):
    """List visibility type."""
    PUBLIC = "public"
    PRIVATE = "private"

class Frequency(StrEnum):
    """Polling frequencies."""
    INSTANT = "instant"
    DAILY = "daily"
    #WEEKLY = "weekly"

FrequencyFilterType = str | list[int] | dict[str, str | list[int]]
"""
Covers the following scenarios
- "all" topics
- A list of topics to be selected that have no category
- A dictionary of categories with either
  - A list of topics
  - "all" topics of a category
"""
DisplayTextFilterType = str | list[str] | dict[str, str | list[str]]

# Feed frequency configurations
def AVAILABLE_FREQUENCY_SETTINGS() -> dict[str, dict[str, Any]]:
    return {
        "freq:instant": {
            "interval_minutes": 5,
            "check_time": None,
            "check_day": None,
            "description": "Every 5 minutes",
        },
        "freq:daily": {
            "interval_minutes": None,
            "check_time": (17, 0),  # 5pm
            "check_day": None,
            "description": "Daily at 5pm",
        },
        # This option can be added on as a special case of daily (Collect 7 daily items and mail on the Friday)
        #"freq:weekly": {
        #    "interval_minutes": None,
        #    "check_time": (17, 0),  # 5pm
        #    "check_day": 4,  # Friday
        #    "description": "Weekly on Friday at 5pm",
        #},
    }


# Account prefixes

FEED_ACCOUNT_PREFIX = "user_"
ROLE_PREFIX = "list_role_"

# Feed description modifiers
LIST_DESC_FEED_URL = "RSS Feed:"
SUB_BASE_URL = "Subscription URL:"
TOPICS_TITLE = "Topics:"

# Enables different filters per frequency. Default to false to only have one frequency type in the filter
MULTIPLE_FREQ = "Multiple freq:" # TODO - Currently not in use

# This is to ask the feed to give details specific to email processing
FEED_URL_RSSMONK_QUERY = "?rssmonk=true" # TODO - Refine?

ALL_FILTER = "all"
"""This keyword is the expected flag to either be all filter types, or all for a category/topic"""

NO_REPLY = os.environ.get("NO_REPLY_EMAIL", "noreply@noreply (No reply location)")
"""The keyword for every option in a filter"""
 
class EmailPhaseType(StrEnum):
    """
    Email template types that may or may be used for emails.
    Mandatory emails
    - subscribe, 
    - instant_digest, daily_digest as required by the feed
    """
    SUBSCRIBE = "subscribe"
    SUBSCRIBE_CONFIRM = "sub_confirm"

    EDIT_PREFERENCES = "edit_preferences"

    UNSUBSCRIBE = "unsubscribe"
    UNSUBSCRIBE_CONFIRM = "unsub_confirm"

    INSTANT_DIGEST = "instant_digest"
    DAILY_DIGEST = "daily_digest"
    #WEEKLY_DIGEST = "weekly_digest"

class ActionsURLSuffix(StrEnum):
    """Standardised URL patterns to append to base urls to perform actions"""
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    EDIT_PREFERENCES = "preferences" # This should be used sparingly

class ErrorMessages:
    NO_AUTH_FEED = "Not authorised to interact with this feed"

class FeedItem:
    """This stores one item from a parsed feed"""
    title: str
    link: str
    description: str
    published: datetime
    guid: str
    email_subject_line: str
    """From wa:subject_line"""
    filter_identifiers: str
    """From wa:identifiers"""