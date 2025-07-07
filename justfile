set dotenv-load
set positional-arguments

# Choose a task to run
default:
  just --choose

# 🚀 Deploy to k3d cluster (primary method)
start:
  @echo "🚀 Starting RSS Monk on k3d..."
  just deploy-k3d



# 📊 Show service status  
status:
  @kubectl get pods -n rssmonk

# 📝 Show service logs
logs:
  @kubectl logs -l app=listmonk-app -n rssmonk -f



# 🧹 Clean up (remove k3d cluster)
clean:
  @echo "🧹 Cleaning up..."
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
  @echo "✅ K3d deployment complete"

# 🔄 Test feed fetching (5min|daily|weekly)
test-fetch freq:
  @case "{{freq}}" in 5min|daily|weekly) echo "Running rssmonk-fetch for frequency: {{freq}} (force + auto-send)" ;; *) echo "Usage: just test-fetch [5min|daily|weekly]" && exit 1 ;; esac
  uv run rssmonk-fetch --frequency {{freq}} --force --auto-send

# 🛠️ Manage RSS feeds
feeds *args:
  uv run rssmonk-cli "$@"

# 🩺 Health check
health:
  uv run python -m rssmonk.health

# 🧪 Run tests
test:
  uv run --with pytest pytest tests/

# 🧹 Lint Python code
lint:
  uv run --with ruff ruff check --fix src/ tests/

# 📊 Analyze code complexity
analyze:
  scc --exclude-dir .git --by-file .
