"""Simple cron job script using Pydantic models."""

import sys
from .core import RSSMonk, Frequency, Settings
from .logging_config import get_logger

logger = get_logger(__name__)


def main():
    """Main cron job entry point."""
    if len(sys.argv) != 2:
        print("Usage: python -m rssmonk.cron_simple <frequency>")
        print("Frequencies: 5min, daily, weekly")
        sys.exit(1)

    try:
        frequency = Frequency(sys.argv[1])
    except ValueError:
        print(f"Invalid frequency: {sys.argv[1]}")
        print("Valid frequencies: 5min, daily, weekly")
        sys.exit(1)

    # Create .env if missing
    if Settings.ensure_env_file():
        print("Created .env file with default settings. Please edit LISTMONK_APITOKEN.")
        sys.exit(1)

    logger.info(f"Starting RSS Monk cron job for {frequency.value} feeds")

    try:
        with RSSMonk() as rss:
            results = rss.process_feeds_by_frequency(frequency)

            if not results:
                logger.info(f"No {frequency.value} feeds due for polling")
                return

            total_campaigns = sum(results.values())
            logger.info(f"Processed {len(results)} feeds, created {total_campaigns} campaigns")

            for feed_name, campaigns in results.items():
                if campaigns > 0:
                    logger.info(f"  {feed_name}: {campaigns} campaigns")
                else:
                    logger.info(f"  {feed_name}: no new articles")

    except Exception as e:
        logger.error(f"Cron job failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
