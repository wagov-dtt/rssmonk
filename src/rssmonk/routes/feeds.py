"""Feed management endpoints - CRUD, templates, and accounts."""

from http import HTTPStatus
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import httpx

from rssmonk.core import RSSMonk, Settings
from rssmonk.logging_config import get_logger
from rssmonk.cache import feed_cache
from rssmonk.config_manager import FeedConfigManager
from rssmonk.models import (
    ApiAccountResponse,
    CreateTemplateRequest,
    DeleteTemplateAdminRequest,
    DeleteTemplateRequest,
    FeedAccountConfigurationRequest,
    FeedAccountPasswordResetRequest,
    FeedAccountRequest,
    FeedCreateRequest,
    FeedDeleteRequest,
    FeedListResponse,
    FeedResponse,
    ListmonkTemplate,
    TemplateResponse,
)
from rssmonk.types import FEED_ACCOUNT_PREFIX
from rssmonk.utils import (
    get_feed_hash_from_username,
    make_api_username,
    make_template_name,
    make_url_hash,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/feeds", tags=["feeds"])
security = HTTPBasic()


@router.post(
    "",
    response_model=FeedResponse,
    status_code=HTTPStatus.CREATED,
    summary="Create RSS Feed (Admin only)",
    description="Add a new RSS feed for processing and newsletter generation. New frequencies are additive to existing lists. Admin only."
)
async def create_feed(
    request: FeedCreateRequest,
    credentials: HTTPBasicCredentials = Depends(security)
) -> FeedResponse:
    """Create a new RSS feed."""
    settings = Settings()
    if not settings.validate_admin_auth(credentials.username, credentials.password):
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED)

    try:
        rss_monk = RSSMonk(local_creds=credentials)
        with rss_monk:
            feed = rss_monk.add_feed(
                str(request.feed_url),
                str(request.email_base_url),
                request.poll_frequencies,
                request.name,
                request.visibility
            )
            return FeedResponse(
                id=feed.id,
                name=feed.name,
                feed_url=feed.feed_url,
                email_base_url=feed.email_base_url,
                poll_frequencies=feed.poll_frequencies,
                url_hash=feed.url_hash
            )
    except ValueError as e:
        logger.error(f"ValueError in create_feed: {e}")
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (401, 403):
            raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Invalid credentials")
        logger.error(f"HTTP create_feed: {e}")
        raise
    except httpx.HTTPError as e:
        logger.error(f"HTTP create_feed: {e}")
        raise


@router.get(
    "",
    response_model=FeedListResponse,
    summary="List RSS Feeds",
    description="Retrieve all configured RSS feeds with their details"
)
async def list_feeds(
    credentials: HTTPBasicCredentials = Depends(security)
) -> FeedListResponse:
    """List all RSS feeds."""
    try:
        rss_monk = RSSMonk(local_creds=credentials)
        with rss_monk:
            feeds = rss_monk.list_feeds()
            return FeedListResponse(
                feeds=[
                    FeedResponse(
                        id=feed.id,
                        name=feed.name,
                        feed_url=feed.feed_url,
                        email_base_url=feed.email_base_url,
                        poll_frequencies=feed.poll_frequencies,
                        url_hash=feed.url_hash
                    )
                    for feed in feeds
                ],
                total=len(feeds)
            )
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (401, 403):
            raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Invalid credentials")
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Failed to retrieve feeds")
    except Exception as e:
        if "401" in str(e) or "403" in str(e) or "Unauthorized" in str(e) or "Forbidden" in str(e):
            raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Invalid credentials")
        logger.error(f"Failed to list feeds: {e}")
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Failed to retrieve feeds")


@router.get(
    "/by-url",
    response_model=FeedResponse,
    summary="Get Feed by URL",
    description="Retrieve a specific RSS feed by its URL"
)
async def get_feed_by_url(
    feed_url: str,
    credentials: HTTPBasicCredentials = Depends(security)
) -> FeedResponse:
    """Get feed by URL."""
    try:
        rss_monk = RSSMonk(local_creds=credentials)
        with rss_monk:
            feed = rss_monk.get_feed_by_url(feed_url)
            if not feed:
                raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Feed not found")
            return FeedResponse(
                id=feed.id,
                name=feed.name,
                feed_url=feed.feed_url,
                email_base_url=feed.email_base_url,
                poll_frequencies=feed.poll_frequencies,
                url_hash=feed.url_hash
            )
    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (401, 403):
            raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Invalid credentials")
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Failed to retrieve feed")
    except Exception as e:
        if "401" in str(e) or "403" in str(e) or "Unauthorized" in str(e) or "Forbidden" in str(e):
            raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Invalid credentials")
        logger.error(f"Failed to get feed by URL: {e}")
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Failed to retrieve feed")


@router.delete(
    "/by-url",
    summary="Delete Feed by URL (Admin only)",
    description="Remove an RSS feed by its URL. Admin only."
)
async def delete_feed_by_url(
    request: FeedDeleteRequest,
    credentials: HTTPBasicCredentials = Depends(security)
):
    """Delete feed by URL."""
    settings = Settings()
    if not settings.validate_admin_auth(credentials.username, credentials.password):
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED)

    try:
        rss_monk = RSSMonk(local_creds=credentials)
        with rss_monk:
            feed_hash = make_url_hash(str(request.feed_url))
            feed_data = rss_monk.get_feed_by_hash(feed_hash)
            if feed_data is not None:
                subscriber_list = rss_monk._client.get_all_feed_subscribers(feed_data.id)
            else:
                subscriber_list = []

            if rss_monk.delete_feed(str(request.feed_url)):
                feed_cache.invalidate_url(str(request.feed_url))
                for subscriber in subscriber_list:
                    rss_monk.remove_subscriber_filter(subscriber["email"], feed_hash)
                rss_monk.delete_list_role(str(request.feed_url))
                rss_monk.delete_feed_templates(str(request.feed_url))
                return {"message": "Feed deleted successfully"}
            else:
                raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Feed not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete feed: {e}")
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Failed to delete feed")


@router.get(
    "/configurations",
    summary="Get URL Configurations",
    description="Get all feed configurations for a specific URL"
)
async def get_url_configurations(
    request: FeedAccountConfigurationRequest,
    credentials: HTTPBasicCredentials = Depends(security)
):
    """Get all configurations for a URL."""
    try:
        rss_monk = RSSMonk(local_creds=credentials)
        with rss_monk:
            config_manager = FeedConfigManager(rss_monk)
            return config_manager.get_url_configurations(request.feed_url)
    except Exception as e:
        logger.error(f"Failed to get URL configurations: {e}")
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Failed to retrieve configurations")


@router.put(
    "/configurations",
    summary="Update Feed Configuration",
    description="Update feed configuration for a URL"
)
async def update_feed_configuration(
    request: FeedCreateRequest,
    credentials: HTTPBasicCredentials = Depends(security)
):
    """Update feed configuration."""
    try:
        rss_monk = RSSMonk(local_creds=credentials)
        with rss_monk:
            config_manager = FeedConfigManager(rss_monk)
            result = config_manager.update_feed_config(
                url=request.feed_url,
                new_frequency=request.poll_frequencies,
                new_name=request.name
            )
            feed_cache.invalidate_url(str(request.feed_url))
            return result
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update feed configuration: {e}")
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Failed to update configuration")


@router.post(
    "/templates",
    response_model=TemplateResponse,
    status_code=HTTPStatus.CREATED,
    summary="Create email templates for RSS Feed",
    description="Creates or updates email templates for RSS feed for newsletter generation."
)
async def create_template(
    request: CreateTemplateRequest,
    credentials: HTTPBasicCredentials = Depends(security)
) -> TemplateResponse:
    """Create or update a template."""
    try:
        rss_monk = RSSMonk(local_creds=credentials)
        with rss_monk:
            feed_hash = make_url_hash(str(request.feed_url))
            rss_monk.validate_feed_visibility(feed_hash)
            template_name = make_template_name(feed_hash, request.phase_type)
            new_subject = request.subject if request.subject is not None else "{{ .Tx.Data.subject }}"
            template_response = rss_monk.add_update_template(
                feed_hash,
                request.phase_type,
                ListmonkTemplate(
                    name=template_name,
                    body=request.body,
                    body_source=request.body_source,
                    subject=new_subject
                )
            )
            return TemplateResponse(
                id=template_response["id"],
                name=template_name,
                subject=request.subject,
                type="tx",
                body=request.body,
                body_source=request.body_source,
                is_default=False
            )
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (401, 403):
            raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Invalid credentials")
        logger.error(f"HTTP create_template: {e}")
        raise
    except httpx.HTTPError as e:
        logger.error(f"HTTP create_template: {e}")
        raise


@router.delete(
    "/templates",
    status_code=200,
    summary="Delete email template for RSS Feed",
    description="Delete email templates for RSS feed."
)
async def delete_feed_template(
    request: DeleteTemplateRequest | DeleteTemplateAdminRequest,
    credentials: HTTPBasicCredentials = Depends(security)
):
    """Delete a template."""
    settings = Settings()
    rss_monk = RSSMonk(local_creds=credentials)
    with rss_monk:
        feed_hash = None
        is_valid_admin = settings.validate_admin_auth(credentials.username, credentials.password)
        if isinstance(request, DeleteTemplateAdminRequest):
            if not is_valid_admin:
                raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED)
            feed_hash = make_url_hash(str(request.feed_url))
        else:
            if is_valid_admin:
                raise HTTPException(status_code=HTTPStatus.UNPROCESSABLE_ENTITY, detail="")
            feed_hash = get_feed_hash_from_username(credentials.username)
        rss_monk.validate_feed_visibility(feed_hash)

        try:
            return rss_monk.delete_template(feed_hash, request.phase_type)
        except ValueError as e:
            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Invalid credentials")
            logger.error(f"HTTP delete_template: {e}")
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP delete_template: {e}")
            raise


@router.post(
    "/account",
    response_model=ApiAccountResponse,
    status_code=HTTPStatus.CREATED,
    summary="Create account for RSS Feed (Admin only)",
    description="Create a new limited access account to operate on the feed. Admin only."
)
async def create_feed_account(
    request: FeedAccountRequest,
    credentials: HTTPBasicCredentials = Depends(security)
) -> ApiAccountResponse:
    """Create a new account for a RSS feed."""
    settings = Settings()
    if not settings.validate_admin_auth(credentials.username, credentials.password):
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED)

    try:
        rss_monk = RSSMonk(local_creds=credentials)
        with rss_monk:
            feed_url = str(request.feed_url)
            account_name = make_api_username(feed_url)
            user_role_id = rss_monk.ensure_limited_user_role_exists()
            list_role_id = rss_monk.ensure_list_role_by_url(feed_url)

            user_data = rss_monk.get_user_by_name(account_name)
            if user_data is not None:
                raise HTTPException(
                    status_code=HTTPStatus.CONFLICT,
                    detail=f"A user already exists for {request.feed_url}"
                )

            api_user = rss_monk.create_api_user(account_name, user_role_id, list_role_id)
            return ApiAccountResponse(
                id=api_user["id"],
                name=account_name,
                api_password=api_user["password"]
            )
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (401, 403):
            raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Invalid credentials")
        logger.error(f"HTTP create_feed_account: {e}")
        raise
    except httpx.HTTPError as e:
        logger.error(f"HTTP create_feed_account: {e}")
        raise


@router.post(
    "/account-reset-password",
    response_model=ApiAccountResponse,
    status_code=HTTPStatus.CREATED,
    summary="Reset password for RSS Feed account (Admin only)",
    description="Resets the password for a RSS Feed account. Admin only."
)
async def reset_feed_account_password(
    request: FeedAccountPasswordResetRequest,
    credentials: HTTPBasicCredentials = Depends(security)
) -> ApiAccountResponse:
    """Reset the password for a RSS feed account."""
    settings = Settings()
    if not settings.validate_admin_auth(credentials.username, credentials.password):
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED)

    try:
        rss_monk = RSSMonk(local_creds=credentials)
        with rss_monk:
            if rss_monk.get_user_by_name(request.account_name) is None:
                raise HTTPException(
                    status_code=HTTPStatus.NOT_FOUND,
                    detail=f"{request.account_name} not found."
                )

            # Delete existing user first (Listmonk only returns token on creation)
            rss_monk.delete_api_user(request.account_name)

            user_role_id = rss_monk.ensure_limited_user_role_exists()
            list_role_id = rss_monk.ensure_list_role_by_hash(
                request.account_name.replace(FEED_ACCOUNT_PREFIX, "")
            )

            api_user = rss_monk.create_api_user(request.account_name, user_role_id, list_role_id)
            return ApiAccountResponse(
                id=api_user["id"],
                name=request.account_name,
                api_password=api_user["password"]
            )
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (401, 403):
            raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Invalid credentials")
        logger.error(f"HTTP reset_feed_account_password: {e}")
        raise
    except httpx.HTTPError as e:
        logger.error(f"HTTP reset_feed_account_password: {e}")
        raise
