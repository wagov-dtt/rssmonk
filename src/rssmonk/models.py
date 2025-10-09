"""Pydantic models for RSS Monk API."""

from enum import Enum
import hashlib
from typing import Any, Optional

from pydantic import BaseModel, Field, HttpUrl

from rssmonk.utils import LIST_DESC_FEED_URL, MULTIPLE_FREQ, SUB_BASE_URL, EmailType

# Data Type Models

# Feed frequency configurations
def AVAILABLE_FREQUENCY_SETTINGS() -> dict[str, dict[str, Any]]:
    return {
        "freq:instant": {
            "interval_minutes": 5,
            "check_time": None,
            "check_day": None,
            "description": "Every 5 minutes",
        },
        "freq:daily": {
            "interval_minutes": None,
            "check_time": (17, 0),  # 5pm
            "check_day": None,
            "description": "Daily at 5pm",
        },
        "freq:weekly": {
            "interval_minutes": None,
            "check_time": (17, 0),  # 5pm
            "check_day": 4,  # Friday
            "description": "Weekly on Friday at 5pm",
        },
    }

class ListVisibilityType(str, Enum):
    """List visibility type."""
    PUBLIC = "public"
    PRIVATE = "private"

class Frequency(str, Enum):
    """Polling frequencies."""
    INSTANT = "instant"
    DAILY = "daily"
    WEEKLY = "weekly"

class Feed(BaseModel):
    """RSS feed model."""

    id: Optional[int] = None
    name: str
    feed_url: str
    subscription_base_url: str
    """Feed subscription base URL This may or may not be different to the link field in the RSS"""
    frequencies: list[Frequency]
    url_hash: str = ""
    mult_freq: bool = False

    def __init__(self, **data):
        super().__init__(**data)
        if not self.url_hash:
            self.url_hash = hashlib.sha256(self.feed_url.encode()).hexdigest()

    @property
    def tags(self) -> list[str]:
        """Generate Listmonk tags."""
        return [f'freq:{x.value}' for x in self.frequencies] + [f"url:{self.url_hash}"]

    @property
    def description(self) -> str:
        """Generate Listmonk description."""
        return f"{LIST_DESC_FEED_URL} {self.feed_url}\n{SUB_BASE_URL} {self.subscription_base_url}"
        # TODO - Need to determine how multiple frequency filters are stored. It may never be used. Default to false
        #return f"{LIST_DESC_FEED_URL} {self.feed_url}\n{SUB_BASE_URL} {self.subscription_base_url}\n{MULTIPLE_FREQ} {str(self.mult_freq)}"

class ListmonkTemplate(BaseModel):
    """Template data model for Listmonk"""
    id: Optional[int] = None
    name: str
    subject: Optional[str] = None
    type: str = "tx"
    body: str
    body_source: Optional[str] = None
    is_default: bool = False

class Subscriber(BaseModel):
    """Subscriber model."""

    id: Optional[int] = None
    email: str
    name: str = ""
    attribs: Optional[dict] = None

    def __init__(self, **data):
        super().__init__(**data)
        if not self.name:
            self.name = self.email

class EmailTemplate(BaseModel):
    """Email template data store"""
    name: str
    subject: str
    body: str


# Request Models

class FeedCreateRequest(BaseModel):
    """Request model for creating an RSS feed."""
    feed_url: HttpUrl = Field(..., description="RSS feed URL")
    subscription_base_url: HttpUrl = Field(..., description="Feed subscription base URL")
    frequency: list[Frequency] = Field(..., description="Polling frequency")
    name: Optional[str] = Field(None, description="Feed name (auto-detected if not provided)")
    visibility: Optional[ListVisibilityType] = Field(ListVisibilityType.PRIVATE, description="RSS feed visibility. Default to private")

class FeedAccountConfigurationRequest(BaseModel):
    """Request model for obtaining the configuration from a RSS feed."""
    feed_url: HttpUrl = Field(..., description="RSS feed URL")

class FeedAccountRequest(BaseModel):
    """Request model for creating an account for a RSS feed."""
    feed_url: HttpUrl = Field(..., description="RSS feed URL")

class FeedProcessRequest(BaseModel):
    """Request model for processing a specific feed."""
    feed_url: HttpUrl = Field(..., description="RSS feed URL to process")
    auto_send: bool = Field(False, description="Automatically send created campaigns")

class TemplateRequest(BaseModel):
    """Request model for creating a template for a RSS feed."""
    feed_url: HttpUrl = Field(..., description="RSS feed URL to process")
    phase_type: EmailType = Field(..., description="The email template subject line")
    type: str = Field(..., description="Type of the template (campaign, campaign_visual, or tx)")
    subject: Optional[str] = Field(None, description="The email template subject line")
    body_source: Optional[str] = Field(None, description="If type is campaign_visual, the JSON source for the email-builder tempalate")
    body: str = Field(..., description="HTML body of the template")

class PublicSubscribeRequest(BaseModel):
    """Request model for public subscription endpoint and no filter."""
    email: str = Field(..., description="Subscriber email address")
    feed_url: HttpUrl = Field(..., description="RSS feed URL to subscribe to")

class SubscribeRequest(BaseModel):
    """Request model for a subscription endpoint with a filter and email confirmation."""
    email: str = Field(..., description="Subscriber email address")
    feed_url: HttpUrl = Field(..., description="RSS feed URL to subscribe to")
    filter: Optional[dict[Frequency, list[str] | dict]] = Field(..., description="The filter as JSON")
    need_confirm: Optional[bool] = Field(True, description="Store filter in a temporary setting and email user")

class SubscriptionPreferencesRequest(BaseModel):
    """Request model for a subscription endpoint with filters for the feed."""
    email: str = Field(..., description="Subscriber email address")
    feed_url: HttpUrl = Field(..., description="RSS feed URL to subscribe to")

class SubscribeConfirmRequest(BaseModel):
    """Request model for a subscription confirmation endpoint."""
    email: str = Field(..., description="Subscriber email address")
    uuid: str = Field(..., description="The uuid of the new subscription filters to confirm as active")
    feed_url: HttpUrl = Field(..., description="RSS feed URL to subscribe to")

class UnSubscribeRequest(BaseModel):
    """Response model for a subscription preferences (filter)."""
    email: str = Field(..., description="Subscriber email address")
    feed_url: HttpUrl = Field(..., description="RSS feed URL to get filters for")

# Response Models

class EmptyResponse(BaseModel):
    pass

class FeedResponse(BaseModel):
    """Response model for RSS feed information."""
    id: int = Field(..., description="Listmonk list ID")
    name: str = Field(..., description="Feed name")
    feed_url: str = Field(..., description="RSS feed URL")
    subscription_base_url: HttpUrl = Field(..., description="Feed subscription base URL")
    frequency: list[Frequency] = Field(..., description="Polling frequency")
    url_hash: str = Field(..., description="SHA-256 hash of the URL")
    subscriber_count: Optional[int] = Field(None, description="Number of subscribers")


class FeedListResponse(BaseModel):
    """Response model for listing RSS feeds."""
    feeds: list[FeedResponse] = Field(..., description="list of RSS feeds")
    total: int = Field(..., description="Total number of feeds")


class FeedProcessResponse(BaseModel):
    """Response model for feed processing."""
    feed_name: str = Field(..., description="Name of processed feed")
    campaigns_created: int = Field(..., description="Number of campaigns created")
    articles_processed: int = Field(..., description="Number of articles processed")


class TemplateResponse(BaseModel):
    """Response model for a template RSS feed."""
    id: int = Field(..., description="ID of the template")
    name: str = Field(..., description="Name of the template")
    subject: Optional[str] = Field(..., description="The email template subject line")
    type: str = Field(..., description="Type of the template (campaign, campaign_visual, or tx)")
    body: str = Field(..., description="HTML body of the template")
    body_source: Optional[str] = Field(..., description="If type is campaign_visual, the JSON source for the email-builder tempalate")
    is_default: bool = Field(..., description="RSS feed URL")


class ApiAccountResponse(BaseModel):
    """Response model for feed accounts."""
    id: int = Field(..., description="Account ID")
    name: str = Field(..., description="Account name")
    api_password: str = Field(..., description="Password that is generated for the API account and never revealed again")


class BulkProcessResponse(BaseModel):
    """Response model for bulk feed processing."""
    frequency: Frequency = Field(..., description="Processed frequency")
    feeds_processed: int = Field(..., description="Number of feeds processed")
    total_campaigns: int = Field(..., description="Total campaigns created")
    results: dict[str, int] = Field(..., description="Per-feed campaign counts")


class SubscriptionPreferencesResponse(BaseModel):
    """Request model for a subscription endpoint with filters for the feed."""
    filter: dict = Field(..., description="The filter as JSON, or empty for no filters")

class SubscriptionResponse(BaseModel):
    """Response model for subscription operations."""
    message: str = Field(..., description="Success message")
    subscriber_id: Optional[int] = Field(None, description="Subscriber ID")
    feed_id: Optional[int] = Field(None, description="Feed list ID")


class HealthResponse(BaseModel):
    """Response model for health check."""
    
    status: str = Field(..., description="Service status")
    feeds_count: Optional[int] = Field(None, description="Total number of feeds")
    subscribers_count: Optional[int] = Field(None, description="Total number of subscribers")
    listmonk_status: Optional[str] = Field(None, description="Listmonk connection status")
    error: Optional[str] = Field(None, description="Error message if unhealthy")


class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    code: Optional[str] = Field(None, description="Error code")


# Listmonk Passthrough Models

class ListmonkList(BaseModel):
    """Listmonk list model for passthrough."""
    id: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    uuid: Optional[str] = None
    name: str
    type: str = "public"
    optin: str = "single" 
    tags: list[str] = []
    description: Optional[str] = ""
    subscriber_count: Optional[int] = None


class ListmonkSubscriber(BaseModel):
    """Listmonk subscriber model for passthrough."""
    id: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    uuid: Optional[str] = None
    email: str
    name: str
    status: str = "enabled"
    lists: list[int] = []
    attribs: dict[str, Any] = {}
    preconfirm_subscriptions: bool = True


class ListmonkCampaign(BaseModel):
    """Listmonk campaign model for passthrough."""
    id: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    uuid: Optional[str] = None
    name: str
    subject: str
    body: str
    type: str = "regular"
    content_type: str = "html"
    status: str = "draft"
    tags: list[str] = []
    lists: list[int] = []
    started_at: Optional[str] = None
    to_send: Optional[int] = None
    sent: Optional[int] = None

# Listmonk Response Models


class ListmonkListsResponse(BaseModel):
    """Listmonk lists access response"""
    data: list[ListmonkList] = Field(..., description="Response data")


class ListmonkSubscriberResponse(BaseModel):
    """Listmonk subscriber access response"""
    data: list[ListmonkSubscriber] = Field(..., description="Response data")


# OpenAPI Response Models for Documentation

class ApiResponse(BaseModel):
    """Generic API response wrapper."""
    data: Any = Field(..., description="Response data")
    message: Optional[str] = Field(None, description="Response message")


class PaginatedResponse(BaseModel):
    """Paginated response model."""
    results: list[Any] = Field(..., description="Results list")
    query: Optional[str] = Field(None, description="Search query")
    total: int = Field(..., description="Total number of items")
    per_page: int = Field(..., description="Items per page")
    page: int = Field(1, description="Current page number")
