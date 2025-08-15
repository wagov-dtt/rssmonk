# RSS Monk Agent Guide

## Quick Start
```bash
just prereqs  # Install k3d, kubectl, scc, uv via Homebrew
just start    # Deploy RSS Monk on k3d cluster
```

## Core Commands
- `just start` - Deploy RSS Monk on k3d cluster
- `just status` - Show service status
- `just logs` - Show service logs
- `just clean` - Remove k3d cluster
- `just api` - Start API server in development mode
- `just setup` - Complete setup for new contributors
- `just check` - Run all quality checks (lint + type-check + test)
- `just lint` - Check code style with ruff
- `just format` - Format code with ruff
- `just type-check` - Run mypy type checking
- `just test` - Run pytest tests
- `just health` - Check system health

## Local Testing
```bash
# Access services locally
# Listmonk: http://localhost:9000 (admin/admin123)
# Mailpit: http://localhost:8025

# Start and access services
just start
```

## CLI Tool
A CLI tool built with typer that closely mimics the HTTP API will be made available for test simplification. In production, use the HTTP endpoints directly.

## Development Philosophy
- **Simplicity first** - Prefer simple solutions over complex ones
- **Minimize dependencies** - Use only what's necessary
- **Keep it concise** - Minimize code, configs, and documentation
- **Maintainable code** - Write code that's easy to understand and modify
- **Self-documenting code** - Code should be readable without explanation
- **Use justfile** - For most commands, define them as reusable recipes in the justfile
- **Fail fast** - Validate early and provide clear error messages

## Documentation Standards
- **Essential information only** - Focus on what users need to know
- **Concrete examples** - Show actual commands and outputs
- **Minimal explanation** - Let the code and commands speak for themselves
- **Clear structure** - Organize information logically
- **Australian English** - Use Australian spelling and terminology

## Code Style
- Python scripts use uv/ruff
- YAML uses 2-space indentation
- Environment variables with `LISTMONK_APIUSER` and `LISTMONK_APITOKEN` prefix
- Container images use latest tags for development
- **ASCII only**: Avoid Unicode/emoji characters in code files (difficult for some tools to parse)
  - Use simple text: "OK", "ERROR", "SUCCESS" instead of ✅❌🎉
  - Use ASCII symbols: "-", "*", "+" for bullets and decoration

## Technical Implementation Notes

### API Architecture
- **Passthrough Proxy**: RSS Monk API acts as authenticated proxy to [Listmonk](https://listmonk.app/)
- **Three RSS Monk Endpoints**:
  - `/api/feeds` - Feed management with RSS Monk logic
  - `/api/feeds/process` - Feed processing (individual or bulk for cron)
  - `/api/public/subscribe` - Public subscription without authentication
- **Listmonk Passthrough**: All other `/api/*` requests pass through to Listmonk with auth validation
- **Public Passthrough**: All other `/api/public/*` requests pass through to Listmonk without auth
- **OpenAPI Documentation**: Default OpenAPI spec includes Listmonk passthrough documentation
- **Dynamic Content**: Pydantic models load content from Listmonk at runtime

### Authentication Strategy
- **Listmonk Validation**: All auth validated directly against Listmonk API
- **Dependency Injection**: FastAPI dependency validates credentials per request for `/api/*` routes
- **Passthrough Headers**: Auth headers preserved and forwarded to Listmonk
- **No Local Auth**: No separate authentication system - relies on Listmonk entirely

### Listmonk Integration
[Listmonk](https://listmonk.app/) is a high-performance bulk messaging system with subscriber management, list expansion, and email campaign capabilities. It uses PostgreSQL as its primary datastore. RSS Monk acts as a proxy layer that adds RSS feed processing capabilities to Listmonk's messaging infrastructure.

### API Client Architecture
- **ListmonkClient**: HTTP wrapper with automatic JSON handling and error logging
- **Response normalization**: Handles both paginated (`{data: {results: []}}`) and direct list responses
- **Authentication**: HTTP Basic Auth with username/password from environment

### State Management Strategy
- **No persistent state files**: All state stored in Listmonk list tags
- **GUID-based deduplication**: RSS item GUIDs prevent duplicate email campaigns  
- **URL hashing**: SHA-256 full digest for guaranteed unique feed identification
- **Frequency isolation**: Separate last-seen tracking per polling frequency

### Error Handling Approach
- **Fail-fast validation**: Environment variable validation at startup
- **Graceful degradation**: Individual feed failures don't stop batch processing
- **Structured logging**: All errors logged with context for debugging
- **Exponential backoff retries**: Uses tenacity for reliable HTTP requests with jitter

### Development Workflow
- **justfile recipes**: All common operations scripted for consistency
- **k3d cluster**: Lightweight local Kubernetes for realistic testing  
- **Mailpit integration**: Email debugging without external SMTP dependencies
- **Hot reloading**: Scripts can be run directly during development

## Common User Support Issues
- **"Nothing happening"** - Check `just logs` and `just status`
- **"Emails not arriving"** - Verify RSS feed URL, check Mailpit at :8025
- **"Want to start over"** - Run `just clean && just start`
- **"How to add feeds"** - Use `just feeds add-feed https://www.abc.net.au/news/feed/10719986/rss.xml daily`
- **"What frequencies work"** - 5min, daily, weekly
