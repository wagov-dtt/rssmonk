"""Simple cron job script to remove expired pending subscriptions."""

import logging
import os
import sys

import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger("rssmonk.cron.notifications")

# Retrieve Listmonk credentials to use with the HTTP request
RSSMONK_URL = os.environ.get('RSSMONK_URL', 'http://localhost:8000')
RSSMONK_USER = os.environ.get('RSSMONK_USER', 'http://localhost:8000')
RSSMONK_PASS = os.environ.get('RSSMONK_PASS', 'http://localhost:8000')


if __name__ == "__main__":

    logger.info("Cleaning expired filter")
    basic_auth = HTTPBasicAuth(RSSMONK_USER, RSSMONK_PASS)

    with requests.Session() as session:
        try:
            # TODO - Interact with Listmonk to grab all subscribers to go through
            response = session.post(f"{RSSMONK_URL}/api/subscribers", basic=basic_auth)

            # Response likely to be in pages

        except Exception as e:
            logger.error("Cron job failed: %s", e)
            sys.exit(1)
