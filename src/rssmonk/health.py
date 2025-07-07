"""Health check utilities."""

import json
import time
from datetime import datetime, timezone
from typing import Dict, Any

from .logging_config import get_logger
from .http_clients import create_client

logger = get_logger(__name__)


def check_listmonk_health() -> Dict[str, Any]:
    """Check if Listmonk API is healthy."""
    try:
        with create_client() as client:
            start_time = time.time()
            data = client.get("/api/lists")
            response_time = time.time() - start_time
            
            return {
                "status": "healthy",
                "response_time": response_time,
                "lists_count": len(data.get('results', [])),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    except Exception as e:
        logger.error(f"Listmonk health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


def get_feed_metrics() -> Dict[str, Any]:
    """Get basic feed metrics."""
    try:
        with create_client() as client:
            data = client.get("/api/lists")
            lists = data.get('results', [])
            
            # Count RSS feeds (those with frequency tags)
            feed_count = sum(1 for feed_list in lists 
                           if any(tag.startswith('freq:') for tag in feed_list.get('tags', [])))
            
            return {
                "status": "healthy",
                "total_feeds": feed_count,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        logger.error(f"Failed to get feed metrics: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


def get_health_status() -> Dict[str, Any]:
    """Get overall health status."""
    listmonk_health = check_listmonk_health()
    feed_metrics = get_feed_metrics()
    
    overall_status = "healthy"
    if listmonk_health["status"] != "healthy":
        overall_status = "unhealthy"
    elif feed_metrics["status"] != "healthy":
        overall_status = "degraded"
    
    return {
        "overall_status": overall_status,
        "listmonk": listmonk_health,
        "feeds": feed_metrics,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


def main():
    """Health check CLI."""
    health = get_health_status()
    print(json.dumps(health, indent=2))
    
    # Exit with non-zero code if unhealthy
    if health["overall_status"] == "unhealthy":
        exit(1)


if __name__ == "__main__":
    main()
