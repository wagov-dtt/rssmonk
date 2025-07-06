# Feed Management Guide

RSS Monk manages feeds through the Listmonk REST API. Each RSS feed is stored as a Listmonk list with frequency tags for automated polling.

## Quick Setup

Add a feed and subscribe emails in one command:

```bash
# Add TechCrunch feed with daily frequency, subscribe two emails
just feed-manager quick-setup \
  "https://feeds.feedburner.com/TechCrunch" \
  daily \
  user1@example.com \
  user2@example.com \
  --name "TechCrunch Daily"
```

## Feed Management Commands

### Add Feed
```bash
# Add RSS feed with frequency control
just feed-manager add-feed "https://hnrss.org/frontpage" 5min --name "Hacker News"
```

### List Feeds
```bash
# Show all RSS feeds with their frequencies and subscriber counts
just feed-manager list-feeds
```

### Subscriber Management
```bash
# Add new subscriber
just feed-manager add-subscriber user@example.com --name "John Doe"

# List all subscribers
just feed-manager list-subscribers

# Subscribe existing user to a feed
just feed-manager subscribe user@example.com 123
```

## REST API Workflow

RSS Monk uses the Listmonk REST API for all operations. Here's the underlying workflow:

### 1. Feed Creation
```http
POST /api/lists
Content-Type: application/json

{
  "name": "TechCrunch",
  "type": "public", 
  "description": "RSS Feed: https://feeds.feedburner.com/TechCrunch",
  "tags": ["freq:daily"]
}
```

### 2. Subscriber Creation
```http
POST /api/subscribers
Content-Type: application/json

{
  "email": "user@example.com",
  "name": "John Doe",
  "status": "enabled"
}
```

### 3. List Subscription
```http
PUT /api/subscribers/{subscriber_id}/lists
Content-Type: application/json

{
  "ids": [123],
  "status": "confirmed"
}
```

### 4. Campaign Creation (Automated)
The feed-fetcher script automatically creates campaigns for new RSS items:

```http
POST /api/campaigns
Content-Type: application/json

{
  "name": "TechCrunch: Article Title",
  "subject": "Article Title",
  "lists": [123],
  "content_type": "html",
  "body": "<html>RSS article content</html>",
  "tags": ["rss", "automated", "daily"]
}
```

## Frequency Control

RSS feeds use tags for scheduling:

- `freq:5min` - Poll every 5 minutes
- `freq:daily` - Poll daily at 5pm UTC
- `freq:weekly` - Poll weekly on Friday at 5pm UTC

The feed-fetcher script uses these tags to:
1. Determine when to check each feed
2. Track last-seen items with `last-seen:freq:5min:GUID` tags
3. Track last poll times with `last-poll:freq:daily:ISO8601` tags

## Performance

The feed-fetcher uses:
- **Thread Pool**: Concurrent processing of up to 10 feeds (configurable with `MAX_WORKERS`)
- **HTTP Caching**: ETag and Last-Modified headers to minimize bandwidth
- **Frequency-based Polling**: Only check feeds when their schedule requires it

```bash
# Run with custom thread pool size
MAX_WORKERS=20 just simulate-cron daily
```

## Environment Variables

```bash
# Listmonk connection
LISTMONK_URL=http://localhost:9000
LISTMONK_USERNAME=listmonk
LISTMONK_PASSWORD=listmonk

# Performance tuning
MAX_WORKERS=10  # Thread pool size for feed processing
```

## Examples

### Personal Blog Setup
```bash
# Add personal tech blog, check weekly
just feed-manager add-feed "https://blog.example.com/rss.xml" weekly --name "Personal Tech Blog"

# Subscribe yourself
just feed-manager add-subscriber me@example.com --name "Me"
just feed-manager subscribe me@example.com 1
```

### News Aggregation
```bash
# High-frequency news feeds
just feed-manager add-feed "https://hnrss.org/frontpage" 5min --name "Hacker News"
just feed-manager add-feed "https://feeds.feedburner.com/TechCrunch" daily --name "TechCrunch"

# Subscribe team members
for email in alice@company.com bob@company.com; do
  just feed-manager add-subscriber $email
  just feed-manager subscribe $email 1  # Hacker News
  just feed-manager subscribe $email 2  # TechCrunch
done
```

### Bulk Email Setup
```bash
# Company newsletter aggregation
just feed-manager quick-setup \
  "https://company.com/blog/rss.xml" \
  weekly \
  team@company.com \
  stakeholders@company.com \
  customers@company.com \
  --name "Company Blog Weekly"
```

## Monitoring

Check feed processing status:
```bash
# View recent logs
kubectl logs -n rssmonk -l app=feed-fetcher --tail=100

# Monitor Listmonk campaigns
kubectl port-forward -n rssmonk svc/listmonk-service 9000:80
# Open http://localhost:9000/campaigns
```
