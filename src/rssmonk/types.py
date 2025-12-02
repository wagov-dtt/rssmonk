import os
from enum import StrEnum
from typing import Any


# RSS Feed types

FrequencyFilterType = list[int] | dict[str, list[int]]
DisplayTextFilterType = list[str] | dict[str, list[str]]

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
        # This option should be rarely used, but is available
        "freq:weekly": {
            "interval_minutes": None,
            "check_time": (17, 0),  # 5pm
            "check_day": 4,  # Friday
            "description": "Weekly on Friday at 5pm",
        },
    }

class ListVisibilityType(StrEnum):
    """List visibility type."""
    PUBLIC = "public"
    PRIVATE = "private"

class Frequency(StrEnum):
    """Polling frequencies."""
    INSTANT = "instant"
    DAILY = "daily"
    WEEKLY = "weekly"


# Account prefixes

FEED_ACCOUNT_PREFIX = "user_"
ROLE_PREFIX = "list_role_"

# Feed description modifiers
LIST_DESC_FEED_URL = "RSS Feed:"
SUB_BASE_URL = "Subscription URL:"

# Enables different filters per frequency. Default to false to only have one frequency type in the filter
MULTIPLE_FREQ = "Multiple freq:" # TODO - Currently not in use

# This is to ask the feed to give details specific to email processing
FEED_URL_RSSMONK_QUERY = "?rssmonk=true" # TODO - Refine?

ALL_FILTER = "all"
"""The keyword for every option in a filter"""
NO_REPLY = os.environ.get("NO_REPLY_EMAIL", "noreply@noreply (No reply location)")
 
class EmailPhaseType(StrEnum):
    """
    Email template types that may or may be used for emails.
    Mandatory emails
    - subscribe, 
    - instant_digest, daily_digest, weekly_digest as required by the feed
    """
    SUBSCRIBE = "subscribe"
    SUBSCRIBE_CONFIRM = "sub_confirm"

    EDIT_PREFERENCES = "edit_preferences"

    UNSUBSCRIBE = "unsubscribe"
    UNSUBSCRIBE_CONFIRM = "unsub_confirm"

    INSTANT_DIGEST = "instant_digest"
    DAILY_DIGEST = "daily_digest"
    WEEKLY_DIGEST = "weekly_digest"

class ActionsURLSuffix(StrEnum):
    """Standardised URL patterns to append to base urls to perform actions"""
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    EDIT_PREFERENCES = "preferences" # This should be used sparingly

class ErrorMessages:
    NO_AUTH_FEED = "Not authorised to interact with this feed"