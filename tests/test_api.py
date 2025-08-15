"""Test API endpoints."""

import os
import pytest
from fastapi.testclient import TestClient


def test_root_endpoint():
    """Test root endpoint works without authentication."""
    # Set required env var for import
    os.environ['LISTMONK_APITOKEN'] = 'test-token'
    
    from rssmonk.api import app
    client = TestClient(app)
    
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "RSS Monk API"
    assert data["version"] == "2.0.0"


def test_health_endpoint():
    """Test health endpoint works without authentication."""
    os.environ['LISTMONK_APITOKEN'] = 'test-token' 
    os.environ['LISTMONK_URL'] = 'http://localhost:9000'
    
    from rssmonk.api import app
    client = TestClient(app)
    
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
