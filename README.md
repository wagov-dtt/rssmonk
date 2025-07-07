# RSS Monk

RSS Monk turns RSS feeds into email newsletters.

## Quick Start

```bash
just prereqs  # Install k3d, kubectl, scc, uv
just start    # Deploy RSS Monk on k3d cluster
just feeds add-feed https://www.abc.net.au/news/feed/10719986/rss.xml daily
```

New content arrives automatically as emails.

## Common Tasks

### Managing Your Feeds
```bash
# See all your feeds
just feeds list-feeds

# Add a new feed (daily emails)
just feeds add-feed https://www.abc.net.au/news/feed/10719986/rss.xml daily

# Add a feed with frequent updates
just feeds add-feed https://www.abc.net.au/news/feed/10719986/rss.xml 5min

# Add a weekly digest
just feeds add-feed https://www.abc.net.au/news/feed/10719986/rss.xml weekly
```

### Checking Status
```bash
# Is everything running?
just status

# What's happening behind the scenes?
just logs

# Test a specific feed
just test-fetch daily
```

### Maintenance
```bash
# Stop everything (removes k3d cluster)
just clean

# Start fresh
just clean && just start
```

## Examples

```bash
# ABC News (daily)
just feeds add-feed https://www.abc.net.au/news/feed/10719986/rss.xml daily

# ABC News (weekly digest)
just feeds add-feed https://www.abc.net.au/news/feed/10719986/rss.xml weekly

# ABC News (frequent updates)
just feeds add-feed https://www.abc.net.au/news/feed/10719986/rss.xml 5min
```

## Web Interface

- **Newsletter Management**: http://localhost:9000 (admin/admin123)
- **Email Testing**: http://localhost:8025

## Installation Requirements

- **k3d, kubectl, scc, uv** (installed via `just prereqs`)

## Development

```bash
just test && just lint
```
