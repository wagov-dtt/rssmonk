set dotenv-load

app_ns := "rssmonk"

# Choose a task to run
default:
  just --choose

# Analyze codebase complexity with scc
analyze:
  scc --exclude-dir .git --by-file .

# Setup k3d cluster with local registry
setup-k3d:
  k3d cluster create rssmonk --port "8080:80@loadbalancer"

k3d:
  k3d cluster list | grep rssmonk || just setup-k3d

deploy-local: k3d
  kubectl get namespace {{app_ns}} || kubectl create namespace {{app_ns}}
  kubectl apply -k kustomize/overlays/k3d

# Simulate cron for frequency (5min|daily|weekly)
simulate-cron freq:
  @[[ "{{freq}}" =~ ^(5min|daily|weekly)$ ]] || (echo "Usage: just simulate-cron [5min|daily|weekly]" && exit 1)
  uv run scripts/feed-fetcher.py

# Feed management CLI
feed-manager *args:
  uv run scripts/feed-manager.py {{args}}
