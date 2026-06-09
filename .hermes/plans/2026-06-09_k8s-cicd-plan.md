# K8s + CI/CD Implementation Plan

> **Objetivo:** Criar manifestos Kubernetes e pipeline CI/CD para a aplicacao
> da oficina mecanica (FIAP Tech Challenge Fase 2).

**Responsavel:** Helio
**Repo:** helyomendesdev/tech-challenge-fase-1-oficina
**Branch de trabalho:** `feat/infra-k8s-cicd`

---

## Estrutura alvo

```
tech-challenge-oficina/
  k8s/
    namespace.yaml
    configmap.yaml
    secret.yaml
    deployment.yaml
    service.yaml
    hpa.yaml
    postgres-statefulset.yaml
    postgres-service.yaml
  .github/
    workflows/
      ci.yml
      cd.yml
```

---

## Task 1: Criar branch de trabalho

**Objetivo:** Isolar as alteracoes de infra em branch separada

**Comandos:**
```bash
cd /Users/helyomendes/Projects/tech-challenge-oficina
git checkout -b feat/infra-k8s-cicd
```

**Verificacao:** `git branch` mostra `* feat/infra-k8s-cicd`

---

## Task 2: Namespace + ConfigMap

**Objetivo:** Criar o namespace dedicado e o ConfigMap com variaveis nao sensiveis

**Arquivos a criar:**
- `k8s/namespace.yaml`
- `k8s/configmap.yaml`

### namespace.yaml

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: oficina
```

**Por que:** Isolar os recursos da aplicacao em um namespace dedicado, evitando
conflito com outros projetos no mesmo cluster. Facilita gerenciamento (`kubectl get all -n oficina`).

### configmap.yaml

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: oficina-config
  namespace: oficina
data:
  DEBUG: "False"
  DJANGO_SETTINGS_MODULE: "app.settings"
  DB_HOST: "oficina-db"
  DB_PORT: "5432"
  DJANGO_LOG_FILE: "/tmp/oficina_atividades.log"
  STATIC_ROOT: "/app/staticfiles"
```

**Por que:** ConfigMap separa configuracao do codigo. Variaveis como DEBUG, DB_HOST
e DB_PORT mudam conforme o ambiente (dev, staging, prod) — nao devem ficar
hardcoded na imagem Docker ou no codigo.

**Verificacao:**
```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl get configmap oficina-config -n oficina
```

---

## Task 3: Secret

**Objetivo:** Criar o Secret com variaveis sensiveis (DB password, SECRET_KEY, tokens)

**Arquivo a criar:**
- `k8s/secret.yaml`

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: oficina-secret
  namespace: oficina
type: Opaque
stringData:
  SECRET_KEY: "CHANGE_ME_SECRET_KEY"
  POSTGRES_DB: "oficina"
  POSTGRES_USER: "oficina_user"
  POSTGRES_PASSWORD: "CHANGE_ME_DB_PASSWORD"
```

**Por que:** Secrets armazenam dados sensiveis (senhas, chaves, tokens) de forma
separada dos manifests. No K8s real, usaria `external-secrets` ou `sealed-secrets`
para criptografar, mas para MVP local o `stringData` e suficiente.

**Atencao:** NUNCA commitar valores reais de secret. Usar placeholders e configurar
via pipeline ou `kubectl create secret` com valores reais.

**Verificacao:**
```bash
kubectl apply -f k8s/secret.yaml
kubectl get secret oficina-secret -n oficina
```

---

## Task 4: PostgreSQL StatefulSet + Service

**Objetivo:** Criar o banco de dados como StatefulSet com volume persistente

**Arquivos a criar:**
- `k8s/postgres-statefulset.yaml`
- `k8s/postgres-service.yaml`

### postgres-statefulset.yaml

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: oficina
spec:
  serviceName: postgres
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:15
        ports:
        - containerPort: 5432
        envFrom:
        - secretRef:
            name: oficina-secret
        volumeMounts:
        - name: postgres-data
          mountPath: /var/lib/postgresql/data
        resources:
          requests:
            cpu: "250m"
            memory: "256Mi"
          limits:
            cpu: "500m"
            memory: "512Mi"
        livenessProbe:
          exec:
            command: ["pg_isready", "-U", "$(POSTGRES_USER)", "-d", "$(POSTGRES_DB)"]
          initialDelaySeconds: 15
          periodSeconds: 10
  volumeClaimTemplates:
  - metadata:
      name: postgres-data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 1Gi
```

**Por que StatefulSet em vez de Deployment?** PostgreSQL precisa de identidade
unica e storage persistente. StatefulSet garante que cada pod tenha seu proprio
PVC (PersistentVolumeClaim) que sobrevive a restart do pod. Deployment e para
apps stateless.

### postgres-service.yaml

```yaml
apiVersion: v1
kind: Service
metadata:
  name: oficina-db
  namespace: oficina
spec:
  selector:
    app: postgres
  ports:
  - port: 5432
    targetPort: 5432
  clusterIP: None
```

**Por que `clusterIP: None`?** Isso cria um Headless Service, que faz o DNS
resolver diretamente para o IP do pod. StatefulSets usam headless services
para que cada pod tenha um DNS estavel (ex: `postgres-0.postgres.oficina.svc.cluster.local`).

**Verificacao:**
```bash
kubectl apply -f k8s/postgres-statefulset.yaml
kubectl apply -f k8s/postgres-service.yaml
kubectl get pods -n oficina -w  # aguardar postgres-0 ficar Running
```

---

## Task 5: Deployment da aplicacao

**Objetivo:** Criar o Deployment da app Django com 2 replicas, probes e resource limits

**Arquivo a criar:**
- `k8s/deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: oficina-app
  namespace: oficina
  labels:
    app: oficina-app
spec:
  replicas: 2
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: oficina-app
  template:
    metadata:
      labels:
        app: oficina-app
    spec:
      containers:
      - name: app
        image: helyomendesdev/tech-challenge-oficina:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: oficina-config
        - secretRef:
            name: oficina-secret
        resources:
          requests:
            cpu: "250m"
            memory: "256Mi"
          limits:
            cpu: "500m"
            memory: "512Mi"
        livenessProbe:
          httpGet:
            path: /
            port: 8000
          initialDelaySeconds: 15
          periodSeconds: 20
        readinessProbe:
          httpGet:
            path: /
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
        startupProbe:
          httpGet:
            path: /
            port: 8000
          initialDelaySeconds: 3
          periodSeconds: 5
          failureThreshold: 30
```

**Por que:**
- **2 replicas:** Minimo para alta disponibilidade. Se um pod cair, o outro atende.
- **RollingUpdate com maxUnavailable=0:** Zero downtime durante deploy. Um pod novo
  sobe antes de derrubar o antigo.
- **LivenessProbe:** Se a app travar (deadlock, memory leak), o K8s mata e recria o pod.
- **ReadinessProbe:** So envia trafego para o pod quando ele estiver pronto.
- **StartupProbe:** Para apps com startup lento (migrations, cache warm). Desativa
  liveness/readiness durante a inicializacao.
- **Resource limits:** Impede que um pod consuma todo o CPU/memoria do node.
  Essencial para HPA funcionar corretamente.

**Verificacao:**
```bash
kubectl apply -f k8s/deployment.yaml
kubectl get pods -n oficina -w  # 2 pods Running
kubectl get deployment oficina-app -n oficina
```

---

## Task 6: Service da aplicacao

**Objetivo:** Expor a aplicacao internamente no cluster

**Arquivo a criar:**
- `k8s/service.yaml`

```yaml
apiVersion: v1
kind: Service
metadata:
  name: oficina-app
  namespace: oficina
spec:
  selector:
    app: oficina-app
  ports:
  - port: 8000
    targetPort: 8000
  type: ClusterIP
```

**Por que ClusterIP?** Em MVP local (kind/minikube), o Service ClusterIP e
suficiente. Para acesso externo, usamos `kubectl port-forward` ou um Ingress.
Type: LoadBalancer so faz sentido em clouds reais (EKS, GKE, AKS).

**Verificacao:**
```bash
kubectl apply -f k8s/service.yaml
kubectl get svc -n oficina
```

---

## Task 7: HPA (Horizontal Pod Autoscaler)

**Objetivo:** Escalar automaticamente de 2 a 10 pods baseado em CPU

**Arquivo a criar:**
- `k8s/hpa.yaml`

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: oficina-app-hpa
  namespace: oficina
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: oficina-app
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

**Por que:**
- **minReplicas: 2** — Garante HA mesmo sem carga.
- **maxReplicas: 10** — Limite superior para nao estourar recursos do cluster.
- **CPU 70%** — Ponto de equilibrio: abaixo de 70% nao escala para nao ficar
  ligando/desligando pod (thrashing). Acima de 70%, escala.
- **autoscaling/v2** — Suporta metricas multiplas (CPU + memory). V1 so CPU.

**Verificacao:**
```bash
kubectl apply -f k8s/hpa.yaml
kubectl get hpa -n oficina
```

---

## Task 8: CI — Pipeline de Integracao Continua

**Objetivo:** Executar lint, testes e build a cada push/PR na main

**Arquivo a criar:**
- `.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: [main, feat/*]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: oficina_test
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_pass
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: "3.11"
    
    - name: Cache pip
      uses: actions/cache@v4
      with:
        path: ~/.cache/pip
        key: ${{ runner.os }}-pip-${{ hashFiles('requirements.txt') }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    
    - name: Run tests
      env:
        DATABASE_URL: postgres://test_user:test_pass@localhost:5432/oficina_test
        DJANGO_SETTINGS_MODULE: app.settings_test
        SECRET_KEY: test-key-not-for-production
      run: |
        python manage.py migrate
        python -m pytest atendimento/tests/ -v --tb=short

  lint:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: "3.11"
    - name: Install lint tools
      run: pip install flake8
    - name: Run linter
      run: flake8 atendimento/ --max-line-length=100
```

**Por que:**
- **Services > postgres:** GitHub Actions oferece servicos auxiliares. Subimos
  um PostgreSQL real para os testes de integracao (que dependem de banco).
- **Cache pip:** Acelera o workflow em ~40s reutilizando dependencias cacheadas.
- **jobs separados (test + lint):** Paralelismo. Lint falha rapido sem esperar
  os testes, e vice-versa.
- **Trigger em feat/*:** Permite que o CI rode em branches de feature antes do PR.

---

## Task 9: CD — Pipeline de Entrega Continua

**Objetivo:** Buildar imagem Docker e fazer deploy no K8s apos merge na main

**Arquivo a criar:**
- `.github/workflows/cd.yml`

```yaml
name: CD

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: "3.11"
    
    - name: Install dependencies
      run: pip install -r requirements.txt
    
    - name: Run tests
      env:
        DJANGO_SETTINGS_MODULE: app.settings_test
        SECRET_KEY: test-key-not-for-production
      run: |
        python -m pytest atendimento/tests/ -v --tb=short --junitxml=report.xml
    
    - name: Log in to GitHub Container Registry
      uses: docker/login-action@v3
      with:
        registry: ghcr.io
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}
    
    - name: Build and push Docker image
      uses: docker/build-push-action@v6
      with:
        context: .
        push: true
        tags: |
          ghcr.io/${{ github.repository }}:latest
          ghcr.io/${{ github.repository }}:${{ github.sha }}
    
    - name: Set up kubectl
      uses: azure/setup-kubectl@v4
      with:
        version: "latest"
    
    - name: Deploy to Kubernetes
      env:
        KUBE_CONFIG: ${{ secrets.KUBE_CONFIG }}
      run: |
        mkdir -p ~/.kube
        echo "$KUBE_CONFIG" > ~/.kube/config
        kubectl set image deployment/oficina-app -n oficina \
          app=ghcr.io/${{ github.repository }}:${{ github.sha }} --record
```

**Por que:**
- **Trigger apenas na main:** So faz deploy quando o codigo e aprovado e mergeado.
- **GHCR (GitHub Container Registry):** Registry integrado ao GitHub, sem custo
  adicional. Alternativa: Docker Hub.
- **`kubectl set image`:** Atualiza a imagem do deployment sem precisar reaplicar
  o YAML inteiro. Dispara rolling update automaticamente.
- **`--junitxml=report.xml:**** Gera relatorio de testes que aparece na UI do
  GitHub Actions.
- **`secrets.KUBE_CONFIG`:** Kubeconfig do cluster armazenado como secret no
  repositorio (Settings > Secrets > Actions). Nunca versionado.

---

## Task 10: Aplicar tudo e verificar

**Objetivo:** Testar os manifests localmente com kind (Kubernetes in Docker)

**Passos:**
```bash
# 1. Instalar kind (se nao tiver)
brew install kind

# 2. Criar cluster local
kind create cluster --name oficina

# 3. Aplicar todos os manifests
kubectl apply -f k8s/

# 4. Verificar tudo
kubectl get all -n oficina

# 5. Port-forward para testar
kubectl port-forward -n oficina svc/oficina-app 8000:8000

# 6. Testar endpoint
curl http://localhost:8000/api/v1/ordens-servico/

# 7. Limpar
kind delete cluster --name oficina
```

---

## Ordem de execucao recomendada

```
Task 1: Criar branch
Task 2: Namespace + ConfigMap
Task 3: Secret
Task 4: PostgreSQL StatefulSet
Task 5: Deployment
Task 6: Service
Task 7: HPA
--- teste local com kind ---
Task 8: CI (GitHub Actions)
Task 9: CD (GitHub Actions)
Task 10: Validacao completa
```

Cada task e auto-contida. Commit apos cada task passar.

---

## Comandos de verificacao rapida

```bash
# Todos os recursos
kubectl get all -n oficina

# Pods
kubectl get pods -n oficina -o wide

# Logs
kubectl logs -n oficina deployment/oficina-app -f

# HPA status
kubectl get hpa -n oficina -w

# Port-forward para testar local
kubectl port-forward -n oficina svc/oficina-app 8000:8000

# Aplicar tudo de uma vez
kubectl apply -f k8s/

# Deletar tudo
kubectl delete -f k8s/
```
