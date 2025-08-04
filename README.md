# RSS Monk

RSS Monk turns RSS feeds into email newsletters using Listmonk.

## Quick Start

```bash
# Install dependencies
just prereqs

# Start services (k3d cluster with Listmonk)
just start

# Add your first feed
rssmonk add-feed https://www.abc.net.au/news/feed/10719986/rss.xml daily

# Quick setup with subscribers
rssmonk quick-setup https://www.abc.net.au/news/feed/10719986/rss.xml daily user@example.com
```

## Core Commands

### Feed Management
```bash
# Add feed
just feeds add-feed <url> <frequency> [--name "Feed Name"]

# List feeds
just feeds list-feeds

# Delete feed
just feeds delete-feed <url>

# Process feed manually
just feeds process-feed <url> [--send]
```

### Subscriber Management
```bash
# Add subscriber
just feeds add-subscriber <email> [--name "Name"]

# Subscribe email to feed
just feeds subscribe <email> <feed-url>

# Quick setup (feed + subscribers)
just feeds quick-setup <url> <frequency> <email1> <email2> ...
```

### Operations
```bash
# Poll feeds by frequency
just feeds poll <frequency>

# Health check
just health
```

## API Server

```bash
# Start API server in development mode
just api

# Or manually
uvicorn rssmonk.api:app --host 0.0.0.0 --port 8000
```

API endpoints:
- `POST /feeds` - Create feed
- `GET /feeds` - List feeds  
- `POST /subscribers` - Create subscriber
- `POST /subscribe` - Subscribe email to feed
- `POST /feeds/process` - Process feed
- `GET /health` - Health check

## Cron Jobs

```bash
# Run polling for specific frequency
just test-fetch 5min
just test-fetch daily
just test-fetch weekly
```

## Configuration

Set environment variables:
```bash
LISTMONK_URL=http://localhost:9000
LISTMONK_APIUSER=api
LISTMONK_APITOKEN=your-token
RSS_AUTO_SEND=true
RSS_TIMEOUT=30.0
```

## Frequencies

- `5min` - Every 5 minutes
- `daily` - Daily at 5pm  
- `weekly` - Weekly on Friday at 5pm

## Web Interfaces

- **Listmonk**: http://localhost:9000 (admin/admin123)
- **Mailpit**: http://localhost:8025 (email testing)
- **RSS Monk API**: http://localhost:8000/docs

## Development

```bash
# Setup for new contributors
just setup

# Run all checks
just check

# Individual commands
just test      # Run tests
just lint      # Check code style
just format    # Format code
just type-check # Type checking
```
