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
just feeds --help # Try the CLI
```

## Project Structure

RSS Monk has a minimal structure:

```
src/rssmonk/
├── __init__.py         # Package init
├── rssmonk.py          # All-in-one: CLI, API, Core logic
└── tests/              # Simple tests
```

## Design Principles

1. **One file for most functionality** - Keep it simple
2. **Pydantic for validation** - Type safety without complexity  
3. **ASCII only** - No Unicode/emoji in code (tool compatibility)
4. **Stateless** - Use Listmonk for all state storage
5. **Environment config** - No config files

## Making Changes

### Adding a CLI Command
1. Add function to `rssmonk.py` 
2. Decorate with `@app.command()`
3. Use existing patterns for error handling
4. Test with `uv run rssmonk your-command`

### Adding an API Endpoint  
1. Add function to `rssmonk.py`
2. Decorate with `@app.post()` etc
3. Use existing request/response models
4. Test with `uvicorn rssmonk:api_app --reload`

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

# Run locally with Listmonk
just start

# Test CLI commands
export LISTMONK_ADMIN_PASSWORD=test123
just feeds health

# Test API server
just api
curl http://localhost:8000/health
```

## Code Style

- Use ASCII text instead of Unicode: `[SUCCESS]` not `✅`
- Keep functions small and focused
- Use type hints with Pydantic models
- Follow existing error handling patterns
- Add docstrings for public functions

## Getting Help

- Check existing code patterns
- Look at tests for examples  
- Ask questions in issues
- Follow the design principles above
