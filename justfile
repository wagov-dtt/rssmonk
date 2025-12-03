set dotenv-load
set positional-arguments

# List available tasks
default:
  just --list

# Deploy to k3d cluster (primary method)
start: prereqs
  docker build -t local/listmonk-proxy .
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

# Manage RSS feeds
feeds *args:
  uv run rssmonk "$@"

# Health check
health:
  uv run rssmonk health

# Lint Python code
lint:
  ruff check --fix src/

# Format Python code  
format:
  ruff format src/

# Type check
type-check:
  uv run mypy src/

# Install dependencies
install:
  uv sync
  uv pip install -e .

# Install prerequisites (tools needed for development)
prereqs:
  @echo "Installing prerequisites via mise..."
  mise install

# Run all checks (lint + type-check + test)
check: lint type-check test

# Run tests
test quick="":
  #!/usr/bin/env sh
  if [ "{{quick}}" == "" ]; then
    echo "Just: Full restart"
    just clean
    just start
    echo "Just: Waiting for pods to start"
    sleep 60
  fi
  uv run --extra test pytest

# Run integration tests (requires k3d cluster)
test-integration:
  @echo "Running integration tests..."
  @echo "Ensure k3d cluster is running: just start"
  uv run --extra test python tests/test_integration.py

# Run end-to-end validation workflow
validate:
  @echo "Running end-to-end validation workflow..."
  @echo "This will test: feed creation, subscriptions, email delivery, and cleanup"
  @just test-integration

# Start API server in development mode
api: start install
  uv run fastapi dev src/rssmonk/api.py --port 8000 --host 0.0.0.0

# Setup for new contributors
setup: prereqs install check
  @echo ""
  @echo "[SUCCESS] RSS Monk development environment ready!"
  @echo ""
  @echo "Available commands:"
  @echo "  just feeds --help      # Try the CLI"
  @echo "  just api               # Start API server"
  @echo "  just check             # Run all checks"
  @echo ""
  @echo "Environment variables (for real usage):"
  @echo "  LISTMONK_ADMIN_PASSWORD=your-token"
  @echo "  LISTMONK_URL=http://localhost:9000"

# Analyze code complexity
analyze:
  scc --exclude-dir .git --by-file .

# Docker build to test
docker:
  docker build -t  wagov-dtt/rssmonk:dev .
  docker images