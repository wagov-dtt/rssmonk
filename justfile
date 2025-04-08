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

deploy-local: minikube
  just install-helm-charts
  kubectl get namespace {{app_ns}} || kubectl create namespace {{app_ns}}
  kubectl apply -k kustomize/overlays/minikube