"""Test Pydantic models."""

import pytest
from pydantic import ValidationError

from rssmonk.models import FeedCreateRequest, FeedProcessRequest, PublicSubscribeRequest
from rssmonk.core import Frequency


def test_feed_create_request_valid():
    """Test valid feed creation request."""
    request = FeedCreateRequest(
        url="https://example.com/feed.rss",
        frequency=Frequency.DAILY,
        name="Test Feed"
    )
    assert str(request.url) == "https://example.com/feed.rss"
    assert request.frequency == Frequency.DAILY
    assert request.name == "Test Feed"


def test_feed_create_request_invalid_url():
    """Test invalid URL validation."""
    with pytest.raises(ValidationError):
        FeedCreateRequest(
            url="not-a-valid-url",
            frequency=Frequency.DAILY
        )


def test_feed_process_request():
    """Test feed processing request."""
    request = FeedProcessRequest(
        url="https://example.com/feed.rss",
        auto_send=True
    )
    assert str(request.url) == "https://example.com/feed.rss"
    assert request.auto_send is True


def test_public_subscribe_request():
    """Test public subscription request."""
    request = PublicSubscribeRequest(
        email="test@example.com",
        feed_url="https://example.com/feed.rss"
    )
    assert request.email == "test@example.com"
    assert str(request.feed_url) == "https://example.com/feed.rss"
