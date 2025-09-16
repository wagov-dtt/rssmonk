"""Test API endpoints."""

import os
import pytest
from fastapi.testclient import TestClient


def test_create_feed():
    """Test create feed endpoint."""
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

