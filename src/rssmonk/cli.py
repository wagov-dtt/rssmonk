"""CLI for RSS Monk feed management."""

import click
import feedparser
import httpx
from .http_clients import create_client
from .utils import create_url_tag, find_feed_by_url, create_or_get_subscriber
from .logging_config import get_logger

logger = get_logger(__name__)


@click.group()
def main():
    """RSS Monk Feed Management CLI"""
    pass


def get_feed_name(url: str, provided_name: str = None) -> str:
    """Get feed name from URL or provided name."""
    if provided_name:
        return provided_name
    
    try:
        feed = feedparser.parse(url)
        return feed.feed.get('title', url)
    except Exception:
        return url


@main.command('add-feed')
@click.argument('url')
@click.argument('frequency', type=click.Choice(['5min', 'daily', 'weekly']))
@click.option('--name', help='Feed name (auto-detected if not provided)')
def add_feed(url: str, frequency: str, name: str = None):
    """Add a new RSS feed."""
    name = get_feed_name(url, name)
    
    with create_client() as client:
        # Check if feed already exists
        existing_feed = find_feed_by_url(client, url)
        if existing_feed:
            click.echo(f"❌ Feed URL already exists: {existing_feed['name']}")
            return
        
        # Create list
        url_tag = create_url_tag(url)
        feed_list = client.create_list(
            name=name,
            description=f"RSS Feed: {url}",
            tags=[f"freq:{frequency}", url_tag]
        )
        click.echo(f"✅ Created feed: {name} (ID: {feed_list['id']})")


@main.command('list-feeds')
def list_feeds():
    """List all RSS feeds."""
    with create_client() as client:
        # Query by frequency tags to get only RSS feeds
        all_feeds = []
        for freq in ['5min', 'daily', 'weekly']:
            feeds = client.get_lists(tag=f"freq:{freq}")
            all_feeds.extend(feeds)
        
        # Remove duplicates by ID
        feed_lists = {f['id']: f for f in all_feeds}.values()
        
        if not feed_lists:
            click.echo("No RSS feeds found")
            return
        
        for feed_list in feed_lists:
            freq_tags = [tag for tag in feed_list.get('tags', []) if tag.startswith('freq:')]
            frequency = freq_tags[0].replace('freq:', '') if freq_tags else 'unknown'
            
            click.echo(f"  {feed_list['name']} (ID: {feed_list['id']})")
            click.echo(f"    Frequency: {frequency}")
            click.echo(f"    Subscribers: {feed_list.get('subscriber_count', 0)}")
            click.echo(f"    Description: {feed_list.get('description', '')}")
            click.echo()


@main.command('add-subscriber')
@click.argument('email')
@click.option('--name', help='Subscriber name (defaults to email)')
def add_subscriber(email: str, name: str = None):
    """Add a new subscriber."""
    with create_client() as client:
        # Check if subscriber already exists
        try:
            subscribers = client.get_subscribers(query=email)
            if subscribers:
                click.echo(f"❌ Subscriber already exists: {email}")
                return
        except Exception:
            pass  # Subscriber doesn't exist, continue
        
        # Create subscriber
        subscriber = client.create_subscriber(email=email, name=name or email)
        click.echo(f"✅ Created subscriber: {email} (ID: {subscriber['id']})")


@main.command('list-subscribers')
def list_subscribers():
    """List all subscribers."""
    with create_client() as client:
        subscribers = client.get_subscribers()
        
        if not subscribers:
            click.echo("No subscribers found")
            return
        
        for subscriber in subscribers:
            click.echo(f"  {subscriber['email']} (ID: {subscriber['id']})")
            click.echo(f"    Name: {subscriber.get('name', 'N/A')}")
            click.echo(f"    Status: {subscriber.get('status', 'N/A')}")
            click.echo()


@main.command()
@click.argument('email')
@click.argument('list_id', type=int)
def subscribe(email: str, list_id: int):
    """Subscribe an email to a feed list."""
    with create_client() as client:
        # Find subscriber by email
        data = client.get("/api/subscribers", params={"query": email})
        if isinstance(data, dict) and 'results' in data:
            subscribers = data['results']
        else:
            subscribers = data if isinstance(data, list) else []
        
        if not subscribers:
            click.echo(f"❌ Subscriber not found: {email}")
            return
        
        subscriber = subscribers[0]
        client.subscribe_to_lists([subscriber['id']], [list_id])
        click.echo(f"✅ Subscribed {email} to list {list_id}")


@main.command('quick-setup')
@click.argument('url')
@click.argument('frequency', type=click.Choice(['5min', 'daily', 'weekly']))
@click.argument('emails', nargs=-1, required=True)
@click.option('--name', help='Feed name (auto-detected if not provided)')
def quick_setup(url: str, frequency: str, emails: tuple, name: str = None):
    """Add feed and subscribe multiple emails in one command."""
    name = get_feed_name(url, name)
    
    with create_client() as client:
        # Check if feed already exists
        feed_list = find_feed_by_url(client, url)
        if feed_list:
            click.echo(f"📋 Using existing feed: {feed_list['name']} (ID: {feed_list['id']})")
        else:
            # Create feed
            url_tag = create_url_tag(url)
            feed_list = client.create_list(
                name=name,
                description=f"RSS Feed: {url}",
                tags=[f"freq:{frequency}", url_tag]
            )
            click.echo(f"✅ Created feed: {name} (ID: {feed_list['id']})")
        
        list_id = feed_list['id']
        
        # Add and subscribe each email
        for email in emails:
            try:
                subscriber = create_or_get_subscriber(client, email)
                client.subscribe_to_lists([subscriber['id']], [list_id])
                click.echo(f"✅ Subscribed {email} to {name}")
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 400:
                    click.echo(f"❌ Invalid email address: {email}")
                else:
                    click.echo(f"❌ Failed to process {email}: HTTP {e.response.status_code}")
                continue
            except Exception as e:
                click.echo(f"❌ Failed to process {email}: {e}")
                continue
        
        click.echo(f"\n🎉 Quick setup complete! Feed: {name}, Subscribers: {len(emails)}")


if __name__ == '__main__':
    main()
