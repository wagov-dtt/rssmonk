#!/usr/bin/env python3
"""
RSS Feed Fetcher Script
Fetches RSS feeds stored as Listmonk lists and creates campaigns for new items.

RSS feeds are stored as Listmonk lists with simple frequency tags:
- freq:5min - Poll every 5 minutes
- freq:daily - Poll daily at 5pm
- freq:weekly - Poll weekly on Friday at 5pm

Uses hishel + feedparser for efficient HTTP caching.

# /// script
# dependencies = [
#     "requests",
#     "feedparser",
#     "python-dateutil",
#     "pydantic",
#     "hishel",
# ]
# ///
"""

import os
import sys
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import feedparser
import hishel
from dateutil.parser import parse as parse_date

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Frequency configurations
FREQUENCIES = {
    'freq:5min': {
        'interval_minutes': 5,
        'check_time': None,  # No specific time check
        'check_day': None    # No specific day check
    },
    'freq:daily': {
        'interval_minutes': None,
        'check_time': (17, 0),  # 5pm
        'check_day': None
    },
    'freq:weekly': {
        'interval_minutes': None,
        'check_time': (17, 0),  # 5pm
        'check_day': 4          # Friday (0=Monday)
    }
}

class ListmonkClient:
    """Client for Listmonk API operations."""
    
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.auth = (username, password)
        
    def get_lists(self) -> List[Dict]:
        """Get all mailing lists."""
        try:
            response = self.session.get(f"{self.base_url}/api/lists")
            response.raise_for_status()
            return response.json()['data']['results']
        except Exception as e:
            logger.error(f"Error fetching lists: {e}")
            return []
    
    def update_list_tags(self, list_id: int, tags: List[str]) -> bool:
        """Update tags for a mailing list."""
        try:
            response = self.session.get(f"{self.base_url}/api/lists/{list_id}")
            response.raise_for_status()
            list_data = response.json()['data']
            
            list_data['tags'] = tags
            
            response = self.session.put(f"{self.base_url}/api/lists/{list_id}", json=list_data)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Error updating list tags: {e}")
            return False
    
    def create_campaign(self, title: str, subject: str, body: str, list_ids: List[int], tags: List[str]) -> bool:
        """Create a campaign."""
        try:
            campaign_data = {
                'name': title,
                'subject': subject,
                'lists': list_ids,
                'type': 'regular',
                'content_type': 'html',
                'body': body,
                'tags': tags
            }
            
            response = self.session.post(f"{self.base_url}/api/campaigns", json=campaign_data)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Error creating campaign: {e}")
            return False

def should_poll_feed(tags: List[str], now: datetime) -> Tuple[bool, Optional[str]]:
    """Check if feed should be polled based on frequency tags."""
    freq_tag = None
    
    # Find frequency tag
    for tag in tags:
        if tag in FREQUENCIES:
            freq_tag = tag
            break
    
    if not freq_tag:
        return False, None
    
    config = FREQUENCIES[freq_tag]
    
    # Find last poll time for this frequency
    last_poll = None
    for tag in tags:
        if tag.startswith(f'last-poll:{freq_tag}:'):
            try:
                last_poll_str = tag.split(':', 2)[2]
                last_poll = parse_date(last_poll_str)
                break
            except:
                pass
    
    # Check based on frequency type
    if config['interval_minutes']:
        # Interval-based (5min)
        if not last_poll:
            return True, freq_tag
        return now - last_poll > timedelta(minutes=config['interval_minutes']), freq_tag
    
    elif config['check_time']:
        # Time-based (daily/weekly)
        target_hour, target_minute = config['check_time']
        
        # Check day if specified (weekly)
        if config['check_day'] is not None:
            if now.weekday() != config['check_day']:
                return False, freq_tag
            
            # For weekly, check if we haven't polled since last week
            if last_poll:
                last_week = now - timedelta(weeks=1)
                if last_poll > last_week:
                    return False, freq_tag
        else:
            # For daily, check if we haven't polled since yesterday
            if last_poll:
                yesterday = now - timedelta(days=1)
                if last_poll > yesterday:
                    return False, freq_tag
        
        # Check if it's past the target time
        today = now.date()
        target_datetime = datetime.combine(today, datetime.min.time().replace(hour=target_hour, minute=target_minute))
        target_datetime = target_datetime.replace(tzinfo=now.tzinfo)
        
        return now >= target_datetime, freq_tag
    
    return False, None

def get_last_seen_guid(tags: List[str], freq_tag: str) -> Optional[str]:
    """Extract last seen GUID from tags for specific frequency."""
    for tag in tags:
        if tag.startswith(f'last-seen:{freq_tag}:'):
            return tag.split(':', 2)[2]
    return None

def update_tags_with_poll_info(tags: List[str], freq_tag: str, now: datetime, last_guid: Optional[str]) -> List[str]:
    """Update tags with poll time and last seen GUID for specific frequency."""
    new_tags = []
    
    # Keep tags that don't match our frequency
    for tag in tags:
        if not tag.startswith(f'last-poll:{freq_tag}:') and not tag.startswith(f'last-seen:{freq_tag}:'):
            new_tags.append(tag)
    
    # Add updated poll info
    new_tags.append(f'last-poll:{freq_tag}:{now.isoformat()}')
    if last_guid:
        new_tags.append(f'last-seen:{freq_tag}:{last_guid}')
    
    return new_tags

def fetch_feed_with_cache(feed_url: str, cache_dir: str = "/tmp/rss_cache") -> Tuple[List[Dict], Optional[str]]:
    """Fetch RSS feed using hishel for HTTP caching."""
    try:
        os.makedirs(cache_dir, exist_ok=True)
        
        client = hishel.CacheClient(
            storage=hishel.FileStorage(base_path=cache_dir),
            ttl=300
        )
        
        logger.info(f"Fetching feed: {feed_url}")
        response = client.get(feed_url)
        
        if response.status_code == 304:
            logger.info(f"Feed unchanged (304): {feed_url}")
            return [], None
        
        response.raise_for_status()
        
        feed = feedparser.parse(response.content)
        
        if feed.bozo:
            logger.warning(f"Feed has issues: {feed.bozo_exception}")
        
        articles = []
        latest_guid = None
        
        for entry in feed.entries:
            guid = entry.get('id', entry.get('link', ''))
            if not latest_guid:
                latest_guid = guid
                
            article = {
                'title': entry.get('title', ''),
                'link': entry.get('link', ''),
                'description': entry.get('description', ''),
                'published': entry.get('published', ''),
                'author': entry.get('author', ''),
                'guid': guid
            }
            articles.append(article)
        
        logger.info(f"Found {len(articles)} articles")
        return articles, latest_guid
        
    except Exception as e:
        logger.error(f"Error fetching feed {feed_url}: {e}")
        return [], None

def process_feed_list(client: ListmonkClient, feed_list: Dict, now: datetime):
    """Process a single RSS feed list."""
    list_id = feed_list['id']
    list_name = feed_list['name']
    description = feed_list.get('description', '')
    tags = feed_list.get('tags', [])
    
    logger.info(f"Processing list: {list_name}")
    
    # Check if this should be polled
    should_poll, freq_tag = should_poll_feed(tags, now)
    if not should_poll:
        logger.info(f"Skipping {list_name} - not time to poll")
        return
    
    # Extract feed URL from description
    feed_url = None
    for line in description.split('\n'):
        line = line.strip()
        if line.startswith('http'):
            feed_url = line
            break
    
    if not feed_url:
        logger.warning(f"No feed URL found in description for {list_name}")
        return
    
    # Get last seen GUID for this frequency
    last_seen_guid = get_last_seen_guid(tags, freq_tag)
    
    # Fetch feed
    articles, latest_guid = fetch_feed_with_cache(feed_url)
    
    # Update tags with poll info
    updated_tags = update_tags_with_poll_info(tags, freq_tag, now, latest_guid or last_seen_guid)
    client.update_list_tags(list_id, updated_tags)
    
    if not articles:
        return
    
    # Create campaigns for new articles
    new_articles = []
    for article in articles:
        if last_seen_guid and article['guid'] == last_seen_guid:
            break
        new_articles.append(article)
    
    new_articles.reverse()
    
    logger.info(f"Creating {len(new_articles)} campaigns for {list_name}")
    
    for article in new_articles:
        campaign_body = f"""
        <h2>{article['title']}</h2>
        <p><strong>Published:</strong> {article['published']}</p>
        <p><strong>Author:</strong> {article['author']}</p>
        <div>{article['description']}</div>
        <p><a href="{article['link']}">Read more</a></p>
        """
        
        client.create_campaign(
            title=f"RSS: {article['title'][:50]}",
            subject=article['title'],
            body=campaign_body,
            list_ids=[list_id],
            tags=['rss', 'automated', freq_tag.split(':')[1]]
        )

def process_feed_worker(client: ListmonkClient, feed_list: Dict, now: datetime) -> tuple:
    """Worker function for processing a single feed."""
    try:
        process_feed_list(client, feed_list, now)
        return (feed_list['name'], True, None)
    except Exception as e:
        logger.error(f"Error processing feed {feed_list['name']}: {e}")
        return (feed_list['name'], False, str(e))


def main():
    """Main function with thread pool for concurrent processing."""
    try:
        listmonk_url = os.getenv('LISTMONK_URL', 'http://localhost:9000')
        listmonk_username = os.getenv('LISTMONK_USERNAME', 'listmonk')
        listmonk_password = os.getenv('LISTMONK_PASSWORD', 'listmonk')
        max_workers = int(os.getenv('MAX_WORKERS', '10'))
        
        client = ListmonkClient(listmonk_url, listmonk_username, listmonk_password)
        now = datetime.now(timezone.utc)
        
        lists = client.get_lists()
        feed_lists = [l for l in lists if any(tag in FREQUENCIES for tag in l.get('tags', []))]
        
        if not feed_lists:
            logger.info("No RSS feeds found with frequency tags")
            return
        
        logger.info(f"Processing {len(feed_lists)} RSS feeds with {max_workers} workers")
        
        # Process feeds concurrently using thread pool
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_feed = {
                executor.submit(process_feed_worker, client, feed_list, now): feed_list
                for feed_list in feed_lists
            }
            
            # Collect results
            successful = 0
            failed = 0
            
            for future in as_completed(future_to_feed):
                feed_name, success, error = future.result()
                if success:
                    successful += 1
                    logger.info(f"✅ Processed feed: {feed_name}")
                else:
                    failed += 1
                    logger.error(f"❌ Failed to process feed: {feed_name} - {error}")
        
        logger.info(f"Feed processing complete: {successful} successful, {failed} failed")
        
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
