# RSS Monk

RSS Monk turns RSS feeds into email newsletters using Listmonk.

## Quick Start

```bash
# Start everything (installs prerequisites, starts k3d cluster, and API server)
just api
```

Then visit http://localhost:8000/docs for the interactive API documentation.

RSS Monk converts RSS feeds into email newsletters using [Listmonk](https://listmonk.app/), a high-performance bulk messaging system. Listmonk provides subscribers, lists, campaigns, and stores feed information as tags on lists and subscriber preferences as attributes on subscribers.

## Running the API Server locally (DevContainer)

```bash
# Start API cluster in development mode
just api

# Or manually (API only)
uvicorn rssmonk.api:app --host 0.0.0.0 --port 8000
```

### API Architecture

RSS Monk acts as a proxy to Listmonk with three areas of endpoints:

**RSS Monk Endpoints:**
- `POST /api/feeds` - Feed management with RSS Monk logic
- `POST /api/feeds/process` - Feed processing (individual or bulk for cron)
- `POST /api/feeds/subscribe` - Add pending subscription
- `POST /api/feeds/subscribe-confirm` - Subscription
- `POST /api/feeds/unsubscribe` - Unsubscribe from a feed

**Utility Endpoints:**
- `GET /health` - Combined RSS Monk + Listmonk health check
- `GET /docs` - Interactive API documentation with passthrough info
- `GET /openapi.json` - OpenAPI spec including Listmonk integration

## API Endpoints

RSS Monk provides a RESTful API with the following resource groups:

**Feed Management** (`/api/feeds`):
- Feed operations: create, list, delete, templates, accounts
- All operations require HTTP Basic Auth

**Subscriptions** (`/api/feeds`):
- `POST /subscribe` - Subscribe email to feed
- `POST /subscribe-confirm` - Confirm subscription  
- `POST /unsubscribe` - Unsubscribe from feed
- `GET /subscribe-preferences` - Get user preferences

**Operations** (health, processing, monitoring):
- `GET /health` - Health check
- `POST /api/feeds/process` - Process single feed
- `POST /api/feeds/process/bulk/{frequency}` - Process all feeds of frequency
- `GET /api/cache/stats` - Cache statistics
- `DELETE /api/cache` - Clear feed cache

## Configuration

Create a `.env` file in the project root to configure RSS Monk:

```bash
# Required
LISTMONK_ADMIN_PASSWORD=your-token

# Optional - defaults shown
LISTMONK_ADMIN_USER=api
LISTMONK_URL=http://localhost:9000
RSS_TIMEOUT=30.0
RSS_USER_AGENT="RSS Monk/2.0 (Feed Aggregator; +https://github.com/wagov-dtt/rssmonk)"
LOG_LEVEL=INFO
```

RSS Monk uses pydantic-settings which automatically loads `.env` files. Only `LISTMONK_ADMIN_PASSWORD` is required.

### API Authentication

The RSS Monk API validates all credentials against Listmonk directly:
- **Authenticated routes** (`/api/*`): Require HTTP Basic Auth validated against Listmonk
- **RSS Monk routes**: Use same Listmonk credentials for backend operations

## Frequencies

- `instant` - Every 5 minutes
- `daily` - Daily at 5pm Perth time (Australia/Perth)

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

# Run all pytest
just test
```

## TODO

- **Container build**: Set up a [Railpack](https://railpack.io/) build to create a production container that can run adjacent to Listmonk in a Kubernetes cluster
- **End-to-end tests**: Create external (non-Python) integration tests that the justfile can run against a fully configured k3d stack. These tests should simulate real API user workflows as documented in this README, providing confidence that the documented quick-start instructions work correctly
