"""Simple Typer CLI for RSS Monk."""
import warnings

from rssmonk.utils import find_highest_frequency, make_url_hash
warnings.warn("This module is no longer supported. Please use the API endpoint instead with your preferred API development tool.", DeprecationWarning)

from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

from .core import RSSMonk, Settings
from .types import Frequency
from .logging_config import setup_logging

console = Console()
app = typer.Typer(help="RSS Monk - RSS feeds to email newsletters")


@app.callback()
def setup_app_logging():
    """Setup logging for the CLI."""
    try:
        # Create .env if missing
        if Settings.ensure_env_file():
            print("Created .env file with default settings. Please edit LISTMONK_ADMIN_PASSWORD.")
        
        settings = Settings()
        setup_logging(level=settings.log_level, format_str=settings.log_format)
    except Exception:
        # Fallback to default logging if settings fail
        setup_logging()


@app.command()
def add_feed(
    url: str = typer.Argument(help="RSS feed URL"),
    frequency: Frequency = typer.Argument(help="Polling frequency"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Feed name (auto-detected if not provided)"),
):
    """Add a new RSS feed."""
    try:
        with RSSMonk() as rss:
            feed = rss.add_feed(url, frequency, name)
            console.print(f"[SUCCESS] Created feed: {feed.name} (ID: {feed.id})", style="green")
            console.print(f"   URL: {feed.feed_url}")
            console.print(f"   Frequency: {feed.poll_frequencies.value}")
    except Exception as e:
        console.print(f"[ERROR] {e}", style="red")
        raise typer.Exit(1)


@app.command()
def list_feeds():
    """List all RSS feeds."""
    try:
        with RSSMonk() as rss:
            feeds = rss.list_feeds()

            if not feeds:
                console.print("No RSS feeds found")
                return

            table = Table(title="RSS Feeds")
            table.add_column("Name", style="cyan")
            table.add_column("URL", style="blue")
            table.add_column("Frequency", style="magenta")
            table.add_column("ID", style="dim")

            for feed in feeds:
                table.add_row(
                    feed.name,
                    feed.feed_url[:50] + "..." if len(feed.feed_url) > 50 else feed.feed_url,
                    feed.poll_frequencies,
                    str(feed.id),
                )

            console.print(table)
    except Exception as e:
        console.print(f"[ERROR] {e}", style="red")
        raise typer.Exit(1)


@app.command()
def add_subscriber(
    email: str = typer.Argument(help="Subscriber email"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Subscriber name"),
):
    """Add a new subscriber."""
    try:
        with RSSMonk() as rss:
            subscriber = rss.add_subscriber(email, name)
            console.print(
                f"[SUCCESS] Created subscriber: {subscriber.email} (ID: {subscriber.id})",
                style="green",
            )
    except Exception as e:
        console.print(f"[ERROR] {e}", style="red")
        raise typer.Exit(1)


@app.command()
def subscribe(
    email: str = typer.Argument(help="Subscriber email"),
    feed_url: str = typer.Argument(help="RSS feed URL"),
):
    """Subscribe an email to a feed."""
    try:
        with RSSMonk() as rss:
            feed_hash = make_url_hash(feed_url)
            rss.subscribe(email, feed_hash)
            console.print(f"[SUCCESS] Subscribed {email} to feed", style="green")
    except Exception as e:
        console.print(f"[ERROR] {e}", style="red")
        raise typer.Exit(1)


@app.command()
def quick_setup(
    url: str = typer.Argument(help="RSS feed URL"),
    frequency: Frequency = typer.Argument(help="Polling frequency"),
    emails: list[str] = typer.Argument(help="Subscriber emails"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Feed name"),
):
    """Add feed and subscribe multiple emails in one command."""
    try:
        with RSSMonk() as rss:
            # Create or get feed
            feed = rss.get_feed_by_url(url)
            if feed:
                console.print(f"[INFO] Using existing feed: {feed.name}")
            else:
                feed = rss.add_feed(url, frequency, name)
                console.print(f"[SUCCESS] Created feed: {feed.name}")

            # Subscribe emails
            success = 0
            for email in emails:
                try:
                    feed_hash = make_url_hash(url)
                    rss.subscribe(email, feed_hash)
                    console.print(f"[SUCCESS] Subscribed {email}")
                    success += 1
                except Exception as e:
                    console.print(f"[ERROR] Failed to subscribe {email}: {e}", style="red")

            console.print(
                f"[COMPLETE] Setup complete! {success}/{len(emails)} subscriptions successful",
                style="green bold",
            )
    except Exception as e:
        console.print(f"[ERROR] {e}", style="red")
        raise typer.Exit(1)


@app.command()
def process_feed(
    feed_url: str = typer.Argument(help="RSS feed URL"),
    auto_send: bool = typer.Option(False, "--send", help="Automatically send campaigns"),
):
    """Manually process a single feed."""
    try:
        with RSSMonk() as rss:
            feed = rss.get_feed_by_url(feed_url)
            if not feed:
                console.print(f"[ERROR] Feed not found: {feed_url}", style="red")
                raise typer.Exit(1)

            lowest_freq: Optional[Frequency] = find_highest_frequency(feed.poll_frequencies)
            campaigns = rss.process_feed(feed, lowest_freq, auto_send)
            action = "sent" if auto_send else "created"

            if campaigns > 0:
                console.print(f"[SUCCESS] {campaigns} campaigns {action} for {feed.name}", style="green")
            else:
                console.print(f"[INFO] No new articles for {feed.name}", style="yellow")
    except Exception as e:
        console.print(f"[ERROR] {e}", style="red")
        raise typer.Exit(1)


@app.command()
def poll(frequency: Frequency = typer.Argument(help="Frequency to poll")):
    """Poll all feeds of a specific frequency that are due."""
    try:
        with RSSMonk() as rss:
            results = rss.process_feeds_by_frequency(frequency)

            if not results:
                console.print(f"No {frequency.value} feeds due for polling")
                return

            table = Table(title=f"Polling Results - {frequency.value}")
            table.add_column("Feed", style="cyan")
            table.add_column("Campaigns", style="green")

            total = 0
            for feed_name, campaigns in results.items():
                table.add_row(feed_name, str(campaigns))
                total += campaigns

            console.print(table)
            console.print(f"[SUMMARY] Total campaigns: {total}", style="green bold")
    except Exception as e:
        console.print(f"[ERROR] {e}", style="red")
        raise typer.Exit(1)


@app.command()
def delete_feed(url: str = typer.Argument(help="RSS feed URL to delete")):
    """Delete a feed by URL."""
    try:
        with RSSMonk() as rss:
            if rss.delete_feed(url):
                console.print(f"[SUCCESS] Deleted feed: {url}", style="green")
            else:
                console.print(f"[ERROR] Feed not found: {url}", style="red")
    except Exception as e:
        console.print(f"[ERROR] {e}", style="red")
        raise typer.Exit(1)


@app.command()
def health():
    """Check RSS Monk health."""
    try:
        settings = Settings()
        settings.validate_required()
        console.print("[SUCCESS] Configuration: Valid", style="green")

        with RSSMonk(settings) as rss:
            feeds = rss.list_feeds()
            subscribers = rss.list_subscribers()

            console.print("[SUCCESS] Listmonk connection: OK", style="green")
            console.print(f"Feeds: {len(feeds)}")
            console.print(f"Subscribers: {len(subscribers)}")
            console.print("[SUCCESS] All systems operational", style="green bold")
    except Exception as e:
        console.print(f"[ERROR] Health check failed: {e}", style="red")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
