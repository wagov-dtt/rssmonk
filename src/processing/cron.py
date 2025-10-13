"""Simple cron job script using Pydantic models."""

import logging
import os
import sys

import requests
from requests.auth import HTTPBasicAuth

from rssmonk.models import Frequency

logger = logging.getLogger("rssmonk.cron")

RSSMONK_URL = os.environ.get('RSSMONK_URL', 'http://localhost:8000')
RSSMONK_USER = os.environ.get('RSSMONK_USER', 'http://localhost:8000')
RSSMONK_PASS = os.environ.get('RSSMONK_PASS', 'http://localhost:8000')


if __name__ == "__main__":
    """Main cron job entry point."""
    if len(sys.argv) != 2:
        print("Usage: python cron <frequency>")
        print("Frequencies: instant, daily, weekly")
        sys.exit(1)

    try:
        frequency = Frequency(sys.argv[1])
    except ValueError:
        print(f"Invalid frequency: {sys.argv[1]}")
        print("Valid frequencies: instant, daily, weekly")
        sys.exit(1)

    # Retrieve Listmonk credentials to use with the HTTP request

    logger.info("Starting RSS Monk cron job for %s feeds", frequency.value)
    basic_auth = HTTPBasicAuth(RSSMONK_USER, RSSMONK_PASS)

    with requests.Session() as session:
        try:
            # Collect the nonce from the login page to sati2sfy CSRF protection
            response = session.post(f"{RSSMONK_URL}/api/feeds/process/bulk/{frequency}", basic=basic_auth)

            print(response.text)

            if response.json is not None:
                results = response.json
                total_campaigns = sum(results.values())
                logger.info("Processed %i feeds, created %i campaigns", len(results), total_campaigns)

                # This is not required for the cron job.
                for feed_name, campaigns in results.items():
                    if campaigns > 0:
                        logger.info("  %s: %s campaigns", feed_name, campaigns)
                    else:
                        logger.info("  %s: no new articles", feed_name)
            else:
                logger.info("No %s feeds due for polling", frequency.value)

        except Exception as e:
            logger.error("Cron job failed: %s", e)
            sys.exit(1)
