set dotenv-load
set positional-arguments

# List available tasks
default:
  just --list

# Deploy to k3d cluster (primary method)
start: prereqs
  just build
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

# Deploy to k3d cluster (advanced)
deploy-k3d:
  k3d cluster create rssmonk --port "9000:30900@server:0" --port "8025:30825@server:0" || true
  kubectl get namespace rssmonk || kubectl create namespace rssmonk
  kubectl apply -k kustomize/overlays/k3d
  @echo "Waiting for pods..."
  kubectl wait --for=condition=ready pod -l app=listmonk-app -n rssmonk --timeout=120s
  kubectl wait --for=condition=ready pod -l app=mailpit -n rssmonk --timeout=120s
  @echo "[SUCCESS] K3d deployment complete"

# Test feed fetching (instant|daily)
test-fetch freq:
  @case "{{freq}}" in instant|daily) echo "Running rssmonk-cron for frequency: {{freq}}" ;; *) echo "Usage: just test-fetch [instant|daily]" && exit 1 ;; esac
  uv run rssmonk-cron {{freq}}

# Health check via API
health:
  @curl -s http://localhost:8000/health | python -m json.tool

# Lint Python code
lint:
  ruff check --fix src/rssmonk/

# Format Python code  
format:
  ruff format src/rssmonk/

# Type check (warnings only - strict mode disabled)
type-check:
  uv run mypy src/rssmonk/ || echo "[WARN] Type check has issues - see above"

# Install dependencies
install:
  uv sync
  uv pip install -e .

# Install prerequisites (tools needed for development)
prereqs:
  @echo "Installing prerequisites via mise..."
  mise install

# Run all checks (lint + type-check)
check: lint type-check

# Run tests (API started automatically by pytest fixture)
test quick="" *args="": (_test-cluster quick)
  uv run --extra test pytest {{args}}

# Ensure k3d cluster is running
[private]
_test-cluster quick:
  @if [ "{{quick}}" = "" ]; then \
    echo "Full restart: cleaning and starting k3d cluster..." && \
    just clean || true && \
    just start && \
    echo "Waiting for services to initialize..." && \
    sleep 30; \
  fi

# Run lifecycle tests (requires running k3d cluster)
test-lifecycle:
  @echo "Running lifecycle tests against k3d cluster..."
  uv run --extra test pytest tests/test_lifecycle.py -v

# Start API server in development mode (with test routes if RSSMONK_TESTING=1)
api: start install
  RSSMONK_TESTING=1 uv run fastapi dev src/rssmonk/api.py --port 8000 --host 0.0.0.0

# Setup for new contributors
setup: prereqs install check
  @echo ""
  @echo "[SUCCESS] RSS Monk development environment ready!"
  @echo ""
  @echo "Quick start:"
  @echo "  just start             # Deploy k3d cluster"
  @echo "  just api               # Start API server"
  @echo "  just test quick        # Run tests (cluster already running)"
  @echo ""
  @echo "Environment variables (for production):"
  @echo "  LISTMONK_ADMIN_PASSWORD=your-token"
  @echo "  LISTMONK_URL=http://localhost:9000"

# Analyze code complexity
analyze:
  scc --exclude-dir .git --by-file .

# Build container image with Railpack and import to k3d
build:
  @docker start buildkit 2>/dev/null || docker run --rm --privileged -d --name buildkit moby/buildkit
  BUILDKIT_HOST=docker-container://buildkit railpack build . --name rssmonk-api
  @k3d cluster list rssmonk >/dev/null 2>&1 && k3d image import rssmonk-api -c rssmonk || true

# Update the dependancies
update:
  uv lock --upgrade