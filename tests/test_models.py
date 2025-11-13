"""Test Pydantic models."""

import pytest
from pydantic import ValidationError

from rssmonk.models import FeedCreateRequest, FeedProcessRequest, PublicSubscribeRequest
from rssmonk.core import Frequency


def test_feed_create_request_valid():
    """Test valid feed creation request."""
    request = FeedCreateRequest(
        feed_url="https://example.com/feed.rss",
        email_base_url="https://example.com/subscribe",
        poll_frequencies=[Frequency.DAILY.value],
        name="Test Feed"
    )
    assert str(request.feed_url) == "https://example.com/feed.rss"
    assert request.poll_frequencies == [Frequency.DAILY.value]
    assert request.name == "Test Feed"


def test_feed_create_request_invalid_url():
    """Test invalid URL validation."""
    with pytest.raises(ValidationError):
        FeedCreateRequest(
            feed_url="not-a-valid-url",
            poll_frequencies=[Frequency.DAILY.value]
        )


def test_feed_process_request():
    """Test feed processing request."""
    request = FeedProcessRequest(
        feed_url="https://example.com/feed.rss",
        auto_send=True
    )
    assert str(request.feed_url) == "https://example.com/feed.rss"
    assert request.auto_send is True

