"""Pydantic models for RSS Monk API."""
import hashlib
from typing import Any, Optional
import uuid

from pydantic import BaseModel, Field, HttpUrl, field_validator

from rssmonk.types import LIST_DESC_FEED_URL, SUB_BASE_URL, TOPICS_TITLE, DisplayTextFilterType, FrequencyFilterType, EmailPhaseType, Frequency, ListVisibilityType

class Feed(BaseModel):
    """RSS feed model."""

    id: Optional[int] = None
    name: str
    feed_url: str
    email_base_url: str
    """Base URL that is used for link generation in emails"""
    poll_frequencies: list[Frequency]
    filter_groups: Optional[list[str]] = None
    url_hash: str = ""
    mult_freq: bool = False

    def __init__(self, **data):
        super().__init__(**data)
        if not self.url_hash:
            self.url_hash = hashlib.sha256(self.feed_url.encode()).hexdigest()

    @property
    def tags(self) -> list[str]:
        """Generate Listmonk tags."""
        return [f'freq:{x.value}' for x in self.poll_frequencies] + [f"url:{self.url_hash}"]

    @property
    def description(self) -> str:
        """Generate Listmonk description."""
        description = f"{LIST_DESC_FEED_URL} {self.feed_url}\n{SUB_BASE_URL} {self.email_base_url}"
        if self.filter_groups:
            description += f"\n{TOPICS_TITLE} {",".join(self.filter_groups)}"
        return description
        # TODO - Need to determine how multiple frequency filters are stored. It may never be used. Default to false
        #return description + f"\n{MULTIPLE_FREQ} {str(self.mult_freq)}"

class ListmonkTemplate(BaseModel):
    """Template data model for Listmonk. Optional fields are for POST to /api/templates"""
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
    email_base_url: HttpUrl = Field(..., description="Base URL used in emails")
    poll_frequencies: list[Frequency] = Field(..., description="Polling frequency options for users", min_length=1)
    filter_groups: Optional[list[str]] = Field(None, description="Topics that the user can filter against and is present in the feed. None will count as 'all' topics to all users")
    name: Optional[str] = Field(None, description="Feed name (auto-detected if not provided)")
    visibility: Optional[ListVisibilityType] = Field(ListVisibilityType.PRIVATE, description="RSS feed visibility. Default to private")

class FeedDeleteRequest(BaseModel):
    """Request model for creating an RSS feed."""
    feed_url: HttpUrl = Field(..., description="RSS feed URL")
    notify: Optional[bool] = Field(False, description="Set to true to send a generic campaign to everyone in the list to notify the end of the campaign")

class FeedAccountConfigurationRequest(BaseModel):
    """Request model for obtaining the configuration from a RSS feed."""
    feed_url: HttpUrl = Field(..., description="RSS feed URL")

class FeedAccountRequest(BaseModel):
    """Request model for creating an account for a RSS feed."""
    feed_url: HttpUrl = Field(..., description="RSS feed URL")

class FeedAccountPasswordResetRequest(BaseModel):
    """Request model for restting the password of an account for a RSS feed."""
    account_name: str = Field(..., description="RSS feed's account name")

class FeedProcessRequest(BaseModel):
    """Request model for processing a specific feed."""
    feed_url: HttpUrl = Field(..., description="RSS feed URL to process")

class CreateTemplateRequest(BaseModel):
    """Request model for creating a template for a RSS feed."""
    feed_url: HttpUrl = Field(..., description="RSS feed URL to process")
    template_type: str = Field(..., description="Type of the template (campaign, campaign_visual, or tx)")
    phase_type: EmailPhaseType = Field(..., description="The phase in the email subscribe cycle the template is for")
    subject: Optional[str] = Field(None, description="The email template subject line. Mandatory for tx templates")
    body_source: Optional[str] = Field(None, description="If type is campaign_visual, the JSON source for the email-builder tempalate")
    body: str = Field(..., description="HTML body of the template")

class DeleteTemplateRequest(BaseModel):
    """Request model for deleting a template for a RSS feed."""
    phase_type: EmailPhaseType = Field(..., description="The phase in the email subscribe cycle the template is for")

class DeleteTemplateAdminRequest(BaseModel):
    """Request model for deleting a template for a RSS feed."""
    feed_url: HttpUrl = Field(..., description="RSS feed URL to process")
    phase_type: EmailPhaseType = Field(..., description="The phase in the email subscribe cycle the template is for")

class PublicSubscribeRequest(BaseModel):
    """Request model for public subscription endpoint and no filter."""
    email: str = Field(..., description="Subscriber email address")
    feed_url: HttpUrl = Field(..., description="RSS feed URL to subscribe to")

class SubscribeRequest(BaseModel):
    """Request model for a subscription endpoint with a filter and email confirmation."""
    email: str = Field(..., description="Subscriber email address")
    filter: dict[Frequency, FrequencyFilterType] = Field(..., description="The filter as JSON")
    display_text: Optional[dict[Frequency, DisplayTextFilterType]] = Field(..., description="The text for the filter above for email")

class SubscribeAdminRequest(BaseModel):
    """Request model for a subscription endpoint with a filter and email confirmation."""
    email: str = Field(..., description="Subscriber email address")
    feed_url: HttpUrl = Field(..., description="RSS feed URL to subscribe to")
    filter: dict[Frequency, FrequencyFilterType] = Field(..., description="The filter as JSON")
    display_text: Optional[dict[Frequency, DisplayTextFilterType]] = Field(..., description="The text for the filter above for email")
    bypass_confirmation: Optional[bool] = Field(False, description="Bypass the temporary filter and email for confirmation.")

class SubscriptionPreferencesRequest(BaseModel):
    """Request model for a subscription endpoint with filters for the feed."""
    email: str = Field(..., description="Subscriber email address")
    feed_url: Optional[HttpUrl] = Field(..., description="RSS feed URL to subscribe to. If not supplied, attempt to obtain preferences of the account attached to the user")

class SubscribeConfirmRequest(BaseModel):
    """Request model for a subscription confirmation endpoint."""
    subscriber_id: str = Field(..., description="The id of the subscriber")
    guid: str = Field(..., description="The uuid of the new subscription filters to confirm as active")

    @field_validator("subscriber_id")
    def subscriber_id_length(cls, value):
        uuid.UUID(value) # ValueError from here is fine to trickle up
        return value

    @field_validator("guid")
    def guid_length(cls, value):
        uuid.UUID(value) # ValueError from here is fine to trickle up
        return value

class UnsubscribeRequest(BaseModel):
    """Request model for unsubscribing from a feed."""
    subscriber_id: str = Field(..., description="The id of the subscriber")
    token: str = Field(..., description="The token to match against the subscriber's filter to remove")

    @field_validator("subscriber_id")
    def subscriber_id_length(cls, value):
        uuid.UUID(value) # ValueError from here is fine to trickle up
        return value

    @field_validator("token")
    def guid_length(cls, value):
        if len(value) == 0:
            raise ValueError("Token should not be empty")
        return value

class UnsubscribeAdminRequest(BaseModel):
    """Admin request model for unsubscribing from a feed."""
    email: str = Field(..., description="Subscriber email address ")
    feed_url: HttpUrl = Field(..., description="RSS feed URL to unsubscribe from")
    bypass_confirmation: Optional[bool] = Field(False, description="Bypass any second email that might be send out for unsubscribing")

class ClearSubscriberRequest(BaseModel):
    """Request model for clearing all subscribers from a feed."""
    feed_url: HttpUrl = Field(..., description="RSS feed URL to unsubscribe from")


# Response Models

class EmptyResponse(BaseModel):
    pass

class FeedResponse(BaseModel):
    """Response model for RSS feed information."""
    id: int = Field(..., description="Listmonk list ID")
    name: str = Field(..., description="Feed name")
    feed_url: str = Field(..., description="RSS feed URL")
    email_base_url: HttpUrl = Field(..., description="Base URL that is used in emails")
    poll_frequencies: list[Frequency] = Field(..., description="How often the feed should be polled for new feed items")
    filter_groups: Optional[list[str]] = Field(None, description="Topics that the user can filter against.")
    url_hash: str = Field(..., description="SHA-256 hash of the URL")
    subscriber_count: Optional[int] = Field(None, description="Number of subscribers")

class FeedAccountConfigurationResponse(BaseModel):
    """Request model for obtaining the configuration from a RSS feed."""
    feed_url: HttpUrl = Field(..., description="RSS feed URL")
    # TODO
    # - Other information that is useful
    #  - Mailing template for the mailing frequencies if the feed list has it (eg. instant email template for a poll freq of instant)

class FeedListResponse(BaseModel):
    """Response model for listing RSS feeds."""
    feeds: list[FeedResponse] = Field(..., description="list of RSS feeds")
    total: int = Field(..., description="Total number of feeds")


class FeedProcessResponse(BaseModel):
    """Response model for feed processing."""
    feed_name: str = Field(..., description="Name of processed feed")
    notifications_sent: int = Field(..., description="Number of notifications created")
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
    total_emails_sent: int = Field(..., description="Total emails sent")
    results: dict[str, int] = Field(..., description="Per-feed email counts")


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

class MetricsResponse(BaseModel):
    """Metrics response that will be scraped"""
    response: str = Field(..., description="Metrics response")

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
