"""Operational endpoints - feed processing, health checks, metrics, cache management."""

from http import HTTPStatus
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPBasicCredentials
from rssmonk.shared import Settings, security, get_settings
import httpx
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from rssmonk.cache import feed_cache, template_cache
from rssmonk.core import RSSMonk
from rssmonk.logging_config import get_logger
from rssmonk.models import (
    BulkProcessResponse,
    FeedProcessRequest,
    FeedProcessResponse,
    Frequency,
    HealthResponse,
)

logger = get_logger(__name__)
router = APIRouter(tags=["health", "processing"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check the health status of RSS Monk and Listmonk services",
)
async def health_check() -> HealthResponse:
    """Check service health."""
    try:
        test_settings = Settings()
        test_settings.validate_required()

        async with httpx.AsyncClient() as client:
            # Check root URL - /api/health requires auth but root page is public
            response = await client.get(test_settings.listmonk_url, timeout=10.0)
            listmonk_status = "healthy" if response.status_code == 200 else "unhealthy"

        return HealthResponse(status="healthy", listmonk_status=listmonk_status)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(status="unhealthy", error=str(e))


@router.get(
    "/metrics", response_model=str, summary="Obtain metrics (Admin)", description="Obtain metrics about RSSMonk (Admin)"
)
async def get_metrics(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    """Get Prometheus metrics."""
    if not get_settings().validate_admin_auth(credentials.username, credentials.password):
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED)

    try:
        # Return metrics page
        data = generate_latest()  # TODO - This appears to also generates extra metrics (such as _created)

        # TODO - Append subsciber_count from /api/lists for each list

        return Response(content=data, media_type=CONTENT_TYPE_LATEST)
    except Exception as e:
        logger.error(f"Metric check failed: {e}")


@router.get("/api/cache/stats", summary="Cache Statistics", description="Get RSS feed and template cache statistics")
async def get_cache_stats(credentials: HTTPBasicCredentials = Depends(security)):
    """Get cache statistics for feeds and templates."""
    if not get_settings().validate_admin_auth(credentials.username, credentials.password):
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED)

    return {
        "feeds": feed_cache.get_stats(),
        "templates": template_cache.get_stats(),
    }


@router.delete("/api/cache", summary="Clear All Caches", description="Clear RSS feed and template cache entries")
async def clear_cache(credentials: HTTPBasicCredentials = Depends(security)):
    """Clear all caches."""
    if not get_settings().validate_admin_auth(credentials.username, credentials.password):
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED)

    feed_cache.clear()
    template_cache.clear()
    return {"message": "All caches cleared successfully"}


@router.post(
    "/api/feeds/process",
    response_model=FeedProcessResponse,
    summary="Process Single Feed",
    description="Manually process a single RSS feed and send emails. Administrator privileges required.",
)
async def process_feed(
    request: FeedProcessRequest, credentials: HTTPBasicCredentials = Depends(security)
) -> FeedProcessResponse:
    """Process a single feed."""
    if not get_settings().validate_admin_auth(credentials.username, credentials.password):
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED)

    try:
        rss_monk = RSSMonk(local_creds=credentials)
        with rss_monk:
            feed = rss_monk.get_feed_by_url(str(request.feed_url))
            if not feed:
                raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Feed not found")

            notifications_sent, articles_found = await rss_monk.process_feed(feed, request.frequency)
            return FeedProcessResponse(
                feed_name=feed.name,
                frequency=request.frequency,
                articles_processed=articles_found,
                notifications_sent=notifications_sent,
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to process feed: %s", e)
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Feed processing failed")


@router.post(
    "/api/feeds/process/bulk/{frequency}",
    response_model=BulkProcessResponse,
    summary="Process Feeds by Frequency",
    description="Process all RSS feeds of a specific frequency (used by cron jobs). Administrator privileges required.",
)
async def process_feeds_bulk(
    frequency: Frequency, credentials: HTTPBasicCredentials = Depends(security)
) -> BulkProcessResponse:
    """Process feeds by frequency."""
    if not get_settings().validate_admin_auth(credentials.username, credentials.password):
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED)

    try:
        rss_monk = RSSMonk(local_creds=credentials)
        with rss_monk:
            results = await rss_monk.process_feeds_by_frequency(frequency)
            total_emails_sent = sum(results.values())

            return BulkProcessResponse(
                frequency=frequency, feeds_processed=len(results), total_emails_sent=total_emails_sent, results=results
            )
    except Exception as e:
        logger.error("Failed to process feeds bulk: %s", e)
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Bulk processing failed")
