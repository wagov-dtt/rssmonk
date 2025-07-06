#!/usr/bin/env python3
"""
Feed Management CLI for RSS Monk
Manage RSS feeds via Listmonk API with frequency control.

# /// script
# dependencies = [
#     "requests",
#     "feedparser",
#     "click",
# ]
# ///
"""

import os
import sys
import json
from typing import List, Dict, Optional

import click
import requests
import feedparser


class ListmonkClient:
    """Client for Listmonk API operations."""
    
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.auth = (username, password)
        
    def get_lists(self) -> List[Dict]:
        """Get all mailing lists."""
        response = self.session.get(f"{self.base_url}/api/lists")
        response.raise_for_status()
        return response.json()['data']['results']
    
    def create_list(self, name: str, description: str, tags: List[str]) -> Dict:
        """Create a new mailing list."""
        data = {
            'name': name,
            'type': 'public',
            'description': description,
            'tags': tags
        }
        response = self.session.post(f"{self.base_url}/api/lists", json=data)
        response.raise_for_status()
        return response.json()['data']
    
    def get_subscribers(self) -> List[Dict]:
        """Get all subscribers."""
        response = self.session.get(f"{self.base_url}/api/subscribers")
        response.raise_for_status()
        return response.json()['data']['results']
    
    def create_subscriber(self, email: str, name: str = None) -> Dict:
        """Create a new subscriber."""
        data = {
            'email': email,
            'name': name or email.split('@')[0],
            'status': 'enabled'
        }
        response = self.session.post(f"{self.base_url}/api/subscribers", json=data)
        response.raise_for_status()
        return response.json()['data']
    
    def subscribe_to_list(self, subscriber_id: int, list_id: int) -> bool:
        """Subscribe a user to a list."""
        data = {
            'ids': [list_id],
            'status': 'confirmed'
        }
        response = self.session.put(f"{self.base_url}/api/subscribers/{subscriber_id}/lists", json=data)
        response.raise_for_status()
        return True


def get_client() -> ListmonkClient:
    """Get configured Listmonk client."""
    base_url = os.getenv('LISTMONK_URL', 'http://localhost:9000')
    username = os.getenv('LISTMONK_USERNAME', 'listmonk')
    password = os.getenv('LISTMONK_PASSWORD', 'listmonk')
    return ListmonkClient(base_url, username, password)


def validate_feed_url(url: str) -> bool:
    """Validate RSS feed URL."""
    try:
        feed = feedparser.parse(url)
        return len(feed.entries) > 0
    except Exception:
        return False


@click.group()
def cli():
    """RSS Monk Feed Management CLI"""
    pass


@cli.command()
@click.argument('url')
@click.argument('frequency', type=click.Choice(['5min', 'daily', 'weekly']))
@click.option('--name', help='Feed name (auto-detected if not provided)')
def add_feed(url: str, frequency: str, name: str = None):
    """Add a new RSS feed with frequency control."""
    client = get_client()
    
    # Validate feed URL
    if not validate_feed_url(url):
        click.echo(f"❌ Invalid RSS feed URL: {url}", err=True)
        sys.exit(1)
    
    # Parse feed for name if not provided
    if not name:
        try:
            feed = feedparser.parse(url)
            name = feed.feed.get('title', url)
        except Exception:
            name = url
    
    # Create list with frequency tag
    tags = [f'freq:{frequency}']
    description = f'RSS Feed: {url}'
    
    try:
        feed_list = client.create_list(name, description, tags)
        click.echo(f"✅ Created feed: {name}")
        click.echo(f"   ID: {feed_list['id']}")
        click.echo(f"   Frequency: {frequency}")
        click.echo(f"   URL: {url}")
    except Exception as e:
        click.echo(f"❌ Failed to create feed: {e}", err=True)
        sys.exit(1)


@cli.command()
def list_feeds():
    """List all RSS feeds."""
    client = get_client()
    
    try:
        lists = client.get_lists()
        feed_lists = [l for l in lists if any(tag.startswith('freq:') for tag in l.get('tags', []))]
        
        if not feed_lists:
            click.echo("No RSS feeds found")
            return
        
        click.echo("RSS Feeds:")
        for feed_list in feed_lists:
            tags = feed_list.get('tags', [])
            freq_tags = [tag for tag in tags if tag.startswith('freq:')]
            frequency = freq_tags[0].replace('freq:', '') if freq_tags else 'unknown'
            
            click.echo(f"  {feed_list['name']} (ID: {feed_list['id']})")
            click.echo(f"    Frequency: {frequency}")
            click.echo(f"    Subscribers: {feed_list['subscriber_count']}")
            click.echo(f"    Description: {feed_list['description']}")
            click.echo()
    except Exception as e:
        click.echo(f"❌ Failed to list feeds: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('email')
@click.option('--name', help='Subscriber name')
def add_subscriber(email: str, name: str = None):
    """Add a new subscriber."""
    client = get_client()
    
    try:
        subscriber = client.create_subscriber(email, name)
        click.echo(f"✅ Created subscriber: {email}")
        click.echo(f"   ID: {subscriber['id']}")
        click.echo(f"   Name: {subscriber['name']}")
    except Exception as e:
        click.echo(f"❌ Failed to create subscriber: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('email')
@click.argument('feed_id', type=int)
def subscribe(email: str, feed_id: int):
    """Subscribe an email to a feed."""
    client = get_client()
    
    try:
        # Find subscriber by email
        subscribers = client.get_subscribers()
        subscriber = next((s for s in subscribers if s['email'] == email), None)
        
        if not subscriber:
            click.echo(f"❌ Subscriber not found: {email}", err=True)
            click.echo("   Use 'add-subscriber' command first")
            sys.exit(1)
        
        # Subscribe to feed
        client.subscribe_to_list(subscriber['id'], feed_id)
        click.echo(f"✅ Subscribed {email} to feed ID {feed_id}")
        
    except Exception as e:
        click.echo(f"❌ Failed to subscribe: {e}", err=True)
        sys.exit(1)


@cli.command()
def list_subscribers():
    """List all subscribers."""
    client = get_client()
    
    try:
        subscribers = client.get_subscribers()
        
        if not subscribers:
            click.echo("No subscribers found")
            return
        
        click.echo("Subscribers:")
        for subscriber in subscribers:
            click.echo(f"  {subscriber['email']} (ID: {subscriber['id']})")
            click.echo(f"    Name: {subscriber['name']}")
            click.echo(f"    Status: {subscriber['status']}")
            click.echo(f"    Lists: {len(subscriber.get('lists', []))}")
            click.echo()
    except Exception as e:
        click.echo(f"❌ Failed to list subscribers: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('url')
@click.argument('frequency', type=click.Choice(['5min', 'daily', 'weekly']))
@click.argument('emails', nargs=-1, required=True)
@click.option('--name', help='Feed name (auto-detected if not provided)')
def quick_setup(url: str, frequency: str, emails: tuple, name: str = None):
    """Quick setup: add feed and subscribe emails in one command."""
    client = get_client()
    
    # Validate feed URL
    if not validate_feed_url(url):
        click.echo(f"❌ Invalid RSS feed URL: {url}", err=True)
        sys.exit(1)
    
    # Parse feed for name if not provided
    if not name:
        try:
            feed = feedparser.parse(url)
            name = feed.feed.get('title', url)
        except Exception:
            name = url
    
    try:
        # Create feed
        tags = [f'freq:{frequency}']
        description = f'RSS Feed: {url}'
        feed_list = client.create_list(name, description, tags)
        click.echo(f"✅ Created feed: {name} (ID: {feed_list['id']})")
        
        # Add subscribers and subscribe them
        for email in emails:
            try:
                # Try to create subscriber (will fail if exists)
                try:
                    subscriber = client.create_subscriber(email)
                    click.echo(f"✅ Created subscriber: {email}")
                except Exception:
                    # Subscriber already exists, find them
                    subscribers = client.get_subscribers()
                    subscriber = next((s for s in subscribers if s['email'] == email), None)
                    if not subscriber:
                        click.echo(f"❌ Could not find or create subscriber: {email}", err=True)
                        continue
                
                # Subscribe to feed
                client.subscribe_to_list(subscriber['id'], feed_list['id'])
                click.echo(f"✅ Subscribed {email} to {name}")
                
            except Exception as e:
                click.echo(f"❌ Failed to setup {email}: {e}", err=True)
        
        click.echo(f"\n🎉 Setup complete! Feed '{name}' created with {len(emails)} subscribers")
        
    except Exception as e:
        click.echo(f"❌ Failed to setup feed: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    cli()
