"""Simple cron job script to remove expired pending subscriptions."""

import logging
import os


import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger("rssmonk.cron.notifications")

# Retrieve Listmonk credentials to use with the HTTP request
RSSMONK_URL = os.environ.get('RSSMONK_URL', 'http://localhost:8000')
RSSMONK_USER = os.environ.get('RSSMONK_USER', 'http://localhost:8000')
RSSMONK_PASS = os.environ.get('RSSMONK_PASS', 'http://localhost:8000')

def _get_subscribe_url(page: int, per_page: int = 1000) -> str:
    return f"subscribers?list_id=&search=&query=&page={page}&per_page={per_page}&subscription_status=&order_by=id&order=desc"

def clean_expiry():
    logger.info("Cleaning expired filter")
    basic_auth = HTTPBasicAuth(RSSMONK_USER, RSSMONK_PASS)

    with requests.Session() as session:
        try:
            # TODO - Interact with Listmonk to grab all subscribers to go through
            response = session.get(f"{RSSMONK_URL}/api/subscribers", basic=basic_auth)
            # Sample results
            # {
            #   "data": {
            #     "results": [],
            #     "search": "",
            #     "query": "",
            #     "total": 3,
            #     "per_page": 20,
            #     "page": 1
            #   }
            # }

            # TODO Get data, and for each attribs, delete anything expired for each feed and push back in

            # Response will be in pages 
            total_pages = 1

        except Exception as e:
            logger.error("Cron job failed: %s", e)


# TODO - This should be called daily.
if __name__ == "__main__":
    clean_expiry()