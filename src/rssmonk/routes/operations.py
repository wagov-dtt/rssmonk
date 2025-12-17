"""Operational endpoints - feed processing, health checks, metrics, cache management."""

from http import HTTPStatus
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import httpx

from rssmonk.cache import feed_cache
from rssmonk.core import RSSMonk, Settings
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
security = HTTPBasic()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check the health status of RSS Monk and Listmonk services"
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
    "/metrics",
    response_model=str,
    summary="Obtain metrics (Admin only)",
    description="Obtain metrics about RSSMonk (Admin only)"
)
async def get_metrics(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    """Get Prometheus metrics."""
    settings = Settings()
    if not settings.validate_admin_auth(credentials.username, credentials.password):
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED)

    raise HTTPException(status_code=HTTPStatus.NOT_IMPLEMENTED)


@router.get(
    "/api/cache/stats",
    summary="Cache Statistics",
    description="Get RSS feed cache statistics and performance metrics"
)
async def get_cache_stats(credentials: HTTPBasicCredentials = Depends(security)):
    """Get feed cache statistics."""
    settings = Settings()
    if not settings.validate_admin_auth(credentials.username, credentials.password):
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED)

    return feed_cache.get_stats()


@router.delete(
    "/api/cache",
    summary="Clear Feed Cache",
    description="Clear all RSS feed cache entries"
)
async def clear_cache(credentials: HTTPBasicCredentials = Depends(security)):
    """Clear feed cache."""
    settings = Settings()
    if not settings.validate_admin_auth(credentials.username, credentials.password):
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED)

    feed_cache.clear()
    return {"message": "Feed cache cleared successfully"}


@router.post(
    "/api/feeds/process",
    response_model=FeedProcessResponse,
    summary="Process Single Feed",
    description="Manually process a single RSS feed and send emails. Admin only."
)
async def process_feed(
    request: FeedProcessRequest,
    credentials: HTTPBasicCredentials = Depends(security)
) -> FeedProcessResponse:
    """Process a single feed."""
    settings = Settings()
    if not settings.validate_admin_auth(credentials.username, credentials.password):
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
                notifications_sent=notifications_sent
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
    description="Process all RSS feeds of a specific frequency (used by cron jobs). Admin only."
)
async def process_feeds_bulk(
    frequency: Frequency,
    credentials: HTTPBasicCredentials = Depends(security)
) -> BulkProcessResponse:
    """Process feeds by frequency."""
    settings = Settings()
    if not settings.validate_admin_auth(credentials.username, credentials.password):
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED)

    try:
        rss_monk = RSSMonk(local_creds=credentials)
        with rss_monk:
            results = await rss_monk.process_feeds_by_frequency(frequency)
            total_emails_sent = sum(results.values())

            return BulkProcessResponse(
                frequency=frequency,
                feeds_processed=len(results),
                total_emails_sent=total_emails_sent,
                results=results
            )
    except Exception as e:
        logger.error("Failed to process feeds bulk: %s", e)
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Bulk processing failed")
