#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLUSTER_NAME="${KIND_CLUSTER_NAME:-oficina}"
CONTEXT_NAME="kind-${CLUSTER_NAME}"
NAMESPACE="${K8S_NAMESPACE:-oficina}"
IMAGE="${APP_IMAGE:-oficina-app:latest}"
METRICS_SERVER_VERSION="${METRICS_SERVER_VERSION:-v0.8.1}"

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "ERRO: comando obrigatorio nao encontrado: $1" >&2
    exit 1
  }
}

for command_name in docker kind kubectl python; do
  require_command "$command_name"
done

cd "$ROOT_DIR"

if kind get clusters | grep -Fxq "$CLUSTER_NAME"; then
  echo "Reutilizando cluster Kind '$CLUSTER_NAME'."
  kubectl cluster-info --context "$CONTEXT_NAME" >/dev/null
else
  echo "Criando cluster Kind '$CLUSTER_NAME'."
  kind create cluster --name "$CLUSTER_NAME" --wait 180s
fi
kubectl config use-context "$CONTEXT_NAME" >/dev/null

echo "Construindo e carregando imagem $IMAGE."
docker build -t "$IMAGE" .
kind load docker-image "$IMAGE" --name "$CLUSTER_NAME"

kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml

if kubectl get secret oficina-secret -n "$NAMESPACE" >/dev/null 2>&1; then
  for key in DJANGO_SECRET_KEY POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD; do
    encoded_value="$(kubectl get secret oficina-secret -n "$NAMESPACE" -o "jsonpath={.data.${key}}")"
    decoded_value="$(python -c 'import base64,sys; print(base64.b64decode(sys.argv[1]).decode())' "$encoded_value")"
    if [[ -z "$decoded_value" || "$decoded_value" == *CHANGE_ME* ]]; then
      echo "ERRO: Secret existente contem valor vazio ou placeholder inseguro em $key." >&2
      exit 1
    fi
  done
  echo "Reutilizando Secret existente para preservar um PostgreSQL persistente."
else
  DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY:-$(python -c 'import secrets; print(secrets.token_urlsafe(48))')}"
  POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-$(python -c 'import secrets; print(secrets.token_urlsafe(32))')}"
  POSTGRES_DB="${POSTGRES_DB:-oficina}"
  POSTGRES_USER="${POSTGRES_USER:-oficina_user}"

  kubectl create secret generic oficina-secret \
    --namespace "$NAMESPACE" \
    --from-literal="DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY" \
    --from-literal="POSTGRES_DB=$POSTGRES_DB" \
    --from-literal="POSTGRES_USER=$POSTGRES_USER" \
    --from-literal="POSTGRES_PASSWORD=$POSTGRES_PASSWORD" \
    --dry-run=client -o yaml | kubectl apply -f -
fi

kubectl apply -f k8s/postgres-service.yaml
kubectl apply -f k8s/postgres-statefulset.yaml
kubectl rollout status statefulset/postgres -n "$NAMESPACE" --timeout=240s
kubectl wait --for=condition=Ready pod -l app=postgres -n "$NAMESPACE" --timeout=240s

echo "Removendo apenas o Job de migration anterior para permitir uma nova execucao idempotente."
kubectl delete job oficina-migrate -n "$NAMESPACE" --ignore-not-found --wait=true
kubectl apply -f k8s/migration-job.yaml
kubectl wait --for=condition=Complete job/oficina-migrate -n "$NAMESPACE" --timeout=240s
kubectl logs job/oficina-migrate -n "$NAMESPACE"

kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/hpa.yaml
kubectl rollout status deployment/oficina-app -n "$NAMESPACE" --timeout=300s
kubectl wait --for=condition=Ready pod -l app=oficina-app -n "$NAMESPACE" --timeout=300s

echo "Instalando Metrics Server $METRICS_SERVER_VERSION."
kubectl apply -f "https://github.com/kubernetes-sigs/metrics-server/releases/download/${METRICS_SERVER_VERSION}/components.yaml"
kubectl patch deployment metrics-server -n kube-system --type=json \
  --patch-file k8s/metrics-server-kind-patch.yaml
kubectl rollout status deployment/metrics-server -n kube-system --timeout=240s
kubectl wait --for=condition=Available apiservice/v1beta1.metrics.k8s.io --timeout=240s

for attempt in $(seq 1 30); do
  if kubectl top nodes >/dev/null 2>&1 && kubectl top pods -n "$NAMESPACE" >/dev/null 2>&1; then
    break
  fi
  if [[ "$attempt" -eq 30 ]]; then
    echo "ERRO: Metrics API nao respondeu a kubectl top." >&2
    exit 1
  fi
  sleep 5
done

for attempt in $(seq 1 30); do
  hpa_metric="$(kubectl get hpa oficina-app-hpa -n "$NAMESPACE" -o jsonpath='{.status.currentMetrics[0].resource.current.averageUtilization}' 2>/dev/null || true)"
  if [[ "$hpa_metric" =~ ^[0-9]+$ ]]; then
    echo "HPA com metrica numerica: ${hpa_metric}%"
    break
  fi
  if [[ "$attempt" -eq 30 ]]; then
    echo "ERRO: HPA permaneceu sem metrica numerica." >&2
    kubectl get hpa -n "$NAMESPACE"
    exit 1
  fi
  sleep 5
done

kubectl get nodes
kubectl get pods -A
kubectl get services,deployments,statefulsets,hpa -n "$NAMESPACE"
kubectl top nodes
kubectl top pods -n "$NAMESPACE"
echo "Deploy Kind concluido com sucesso."
