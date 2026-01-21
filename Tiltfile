# Tiltfile for RSS Monk local development
# Requires: k3d cluster named 'rssmonk' (created via `just deploy-k3d`)

# Only allow k3d-rssmonk context to prevent accidental prod deployments
allow_k8s_contexts('k3d-rssmonk')

# Build rssmonk-api using Railpack via custom_build
# Rebuilds on any source changes, then imports to k3d
custom_build(
    'rssmonk-api',
    'docker start buildkit 2>/dev/null || docker run --rm --privileged -d --name buildkit moby/buildkit && ' +
    'BUILDKIT_HOST=docker-container://buildkit railpack build . --name rssmonk-api && ' +
    'k3d image import rssmonk-api -c rssmonk',
    deps=['src/', 'pyproject.toml', 'railpack.json'],
    ignore=['**/__pycache__', '**/*.pyc', '.git'],
)

# Load kustomize manifests for k3d overlay
k8s_yaml(kustomize('kustomize/overlays/k3d'))

# Configure resources with port forwards and labels
k8s_resource(
    'listmonk-app',
    port_forwards=['9000:9000'],
    labels=['backend'],
)

k8s_resource(
    'mailpit',
    port_forwards=['8025:8025'],
    labels=['email'],
)

k8s_resource(
    'rssmonk-api',
    port_forwards=['8000:8000'],
    labels=['api'],
    resource_deps=['listmonk-app'],  # Wait for Listmonk before starting
)

k8s_resource(
    'postgres',
    labels=['database'],
)
