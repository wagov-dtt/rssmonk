# RSS Monk

RSS Monk turns RSS feeds into email newsletters using Listmonk.

## Quick Start

```bash
# Install dependencies
just prereqs

# Start services (k3d cluster with Listmonk)
just start

# Start API server
just api
```

RSS Monk converts RSS feeds into email newsletters using [Listmonk](https://listmonk.app/), a high-performance bulk messaging system. Listmonk provides subscribers, lists, campaigns, and stores feed information as tags on lists and subscriber preferences as tags on subscribers.

## API Server

```bash
# Start API server in development mode
just api

# Or manually
uvicorn rssmonk.api:app --host 0.0.0.0 --port 8000
```

### API Architecture

RSS Monk acts as a proxy to Listmonk with three endpoints:

**RSS Monk Endpoints:**
- `POST /api/feeds` - Feed management with RSS Monk logic
- `POST /api/feeds/process` - Feed processing (individual or bulk for cron)
- `POST /api/public/subscribe` - Public subscription (no auth required)

**Listmonk Passthrough:**
- `GET|POST|PUT|DELETE /api/*` - All other requests pass through to Listmonk with authentication
- `GET|POST|PUT|DELETE /api/public/*` - Public Listmonk endpoints (no auth required)

**Utility Endpoints:**
- `GET /health` - Combined RSS Monk + Listmonk health check
- `GET /docs` - Interactive API documentation with passthrough info
- `GET /openapi.json` - OpenAPI spec including Listmonk integration

## CLI Tool
A CLI tool built with typer that closely mimics the HTTP API will be made available for test simplification. In production, use the HTTP endpoints directly.

## Configuration

Environment variables (managed via pydantic-settings):
```bash
# Listmonk Connection (required)
LISTMONK_APITOKEN=your-token           # Listmonk API password/token
LISTMONK_APIUSER=api                   # Listmonk API username (default: api)
LISTMONK_URL=http://localhost:9000     # Listmonk API URL (default: http://localhost:9000)

# RSS Processing
RSS_AUTO_SEND=true                     # Automatically send campaigns (default: false)
RSS_TIMEOUT=30.0                       # HTTP timeout for RSS requests (default: 30.0)
RSS_USER_AGENT="RSS Monk/2.0"          # User agent for RSS requests

# Logging
LOG_LEVEL=INFO                         # Logging level (default: INFO)
```

Only `LISTMONK_APITOKEN` is required - all others have sensible defaults.

### API Authentication

The RSS Monk API validates all credentials against Listmonk directly:
- **Authenticated routes** (`/api/*`): Require HTTP Basic Auth validated against Listmonk
- **Public routes** (`/api/public/*`): No authentication required
- **RSS Monk routes**: Use same Listmonk credentials for backend operations

## Frequencies

- `5min` - Every 5 minutes
- `daily` - Daily at 5pm Perth time (Australia/Perth)
- `weekly` - Weekly on Friday at 5pm Perth time (Australia/Perth)

## Web Interfaces

- **Listmonk**: http://localhost:9000 (admin/admin123)
- **Mailpit**: http://localhost:8025 (email testing)
- **RSS Monk API**: http://localhost:8000/docs
- **OpenAPI Spec**: http://localhost:8000/openapi.json

## Development

```bash
# Setup for new contributors
just setup

# See all available commands
just --list

# Run all quality checks
just check
```
