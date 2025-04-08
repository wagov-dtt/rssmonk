set dotenv-load

app_ns := "rssmonk"

# Choose a task to run
default:
  just --choose

# Install project tools
prereqs:
  brew bundle install

# Enable full use of parent container, snapshots, block volumes
# on base minikube setup
setup-minikube: prereqs
  minikube config set memory no-limit
  minikube config set cpus no-limit
  # Setup minikube
  minikube start
  minikube addons enable volumesnapshots
  minikube addons enable csi-hostpath-driver
  minikube addons disable storage-provisioner
  minikube addons disable default-storageclass

minikube:
  sudo chown $(whoami) /var/run/docker.sock
  minikube status || just setup-minikube

HELM_UPGRADE := "0"
HELM_ACTION := if HELM_UPGRADE == "1" { "upgrade --install" } else { "install" }

helm-install NAME NAMESPACE CHART REPO:
  kubectl get namespace {{NAMESPACE}} || kubectl create namespace {{NAMESPACE}}
  helm repo add {{parent_directory(CHART)}} {{REPO}}
  helm {{HELM_ACTION}} {{NAME}} {{CHART}} --namespace {{NAMESPACE}} -f kustomize/helm-values/{{NAME}}.yaml

# Structure: "NAME": "NAMESPACE CHART REPO"
HELM_INSTALLS := '{
  "traefik": "traefik traefik/traefik https://traefik.github.io/charts",
  "everest-core": "everest-system percona/everest https://percona.github.io/percona-helm-charts",
  "elastic-operator": "elastic-system elastic/eck-operator https://helm.elastic.co",
  "k8up": "k8up k8up-io/k8up https://k8up-io.github.io/k8up"
}'

# Use helm to enable traefik (gateway), everest (dbs) in a kubernetes cluster
install-helm-charts +CHARTS="traefik everest-core":
  #kubectl apply --server-side -f "https://github.com/k8up-io/k8up/releases/download/v2.12.0/k8up-crd.yaml"
  @-for name in {{CHARTS}}; do just helm-install $name $(echo '{{HELM_INSTALLS}}' | jq -r ".\"$name\""); done

deploy-local: minikube
  just install-helm-charts
  kubectl get namespace {{app_ns}} || kubectl create namespace {{app_ns}}
  kubectl apply -k kustomize/overlays/minikube
  kubectl get secret everest-secrets-postgres01 --namespace=everest -o yaml | grep -v namespace | kubectl apply --namespace={{app_ns}} -f - --force