"""Pydantic models for RSS Monk API."""

from typing import Any, Optional

from pydantic import BaseModel, Field, HttpUrl

from .core import Frequency


# Request Models

class FeedCreateRequest(BaseModel):
    """Request model for creating an RSS feed."""
    
    url: HttpUrl = Field(..., description="RSS feed URL")
    frequency: list[Frequency] = Field(..., description="Polling frequency")
    name: Optional[str] = Field(None, description="Feed name (auto-detected if not provided)")


class FeedProcessRequest(BaseModel):
    """Request model for processing a specific feed."""
    
    url: HttpUrl = Field(..., description="RSS feed URL to process")
    auto_send: bool = Field(False, description="Automatically send created campaigns")


class PublicSubscribeRequest(BaseModel):
    """Request model for public subscription endpoint and no filter."""
    
    email: str = Field(..., description="Subscriber email address")
    feed_url: HttpUrl = Field(..., description="RSS feed URL to subscribe to")

class SubscribeRequest(BaseModel): # TODO - Fix up
    """Request model for public subscription endpoint."""
    
    email: str = Field(..., description="Subscriber email address")
    feed_url: HttpUrl = Field(..., description="RSS feed URL to subscribe to")
    #filter: dict[Any] =  Field(..., description="The filter as JSON")

# Response Models

class FeedResponse(BaseModel):
    """Response model for RSS feed information."""
    
    id: int = Field(..., description="Listmonk list ID")
    name: str = Field(..., description="Feed name")
    url: str = Field(..., description="RSS feed URL")
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


class BulkProcessResponse(BaseModel):
    """Response model for bulk feed processing."""
    
    frequency: Frequency = Field(..., description="Processed frequency")
    feeds_processed: int = Field(..., description="Number of feeds processed")
    total_campaigns: int = Field(..., description="Total campaigns created")
    results: dict[str, int] = Field(..., description="Per-feed campaign counts")


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
