"""RSS Monk API - Authenticated proxy to Listmonk with RSS processing capabilities."""

from datetime import datetime, timezone
import hmac
from typing import Annotated
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from http import HTTPStatus
import httpx

import sys

from pydantic import BaseModel

from rssmonk.utils import FEED_ACCOUNT_PREFIX, ErrorMessages, make_url_hash, numberfy_subbed_lists    
print("In module products sys.path[0], __package__ ==", sys.path[0], __package__)

from .cache import feed_cache
from .config_manager import FeedConfigManager
from .core import RSSMonk, AdminRSSMonk, Settings
from .logging_config import get_logger
from .models import (
    ApiAccountResponse,
    BulkProcessResponse,
    EmptyResponse,
    ErrorResponse,
    FeedAccountCreateRequest,
    FeedCreateRequest,
    FeedListResponse,
    FeedProcessRequest,
    FeedProcessResponse,
    FeedResponse,
    Frequency,
    HealthResponse,
    PublicSubscribeRequest,
    SubscribeConfirmRequest,
    SubscribeRequest,
    SubscriptionPreferencesRequest,
    SubscriptionPreferencesResponse,
    SubscriptionResponse,
    UnSubscribeRequest,
)

logger = get_logger(__name__)

# Initialize settings and create .env if missing
if Settings.ensure_env_file():
    print("Created .env file with default settings. Please edit LISTMONK_APITOKEN before starting.")

settings = Settings()
security = HTTPBasic()

# Configure Swagger UI with actual credentials from environment
swagger_ui_params = {
    "defaultModelsExpandDepth": -1,
    "persistAuthorization": True,
    "preauthorizeBasic": {
        "username": settings.listmonk_username,
        "password": settings.listmonk_password
    }
} if settings.listmonk_password else {
    "defaultModelsExpandDepth": -1,
    "persistAuthorization": True,
}

# FastAPI app with comprehensive OpenAPI configuration
app = FastAPI(
    title="RSS Monk API",
    version="2.0.0",
    description="""
RSS Monk - RSS feed aggregator that turns RSS feeds into email newsletters using Listmonk.

This API provides three main functions:

1. **RSS Monk Core Endpoints** - Feed management with RSS processing logic
   - `/api/feeds` - Manage RSS feeds  
   - `/api/feeds/process` - Process feeds (individual or bulk for cron jobs)
   - `/api/public/subscribe` - Public subscription without authentication

2. **Listmonk Passthrough** - All other `/api/*` requests are passed through to Listmonk with authentication
   
3. **Public Passthrough** - All other `/api/public/*` requests are passed through to Listmonk without authentication

## Authentication

All `/api/*` endpoints (except `/api/public/*`) require HTTP Basic Authentication validated against your Listmonk instance.
Uses your Listmonk API credentials (username: `api`, password: your API token).

## State Management

RSS Monk uses Listmonk lists as the source of truth:
- Feed metadata stored in list descriptions
- Processing state stored in list tags
- GUID-based deduplication prevents duplicate campaigns
- No persistent state files required
    """,
    contact={
        "name": "RSS Monk",
        "url": "https://github.com/wagov-dtt/rssmonk",
    },
    license_info={
        "name": "MIT License",
        "url": "https://github.com/wagov-dtt/rssmonk/blob/main/LICENSE",
    },
    openapi_tags=[
        {
            "name": "feeds",
            "description": "RSS feed management operations",
        },
        {
            "name": "processing",
            "description": "Feed processing and campaign creation",
        },
        {
            "name": "public",
            "description": "Public endpoints (no authentication required)",
        },
        {
            "name": "health",
            "description": "Health and status monitoring",
        },
        {
            "name": "listmonk-lists",
            "description": "Listmonk list management (passthrough)",
        },
        {
            "name": "listmonk-subscribers",
            "description": "Listmonk subscriber management (passthrough)",
        },
        {
            "name": "listmonk-campaigns",
            "description": "Listmonk campaign management (passthrough)",
        },
    ],
    swagger_ui_parameters=swagger_ui_params,
)

# Dependencies
security = HTTPBasic()

async def validate_auth(credentials: HTTPBasicCredentials = Depends(security)) -> tuple[str, str]:
    """Validate credentials against Listmonk API."""
    try:
        # Test credentials against Listmonk
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.listmonk_url}/api/health",
                auth=httpx.BasicAuth(username=credentials.username, password=credentials.password),
                timeout=10.0
            )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials",
                    headers={"WWW-Authenticate": "Basic"},
                )
        return credentials.username, credentials.password
    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Listmonk service unavailable"
        )

def _validate_admin_auth(credentials: HTTPBasicCredentials) -> bool:
    # Only used as a quick check before going to work against Listmonk.
    # The password with Listmonk may have drifted, but Ops will sync them
    return hmac.compare_digest(credentials.password, settings.listmonk_password)

def get_rss_monk(credentials: tuple[str, str] = Depends(validate_auth)) -> RSSMonk:
    """Get RSS Monk instance with validated credentials."""
    username, password = credentials
    return RSSMonk(local_creds=HTTPBasicCredentials(username=username, password=password))


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with structured error response."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(error=exc.detail).model_dump()
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="Internal server error",
            detail=str(exc)
        ).model_dump()
    )


# RSS Monk Core Endpoints

@app.get(
    "/",
    summary="API Information",
    description="Get basic API information and links to documentation"
)
async def root():
    """Root endpoint with API information."""
    return {
        "name": "RSS Monk API",
        "version": "2.0.0",
        "description": "RSS feed aggregator using Listmonk",
        "documentation": "/docs",
        "health_check": "/health"
    }


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["health"],
    summary="Health Check",
    description="Check the health status of RSS Monk and Listmonk services"
)
async def health_check():
    """Health check endpoint."""
    try:
        # Validate settings without credentials
        test_settings = Settings()
        test_settings.validate_required()
        
        # Test Listmonk connection
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{test_settings.listmonk_url}/api/health", timeout=10.0)
            listmonk_status = "healthy" if response.status_code == 200 else "unhealthy"

        # TODO - Check 

        # Get basic stats (without auth)
        return HealthResponse(
            status="healthy",
            listmonk_status=listmonk_status
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            error=str(e)
        )


@app.get(
    "/api/cache/stats",
    tags=["health"],
    summary="Cache Statistics",
    description="Get RSS feed cache statistics and performance metrics"
)
async def get_cache_stats(credentials: Annotated[HTTPBasicCredentials, Depends(security)]):
    """Get feed cache statistics."""
    # TODO - Check against admin
    return feed_cache.get_stats()


@app.delete(
    "/api/cache",
    tags=["health"], 
    summary="Clear Feed Cache",
    description="Clear all RSS feed cache entries"
)
async def clear_cache(credentials: Annotated[HTTPBasicCredentials, Depends(security)]):
    # TODO - Check that the admin
    """Clear feed cache."""
    feed_cache.clear()
    return {"message": "Feed cache cleared successfully"}


@app.post(
    "/api/feeds",
    response_model=FeedResponse,
    status_code=201,
    tags=["feeds"],
    summary="Create RSS Feed",
    description="Add a new RSS feed for processing and newsletter generation. New frequencies are additive to existing lists"
)
async def create_feed(
    request: FeedCreateRequest,
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
    rss_monk: RSSMonk = Depends(get_rss_monk)
) -> FeedResponse:
    """Create a new RSS feed."""

    if not _validate_admin_auth(credentials=credentials):
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED)

    try:
        with rss_monk:
            feed = rss_monk.add_feed(str(request.url), request.frequency, request.name)
            return FeedResponse(
                id=feed.id,
                name=feed.name,
                url=feed.url,
                frequency=feed.frequencies,
                url_hash=feed.url_hash
            )
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))
    except httpx.HTTPError as e:
        logger.error(f"HTTP create_feed: {e}")
        raise


@app.post(
    "/api/feeds/account",
    response_model=FeedResponse,
    status_code=201,
    tags=["feeds"],
    summary="Create account RSS Feed",
    description="Create a new limited access account to operate on the feed"
)
async def create_feed_account(
    request: FeedAccountCreateRequest,
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
    rss_monk: RSSMonk = Depends(get_rss_monk)
) -> ApiAccountResponse:
    """Create a new account for a RSS feed."""
    # TODO - This is currently not working. Remove 418 once fixed
    raise HTTPException(status_code=HTTPStatus.IM_A_TEAPOT)

    if not _validate_admin_auth(credentials=credentials):
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED)
    
    admin_monk: AdminRSSMonk = AdminRSSMonk(rss_monk.settings.listmonk_password)

    try:
        with rss_monk:
            user = admin_monk.find_api_user(username=f'user_{request.url}')
            if feed is not None:
                raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=f"A user already exists for {request.url}")

            # TODO - Ensure limited role has been created
            admin_monk.create_api_user
            # TODO - Check is account has already been created
            feed = rss_monk.create_user(str(request.url))
            return ApiAccountResponse(
                # TODO
            )
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))
    except httpx.HTTPError as e:
        logger.error(f"HTTP create_feed: {e}")
        raise


@app.get(
    "/api/feeds",
    response_model=FeedListResponse,
    tags=["feeds"],
    summary="List RSS Feeds",
    description="Retrieve all configured RSS feeds with their details"
)
async def list_feeds(
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
    rss_monk: RSSMonk = Depends(get_rss_monk)
) -> FeedListResponse:
    """List all RSS feeds."""
    
    try:
        with rss_monk:
            feeds = rss_monk.list_feeds()
            return FeedListResponse(
                feeds=[
                    FeedResponse(
                        id=feed.id,
                        name=feed.name,
                        url=feed.url,
                        frequency=feed.frequencies,
                        url_hash=feed.url_hash
                    )
                    for feed in feeds
                ],
                total=len(feeds)
            )
    except Exception as e:
        logger.error(f"Failed to list feeds: {e}")
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Failed to retrieve feeds")


@app.get(
    "/api/feeds/by-url",
    response_model=FeedResponse,
    tags=["feeds"],
    summary="Get Feed by URL",
    description="Retrieve a specific RSS feed by its URL"
)
async def get_feed_by_url(
    url: str,
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
    rss_monk: RSSMonk = Depends(get_rss_monk)
) -> FeedResponse:
    """Get feed by URL."""
    try:
        with rss_monk:
            feed = rss_monk.get_feed_by_url(url)
            if not feed:
                raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Feed not found")
            
            return FeedResponse(
                id=feed.id,
                name=feed.name,
                url=feed.url,
                frequency=feed.frequencies,
                url_hash=feed.url_hash
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get feed by URL: {e}")
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Failed to retrieve feed")


@app.delete(
    "/api/feeds/by-url",
    tags=["feeds"],
    summary="Delete Feed by URL",
    description="Remove an RSS feed by its URL"
)
async def delete_feed_by_url(
    url: str,
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
    rss_monk: RSSMonk = Depends(get_rss_monk)
):
    """Delete feed by URL."""

    if not _validate_admin_auth(credentials=credentials):
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED)

    try:
        with rss_monk:
            if rss_monk.delete_feed(url):
                # Invalidate cache for this URL
                feed_cache.invalidate_url(url)
                return {"message": "Feed deleted successfully"}
            else:
                raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Feed not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete feed: {e}")
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Failed to delete feed")


@app.get(
    "/api/feeds/configurations/{url:path}",
    tags=["feeds"],
    summary="Get URL Configurations",
    description="Get all feed configurations for a specific URL"
)
async def get_url_configurations(
    url: str,
    rss_monk: RSSMonk = Depends(get_rss_monk)
):
    # TODO - Not sure what this is for??
    """Get all configurations for a URL."""
    try:
        with rss_monk:
            config_manager = FeedConfigManager(rss_monk)
            configurations = config_manager.get_url_configurations(url)
            return configurations
    except Exception as e:
        logger.error(f"Failed to get URL configurations: {e}")
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Failed to retrieve configurations")


@app.put(
    "/api/feeds/configurations/{url:path}",
    tags=["feeds"],
    summary="Update Feed Configuration",
    description="Update feed configuration for a URL, with optional subscriber migration"
)
async def update_feed_configuration(
    url: str,
    request: FeedCreateRequest,
    rss_monk: RSSMonk = Depends(get_rss_monk)
):
    """Update feed configuration with migration options."""
    try:
        with rss_monk:
            config_manager = FeedConfigManager(rss_monk)
            
            result = config_manager.update_feed_config(
                url=url,
                new_frequency=request.frequency,
                new_name=request.name
            )
            
            # Invalidate cache for this URL
            feed_cache.invalidate_url(url)
            
            return result
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update feed configuration: {e}")
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Failed to update configuration")


@app.post(
    "/api/feeds/process",
    response_model=FeedProcessResponse,
    tags=["processing"],
    summary="Process Single Feed",
    description="Process a specific RSS feed and create email campaigns for new articles"
)
async def process_feed(
    request: FeedProcessRequest,
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
    rss_monk: RSSMonk = Depends(get_rss_monk)
) -> FeedProcessResponse:
    """Process a single RSS feed."""
    try:
        with rss_monk:
            feed = rss_monk.get_feed_by_url(str(request.url))
            if not feed:
                raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Feed not found")
            
            campaigns = rss_monk.process_feed(feed, request.auto_send)
            return FeedProcessResponse(
                feed_name=feed.name,
                campaigns_created=campaigns,
                articles_processed=campaigns  # Assuming 1:1 for now
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process feed: {e}")
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Feed processing failed")


@app.post(
    "/api/feeds/process/bulk/{frequency}",
    response_model=BulkProcessResponse,
    tags=["processing"],
    summary="Process Feeds by Frequency",
    description="Process all RSS feeds of a specific frequency (used by cron jobs)"
)
async def process_feeds_bulk(
    frequency: Frequency,
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
    rss_monk: RSSMonk = Depends(get_rss_monk)
) -> BulkProcessResponse:
    """Process feeds by frequency."""
    try:
        with rss_monk:
            results = rss_monk.process_feeds_by_frequency(frequency)
            total_campaigns = sum(results.values())
            
            return BulkProcessResponse(
                frequency=frequency,
                feeds_processed=len(results),
                total_campaigns=total_campaigns,
                results=results
            )
    except Exception as e:
        logger.error(f"Failed to process feeds bulk: {e}")
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Bulk processing failed")


@app.get(
    "/api/feeds/subscribe-preferences",
    response_model=SubscriptionPreferencesResponse,
    tags=["feeds"],
    summary="Subscribe to a Feed",
    description="Subscribe an email address to an RSS feed. Authentication required"
)
async def feed_get_subscription_preferences(
    request: SubscriptionPreferencesRequest,
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
    rss_monk: RSSMonk = Depends(get_rss_monk)
) -> SubscriptionPreferencesResponse:
    """Get feed subscription user's preferences endpoint."""
    try:
        with rss_monk:
            if not rss_monk._validate_feed_visibility(credentials=credentials, feed_url=str(request.feed_url)):
                raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Not permitted to interact with this feed")

            attribs = rss_monk.get_subscriber_feed_filter(request.email)
            if attribs is not None:
                # Remove feeds not permitted to be seen by the account
                #feed_hash = credentials.username.replace(FEED_ACCOUNT_PREFIX, "").strip() TODO - Fix when account creations is fixed
                feed_hash = make_url_hash(request.feed_url.encoded_string())
                print(attribs)
                if feed_hash in attribs and "filter" in attribs[feed_hash]:
                    return SubscriptionPreferencesResponse(filter=attribs[feed_hash]["filter"]) # TODO - Need to operate as list of dicts
            return SubscriptionPreferencesResponse(filter={})
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Subscription fetch failed: {e}")
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Subscription retrieval failed")


@app.post(
    "/api/feeds/subscribe",
    response_model=SubscriptionResponse,
    tags=["feeds"],
    summary="Subscribe to a Feed",
    description="Subscribe an email address to an RSS feed. Authentication required"
)
async def feed_subscribe(
    request: SubscribeRequest,
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
    rss_monk: RSSMonk = Depends(get_rss_monk)
) -> SubscriptionResponse:
    """Feed subscription endpoint."""
    # This can cover public, or private feeds
    try:
        # Use default settings for public endpoint
        with rss_monk:
            if not rss_monk._validate_feed_visibility(credentials=credentials, feed_url=str(request.feed_url)):
                raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Not permitted to interact with this feed")
            
            rss_monk.subscribe(request.email, str(request.feed_url))
            if request.filter is not None:
                # Add filter to the subscriber
                uuid = rss_monk.update_filter(request.email, str(request.feed_url), request.need_confirm, request.filter)
                if request.need_confirm is not None and request.need_confirm:
                    url_hash = make_url_hash(request.feed_url.encoded_string())
                    base_url = "http://subscribe.dpc.wa.gov.au/confirm" # TODO - Fetch url .... not sure how to get this
                    confirmation_link = f"{base_url}?id={request.email}&guid={uuid}"
                    transaction = {
                        "subscriber_email": request.email,
                        "confirmation_link": confirmation_link,
                    }
                    # Temporarily print out the uuid of the pending subscription to console until email is properly worked on
                    print(f"{{ \"url\": {url_hash}, \"uuid\" {uuid} }} ")
                    # Send email out for the user - # TODO - Use proper values
                    rss_monk._client.make_transactional(transaction, "noreply@noreply", 3)
                    pass
            return SubscriptionResponse(
                message="Subscription successful"
            )
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to subscribe: {e}")
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Subscription failed")

@app.post(
    "/api/feeds/subscribe-confirm",
    response_model=EmptyResponse,
    tags=["feeds"],
    summary="Confirm subscription to a Feed",
    description="Confirm the filtered subscription of an email address to an RSS feed. Authentication required"
)
async def feed_subscribe_confirm(
    request: SubscribeConfirmRequest,
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
    rss_monk: RSSMonk = Depends(get_rss_monk)   
):
    """Feed subscription confirmation endpoint."""
    try:
        # Use default settings for public endpoint
        with rss_monk:
            if not rss_monk._validate_feed_visibility(credentials=credentials, feed_url=str(request.feed_url)):
                raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Not permitted to interact with this feed")

            email = request.email
            sub_list = rss_monk._admin.get_subscribers(query=f"subscribers.email = '{email}'")
            uuid = request.uuid
            subs: dict  = sub_list[0] if sub_list is not None else None
            if not subs or "id" not in subs:
                raise HTTPException(status_code=HTTPStatus.UNPROCESSABLE_CONTENT, detail="Invalid details")

            # Search for subscription for the user
            #feed_hash = credentials.username.replace(FEED_ACCOUNT_PREFIX, "").strip() TODO - Fix when account creations is fixed
            feed_hash = make_url_hash(request.feed_url.encoded_string())
            if feed_hash not in subs["attribs"]:
                raise HTTPException(status_code=HTTPStatus.UNPROCESSABLE_CONTENT, detail="Link has expired")

            feed_attribs = subs["attribs"][feed_hash]
            if uuid not in feed_attribs:
                # Count as expired
                raise HTTPException(status_code=HTTPStatus.UNPROCESSABLE_CONTENT, detail="Link has expired")

            # Expired links are removed from the attributes for one feed
            print(f'{feed_attribs[uuid]['expires']} < {datetime.now(timezone.utc).timestamp()}')
            if feed_attribs[uuid]['expires'] < datetime.now(timezone.utc).timestamp():
                # No deletion will occur here, there will be a cronjob to remove expired pending filters
                raise HTTPException(status_code=HTTPStatus.UNPROCESSABLE_CONTENT, detail="Link has expired")

            # Move filter to feed_attribs
            feed_attribs["filter"] = feed_attribs[uuid]["filter"]
            del subs["attribs"][feed_hash][uuid]
            # Have to covert the extracted lists to be a plain list of numbers to retain subscriptions
            subs["lists"] = numberfy_subbed_lists(subs["lists"])
            # Update the subscriber
            rss_monk._client.update_subscriber(subs["id"], subs)
            return EmptyResponse()
       
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))
    except HTTPException as e:
        raise e # Deliberate reraise
    except Exception as e:
        logger.error(f"Failed to confirm subscription: {e}")
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Subscription confirmation failed")

@app.post(
    "/api/feeds/unsubscribe",
    response_model=EmptyResponse,
    tags=["feeds"],
    summary="Unsubscribes a user from a Feed",
    description="Removes the email address from a RSS feed. Authentication required"
)
async def feed_unsubscribe(
    request: UnSubscribeRequest,
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
    rss_monk: RSSMonk = Depends(get_rss_monk)   
):
    """Feed subscription confirmation endpoint."""
    try:
        # Use default settings for public endpoint
        with rss_monk:
            if not rss_monk._validate_feed_visibility(credentials=credentials, feed_url=str(request.feed_url)):
                raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail=ErrorMessages.NO_AUTH_FEED)

            email = request.email
            sub_list = rss_monk._admin.get_subscribers(query=f"subscribers.email = '{email}'")
            subs: dict  = sub_list[0] if sub_list is not None else None
            if not subs or "id" not in subs:
                raise HTTPException(status_code=HTTPStatus.UNPROCESSABLE_CONTENT, detail="Invalid details")

            # Search for subscription for the user to delete
            #feed_hash = credentials.username.replace(FEED_ACCOUNT_PREFIX, "").strip() TODO - Fix when account creations is done
            feed_hash = make_url_hash(request.feed_url.encoded_string())
            feed_list = rss_monk._client.find_list_by_tag(f'url:{feed_hash}')
            if feed_list is None:
                # Treat as if the subscriber has been removed from the list. 
                if feed_hash in credentials.username:
                    # Log this discrepency. The feed appears to have gome missing, with the account linked to it, still existing
                    logger.warning("Non existent feed (hash: %s) access with user account %s. Possible misconfiguration", feed_hash, credentials.username)
                return EmptyResponse()
            feed_data = rss_monk._parse_feed_from_list(feed_list)

            # Remove list from subscriber's list
            subs_lists = numberfy_subbed_lists(subs["lists"])
            if feed_data.id in subs_lists:
                subs_lists.remove(feed_data.id)
            subs["lists"] = subs_lists

            # Remove subscription filters from the subscriber
            if feed_hash in subs["attribs"]:
                del subs["attribs"][feed_hash]

            # Update the subscriber
            rss_monk._client.update_subscriber(subs["id"], subs)
            return EmptyResponse()
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))
    except HTTPException as e:
        raise e # Deliberate reraise
    except Exception as e:
        logger.error(f"Failed to confirm subscription: {e}")
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Unsubscribe failed")


@app.post(
    "/api/public/subscribe",
    response_model=SubscriptionResponse,
    tags=["public"],
    summary="Public Subscribe to Feed",
    description="Subscribe an email address to an RSS feed (no authentication required)"
)
async def public_subscribe(request: PublicSubscribeRequest) -> SubscriptionResponse:
    """Public subscription endpoint."""
    # No filters enabled.
    try:
        # Use default settings for public endpoint
        with RSSMonk() as rss_monk:
            rss_monk.subscribe(request.email, str(request.feed_url))
            return SubscriptionResponse(
                message="Subscription successful"
            )
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to subscribe: {e}")
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Subscription failed")


# Listmonk Passthrough Logic

@app.api_route(
    "/api/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    tags=["listmonk-passthrough"],
    summary="Listmonk API Passthrough",
    description="Pass authenticated requests to Listmonk API",
    include_in_schema=False  # Don't include in main schema to avoid clutter
)
async def listmonk_passthrough(
    request: Request,
    path: str,
    auth: tuple[str, str] = Depends(validate_auth)
):
    print(f"{path} at /api")
    """Passthrough authenticated requests to Listmonk API."""
    # TODO - FastAPI doesn't need this code snipper, this should be handled with positioning of functions.
    # Skip our own endpoints
    # if path in ["feeds", "feeds/process", "feeds/process/bulk", "public/subscribe"] or path.startswith("feeds/"):
    #    raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not found")
    
    username, password = auth
    print(password)
    
    try:
        async with httpx.AsyncClient() as client:
            # Forward the request to Listmonk
            url = f"{settings.listmonk_url}/api/{path}"
            
            # Get request body if present
            body = None
            if request.method in ["POST", "PUT", "PATCH"]:
                body = await request.body()
            
            response = await client.request(
                method=request.method,
                url=url,
                params=request.query_params,
                content=body,
                headers={
                    "Content-Type": request.headers.get("Content-Type", "application/json"),
                    "Accept": request.headers.get("Accept", "application/json"),
                },
                auth=httpx.BasicAuth(username=username, password=password),
                timeout=30.0
            )
            
            # Return the Listmonk response
            return JSONResponse(
                status_code=response.status_code,
                content=response.json() if response.content else None,
                headers={"Content-Type": "application/json"}
            )
            
    except httpx.RequestError as e:
        logger.error(f"Listmonk passthrough error: {e}")
        raise HTTPException(
            status_code=503,
            detail="Listmonk service unavailable"
        )


@app.api_route(
    "/api/public/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    tags=["public"],
    summary="Public Listmonk API Passthrough",
    description="Pass public requests to Listmonk API without authentication",
    include_in_schema=False  # Don't include in main schema
)
async def public_listmonk_passthrough(
    request: Request,
    path: str
):
    """Passthrough public requests to Listmonk API without authentication."""
    # Skip our own endpoint
    if path == "subscribe":
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Not found")
    
    try:
        async with httpx.AsyncClient() as client:
            # Forward the request to Listmonk
            url = f"{settings.listmonk_url}/api/public/{path}"
            
            # Get request body if present
            body = None
            if request.method in ["POST", "PUT", "PATCH"]:
                body = await request.body()
            
            response = await client.request(
                method=request.method,
                url=url,
                params=request.query_params,
                content=body,
                headers={
                    "Content-Type": request.headers.get("Content-Type", "application/json"),
                    "Accept": request.headers.get("Accept", "application/json"),
                },
                timeout=30.0
            )
            
            # Return the Listmonk response
            return JSONResponse(
                status_code=response.status_code,
                content=response.json() if response.content else None,
                headers={"Content-Type": "application/json"}
            )
            
    except httpx.RequestError as e:
        logger.error(f"Public Listmonk passthrough error: {e}")
        raise HTTPException(
            status_code=503,
            detail="Listmonk service unavailable"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, port=8000, log_level="info")
