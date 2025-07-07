"""Tests for feed processor module."""

from datetime import datetime, timezone, timedelta
from unittest.mock import Mock

from rssmonk.feed_processor import FeedProcessor, CampaignCreator
from rssmonk.utils import extract_feed_url, get_frequency_from_tags

def test_extract_feed_url():
    """Test feed URL extraction."""
    # RSS Feed format
    assert extract_feed_url("RSS Feed: http://example.com/feed.xml") == "http://example.com/feed.xml"
    
    # URL on separate line
    description = "Some description\nhttp://example.com/feed.xml\nMore text"
    assert extract_feed_url(description) == "http://example.com/feed.xml"
    
    # No URL found
    assert extract_feed_url("No URL here") is None

def test_get_frequency_from_tags():
    """Test frequency extraction from tags."""
    assert get_frequency_from_tags(['freq:5min', 'other']) == 'freq:5min'
    assert get_frequency_from_tags(['freq:daily']) == 'freq:daily'
    assert get_frequency_from_tags(['freq:weekly']) == 'freq:weekly'
    assert get_frequency_from_tags(['other', 'tags']) is None

def test_campaign_creator_content():
    """Test campaign content creation."""
    article = {
        'title': 'Test Article',
        'link': 'http://example.com/article',
        'description': 'Test description',
        'published': '2023-01-01',
        'author': 'Test Author'
    }
    
    content = CampaignCreator.create_content(article, 'Test Feed')
    
    assert 'Test Article' in content
    assert 'http://example.com/article' in content
    assert 'Test description' in content
    assert 'Test Feed' in content

def test_campaign_creator_data():
    """Test campaign data creation."""
    article = {
        'title': 'Test Article',
        'link': 'http://example.com/article',
        'description': 'Test description'
    }
    
    feed_list = {'id': 123, 'name': 'Test Feed'}
    
    data = CampaignCreator.create_campaign_data(article, feed_list, 'freq:daily')
    
    assert data['subject'] == 'Test Article'
    assert data['lists'] == [123]
    assert 'daily' in data['tags']

def test_feed_processor_should_poll():
    """Test feed polling logic with Listmonk tags."""
    mock_client = Mock()
    processor = FeedProcessor(mock_client)
    
    now = datetime.now(timezone.utc)
    
    # Test 5min frequency - no last poll tag
    feed_list = {
        'id': 123,
        'name': 'Test Feed',
        'tags': ['freq:5min']
    }
    assert processor.should_poll_feed(feed_list, 'freq:5min', now) is True
    
    # Test 5min frequency - last poll 10 minutes ago
    last_poll = (now - timedelta(minutes=10)).isoformat()
    feed_list['tags'] = ['freq:5min', f'last-poll:freq:5min:{last_poll}']
    assert processor.should_poll_feed(feed_list, 'freq:5min', now) is True
    
    # Test 5min frequency - last poll 2 minutes ago (should NOT poll)
    last_poll = (now - timedelta(minutes=2)).isoformat()
    feed_list['tags'] = ['freq:5min', f'last-poll:freq:5min:{last_poll}']
    assert processor.should_poll_feed(feed_list, 'freq:5min', now) is False

def test_feed_processor_find_new_articles():
    """Test finding new articles from Listmonk tags."""
    mock_client = Mock()
    processor = FeedProcessor(mock_client)
    
    articles = [
        {'guid': 'article1', 'title': 'Article 1'},
        {'guid': 'article2', 'title': 'Article 2'},
        {'guid': 'article3', 'title': 'Article 3'}
    ]
    
    # No last GUID tag - all articles are new
    feed_list = {
        'id': 123,
        'name': 'Test Feed',
        'tags': ['freq:daily']
    }
    new_articles = processor.find_new_articles(articles, feed_list, 'freq:daily')
    assert len(new_articles) == 3
    
    # Last GUID is article2 - only article1 is new (newest article)
    feed_list['tags'] = ['freq:daily', 'last-seen:freq:daily:article2']
    new_articles = processor.find_new_articles(articles, feed_list, 'freq:daily')
    assert len(new_articles) == 1
    assert new_articles[0]['guid'] == 'article1'

def test_feed_processor_update_tags():
    """Test tag update after processing."""
    mock_client = Mock()
    processor = FeedProcessor(mock_client)
    
    articles = [
        {'guid': 'article1', 'title': 'Article 1'},
        {'guid': 'article2', 'title': 'Article 2'}
    ]
    
    feed_list = {
        'id': 123,
        'name': 'Test Feed',
        'description': 'RSS Feed: http://example.com/feed.xml',
        'tags': ['freq:daily', 'old-tag'],
        'type': 'public'
    }
    
    now = datetime.now(timezone.utc)
    
    processor.update_tags(feed_list, 'freq:daily', articles, now)
    
    # Check that the client.put was called with updated tags
    mock_client.put.assert_called_once()
    call_args = mock_client.put.call_args
    
    assert call_args[0][0] == "/api/lists/123"
    update_data = call_args[0][1]
    
    # Should have original non-state tags plus new state tags
    tags = update_data['tags']
    assert 'freq:daily' in tags
    assert 'old-tag' in tags
    assert any(tag.startswith('last-poll:freq:daily:') for tag in tags)
    assert any(tag.startswith('last-seen:freq:daily:') for tag in tags)
    assert 'last-seen:freq:daily:article2' in tags
