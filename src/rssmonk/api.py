"""RSS Monk API - Authenticated proxy to Listmonk with RSS processing capabilities."""

import os
from http import HTTPStatus
import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasicCredentials
from rssmonk.shared import settings, security

from rssmonk.core import RSSMonk
from rssmonk.logging_config import get_logger
from rssmonk.models import ErrorResponse
from rssmonk.routes import feeds, operations, subscriptions

logger = get_logger(__name__)



# Configure Swagger UI with actual credentials from environment
swagger_ui_params = {
    "defaultModelsExpandDepth": -1,
    "persistAuthorization": True,
    "preauthorizeBasic": {
        "username": settings.listmonk_admin_username,
        "password": settings.listmonk_admin_password
    }
} if settings.listmonk_admin_password else {
    "defaultModelsExpandDepth": -1,
    "persistAuthorization": True,
}

# FastAPI app with comprehensive OpenAPI configuration
app = FastAPI(
    title="RSS Monk API",
    version="0.2.1",
    description="""
RSS Monk - RSS feed aggregator that turns RSS feeds into email newsletters using Listmonk.

This API provides three main functions:

1. **RSS Monk Core Endpoints** - Feed management with RSS processing logic
   - `/api/feeds` - Manage RSS feeds  
   - `/api/feeds/process` - Process feeds (individual or bulk for cron jobs)

2. **Listmonk Passthrough** - All other `/api/*` requests are passed through to Listmonk with authentication (Requires admin privileges)
   
3. **Public Passthrough** - All other `/api/public/*` requests are passed through to Listmonk without authentication

## Authentication

All `/api/*` endpoints (except `/api/public/*`) require HTTP Basic Authentication validated against your Listmonk instance.
Uses your Listmonk API credentials (username: `api`, password: your API token).

## State Management

RSS Monk uses Listmonk lists as the source of truth:
- Feed metadata stored in list descriptions
- Processing state stored in list tags
- UUID-based deduplication prevents duplicate campaigns
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
            "name": "health",
            "description": "Health and status monitoring",
        },
        {
            "name": "processing",
            "description": "Feed processing and campaign creation",
        },
    ],
    swagger_ui_parameters=swagger_ui_params,
)



async def validate_auth(credentials: HTTPBasicCredentials = Depends(security)) -> tuple[str, str]:
    """Validate credentials against Listmonk API."""
    logger.info(f"Auth attempt: user={credentials.username}, expected_user={settings.listmonk_admin_username}")
    if settings.validate_admin_auth(credentials.username, credentials.password):
        return credentials.username, credentials.password

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.listmonk_url}/api/health",
                auth=httpx.BasicAuth(username=credentials.username, password=credentials.password),
                timeout=10.0
            )
            if response.status_code != HTTPStatus.OK:
                raise HTTPException(
                    status_code=HTTPStatus.UNAUTHORIZED,
                    detail="Invalid credentials",
                    headers={"WWW-Authenticate": "Basic"},
                )
        return credentials.username, credentials.password
    except httpx.RequestError:
        raise HTTPException(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            detail="Listmonk service unavailable"
        )


def get_rss_monk(credentials: tuple[str, str] = Depends(validate_auth)) -> RSSMonk:
    """Get RSS Monk instance with validated credentials."""
    from fastapi.security import HTTPBasicCredentials as HTTPBasicCreds
    username, password = credentials
    return RSSMonk(local_creds=HTTPBasicCreds(username=username, password=password))


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


# Root endpoint
@app.get(
    "/",
    summary="API Information",
    description="Get basic API information and links to documentation"
)
async def root():
    """Root endpoint with API information."""
    return {
        "name": "RSS Monk API",
        "version": "0.2.1",
        "description": "RSS feed aggregator using Listmonk",
        "documentation": "/docs",
        "health_check": "/health"
    }


# Register routers
app.include_router(feeds.router)
app.include_router(subscriptions.router)
app.include_router(operations.router)

# Only include testing routes when RSSMONK_TESTING=1
if os.environ.get("RSSMONK_TESTING") == "1":
    from rssmonk.routes import testing
    app.include_router(testing.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, port=8000, log_level="info")
