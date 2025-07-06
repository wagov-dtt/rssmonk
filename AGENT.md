# RSS Monk Agent Guide

## Quick Start
```bash
just deploy-local  # Deploy complete stack to k3d
```

## Core Commands
- `just setup-k3d` - Create k3d cluster
- `just deploy-local` - Deploy postgres, listmonk, mailpit using kustomize
- `just analyze` - Run scc to analyze codebase complexity
- `just simulate-cron [5min|daily|weekly]` - Test feed fetcher locally
- `just feed-manager <command>` - Manage RSS feeds and subscribers
- `k9s` - Interactively monitor/debug cluster

## RSS Feed Management Strategy

### Feed Storage as Listmonk Lists
Each RSS feed is stored as a **Listmonk list** with:
- **List name**: RSS feed title (e.g., "TechCrunch", "Hacker News")
- **Description**: Feed URL and metadata
- **Tags**: Control cronjob behavior

### Tag-Based Frequency Control
Lists use tags to control polling frequency:
- `freq:5min` - Poll every 5 minutes
- `freq:daily` - Poll daily at 5pm
- `freq:weekly` - Poll weekly on Friday at 5pm
- `last-seen:freq:5min:GUID` - Track last processed item per frequency
- `last-poll:freq:daily:ISO8601` - Track last poll time per frequency

### HTTP Caching Strategy
Scripts use `hishel` + `feedparser` for efficient polling:
- **ETag headers**: Avoid re-downloading unchanged feeds
- **Last-Modified**: Conditional requests
- **Cache-Control**: Respect feed publisher caching directives
- **Local cache**: Store feed responses to minimize bandwidth

## Cronjob Scripts

### RSS Feed Fetcher
```bash
uv run scripts/feed-fetcher.py
```
- Polls RSS feeds based on frequency tags
- Creates campaigns for new items
- Updates `last-seen` tags with latest GUIDs
- Uses HTTP caching for efficient polling

### Campaign Cleanup
```bash
uv run scripts/cleanup-campaigns.py
```
- Removes old RSS campaigns (30+ days)
- Keeps database clean
- Preserves manual campaigns (non-RSS)

## Local Testing
```bash
# Access services locally
kubectl port-forward -n rssmonk svc/listmonk-service 9000:80    # Listmonk
kubectl port-forward -n rssmonk svc/mailpit 8025:8025          # Mailpit
```

## Architecture
- **CNCF Based**: k3d + postgres + listmonk + mailpit
- **Namespace**: `rssmonk` for all resources
- **Caching**: Hishel for HTTP caching
- **Feeds**: Stored as listmonk lists with tag-based controls

## Development Philosophy
- **Reduce complexity** - Prefer simple solutions over complex ones
- **Keep it concise** - Minimize code, configs, and documentation
- **Minimal comments** - Only comment design decisions, not obvious code
- **Self-documenting code** - Code should be readable without explanation

## Code Style
- Python scripts use uv inline dependencies
- YAML uses 2-space indentation
- Environment variables with `LISTMONK_` prefix
- Container images use latest tags for development
