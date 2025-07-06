# RSS Monk Scripts

This directory contains Python scripts for RSS feed processing and Listmonk management.

## RSS Feed Management Strategy

RSS feeds are stored as **Listmonk lists** with tag-based control:

### Creating RSS Feed Lists
1. Create a new list in Listmonk
2. Set the **description** to the RSS feed URL
3. Add frequency tags with specific timing
4. The script will automatically add tracking tags

### Frequency Tag Examples
- `freq:5min` - Poll every 5 minutes
- `freq:daily` - Poll daily at 5pm
- `freq:weekly` - Poll weekly on Friday at 5pm

### Example List Configuration
- **Name**: "Hacker News"
- **Description**: "https://hnrss.org/frontpage"
- **Tags**: `freq:daily`

## Scripts

### feed-fetcher.py
Fetches RSS feeds stored as Listmonk lists and creates campaigns for new items.

**Features:**
- HTTP caching with hishel (respects ETag, Last-Modified, Cache-Control)
- Frequency-based polling (5min, daily, weekly)
- Per-frequency tracking of last seen items
- Conditional requests to minimize bandwidth

**Usage:**
```bash
# Local execution with uv
uv run scripts/feed-fetcher.py

# Or with python directly
python scripts/feed-fetcher.py
```

**Environment Variables:**
- `LISTMONK_URL`: Listmonk base URL (default: http://localhost:9000)
- `LISTMONK_USERNAME`: Listmonk username (default: listmonk)
- `LISTMONK_PASSWORD`: Listmonk password (default: listmonk)

### cleanup-campaigns.py
Removes old RSS campaigns to keep the database clean.

**Usage:**
```bash
# Local execution with uv
uv run scripts/cleanup-campaigns.py

# Or with python directly
python scripts/cleanup-campaigns.py
```

**Environment Variables:**
- `LISTMONK_URL`: Listmonk base URL (default: http://localhost:9000)
- `LISTMONK_USERNAME`: Listmonk username (default: listmonk)
- `LISTMONK_PASSWORD`: Listmonk password (default: listmonk)
- `CLEANUP_KEEP_DAYS`: Days to keep campaigns (default: 30)
- `CLEANUP_DRY_RUN`: Enable dry run mode (default: false)

## Development

These scripts use uv's inline script dependencies feature, so they can be run without a virtual environment or separate requirements file.

### Container Deployment

These scripts will eventually be packaged as container images and deployed as Kubernetes CronJobs.

### Local Testing

With mailpit running in the cluster, you can test email delivery locally:

```bash
# Port forward mailpit web interface
kubectl port-forward -n rssmonk svc/mailpit 8025:8025

# Access mailpit at http://localhost:8025
```

## Script Dependencies

All dependencies are embedded in the script files using uv's inline dependency format. No separate requirements.txt files are needed.
