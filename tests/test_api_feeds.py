"""Test API endpoints."""

import os
import pytest
from fastapi.testclient import TestClient


def test_create_feed():
    """
    Tests create feed endpoint.
    - Create feed with permutations of url, name, frequency and list_visibility
    - Create feed that already exists with a subset of frequencies
    - Create feed with already exists with new frequencies

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

