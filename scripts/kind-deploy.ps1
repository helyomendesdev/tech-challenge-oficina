[CmdletBinding()]
param(
    [string]$ClusterName = $(if ($env:KIND_CLUSTER_NAME) { $env:KIND_CLUSTER_NAME } else { 'oficina' }),
    [string]$Namespace = $(if ($env:K8S_NAMESPACE) { $env:K8S_NAMESPACE } else { 'oficina' }),
    [string]$Image = $(if ($env:APP_IMAGE) { $env:APP_IMAGE } else { 'oficina-app:latest' }),
    [string]$MetricsServerVersion = $(if ($env:METRICS_SERVER_VERSION) { $env:METRICS_SERVER_VERSION } else { 'v0.8.1' })
)

$ErrorActionPreference = 'Stop'
$RootDir = Split-Path -Parent $PSScriptRoot
$ContextName = "kind-$ClusterName"

foreach ($commandName in @('docker', 'kind', 'kubectl', 'python')) {
    if (-not (Get-Command $commandName -ErrorAction SilentlyContinue)) {
        throw "Comando obrigatorio nao encontrado: $commandName"
    }
}

Push-Location $RootDir
try {
    $clusters = @(kind get clusters)
    if ($clusters -contains $ClusterName) {
        Write-Host "Reutilizando cluster Kind '$ClusterName'."
        kubectl cluster-info --context $ContextName | Out-Null
    }
    else {
        Write-Host "Criando cluster Kind '$ClusterName'."
        kind create cluster --name $ClusterName --wait 180s
    }
    kubectl config use-context $ContextName | Out-Null

    Write-Host "Construindo e carregando imagem $Image."
    docker build -t $Image .
    if ($LASTEXITCODE -ne 0) { throw 'Falha no docker build.' }
    kind load docker-image $Image --name $ClusterName
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao carregar a imagem no Kind.' }

    kubectl apply -f k8s/namespace.yaml
    kubectl apply -f k8s/configmap.yaml

    $secretNames = @(kubectl get secrets -n $Namespace -o jsonpath='{.items[*].metadata.name}') -split ' '
    if ($secretNames -contains 'oficina-secret') {
        foreach ($key in @('DJANGO_SECRET_KEY', 'POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD')) {
            $encodedValue = kubectl get secret oficina-secret -n $Namespace -o "jsonpath={.data.$key}"
            $decodedValue = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($encodedValue))
            if ([string]::IsNullOrWhiteSpace($decodedValue) -or $decodedValue -like '*CHANGE_ME*') {
                throw "Secret existente contem valor vazio ou placeholder inseguro em $key."
            }
        }
        Write-Host 'Reutilizando Secret existente para preservar um PostgreSQL persistente.'
    }
    else {
        $djangoSecret = if ($env:DJANGO_SECRET_KEY) { $env:DJANGO_SECRET_KEY } else { python -c "import secrets; print(secrets.token_urlsafe(48))" }
        $postgresPassword = if ($env:POSTGRES_PASSWORD) { $env:POSTGRES_PASSWORD } else { python -c "import secrets; print(secrets.token_urlsafe(32))" }
        $postgresDb = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { 'oficina' }
        $postgresUser = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { 'oficina_user' }

        kubectl create secret generic oficina-secret `
            --namespace $Namespace `
            --from-literal="DJANGO_SECRET_KEY=$djangoSecret" `
            --from-literal="POSTGRES_DB=$postgresDb" `
            --from-literal="POSTGRES_USER=$postgresUser" `
            --from-literal="POSTGRES_PASSWORD=$postgresPassword" `
            --dry-run=client -o yaml | kubectl apply -f -
    }

    kubectl apply -f k8s/postgres-service.yaml
    kubectl apply -f k8s/postgres-statefulset.yaml
    kubectl rollout status statefulset/postgres -n $Namespace --timeout=240s
    kubectl wait --for=condition=Ready pod -l app=postgres -n $Namespace --timeout=240s

    Write-Host 'Removendo apenas o Job de migration anterior para permitir uma nova execucao idempotente.'
    kubectl delete job oficina-migrate -n $Namespace --ignore-not-found --wait=true
    kubectl apply -f k8s/migration-job.yaml
    kubectl wait --for=condition=Complete job/oficina-migrate -n $Namespace --timeout=240s
    kubectl logs job/oficina-migrate -n $Namespace

    kubectl apply -f k8s/service.yaml
    kubectl apply -f k8s/deployment.yaml
    kubectl apply -f k8s/hpa.yaml
    kubectl rollout status deployment/oficina-app -n $Namespace --timeout=300s
    kubectl wait --for=condition=Ready pod -l app=oficina-app -n $Namespace --timeout=300s

    Write-Host "Instalando Metrics Server $MetricsServerVersion."
    kubectl apply -f "https://github.com/kubernetes-sigs/metrics-server/releases/download/$MetricsServerVersion/components.yaml"
    kubectl patch deployment metrics-server -n kube-system --type=json --patch-file k8s/metrics-server-kind-patch.yaml
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao configurar Metrics Server para Kind.' }
    kubectl rollout status deployment/metrics-server -n kube-system --timeout=240s
    if ($LASTEXITCODE -ne 0) { throw 'Metrics Server nao ficou Available.' }
    kubectl wait --for=condition=Available apiservice/v1beta1.metrics.k8s.io --timeout=240s
    if ($LASTEXITCODE -ne 0) { throw 'APIService de metricas nao ficou Available.' }

    $metricsReady = $false
    foreach ($attempt in 1..30) {
        $previousErrorAction = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        kubectl top nodes *> $null
        $nodesReady = $LASTEXITCODE -eq 0
        kubectl top pods -n $Namespace *> $null
        $podsReady = $LASTEXITCODE -eq 0
        $ErrorActionPreference = $previousErrorAction
        if ($nodesReady -and $podsReady) {
            $metricsReady = $true
            break
        }
        Start-Sleep -Seconds 5
    }
    if (-not $metricsReady) { throw 'Metrics API nao respondeu a kubectl top.' }

    $hpaReady = $false
    foreach ($attempt in 1..30) {
        $hpaMetric = kubectl get hpa oficina-app-hpa -n $Namespace -o jsonpath='{.status.currentMetrics[0].resource.current.averageUtilization}' 2>$null
        if ($hpaMetric -match '^\d+$') {
            Write-Host "HPA com metrica numerica: $hpaMetric%"
            $hpaReady = $true
            break
        }
        Start-Sleep -Seconds 5
    }
    if (-not $hpaReady) { throw 'HPA permaneceu sem metrica numerica.' }

    kubectl get nodes
    kubectl get pods -A
    kubectl get services,deployments,statefulsets,hpa -n $Namespace
    kubectl top nodes
    kubectl top pods -n $Namespace
    Write-Host 'Deploy Kind concluido com sucesso.'
}
finally {
    Pop-Location
}
