set dotenv-load
set positional-arguments

# Choose a task to run
default:
  just --choose

# Deploy to k3d cluster (primary method)
start:
  @echo "Starting RSS Monk on k3d..."
  just deploy-k3d



# Show service status  
status:
  @kubectl get pods -n rssmonk

# Show service logs
logs:
  @kubectl logs -l app=listmonk-app -n rssmonk -f



# Clean up (remove k3d cluster)
clean:
  @echo "Cleaning up..."
  @k3d cluster delete rssmonk

# Install prerequisites (for k3d deployment)
prereqs:
  @echo "Installing prerequisites..."
  brew install k3d kubectl scc uv

# Deploy to k3d cluster (advanced)
deploy-k3d:
  k3d cluster create rssmonk --port "9000:30900@server:0" --port "8025:30825@server:0" || true
  kubectl get namespace rssmonk || kubectl create namespace rssmonk
  kubectl apply -k kustomize/overlays/k3d
  @echo "Waiting for pods..."
  kubectl wait --for=condition=ready pod -l app=listmonk-app -n rssmonk --timeout=120s
  kubectl wait --for=condition=ready pod -l app=mailpit -n rssmonk --timeout=120s
  @echo "[SUCCESS] K3d deployment complete"

# Test feed fetching (5min|daily|weekly)
test-fetch freq:
  @case "{{freq}}" in 5min|daily|weekly) echo "Running rssmonk-cron for frequency: {{freq}}" ;; *) echo "Usage: just test-fetch [5min|daily|weekly]" && exit 1 ;; esac
  uv run rssmonk-cron {{freq}}

# Manage RSS feeds
feeds *args:
  uv run rssmonk "$@"

# Health check
health:
  uv run rssmonk health

# Run tests
test:
  uv run pytest

# Lint Python code
lint:
  uv run ruff check src/ tests/

# Format Python code  
format:
  uv run ruff format src/ tests/

# Type check
type-check:
  uv run mypy src/

# Install dependencies
install:
  uv sync

# Run all checks
check: lint type-check test

# Start API server in development mode
api:
  uv run uvicorn rssmonk.api:app --reload --host 0.0.0.0 --port 8000

# Setup for new contributors
setup: install check
  @echo ""
  @echo "[SUCCESS] RSS Monk development environment ready!"
  @echo ""
  @echo "Available commands:"
  @echo "  just feeds --help      # Try the CLI"
  @echo "  just api               # Start API server"
  @echo "  just test              # Run tests"
  @echo "  just check             # Run all checks"
  @echo ""
  @echo "Environment variables (for real usage):"
  @echo "  LISTMONK_APITOKEN=your-token"
  @echo "  LISTMONK_URL=http://localhost:9000"

# Analyze code complexity
analyze:
  scc --exclude-dir .git --by-file .
