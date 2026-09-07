#!/usr/bin/env bash
set -Eeuo pipefail

# aws-deploy.sh — Deploy da aplicacao no EKS via GitHub Actions ou localmente.
# Requis: aws cli, kubectl, docker, variaveis de ambiente AWS configuradas.
#
# Variaveis:
#   AWS_REGION       (default: us-east-1)
#   EKS_CLUSTER_NAME (default: oficina-cluster)
#   ECR_REPOSITORY   (default: oficina-api)
#   IMAGE_TAG        (default: github.sha ou latest)
#   K8S_NAMESPACE    (default: oficina)

AWS_REGION="${AWS_REGION:-us-east-1}"
EKS_CLUSTER_NAME="${EKS_CLUSTER_NAME:-oficina-cluster}"
ECR_REPOSITORY="${ECR_REPOSITORY:-oficina-api}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
K8S_NAMESPACE="${K8S_NAMESPACE:-oficina}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:?AWS_ACCOUNT_ID nao definido}"

ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}"
FULL_IMAGE="${ECR_URI}:${IMAGE_TAG}"

echo "=== Deploy AWS ==="
echo "Regiao:       ${AWS_REGION}"
echo "Cluster EKS:  ${EKS_CLUSTER_NAME}"
echo "ECR repo:     ${ECR_REPOSITORY}"
echo "Image tag:    ${IMAGE_TAG}"
echo "Full image:   ${FULL_IMAGE}"
echo ""

# 1. Configurar kubeconfig para o cluster EKS
echo "[1/5] Configurando kubeconfig..."
aws eks update-kubeconfig \
  --region "${AWS_REGION}" \
  --name "${EKS_CLUSTER_NAME}" \
  --alias "eks-${EKS_CLUSTER_NAME}"

kubectl config use-context "eks-${EKS_CLUSTER_NAME}"
kubectl cluster-info
echo ""

# 2. Verificar/criar namespace
echo "[2/5] Verificando namespace..."
kubectl create namespace "${K8S_NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -
echo ""

# 3. Aplicar manifestos (secret deve existir previamente via Terraform ou manual)
echo "[3/5] Aplicando manifestos K8s..."
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/postgres-service.yaml
kubectl apply -f k8s/postgres-statefulset.yaml
kubectl rollout status statefulset/postgres -n "${K8S_NAMESPACE}" --timeout=240s
echo ""

# 4. Executar migration job
echo "[4/5] Executando migration job..."
kubectl delete job oficina-migrate -n "${K8S_NAMESPACE}" --ignore-not-found --wait=true
kubectl apply -f k8s/migration-job.yaml
kubectl wait --for=condition=Complete job/oficina-migrate -n "${K8S_NAMESPACE}" --timeout=240s
kubectl logs job/oficina-migrate -n "${K8S_NAMESPACE}"
echo ""

# 5. Deploy da aplicacao com nova imagem
echo "[5/5] Atualizando deployment com imagem ${FULL_IMAGE}..."
kubectl set image deployment/oficina-app \
  app="${FULL_IMAGE}" \
  -n "${K8S_NAMESPACE}"
kubectl rollout status deployment/oficina-app -n "${K8S_NAMESPACE}" --timeout=300s
kubectl wait --for=condition=Ready pod -l app=oficina-app -n "${K8S_NAMESPACE}" --timeout=300s

echo ""
echo "=== Deploy concluido ==="
kubectl get pods -n "${K8S_NAMESPACE}"
kubectl get svc -n "${K8S_NAMESPACE}"
