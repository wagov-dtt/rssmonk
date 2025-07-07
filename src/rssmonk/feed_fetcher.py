#!/usr/bin/env python3
"""RSS Feed Fetcher Script using Listmonk tags for state."""

import sys
import click
from datetime import datetime, timezone
from typing import Dict

from .config import config, FREQUENCIES
from .logging_config import setup_logging, get_logger
from .http_clients import create_client, fetch_feed
from .feed_processor import FeedProcessor, CampaignCreator
from .utils import extract_feed_url, get_frequency_from_tags

# Setup logging
setup_logging()
logger = get_logger(__name__)

def create_and_send_campaign(article: Dict, feed_list: Dict, frequency: str, client, auto_send: bool = False) -> bool:
    """Create and optionally send campaign."""
    try:
        campaign_data = CampaignCreator.create_campaign_data(article, feed_list, frequency)
        
        campaign = client.create_campaign(
            name=campaign_data['name'],
            subject=campaign_data['subject'],
            body=campaign_data['body'],
            list_ids=campaign_data['lists'],
            tags=campaign_data['tags']
        )
        
        campaign_id = campaign['id']
        logger.info(f"Created campaign: {campaign_data['name']} (ID: {campaign_id})")
        
        if auto_send:
            client.start_campaign(campaign_id)
            logger.info(f"Started campaign: {campaign_data['name']}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to create campaign for {article.get('title', 'Unknown')}: {e}")
        return False


def process_feed_list(feed_list: Dict, now: datetime, client, processor: FeedProcessor, force: bool = False, auto_send: bool = False) -> bool:
    """Process a single RSS feed list."""
    list_name = feed_list['name']
    description = feed_list.get('description', '')
    tags = feed_list.get('tags', [])
    
    try:
        logger.info(f"Processing list: {list_name}")
        
        # Get frequency from tags
        frequency = get_frequency_from_tags(tags)
        if not frequency:
            logger.warning(f"No frequency tag found for {list_name}")
            return False
        
        # Check if should poll (unless forced)
        if not force and not processor.should_poll_feed(feed_list, frequency, now):
            logger.info(f"Skipping {list_name} - not time to poll")
            return True
        
        # Extract feed URL
        feed_url = extract_feed_url(description)
        if not feed_url:
            logger.warning(f"No feed URL found for {list_name}")
            return False
        
        # Fetch feed
        articles, latest_guid = fetch_feed(feed_url, config.timeout)
        
        if not articles:
            logger.info(f"No articles found for {list_name}")
            processor.update_tags(feed_list, frequency, [], now)
            return True
        
        # Find new articles
        new_articles = processor.find_new_articles(articles, feed_list, frequency)
        
        if not new_articles:
            logger.info(f"No new articles for {list_name}")
            processor.update_tags(feed_list, frequency, [], now)
            return True
        
        logger.info(f"Creating {len(new_articles)} campaigns for {list_name}")
        
        # Process articles
        success_count = 0
        for article in new_articles:
            if create_and_send_campaign(article, feed_list, frequency, client, auto_send or config.auto_send):
                success_count += 1
        
        # Update tags with state
        processor.update_tags(feed_list, frequency, new_articles, now)
        
        logger.info(f"Successfully processed {success_count}/{len(new_articles)} articles for {list_name}")
        return success_count > 0
        
    except Exception as e:
        logger.error(f"Error processing {list_name}: {e}")
        return False


@click.command()
@click.option('--frequency', type=click.Choice(['5min', 'daily', 'weekly']), help='Only process feeds with this frequency')
@click.option('--force', is_flag=True, help='Force processing even if not time to poll')
@click.option('--auto-send', is_flag=True, help='Automatically send campaigns (start them)')
def main(frequency, force, auto_send):
    """Main function."""
    try:
        # Validate configuration
        config.validate()
        
        now = datetime.now(timezone.utc)
        
        logger.info("Starting RSS feed processing")
        
        with create_client() as client:
            processor = FeedProcessor(client)
            
            # Get all lists
            lists = client.get_lists()
            
            # Filter by frequency if specified
            feed_lists = []
            for feed_list in lists:
                tags = feed_list.get('tags', [])
                if any(tag in FREQUENCIES for tag in tags):
                    if frequency:
                        freq_tag = f"freq:{frequency}"
                        if freq_tag in tags:
                            feed_lists.append(feed_list)
                    else:
                        feed_lists.append(feed_list)
            
            if not feed_lists:
                logger.info("No RSS feeds found")
                return
            
            logger.info(f"Processing {len(feed_lists)} RSS feeds")
            
            # Process feeds
            processed_count = 0
            success_count = 0
            for feed_list in feed_lists:
                processed_count += 1
                if process_feed_list(feed_list, now, client, processor, force, auto_send):
                    success_count += 1
            
            logger.info(f"Feed processing complete: {success_count}/{processed_count} feeds processed successfully")
        
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
