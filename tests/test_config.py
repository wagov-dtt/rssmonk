"""Tests for configuration module."""

import os
import pytest
from unittest.mock import patch

from rssmonk.config import Config, FREQUENCIES

def test_frequencies_defined():
    """Test that all required frequencies are defined."""
    assert 'freq:5min' in FREQUENCIES
    assert 'freq:daily' in FREQUENCIES
    assert 'freq:weekly' in FREQUENCIES

def test_config_defaults():
    """Test configuration defaults."""
    with patch.dict(os.environ, {}, clear=True):
        config = Config()
        assert config.listmonk_url == 'http://localhost:9000'
        assert config.listmonk_username == 'api'
        assert config.max_workers == 10
        assert config.auto_send is False

def test_config_from_env():
    """Test configuration from environment variables."""
    test_env = {
        'LISTMONK_URL': 'http://test:9000',
        'LISTMONK_APIUSER': 'testuser',
        'LISTMONK_APITOKEN': 'testpass',
        'MAX_WORKERS': '5',
        'RSS_AUTO_SEND': 'true'
    }
    
    with patch.dict(os.environ, test_env, clear=True):
        config = Config()
        assert config.listmonk_url == 'http://test:9000'
        assert config.listmonk_username == 'testuser'
        assert config.listmonk_password == 'testpass'
        assert config.max_workers == 5
        assert config.auto_send is True

def test_config_validation():
    """Test configuration validation."""
    with patch.dict(os.environ, {}, clear=True):
        config = Config()
        with pytest.raises(ValueError, match="LISTMONK_APITOKEN"):
            config.validate()

def test_config_validation_success():
    """Test successful configuration validation."""
    with patch.dict(os.environ, {'LISTMONK_APITOKEN': 'test'}, clear=True):
        config = Config()
        config.validate()  # Should not raise
