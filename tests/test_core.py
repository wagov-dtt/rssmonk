"""Simple tests for RSS Monk core functionality."""

import pytest
from unittest.mock import Mock, patch
from rssmonk.core import RSSMonk, Settings, Feed, Frequency


@pytest.fixture
def mock_settings(monkeypatch):
    """Mock settings for testing."""
    monkeypatch.setenv("LISTMONK_APITOKEN", "test123")
    settings = Settings()
    return settings


def test_settings_validation(monkeypatch):
    """Test settings validation."""
    # Test validation method with missing token
    monkeypatch.setenv("LISTMONK_APITOKEN", "test123")
    settings = Settings()
    settings.listmonk_password = ""  # Clear the password

    # Should raise error without password
    with pytest.raises(ValueError, match="LISTMONK_APITOKEN"):
        settings.validate_required()

    # Should pass with password
    settings.listmonk_password = "test123"
    settings.validate_required()  # Should not raise


def test_feed_creation():
    """Test creating a feed model."""
    feed = Feed(name="Test Feed", url="https://example.com/feed.xml", frequency=Frequency.DAILY)

    assert feed.name == "Test Feed"
    assert feed.url == "https://example.com/feed.xml"
    assert feed.frequency == Frequency.DAILY
    assert feed.base_url == "https://example.com/feed.xml"
    assert len(feed.url_hash) == 64  # SHA-256 hash


def test_frequency_enum():
    """Test frequency enum values."""
    assert Frequency.FIVE_MIN == "5min"
    assert Frequency.DAILY == "daily"
    assert Frequency.WEEKLY == "weekly"


@patch("rssmonk.core.ListmonkClient")
def test_rssmonk_context_manager(mock_client_class, mock_settings):
    """Test RSSMonk context manager."""
    mock_client = Mock()
    mock_client.__exit__ = Mock()  # Add __exit__ method
    mock_client_class.return_value.__enter__.return_value = mock_client

    with RSSMonk(mock_settings) as rss:
        assert rss._client == mock_client

    # Client should be created with proper parameters
    mock_client_class.assert_called_once_with(
        base_url=mock_settings.listmonk_url,
        username=mock_settings.listmonk_username,
        password=mock_settings.listmonk_password,
        timeout=mock_settings.rss_timeout,
    )


def test_settings_with_environment_variables(monkeypatch):
    """Test settings loading from environment variables."""
    monkeypatch.setenv("LISTMONK_APITOKEN", "test-token")
    monkeypatch.setenv("LISTMONK_URL", "http://test:9000")
    monkeypatch.setenv("RSS_AUTO_SEND", "true")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    settings = Settings()

    assert settings.listmonk_password == "test-token"
    assert settings.listmonk_url == "http://test:9000"
    assert settings.rss_auto_send is True
    assert settings.log_level == "DEBUG"


def test_settings_defaults(monkeypatch):
    """Test default settings values."""
    monkeypatch.setenv("LISTMONK_APITOKEN", "test123")
    settings = Settings()

    assert settings.listmonk_url == "http://localhost:9000"
    assert settings.listmonk_username == "api"
    assert settings.rss_auto_send is False
    assert settings.rss_timeout == 30.0
    assert settings.log_level == "INFO"
    assert "RSS Monk/2.0" in settings.rss_user_agent
