# RSS Monk

RSS Monk turns RSS feeds into email newsletters using Listmonk.

## Quick Start

```bash
# Start everything (installs prerequisites, starts k3d cluster, and API server)
just api
```

Then visit http://localhost:8000/docs for the interactive API documentation.

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

**Listmonk Non Passthrough:** - TODO
- `GET|PATCH|POST|PUT|DELETE /api/subscriber*` - These requests will handle attributes to ensure only the segment attributes are updated correctly

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

Create a `.env` file in the project root to configure RSS Monk:

```bash
# Required
LISTMONK_ADMIN_PASSWORD=your-token

# Optional - defaults shown
LISTMONK_ADMIN_USER=api
LISTMONK_URL=http://localhost:9000
RSS_AUTO_SEND=false
RSS_TIMEOUT=30.0
RSS_USER_AGENT="RSS Monk/2.0 (Feed Aggregator; +https://github.com/wagov-dtt/rssmonk)"
LOG_LEVEL=INFO
```

RSS Monk uses pydantic-settings which automatically loads `.env` files. Only `LISTMONK_ADMIN_PASSWORD` is required.

### API Authentication

The RSS Monk API validates all credentials against Listmonk directly:
- **Authenticated routes** (`/api/*`): Require HTTP Basic Auth validated against Listmonk
- **Public routes** (`/api/public/*`): No authentication required
- **RSS Monk routes**: Use same Listmonk credentials for backend operations

## Frequencies

- `instant` - Every 5 minutes
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
