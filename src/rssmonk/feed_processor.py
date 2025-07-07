"""Feed processing logic using Listmonk tags for state."""

import re
from datetime import datetime, timedelta
from typing import Dict, List

from .config import FREQUENCIES
from .logging_config import get_logger

logger = get_logger(__name__)

class FeedProcessor:
    """Handles feed polling logic using Listmonk tags for state."""
    
    def __init__(self, listmonk_client):
        self.client = listmonk_client
    
    def should_poll_feed(self, feed_list: Dict, frequency: str, now: datetime) -> bool:
        """Check if feed should be polled based on frequency and tags."""
        if frequency not in FREQUENCIES:
            logger.warning(f"Unknown frequency: {frequency}")
            return False
        
        config = FREQUENCIES[frequency]
        tags = feed_list.get('tags', [])
        
        # Find last poll time from tags
        last_poll = None
        for tag in tags:
            if tag.startswith(f'last-poll:{frequency}:'):
                try:
                    last_poll_str = tag.split(':', 3)[3]  # Changed from split(':', 2)[2]
                    last_poll = datetime.fromisoformat(last_poll_str)
                    break
                except Exception:
                    continue
        
        # Check based on frequency type
        if config['interval_minutes']:
            if not last_poll:
                return True
            return now - last_poll > timedelta(minutes=config['interval_minutes'])
        
        elif config['check_time']:
            target_hour, target_minute = config['check_time']
            
            # Weekly check
            if config['check_day'] is not None:
                if now.weekday() != config['check_day']:
                    return False
                
                if last_poll:
                    last_week = now - timedelta(weeks=1)
                    if last_poll > last_week:
                        return False
            
            # Daily check
            else:
                if last_poll:
                    yesterday = now - timedelta(days=1)
                    if last_poll > yesterday:
                        return False
            
            today = now.date()
            target_datetime = datetime.combine(
                today, 
                datetime.min.time().replace(hour=target_hour, minute=target_minute)
            )
            target_datetime = target_datetime.replace(tzinfo=now.tzinfo)
            
            return now >= target_datetime
        
        return False
    
    def find_new_articles(self, articles: List[Dict], feed_list: Dict, frequency: str) -> List[Dict]:
        """Find new articles since last poll."""
        tags = feed_list.get('tags', [])
        last_guid = None
        
        # Find last seen GUID from tags
        for tag in tags:
            if tag.startswith(f'last-seen:{frequency}:'):
                last_guid = tag.split(':', 3)[3]  # Changed from split(':', 2)[2]
                break
        
        if not last_guid:
            return articles
        
        # Find the index of the last seen article
        last_index = -1
        for i, article in enumerate(articles):
            if article['guid'] == last_guid:
                last_index = i
                break
        
        # If last_guid not found, return all articles
        if last_index == -1:
            return articles
        
        # Return articles that come before the last seen article (newer articles)
        return articles[:last_index]
    
    def update_tags(self, feed_list: Dict, frequency: str, articles: List[Dict], now: datetime) -> None:
        """Update list tags with new state information."""
        from .utils import update_list_tags
        
        tags = feed_list.get('tags', []).copy()
        
        # Remove old state tags
        tags = [tag for tag in tags if not tag.startswith(f'last-poll:{frequency}:') 
               and not tag.startswith(f'last-seen:{frequency}:')]
        
        # Add new poll time
        tags.append(f'last-poll:{frequency}:{now.isoformat()}')
        
        # Add new last seen GUID if we have articles
        if articles:
            latest_guid = articles[-1]['guid']
            tags.append(f'last-seen:{frequency}:{latest_guid}')
        
        # Update the list
        update_list_tags(
            self.client, 
            feed_list['id'],
            tags,
            feed_list['name'],
            feed_list.get('description', ''),
            feed_list.get('type', 'public')
        )

class CampaignCreator:
    """Handles campaign creation and content formatting."""
    
    @staticmethod
    def create_content(article: Dict, feed_name: str) -> str:
        """Create HTML content for campaign."""
        title = article.get('title', 'No title')
        link = article.get('link', '')
        description = article.get('description', '')
        published = article.get('published', '')
        author = article.get('author', '')
        
        # Clean up HTML content
        if description:
            description = CampaignCreator._clean_html(description)
        
        return f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h1 style="color: #333; border-bottom: 2px solid #007cba; padding-bottom: 10px;">{title}</h1>
            
            <div style="margin: 20px 0; color: #666; font-size: 14px;">
                <p><strong>From:</strong> {feed_name}</p>
                {f"<p><strong>Published:</strong> {published}</p>" if published else ""}
                {f"<p><strong>Author:</strong> {author}</p>" if author else ""}
            </div>
            
            <div style="margin: 20px 0; line-height: 1.6;">
                {description}
            </div>
            
            <div style="margin: 30px 0; text-align: center;">
                <a href="{link}" style="background-color: #007cba; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; display: inline-block;">
                    Read Full Article
                </a>
            </div>
            
            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; color: #666; font-size: 12px; text-align: center;">
                <p>This email was sent automatically from RSS Monk</p>
                <p>Article URL: <a href="{link}">{link}</a></p>
            </div>
        </div>
        """
    
    @staticmethod
    def _clean_html(content: str) -> str:
        """Clean HTML content by removing scripts and styles."""
        # Remove script tags
        content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
        # Remove style tags
        content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)
        return content
    
    @staticmethod
    def create_campaign_data(article: Dict, feed_list: Dict, frequency: str) -> Dict:
        """Create campaign data for API."""
        title = article.get('title', 'No title')
        campaign_name = f"RSS: {title[:50]}..." if len(title) > 50 else f"RSS: {title}"
        
        content = CampaignCreator.create_content(article, feed_list['name'])
        
        return {
            "name": campaign_name,
            "subject": title,
            "body": content,
            "lists": [feed_list['id']],
            "content_type": "richtext",
            "messenger": "email",
            "type": "regular",
            "tags": ['rss', 'automated', frequency.split(':')[1] if ':' in frequency else frequency]
        }


