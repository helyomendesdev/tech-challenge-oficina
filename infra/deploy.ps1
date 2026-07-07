[CmdletBinding()]
param(
    [string]$MetricsServerVersion = 'v0.8.1'
)

$ErrorActionPreference = 'Stop'
$InfraDir = $PSScriptRoot
$RootDir = Split-Path -Parent $InfraDir

foreach ($commandName in @('terraform', 'docker', 'kind', 'kubectl', 'python')) {
    if (-not (Get-Command $commandName -ErrorAction SilentlyContinue)) {
        throw "Comando obrigatorio nao encontrado: $commandName"
    }
}

if (-not $env:TF_VAR_postgres_password) {
    throw 'Defina TF_VAR_postgres_password antes do deploy.'
}
if (-not $env:TF_VAR_django_secret_key) {
    throw 'Defina TF_VAR_django_secret_key antes do deploy.'
}

Push-Location $InfraDir
try {
    $clusterName = if ($env:TF_VAR_cluster_name) { $env:TF_VAR_cluster_name } else { 'oficina' }
    $knownClusters = @(kind get clusters)
    $managedCluster = $false
    if (Test-Path terraform.tfstate) {
        $managedCluster = @(terraform state list) -contains 'kind_cluster.oficina'
    }
    if (($knownClusters -contains $clusterName) -and -not $managedCluster) {
        throw "O cluster '$clusterName' existe, mas nao pertence ao state Terraform atual. Remova-o explicitamente ou use outro TF_VAR_cluster_name."
    }

    Write-Host '1/5 Criando o cluster Kind gerenciado pelo Terraform.'
    terraform apply '-target=kind_cluster.oficina' -auto-approve
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao criar o cluster Kind.' }

    $clusterName = terraform output -raw cluster_name
    kind export kubeconfig --name $clusterName
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao exportar kubeconfig do Kind.' }

    Write-Host '2/5 Construindo e carregando a imagem local no Kind.'
    Push-Location $RootDir
    try {
        $appImage = if ($env:TF_VAR_app_image) { $env:TF_VAR_app_image } else { 'oficina-app:latest' }
        docker build -t $appImage .
        if ($LASTEXITCODE -ne 0) { throw 'Falha no docker build.' }
        kind load docker-image $appImage --name $clusterName
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao carregar a imagem no Kind.' }
    }
    finally {
        Pop-Location
    }

    Write-Host '3/5 Aplicando namespace, banco, migrations, aplicacao e HPA.'
    terraform apply -auto-approve
    if ($LASTEXITCODE -ne 0) { throw 'Falha no terraform apply completo.' }

    $namespace = terraform output -raw namespace
    kubectl rollout status statefulset/postgres -n $namespace --timeout=240s
    if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL nao ficou Ready.' }
    kubectl rollout status deployment/oficina-app -n $namespace --timeout=300s
    if ($LASTEXITCODE -ne 0) { throw 'Aplicacao nao ficou Ready.' }

    Write-Host '4/5 Instalando e validando Metrics Server para Kind.'
    kubectl apply -f "https://github.com/kubernetes-sigs/metrics-server/releases/download/$MetricsServerVersion/components.yaml"
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao aplicar Metrics Server.' }
    kubectl patch deployment metrics-server -n kube-system --type=json --patch-file "$RootDir/k8s/metrics-server-kind-patch.yaml"
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao configurar Metrics Server para Kind.' }
    kubectl rollout status deployment/metrics-server -n kube-system --timeout=240s
    if ($LASTEXITCODE -ne 0) { throw 'Metrics Server nao ficou Available.' }
    kubectl wait --for=condition=Available apiservice/v1beta1.metrics.k8s.io --timeout=240s
    if ($LASTEXITCODE -ne 0) { throw 'APIService de metricas nao ficou Available.' }

    $metricsReady = $false
    foreach ($attempt in 1..30) {
        $previousErrorAction = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        kubectl top pods -n $namespace *> $null
        $metricsReady = $LASTEXITCODE -eq 0
        $ErrorActionPreference = $previousErrorAction
        if ($metricsReady) { break }
        Start-Sleep -Seconds 5
    }
    if (-not $metricsReady) { throw 'kubectl top nao recebeu metricas.' }

    $hpaReady = $false
    foreach ($attempt in 1..30) {
        $metric = kubectl get hpa oficina-app-hpa -n $namespace -o jsonpath='{.status.currentMetrics[0].resource.current.averageUtilization}' 2>$null
        if ($metric -match '^\d+$') {
            $hpaReady = $true
            break
        }
        Start-Sleep -Seconds 5
    }
    if (-not $hpaReady) { throw 'HPA permaneceu sem metrica numerica.' }

    Write-Host '5/5 Executando smoke test contra a aplicacao implantada.'
    Push-Location $RootDir
    try {
        $env:K8S_NAMESPACE = $namespace
        python scripts/smoke_test.py
        if ($LASTEXITCODE -ne 0) { throw 'Smoke test falhou.' }
    }
    finally {
        Pop-Location
    }

    kubectl get pods,services,deployments,statefulsets,hpa -n $namespace
    kubectl top pods -n $namespace
    Write-Host 'Provisionamento Terraform concluido com sucesso.'
}
finally {
    Pop-Location
}
