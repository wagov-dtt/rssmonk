"""Test Pydantic models."""

import pytest
from pydantic import ValidationError

from rssmonk.models import FeedCreateRequest
from rssmonk.core import Frequency
from rssmonk.types import ListVisibilityType


def test_valid_feed_create_request():
    data = {
        "feed_url": "https://example.com/rss",
        "email_base_url": "https://example.com/email",
        "poll_frequencies": [Frequency.DAILY],
        "filter_groups": ["tech", "news"],
        "name": "My Feed",
        "visibility": ListVisibilityType.PRIVATE
    }
    model = FeedCreateRequest(**data)
    assert model.feed_url.encoded_string() == "https://example.com/rss"
    assert model.visibility == ListVisibilityType.PRIVATE
    assert model.filter_groups == ["tech", "news"]


def test_missing_required_fields():
    data = {
        "email_base_url": "https://example.com/email",
        "poll_frequencies": [Frequency.DAILY]
    }
    with pytest.raises(ValidationError):
        FeedCreateRequest(**data)


def test_optional_fields_default():
    data = {
        "feed_url": "https://example.com/rss",
        "email_base_url": "https://example.com/email",
        "poll_frequencies": [Frequency.DAILY]
    }
    model = FeedCreateRequest(**data)
    assert model.name is None
    assert model.visibility == ListVisibilityType.PRIVATE
    assert model.filter_groups is None


def test_invalid_url():
    data = {
        "feed_url": "not-a-url",
        "email_base_url": "https://example.com/email",
        "poll_frequencies": [Frequency.DAILY]
    }
    with pytest.raises(ValidationError):
        FeedCreateRequest(**data)


def test_empty_poll_frequencies():
    data = {
        "feed_url": "https://example.com/rss",
        "email_base_url": "https://example.com/email",
        "poll_frequencies": []
    }
    with pytest.raises(ValidationError):
        FeedCreateRequest(**data)
