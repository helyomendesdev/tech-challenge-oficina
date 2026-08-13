# Especificação de Observabilidade — Tech Challenge Fase 3

**Responsável:** Luís Fernando Montes
**Escopo:** transversal aos 4 repositórios
**Prazo interno do grupo:** 05/09/2026
**Status:** especificação — aguardando validação do grupo

---

## 1. O que esta frente entrega

O enunciado da Fase 3 exige, na seção *Monitoramento e Observabilidade*:

| Requisito do enunciado | Onde é atendido nesta spec |
|---|---|
| Integração com Datadog ou New Relic | §2, §3 |
| Latência das APIs | §5.3, §6 (D4) |
| Consumo de recursos do Kubernetes (CPU, memória) | §5.3, §6 (D5) |
| Healthchecks e uptime | §5.5, §6 (D5) |
| Alertas para falhas no processamento de ordens de serviço | §7 (A1) |
| Logs estruturados (JSON) com correlação entre requisições | §5.1, §5.2 |
| Dashboard: volume diário de ordens de serviço | §6 (D1) |
| Dashboard: tempo médio de execução por status | §6 (D2) |
| Dashboard: erros e falhas nas integrações | §6 (D3) |

Fora do escopo desta frente (pertencem a outros integrantes): provisionamento de EKS/RDS
(Sophia), Lambda e API Gateway (Lucas), pipelines e proteção de branch (Hélio). Esta frente
**especifica o que precisa existir neles** — ver `requisitos-para-o-time.md`.

---

## 2. Decisões

| # | Decisão | Escolha | Motivo |
|---|---|---|---|
| D-01 | Ferramenta de observabilidade | **New Relic** | Free tier de 100 GB/mês perpétuo, 1 usuário full-platform, sem cartão de crédito. O Datadog só oferece trial de 14 dias, que expira antes da entrega de 05/09. |
| D-02 | Estratégia de instrumentação | **Agente nativo New Relic** (Python + Lambda layer + `nri-bundle` no K8s) | Auto-instrumenta Django, DRF e psycopg2 sem código; traz *logs in context* (injeção automática de `trace.id` no log) e tracing distribuído W3C prontos. OTel puro daria portabilidade, mas exige instrumentação manual de propagação e adiciona risco de prazo. |
| D-03 | Padrão de correlação | **W3C Trace Context** (`traceparent` / `tracestate`) + `X-Request-Id` de negócio | Padrão aberto, suportado pelo agente New Relic e por qualquer sucessor. Se D-02 mudar, a correlação sobrevive. |
| D-04 | Métricas de negócio | **Custom Events** emitidos pela aplicação nas transições de status da OS | Volume diário e tempo médio por status não existem como métrica técnica — precisam ser emitidos pelo domínio. Derivar de log é frágil. |
| D-05 | Onde mora o trabalho desta frente | **PRs nos 4 repositórios existentes**, sem criar um 5º | O enunciado exige exatamente 4 repositórios. Observabilidade é transversal por natureza. |
| D-06 | Destino dos logs da aplicação | **stdout apenas** (remover `FileHandler`) | Em container, log em arquivo se perde no restart do pod e não é coletado pelo agente. |

D-01, D-02 e D-03 devem ser formalizados como ADR/RFC — ver §9.

---

## 3. Arquitetura de observabilidade

```text
                        ┌───────────────────────────────────────────┐
   Cliente ──traceparent──▶  API Gateway (access log JSON)          │
                        │        │                                  │
                        │        ├──▶ Lambda auth (CPF → JWT)       │
                        │        │      └ NR Lambda layer           │
                        │        │                                  │
                        │        └──▶ App Django no EKS             │
                        │               ├ NR Python agent (APM)     │
                        │               ├ log JSON em stdout        │
                        │               └ custom events de OS       │
                        │                      │                    │
                        │        EKS ── nri-bundle (kube-state)     │
                        │        RDS ── Enhanced Monitoring + PI    │
                        └───────────────────┬───────────────────────┘
                                            │  OTLP / HTTPS 443
                                            ▼
                                    New Relic One
                                 ├ APM & Distributed Tracing
                                 ├ Logs (in context)
                                 ├ Kubernetes cluster explorer
                                 ├ Synthetics (uptime)
                                 ├ Dashboards (NRQL)
                                 └ Alert policy + notificação
```

Um único `trace.id` atravessa Gateway → Lambda → Django → banco. Esse é o requisito de
*"correlação entre requisições"* do enunciado e é o que permite, no vídeo, clicar num erro de
dashboard e chegar na linha de log da requisição que o causou.

---

## 4. Ambientes

| Branch | Ambiente | Nome do app no New Relic | Cluster |
|---|---|---|---|
| `develop` | Homologação | `oficina-api-hml` | `oficina-hml` |
| `main` | Produção | `oficina-api-prd` | `oficina-prd` |

Todo dado enviado carrega o atributo `service.environment` (`homologacao` \| `producao`).
Dashboards e alertas fazem *facet* por esse atributo — uma conta New Relic só, dois ambientes
separados por atributo (o free tier não dá sub-contas).

---

## 5. Sinais

### 5.1 Logs estruturados (JSON)

Formato único para aplicação, Lambda e API Gateway. Uma linha JSON por evento, em `stdout`.

```json
{
  "timestamp": "2026-09-01T14:22:31.123-03:00",
  "level": "INFO",
  "logger": "atendimento.ordens",
  "message": "Ordem de serviço transicionada",
  "service.name": "oficina-api",
  "service.environment": "producao",
  "service.version": "1.4.2",
  "trace.id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span.id": "00f067aa0ba902b7",
  "request.id": "c7d1f0a2-8b3e-4a11-9f2c-5e6d7a8b9c01",
  "http.method": "PATCH",
  "http.route": "/api/v1/ordens-servico/{id}/status",
  "http.status_code": 200,
  "duration_ms": 87,
  "os.id": 1421,
  "os.status_anterior": "DIAGNOSTICO",
  "os.status_novo": "EXECUCAO",
  "cliente.ref": "sha256:9c1e4a...b2"
}
```

Regras invioláveis:

- **Nunca logar CPF, e-mail ou telefone em claro.** O identificador do cliente entra como
  `cliente.ref`, um hash SHA-256 com *salt* de ambiente. Vale para a Lambda de autenticação,
  que é justamente quem recebe o CPF.
- `trace.id` e `span.id` são obrigatórios em toda linha emitida dentro de uma requisição.
- Erro sempre carrega `error.type`, `error.message` e `error.stack`.
- Log de integração externa sempre carrega `integracao` (ex.: `simulador-orcamento`) e
  `integracao.status`.

### 5.2 Correlação entre requisições

1. O API Gateway repassa o header `traceparent` recebido do cliente; se não houver, a Lambda
   ou a aplicação gera um novo.
2. Todo componente **propaga** `traceparent` e `tracestate` nas chamadas que faz adiante.
3. A aplicação expõe um middleware que:
   - lê `traceparent` e `X-Request-Id` da requisição (gera UUIDv4 se ausente);
   - guarda ambos em `contextvars`, para o formatter de log injetar sem passar parâmetro;
   - devolve `X-Request-Id` no header da resposta, para o cliente citar num suporte.
4. Chamadas HTTP saintes (ex.: webhook de orçamento) reinjetam os headers.

### 5.3 Métricas técnicas

Coletadas automaticamente pelo agente — sem código:

| Métrica | Origem | Evento/atributo |
|---|---|---|
| Latência por rota (p50/p95/p99) | APM Python | `Transaction.duration` |
| Throughput e taxa de erro | APM Python | `Transaction.error` |
| Tempo em banco por query | APM Python | `DatastoreSample` |
| CPU/memória por pod e container | `nri-bundle` | `K8sContainerSample` |
| Réplicas desejadas vs. prontas (HPA) | `nri-bundle` | `K8sHpaSample` |
| Reinícios e OOMKill | `nri-bundle` | `K8sContainerSample.restartCount` |
| Conexões, CPU e IOPS do RDS | AWS RDS integration | `DatastoreSample` (`provider: RdsDbInstance`) |
| Query lenta no banco | `nri-postgresql` + `pg_stat_statements` | Query performance monitoring |
| Duração, erro e cold start da Lambda | NR Lambda layer | `AwsLambdaInvocation` |

### 5.4 Eventos de negócio (custom events)

Emitidos pela aplicação. Evento `OrdemServicoEvento`:

| Atributo | Tipo | Descrição |
|---|---|---|
| `evento` | string | `ABERTURA` \| `TRANSICAO` \| `CONCLUSAO` \| `FALHA` |
| `osId` | int | Identificador da OS |
| `statusAnterior` | string | `RECEBIDA`, `DIAGNOSTICO`, `AGUARDANDO_APROVACAO`, `EXECUCAO`, `FINALIZADA`, `ENTREGUE` |
| `statusNovo` | string | idem |
| `duracaoStatusSegundos` | float | Tempo que a OS permaneceu em `statusAnterior` |
| `unidade` | string | Unidade da oficina (multi-unidade é a premissa do enunciado) |
| `erroTipo` | string | Preenchido só quando `evento = FALHA` |
| `traceId` | string | Liga o evento ao trace e ao log |

O cálculo de `duracaoStatusSegundos` exige registrar o instante da transição anterior.
**Isso é uma mudança de modelo** — ver §8, item 6.

### 5.5 Healthchecks e uptime

A aplicação já expõe `GET /health/live/` e `GET /health/ready/` (`app/urls.py`).

- `live`: processo respondendo — usado pelo `livenessProbe` do K8s.
- `ready`: dependências OK (banco acessível) — usado pelo `readinessProbe`.
- **Uptime externo:** monitor Synthetics do tipo *Ping* contra a URL pública de cada ambiente,
  a cada 1 minuto, de 2 regiões. É o que produz o número de uptime para o dashboard e o vídeo.

---

## 6. Dashboards

Um dashboard "Oficina — Operação", com 3 páginas. Consultas NRQL de referência:

**D1 — Volume diário de ordens de serviço** *(exigido)*
```sql
SELECT count(*) FROM OrdemServicoEvento
WHERE evento = 'ABERTURA' AND service.environment = 'producao'
TIMESERIES 1 day SINCE 30 days ago FACET unidade
```

**D2 — Tempo médio de execução por status** *(exigido)*
```sql
SELECT average(duracaoStatusSegundos) / 60 AS 'Minutos médios'
FROM OrdemServicoEvento
WHERE evento = 'TRANSICAO' AND statusAnterior IN ('DIAGNOSTICO', 'EXECUCAO', 'FINALIZADA')
FACET statusAnterior SINCE 7 days ago
```

**D3 — Erros e falhas nas integrações** *(exigido)*
```sql
SELECT count(*) FROM Log
WHERE level = 'ERROR' AND integracao IS NOT NULL
FACET integracao, error.type TIMESERIES SINCE 24 hours ago
```

**D4 — Latência das APIs**
```sql
SELECT percentile(duration, 50, 95, 99) FROM Transaction
WHERE appName LIKE 'oficina-api%' FACET name TIMESERIES SINCE 6 hours ago
```

**D5 — Kubernetes e disponibilidade**
```sql
SELECT average(cpuUsedCores), average(memoryWorkingSetBytes) / 1e6 AS 'MB'
FROM K8sContainerSample WHERE clusterName = 'oficina-prd'
FACET podName TIMESERIES SINCE 3 hours ago
```

**D6 — Fluxo de autenticação** (liga a frente do Lucas)
```sql
SELECT count(*) FROM AwsLambdaInvocation
WHERE entityName = 'oficina-auth-cpf' FACET error TIMESERIES SINCE 24 hours ago
```

---

## 7. Alertas

Política `Oficina — Produção`, com notificação em canal do grupo (e-mail e/ou webhook).

| # | Alerta | Condição | Severidade |
|---|---|---|---|
| **A1** | **Falha no processamento de ordens de serviço** *(exigido)* | `SELECT count(*) FROM OrdemServicoEvento WHERE evento = 'FALHA'` > 0 por 5 min | Crítico |
| A2 | Taxa de erro da API | `percentage(count(*), WHERE error IS true) FROM Transaction` > 5% por 5 min | Crítico |
| A3 | Latência degradada | p95 de `Transaction.duration` > 1,5 s por 10 min | Aviso |
| A4 | Endpoint fora do ar | Monitor Synthetics falhando em 2 localidades | Crítico |
| A5 | Saturação de pod | `K8sContainerSample.memoryWorkingSetBytes` > 90% do limite por 10 min | Aviso |
| A6 | Pod em CrashLoop | `restartCount` cresce mais de 3 vezes em 15 min | Crítico |
| A7 | Falha de autenticação sistêmica | Taxa de erro da Lambda de auth > 10% por 5 min | Crítico |
| A8 | Banco saturado | Conexões do RDS > 80% do máximo por 10 min | Aviso |

Cada alerta precisa de um **runbook** de uma página: o que significa, onde olhar, o que fazer.
Isso conta como documentação arquitetural e é rápido de produzir.

---

## 8. Mudanças necessárias na aplicação

Estas entram como PR no repositório `tech-challenge-oficina`:

1. `requirements.txt`: `newrelic`, `python-json-logger`.
2. `app/observabilidade/logging.py` — formatter JSON + filtro que injeta `trace.id`,
   `span.id`, `request.id` a partir de `contextvars`.
3. `app/observabilidade/middleware.py` — `CorrelationIdMiddleware` (§5.2), registrado como o
   **primeiro** item de `MIDDLEWARE`.
4. `app/settings.py` — substituir o bloco `LOGGING` atual (formato texto, `FileHandler` +
   console) por handler único de `stdout` com o formatter JSON. **O `FileHandler` sai** (D-06).
5. `atendimento/infrastructure/external_services/` — propagar `traceparent` nas chamadas
   saintes e emitir log de integração no padrão de §5.1.
6. **Domínio da OS** — registrar `data_ultima_transicao` na `OrdemServico` e emitir
   `OrdemServicoEvento` (§5.4) na camada de caso de uso, não na view. Requer migration.
7. `Dockerfile` / entrypoint — subir sob `newrelic-admin run-program gunicorn ...` e aceitar as
   variáveis `NEW_RELIC_*`.
8. `k8s/deployment.yaml` — `envFrom` do secret `newrelic-license`, labels `app`/`env`/`version`,
   e as probes apontando para `live` e `ready` separadamente.

**Ponto de atenção do item 6 — já conferido:** os `STATUS_CHOICES` de `OrdemServico`
(`atendimento/models.py:117`) são `RECEBIDA, DIAGNOSTICO, AGUARDANDO, EXECUCAO, FINALIZADA,
ENTREGUE, CANCELADA` — os três nomes citados pelo enunciado (Diagnóstico, Execução,
Finalização) existem, então D2 é implementável sem renomear nada. O modelo já tem
`data_abertura`, `data_inicio_execucao` e `data_finalizacao`, o que cobre a duração de
*Execução*, mas **não** a de Diagnóstico nem a das demais transições. Daí a necessidade de
`data_ultima_transicao` — é um campo novo, não uma renomeação, e entra como *"ajuste no modelo
relacional"* na documentação cobrada pelo enunciado.

---

## 9. Entregáveis desta frente

| Entregável | Onde |
|---|---|
| ADR — escolha da ferramenta de observabilidade (D-01/D-02) | `docs/adrs/` do repo da aplicação |
| ADR — estratégia de correlação W3C Trace Context (D-03) | `docs/adrs/` |
| RFC — padrão de logs estruturados JSON | `docs/rfcs/` |
| Camada de instrumentação da aplicação | PR em `tech-challenge-oficina` |
| Instrumentação da Lambda | PR em `tech-challenge-oficina-auth` (com Lucas) |
| Agente e secret no cluster | PR em `tech-challenge-oficina-k8s` (com Sophia) |
| Monitoramento do banco | PR em `tech-challenge-oficina-database` (com Sophia) |
| Dashboards como código (JSON exportado do New Relic) | `observabilidade/dashboards/` no repo da app |
| Alertas e runbooks | `observabilidade/alertas/` |
| Visão de monitoramento no Diagrama de Componentes | doc arquitetural do grupo |
| Roteiro das duas cenas do vídeo (dashboard ao vivo; logs e traces) | doc do grupo |

---

## 10. Ordem de execução sugerida

1. Criar conta New Relic e a chave de licença; guardar em Secrets Manager/SSM (não em repo).
2. **Enviar `requisitos-para-o-time.md` para Sophia e Lucas** — é o que destrava a infra deles.
3. Instrumentar a aplicação localmente (kind + Docker) e validar que trace e log chegam.
4. Emitir os custom events e montar D1/D2/D3 com dados sintéticos.
5. Ligar o cluster real e o RDS quando a Sophia entregar.
6. Ligar a Lambda com o Lucas e provar o trace atravessando os três componentes.
7. Alertas, runbooks, ADRs/RFC.
8. Ensaiar as cenas do vídeo.

---

## 11. Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| Infra da Sophia atrasar e não haver cluster real para monitorar | Alto — o vídeo exige dashboard ao vivo | Desenvolver e demonstrar contra `kind` local + agente New Relic; o cluster real vira só troca de endpoint |
| Estourar o free tier de 100 GB/mês | Médio — corte de ingestão | `log_level=INFO` em produção, *sampling* de trace em 100% só em homologação, sem log de body |
| CPF vazar em log da Lambda | Alto — reprovação em segurança e LGPD | Regra de hash em §5.1 acordada por escrito com Lucas antes dele codar |
| Nomes de status divergirem do enunciado | Médio — dashboard D2 não bate com o pedido | Conferir `STATUS_CHOICES` já na semana 1 (§8, item 6) |
| **A nuvem não ser AWS** | **Alto — pode inviabilizar o requisito de correlação** | Ver §12. Confirmar por escrito com o grupo antes de qualquer provisionamento |

---

## 12. Dependência da nuvem escolhida

Levantamento em 13/08 contra a documentação oficial do New Relic. **Mais da metade dos
requisitos de `requisitos-para-o-time.md` mudariam se a nuvem não fosse AWS** — a maioria só
de nome, mas dois pontos mudam de natureza:

| Frente | AWS | Azure | GCP |
|---|---|---|---|
| APM, logs e Kubernetes (`nri-bundle`) | Baixo esforço | Baixo | Baixo (GKE Autopilot exige `provider=GKE_AUTOPILOT`) |
| Query lenta no banco | Documentado para RDS/Aurora | Documentado para Flexible Server | **Cloud SQL não aparece na doc** |
| Instrumentação da function | Layer + 1 variável de ambiente | Agente Python, só `HttpTrigger` | Não existe agente — só métricas por polling de 5 min |
| **Trace distribuído function ↔ APM** | **Suportado** | **Não suportado em Python** | **Não suportado** |
| API Gateway | Integrações v1 e v2, métricas + access log | Polling; log exige Event Hub + ARM | Uma métrica documentada |

**A consequência prática:** em Azure com runtime Python, a documentação de compatibilidade do
New Relic não lista distributed tracing — atender o requisito exigiria trocar a function para
.NET ou escrever propagação OpenTelemetry manual. Em GCP, Cloud Functions não tem agente,
e a saída seria migrar para Cloud Run, o que deixa de ser "function serverless" no sentido do
enunciado.

Itens **agnósticos de nuvem** (não mudam em nenhum cenário): K5, K6, K7, K8, B3, L5, L6, L7, L8.

Pontos que a pesquisa **não conseguiu confirmar** em fonte oficial e que continuam em aberto:
o que exatamente acontece ao exceder os 100 GB/mês do free tier; se o `nri-postgresql` cobre
Google Cloud SQL; e o mecanismo exato de envio de logs das Azure Functions.
