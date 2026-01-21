set dotenv-load
set positional-arguments

# k3d cluster name
k3d_cluster := "rssmonk"
k3d_context := "k3d-" + k3d_cluster

# List available tasks
default:
  just --list

# ============================================================================
# SETUP
# ============================================================================

# Install prerequisites (tools needed for development)
prereqs:
  @echo "Installing prerequisites via mise..."
  mise install

# Install Python dependencies
install:
  uv sync
  uv pip install -e .

# Setup for new contributors
setup: prereqs install check
  @echo ""
  @echo "[SUCCESS] RSS Monk development environment ready!"
  @echo ""
  @echo "Quick start:"
  @echo "  just tilt              # Start Tilt for hot-reload development"
  @echo "  just test quick        # Run tests (cluster already running)"
  @echo ""
  @echo "Environment variables (for production):"
  @echo "  LISTMONK_ADMIN_PASSWORD=your-token"
  @echo "  LISTMONK_URL=http://localhost:9000"

# ============================================================================
# DEVELOPMENT
# ============================================================================

# Start Tilt development environment (hot-reload workflow)
tilt: prereqs _k3d-context
  @k3d cluster list {{k3d_cluster}} >/dev/null 2>&1 || just deploy-k3d
  tilt up

# Stop Tilt (cluster remains running)
tilt-down:
  tilt down

# Start API server in development mode (with test routes)
api: start install
  RSSMONK_TESTING=1 uv run fastapi dev src/rssmonk/api.py --port 8000 --host 0.0.0.0

# Health check via API
health:
  @curl -s http://localhost:8000/health | python -m json.tool

# ============================================================================
# CODE QUALITY
# ============================================================================

# Run all checks (lint + format check + type-check)
check: lint format-check type-check
  @echo "[SUCCESS] All checks passed"

# Lint Python code (with autofix)
lint:
  ruff check --fix src/ tests/

# Check code formatting (no changes)
format-check:
  ruff format --check src/ tests/

# Format Python code
format:
  ruff format src/ tests/

# Type check
type-check:
  uv run mypy src/rssmonk/ || echo "[WARN] Type check has issues - see above"

# Lint and format in one go
fix: lint format

# ============================================================================
# TESTING
# ============================================================================

# Run tests (API started automatically by pytest fixture)
test quick="" *args="": (_test-cluster quick)
  uv run --extra test pytest {{args}}

# Run a single test (assumes cluster is running)
test-one *args="": _k3d-context _kill-stale-api
  uv run --extra test pytest {{args}}

# Run tests with verbose output
test-v quick="": (_test-cluster quick)
  uv run --extra test pytest -v

# Run lifecycle tests (requires running k3d cluster)
test-lifecycle: _k3d-context
  @echo "Running lifecycle tests against k3d cluster..."
  uv run --extra test pytest tests/test_lifecycle.py -v

# Test feed fetching (instant|daily)
test-fetch freq:
  @case "{{freq}}" in instant|daily) echo "Running rssmonk-cron for frequency: {{freq}}" ;; *) echo "Usage: just test-fetch [instant|daily]" && exit 1 ;; esac
  uv run rssmonk-cron {{freq}}

# Ensure k3d cluster is running and clean up stale processes
[private]
_test-cluster quick: _k3d-context _kill-stale-api
  @if [ "{{quick}}" = "" ]; then \
    echo "Full restart: cleaning and starting k3d cluster..." && \
    just clean || true && \
    just start && \
    echo "Waiting for services to initialize..." && \
    sleep 30; \
  fi

# Kill stale API processes (separate recipe to handle exit codes properly)
[private]
_kill-stale-api:
  -pkill -f "uvicorn.*rssmonk.api" || true

# Switch to k3d context (silently)
[private]
_k3d-context:
  @kubectl config use-context {{k3d_context}} >/dev/null 2>&1 || true

# ============================================================================
# DEPLOYMENT
# ============================================================================

# Deploy to k3d cluster (primary method)
start: prereqs
  just build
  @echo "Starting RSS Monk on k3d..."
  just deploy-k3d

# Deploy to k3d cluster (creates cluster if needed)
deploy-k3d: _k3d-context
  k3d cluster create {{k3d_cluster}} --port "9000:30900@server:0" --port "8025:30825@server:0" --port "8000:30901@server:0" || true
  @just _k3d-context
  kubectl get namespace rssmonk || kubectl create namespace rssmonk
  kubectl apply -k kustomize/overlays/k3d
  @echo "Waiting for pods..."
  kubectl wait --for=condition=ready pod -l app=listmonk-app -n rssmonk --timeout=120s
  kubectl wait --for=condition=ready pod -l app=mailpit -n rssmonk --timeout=120s
  @echo "[SUCCESS] K3d deployment complete"

# Build container image with Railpack and import to k3d
build:
  @docker start buildkit 2>/dev/null || docker run --rm --privileged -d --name buildkit moby/buildkit
  BUILDKIT_HOST=docker-container://buildkit railpack build . --name rssmonk-api
  @k3d cluster list {{k3d_cluster}} >/dev/null 2>&1 && k3d image import rssmonk-api -c {{k3d_cluster}} || true

# Show service status
status: _k3d-context
  @kubectl get pods -n rssmonk

# Show service logs
logs: _k3d-context
  @kubectl logs -l app=listmonk-app -n rssmonk -f

# Show rssmonk-api logs
logs-api: _k3d-context
  @kubectl logs -l app=rssmonk-api -n rssmonk -f

# Clean up (remove k3d cluster)
clean:
  @echo "Cleaning up..."
  @k3d cluster delete {{k3d_cluster}} || true

# ============================================================================
# UTILITIES
# ============================================================================

# Update dependencies
update:
  uv lock --upgrade

# Analyze code complexity
analyze:
  scc --exclude-dir .git --by-file .
