# RSS Monk Agent Guide

## Quick Start
```bash
just prereqs  # Install development tools via mise
just tilt     # Start Tilt for hot-reload development
```

## Commands
**Setup:** `prereqs` `install` `setup`  
**Development:** `tilt` `tilt-down` `api` `check` `lint` `format` `type-check`  
**Deployment:** `start` `deploy-k3d` `build` `status` `logs` `clean` `health`  
**Testing:** `test` (full restart), `test quick` (reuse cluster), `test-one` (single test), `test-lifecycle`  

### Agent Testing Commands
Agents CAN run individual tests directly using `just test-one`. This command assumes the k3d cluster is already running (human should start it with `just start` or `just tilt` first).

```bash
# Run a single test file
just test-one tests/test_api_account.py -v

# Run a specific test
just test-one tests/test_api_unsubscribe.py::TestRSSMonkUnsubscribe::test_post_unsubscribe_no_credentials -v

# Run tests matching a pattern
just test-one -k "unsubscribe" -v
```

**Long-running commands (ask human to run):** `just test`, `just start`, `just tilt`

## Local Access
- **RSS Monk API:** http://localhost:8000
- **Listmonk:** http://localhost:9000 (admin/admin123)
- **Mailpit:** http://localhost:8025

---

## Development Philosophy (The Grug Way)

This project follows principles from [grugbrain.dev](https://grugbrain.dev) - a philosophy of pragmatic simplicity.

### Complexity is the Enemy

> complexity very, very bad

The apex predator of any codebase is complexity. It enters through well-meaning abstractions, premature optimisations, and features nobody asked for. When you sense complexity creeping in, reach for the magic word: **"no"**.

- No, we don't need that abstraction yet
- No, we don't need to handle that edge case
- No, we don't need another dependency

### 80/20 Solutions

When you must say "ok" to a feature, build the 80/20 solution - 80% of the value with 20% of the code. It might not have all the bells and whistles, but it works and keeps the complexity demon at bay.

### Factor Code Later

> early on in project everything very abstract and like water

Don't factor your code too early. Let the system's shape emerge through experience. Good cut points reveal themselves over time - narrow interfaces that trap complexity inside like a crystal. Grug waits patiently for these to appear.

### Integration Tests Over Unit Tests

> integration tests sweet spot according to grug

Unit tests break when implementation changes. End-to-end tests are hard to debug. Integration tests hit the sweet spot - high enough to test correctness, low enough to see what broke.

Focus testing effort on:
1. Integration tests at natural cut points (API boundaries)
2. A small, well-curated end-to-end test suite for critical paths
3. Unit tests sparingly, mainly at project start

### Logging Matters

> logging very important!

Log all major logical branches. Include request IDs for tracing across services. Make log levels dynamically controllable. Good logging pays off massively when debugging production issues.

### No FOLD (Fear Of Looking Dumb)

> very good if senior grug willing to say publicly: "hmmm, this too complex for grug"

It's OK to say "this is too complex for me to understand". Admitting confusion makes it safe for others to do the same. FOLD is a major source of complexity demon power.

### Chesterton's Fence

> grug not start tearing code out willy nilly, no matter how ugly look

Before removing code, understand why it exists. The world is ugly and gronky, and sometimes code must be too. Take time to understand a system before "improving" it.

### Expression Clarity

Break complex conditionals into named variables:

```python
# Hard to debug
if contact and not contact.is_active() and (contact.in_group(FAMILY) or contact.in_group(FRIENDS)):
    ...

# Easier to debug - see each value in debugger
contact_is_inactive = not contact.is_active()
contact_is_family_or_friends = contact.in_group(FAMILY) or contact.in_group(FRIENDS)
if contact and contact_is_inactive and contact_is_family_or_friends:
    ...
```

### Keep Commits Reviewable

Commit in small chunks (~500 lines or less) that a human can easily review. Large commits hide bugs and make code review painful. If a change is large, break it into logical steps.

---

## Documentation Standards
- **Essential information only** - Focus on what users need to know
- **Concrete examples** - Show actual commands and outputs
- **Minimal explanation** - Let the code and commands speak for themselves
- **Clear structure** - Organise information logically
- **Australian English** - Use Australian spelling and terminology

## Code Style
- Python scripts use uv/ruff
- YAML uses 2-space indentation
- Environment variables with `LISTMONK_ADMIN_USER` and `LISTMONK_ADMIN_PASSWORD` prefix
- Container images use latest tags for development
- **ASCII only**: Avoid Unicode/emoji characters in code files (difficult for some tools to parse)
  - Use simple text: "OK", "ERROR", "SUCCESS" instead of emojis
  - Use ASCII symbols: "-", "*", "+" for bullets and decoration

## Development Tools
- **uv**: Python package management and script execution
- **mise**: Version management for development tools (ruff, mypy, tilt, etc.)
- **tilt**: Local Kubernetes development with hot-reload
- **ruff**: Python linting and formatting
- **mypy**: Type checking (run via uv for proper environment)
- **pytest**: Testing framework (run via uv with test extras)
- **k3d**: Lightweight local Kubernetes clusters

---

## Technical Implementation Notes

### API Architecture
- **Passthrough Proxy**: RSS Monk API acts as authenticated proxy to [Listmonk](https://listmonk.app/)
- **RSS Monk Core Endpoints**:
  - `/api/feeds` - Feed management with RSS Monk logic
  - `/api/feeds/process` - Feed processing (individual or bulk for cron)
  - `/api/feeds/configurations/{url}` - URL configuration management
  - `/api/cache/stats` - RSS feed cache statistics
- **Listmonk Passthrough**: All other `/api/*` requests pass through to Listmonk with auth validation
- **OpenAPI Documentation**: Comprehensive OpenAPI spec with all endpoints documented
- **Dynamic Content**: Pydantic models provide validation and documentation

### Authentication Strategy
- **Listmonk Validation**: All auth validated directly against Listmonk API
- **Dependency Injection**: FastAPI dependency validates credentials per request for `/api/*` routes
- **Passthrough Headers**: Auth headers preserved and forwarded to Listmonk
- **No Local Auth**: No separate authentication system - relies on Listmonk entirely

### Listmonk Integration
[Listmonk](https://listmonk.app/) is a high-performance bulk messaging system with subscriber management, list expansion, and email campaign capabilities. It uses PostgreSQL as its primary datastore. RSS Monk acts as a proxy layer that adds RSS feed processing capabilities to Listmonk's messaging infrastructure.

### State Management Strategy
- **No persistent state files**: All state stored in Listmonk list tags
- **UUID-based deduplication**: RSS item UUIDs prevent duplicate email campaigns  
- **URL hashing**: SHA-256 full digest for guaranteed unique feed identification
- **Frequency isolation**: Separate last-guid tracking per polling frequency

### Error Handling Approach
- **Fail-fast validation**: Environment variable validation at startup
- **Graceful degradation**: Individual feed failures don't stop batch processing
- **Structured logging**: All errors logged with context for debugging

### Development Workflow
- **Tilt for development**: `just tilt` starts hot-reload workflow with k3d
- **justfile recipes**: All common operations scripted for consistency
- **k3d cluster**: Lightweight local Kubernetes for realistic testing  
- **Mailpit integration**: Email debugging without external SMTP dependencies

---

## Common User Support Issues
- **"Nothing happening"** - Check `just logs` and `just status`
- **"Emails not arriving"** - Verify RSS feed URL, check Mailpit at :8025
- **"Want to start over"** - Run `just clean && just start`
- **"What frequencies work"** - instant, daily

## Outstanding Work

See the **Known Limitations** section in [README.md](README.md) for tracking incomplete features and planned improvements.
