"""Test API endpoints."""

import os
import pytest
from fastapi.testclient import TestClient


def test_create_feed():
    """
    Tests create feed endpoint. POST /api/feeds
    - Create feed with permutations of url, name (optional), frequency and list_visibility with no pre-existing feed
    - Create feed that already exists with incoming frequencies being a subset of existing
    - Create feed with already exists with incoming frequencies having no overlap with existing
    - Create feed with already exists with incoming frequencies having partial overlap with existing
    - Create feed with invalid url, frequency and list_visibility
    """
    # TODO - This will require a Listmonk to be run to be the endpoint
    # Set required env var for import
    os.environ['LISTMONK_APITOKEN'] = 'test-token'
    
    from rssmonk.api import app
    client = TestClient(app)
    
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "RSS Monk API"
    assert data["version"] == "2.0.0"

def test_update_feed():
    """
    Tests create feed endpoint. PUT /api/feeds/configurations
    -
    """
    pass

def test_create_feed_account():
    """
    Tests create feed account endpoint. POST /api/feeds/account
    - Create feed account. Ensure list role and account have been created with limited role
    """
    pass

def test_create_update_feed_email_template():
    """
    Tests create feed template endpoint. POST /api/feeds/templates
    - Create feed template
    """
    pass

def test_delete_feed():
    """
    Tests delete feed endpoint. DELETE /api/feeds/by-url
    - Delete non existing feed
    - Delete existing feed. Ensure feed, user account, list role, templates are removed

    """
    pass

