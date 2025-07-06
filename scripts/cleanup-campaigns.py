#!/usr/bin/env python3
"""
Listmonk Campaign Cleanup Script
Removes old campaigns and manages campaign lifecycle.

This script can be run locally with: python scripts/cleanup-campaigns.py
Or as a uv script with: uv run scripts/cleanup-campaigns.py

# /// script
# dependencies = [
#     "requests",
#     "python-dateutil",
#     "pydantic",
# ]
# ///
"""

import os
import sys
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict

import requests
from dateutil.parser import parse as parse_date
from pydantic import BaseModel, HttpUrl

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ListmonkConfig(BaseModel):
    base_url: HttpUrl
    username: str
    password: str

def load_config() -> Dict:
    """Load configuration from environment variables."""
    config = {
        'listmonk': {
            'base_url': os.getenv('LISTMONK_URL', 'http://localhost:9000'),
            'username': os.getenv('LISTMONK_USERNAME', 'listmonk'),
            'password': os.getenv('LISTMONK_PASSWORD', 'listmonk')
        },
        'cleanup': {
            'keep_days': int(os.getenv('CLEANUP_KEEP_DAYS', '30')),
            'dry_run': os.getenv('CLEANUP_DRY_RUN', 'false').lower() == 'true'
        }
    }
    return config

def get_campaigns(config: ListmonkConfig) -> List[Dict]:
    """Get all campaigns from Listmonk."""
    session = requests.Session()
    session.auth = (config.username, config.password)
    
    try:
        response = session.get(f"{config.base_url}/api/campaigns")
        response.raise_for_status()
        
        data = response.json()
        campaigns = data.get('data', {}).get('results', [])
        logger.info(f"Found {len(campaigns)} campaigns")
        return campaigns
        
    except Exception as e:
        logger.error(f"Error fetching campaigns: {e}")
        return []

def delete_campaign(config: ListmonkConfig, campaign_id: int, dry_run: bool = False) -> bool:
    """Delete a campaign."""
    if dry_run:
        logger.info(f"DRY RUN: Would delete campaign {campaign_id}")
        return True
        
    session = requests.Session()
    session.auth = (config.username, config.password)
    
    try:
        response = session.delete(f"{config.base_url}/api/campaigns/{campaign_id}")
        response.raise_for_status()
        logger.info(f"Deleted campaign {campaign_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error deleting campaign {campaign_id}: {e}")
        return False

def cleanup_old_campaigns(config: ListmonkConfig, keep_days: int, dry_run: bool = False):
    """Clean up old campaigns."""
    campaigns = get_campaigns(config)
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=keep_days)
    
    deleted_count = 0
    
    for campaign in campaigns:
        try:
            # Parse campaign creation date
            created_at = parse_date(campaign.get('created_at', ''))
            
            # Only delete old RSS campaigns
            if (created_at < cutoff_date and 
                campaign.get('status') == 'finished' and
                'rss' in campaign.get('tags', [])):
                
                if delete_campaign(config, campaign['id'], dry_run):
                    deleted_count += 1
                    
        except Exception as e:
            logger.error(f"Error processing campaign {campaign.get('id')}: {e}")
    
    logger.info(f"{'Would delete' if dry_run else 'Deleted'} {deleted_count} old campaigns")

def main():
    """Main function."""
    try:
        config_data = load_config()
        config = ListmonkConfig(**config_data['listmonk'])
        
        cleanup_old_campaigns(
            config,
            config_data['cleanup']['keep_days'],
            config_data['cleanup']['dry_run']
        )
        
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
