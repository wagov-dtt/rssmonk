"""Simple FastAPI server for RSS Monk."""

from typing import List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .core import RSSMonk, Settings, Frequency, Feed, Subscriber

app = FastAPI(title="RSS Monk API", version="2.0.0")


# Request models
class AddFeedRequest(BaseModel):
    url: str
    frequency: Frequency
    name: Optional[str] = None


class AddSubscriberRequest(BaseModel):
    email: str
    name: Optional[str] = None


class SubscribeRequest(BaseModel):
    email: str
    feed_url: str


# Response models
class FeedResponse(BaseModel):
    id: Optional[int]
    name: str
    url: str
    base_url: str
    frequency: str


class SubscriberResponse(BaseModel):
    id: Optional[int]
    email: str
    name: str


# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return {"error": str(exc)}


# Feed endpoints
@app.post("/feeds", response_model=FeedResponse)
async def create_feed(request: AddFeedRequest):
    """Create a new RSS feed."""
    try:
        with RSSMonk() as rss:
            feed = rss.add_feed(request.url, request.frequency, request.name)
            return FeedResponse(
                id=feed.id,
                name=feed.name,
                url=feed.url,
                base_url=feed.base_url,
                frequency=feed.frequency.value,
            )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/feeds", response_model=List[FeedResponse])
async def list_feeds():
    """List all RSS feeds."""
    try:
        with RSSMonk() as rss:
            feeds = rss.list_feeds()
            return [
                FeedResponse(
                    id=feed.id,
                    name=feed.name,
                    url=feed.url,
                    base_url=feed.base_url,
                    frequency=feed.frequency.value,
                )
                for feed in feeds
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/feeds/by-url")
async def get_feed_by_url(url: str):
    """Get feed by URL."""
    try:
        with RSSMonk() as rss:
            feed = rss.get_feed_by_url(url)
            if not feed:
                raise HTTPException(status_code=404, detail="Feed not found")

            return FeedResponse(
                id=feed.id,
                name=feed.name,
                url=feed.url,
                base_url=feed.base_url,
                frequency=feed.frequency.value,
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/feeds/by-url")
async def delete_feed_by_url(url: str):
    """Delete feed by URL."""
    try:
        with RSSMonk() as rss:
            if rss.delete_feed(url):
                return {"message": "Feed deleted successfully"}
            else:
                raise HTTPException(status_code=404, detail="Feed not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Subscriber endpoints
@app.post("/subscribers", response_model=SubscriberResponse)
async def create_subscriber(request: AddSubscriberRequest):
    """Create a new subscriber."""
    try:
        with RSSMonk() as rss:
            subscriber = rss.add_subscriber(request.email, request.name)
            return SubscriberResponse(
                id=subscriber.id, email=subscriber.email, name=subscriber.name
            )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/subscribers", response_model=List[SubscriberResponse])
async def list_subscribers():
    """List all subscribers."""
    try:
        with RSSMonk() as rss:
            subscribers = rss.list_subscribers()
            return [
                SubscriberResponse(id=sub.id, email=sub.email, name=sub.name) for sub in subscribers
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/subscribe")
async def subscribe_to_feed(request: SubscribeRequest):
    """Subscribe an email to a feed."""
    try:
        with RSSMonk() as rss:
            rss.subscribe(request.email, request.feed_url)
            return {"message": "Subscription successful"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Processing endpoints
@app.post("/feeds/process")
async def process_feed(feed_url: str, auto_send: bool = False):
    """Process a single feed."""
    try:
        with RSSMonk() as rss:
            feed = rss.get_feed_by_url(feed_url)
            if not feed:
                raise HTTPException(status_code=404, detail="Feed not found")

            campaigns = rss.process_feed(feed, auto_send)
            return {"feed_name": feed.name, "campaigns_created": campaigns}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/feeds/poll/{frequency}")
async def poll_feeds_by_frequency(frequency: Frequency):
    """Poll feeds by frequency."""
    try:
        with RSSMonk() as rss:
            results = rss.process_feeds_by_frequency(frequency)
            total_campaigns = sum(results.values())

            return {
                "frequency": frequency.value,
                "feeds_processed": len(results),
                "campaigns_created": total_campaigns,
                "results": results,
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Health endpoint
@app.get("/health")
async def health_check():
    """Health check."""
    try:
        settings = Settings()
        settings.validate_required()

        with RSSMonk(settings) as rss:
            feeds = rss.list_feeds()
            subscribers = rss.list_subscribers()

            return {
                "status": "healthy",
                "feeds_count": len(feeds),
                "subscribers_count": len(subscribers),
            }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@app.get("/")
async def root():
    """Root endpoint."""
    return {"name": "RSS Monk API", "version": "2.0.0", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
