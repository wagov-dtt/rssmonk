# Contributing to RSS Monk

RSS Monk is designed to be simple and easy to contribute to. We use **justfile** for all development commands and **uv** for Python package management.

## Quick Start for Contributors

```bash
# Clone and setup
git clone https://github.com/wagov-dtt/rssmonk
cd rssmonk

# One-command setup (installs deps + runs all checks)
just setup

# Or step by step:
just install     # Install dependencies
just test        # Run tests
just lint        # Check code style
just api         # Start API server
```

## Project Structure

RSS Monk uses modular route handlers for easy discovery:

```
src/rssmonk/
├── api.py              # FastAPI app setup and router registration
├── core.py             # RSSMonk service and Settings
├── routes/             # Endpoint modules (organized by resource)
│   ├── feeds.py        # Feed CRUD, templates, accounts
│   ├── subscriptions.py # Subscribe, confirm, unsubscribe
│   └── operations.py   # Processing, health, metrics, cache
├── models.py           # Pydantic request/response models
├── http_clients.py     # Listmonk HTTP client
├── cache.py            # Feed caching
├── types.py            # Constants and enums
├── utils.py            # Utility functions
└── tests/              # Tests
```

## Design Principles

1. **Modular routes** - One module per resource domain (feeds, subscriptions, operations)
2. **Pydantic for validation** - Type safety without complexity  
3. **ASCII only** - No Unicode/emoji in code (tool compatibility)
4. **Stateless** - Use Listmonk for all state storage
5. **Environment config** - No config files
6. **Single responsibility** - Each route module handles ~80-120 lines

## Making Changes

### Adding an API Endpoint  
1. Identify the resource: feeds, subscriptions, or operations
2. Add function to the appropriate module in `routes/`
3. Use `@router.post()`, `@router.get()` etc
4. Use existing request/response models from `models.py`
5. Test with `uvicorn rssmonk.api:app --reload`

Example - adding a feed endpoint:
```python
# In routes/feeds.py
@router.get("/{feed_id}")
async def get_feed(feed_id: int, ...):
    """Get a single feed by ID."""
    ...
```

### Adding Tests
1. Create test in `tests/`
2. Use pytest fixtures for common setup
3. Mock external services (Listmonk API)
4. Run with `just test`

## Common Tasks

```bash
# Test your changes
just test

# Check code style  
just lint

# Format code
just format

# Type checking
just type-check

# Run all quality checks
just check

# Run API server locally
just api

# Test endpoints
curl http://localhost:8000/health
curl -u api:your-token http://localhost:8000/api/feeds
```

## Code Style

- Use ASCII text instead of Unicode: [SUCCESS] not ✅
- Keep functions small and focused
- Use type hints with Pydantic models
- Follow existing error handling patterns
- Add docstrings for public functions

## Getting Help

- Check existing code patterns
- Look at tests for examples  
- Ask questions in issues
- Follow the design principles above
