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

A arquitetura da Fase 3 (`docs/fase3/integracao-repositorios.md`) tem **dois fluxos que saem do
API Gateway**, não uma cadeia única:

```text
                      ┌─────────────────────────────────────────────────────┐
                      │  API Gateway (access log JSON)                      │
  Cliente ─traceparent─▶                                                    │
     │                │  ① POST /auth  ──────▶ Lambda auth (CPF → JWT) ──▶ RDS
     │  (JWT em mão)  │      « trace A »          └ NR Lambda layer         │
     │                │                                                     │
     └────────────────▶  ② Bearer JWT ────────▶ App Django no EKS ─────▶ RDS
                      │      « trace B »          ├ NR Python agent (APM)   │
                      │                           ├ log JSON em stdout      │
                      │                           └ custom events de OS     │
                      └──────────────────────┬──────────────────────────────┘
                          EKS ── nri-bundle (kube-state)
                          RDS ── Enhanced Monitoring + nri-postgresql
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

**Não existe um `trace.id` único indo do Gateway ao banco passando pela Lambda.** ① termina
quando a Lambda devolve o JWT; ② é uma requisição **nova** do cliente, já autenticado, e nasce
com um trace próprio. São dois traces, cada um completo de ponta a ponta **dentro do seu
fluxo** — e é isso que o enunciado pede por *"correlação entre requisições"*: dado um erro no
dashboard, chegar na linha de log da requisição que o causou. Isso continua valendo, em ambos
os fluxos.

O que liga um fluxo ao outro, quando a investigação precisa cruzá-los (*"esse cliente não
conseguiu abrir OS"*), é o **`X-Correlation-Id`**: enviado pelo cliente nas duas chamadas e
**encaminhado sem modificação pelo API Gateway**; quem **valida, gera quando falta e devolve
o valor na resposta** são a Lambda e a aplicação — é do valor devolvido que o cliente que não
gerou nada tira o que reusar na segunda chamada. **Decidido pelo grupo em 2026-08-23** (Lucas),
a partir da revisão do Hélio no PR #11, com a divisão de responsabilidade acertada em
2026-08-24 — formalizado no ADR-006 (`docs/adrs/`, PR #15).

O `cliente.ref` (§5.1) mais a janela de tempo continuam servindo como laço fraco, para o caso
de uma requisição chegar sem o header. É laço de última instância: depende de janela de tempo
e não distingue duas tentativas do mesmo cliente.

O trace de ① só se estende até a aplicação se a Lambda passar a chamá-la (hoje ela vai direto
ao banco). É para esse caso, e para as chamadas que ela já faz adiante, que existe o requisito
L2 de `requisitos-para-o-time.md`.

---

## 4. Ambientes

| Branch | Ambiente | Nome do app no New Relic | Cluster |
|---|---|---|---|
| `develop` | Homologação | `oficina-api-hml` | `oficina-hml` |
| `main` | Produção | `oficina-api-prd` | `oficina-prd` |

Todo dado enviado carrega o atributo `service.environment` (`homologacao` \| `producao`).
É uma conta New Relic só, com os dois ambientes separados por atributo — o free tier não dá
sub-contas.

**Regra: todo widget e toda condição de alerta filtram ambiente explicitamente.** *Facet* não
serve para isso — faceta separa a visualização, mas o dado dos dois ambientes continua na mesma
consulta, e num alerta isso significa homologação disparando plantão de produção. A chave de
filtro muda conforme a fonte, porque nem todo tipo de evento aceita atributo customizado:

| Fonte | Tipo de evento | Como filtrar produção |
|---|---|---|
| Aplicação (eventos de negócio) | `OrdemServicoEvento` | `service.environment = 'producao'` |
| Log (app, Lambda, Gateway) | `Log` | `service.environment = 'producao'` |
| APM | `Transaction` | `appName = 'oficina-api-prd'` |
| Kubernetes | `K8sContainerSample` | `clusterName = 'oficina-prd'` |
| Lambda | `AwsLambdaInvocation` | `entityName = 'oficina-auth-cpf-prd'` |
| Banco | `DatastoreSample` | tag `Environment = 'prd'` (B7) |

Para homologação, as mesmas consultas com o sufixo `-hml` / `homologacao`. Os dashboards de
homologação são uma cópia do dashboard de produção com essa troca — não widgets misturados.

---

## 5. Sinais

### 5.1 Logs estruturados (JSON)

Formato único para aplicação e Lambda. Ambas escrevem uma linha JSON por evento em `stdout`; o API Gateway produz access logs em JSON no CloudWatch.

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
- **Detalhe de falha de autenticação vive só no log.** O motivo (`cpf_invalido`,
  `nao_encontrado`, `inativo`) entra como `auth.motivo`; a resposta HTTP é 401 genérica em
  todos os casos. Devolver 404 para CPF inexistente e 403 para inativo entregaria ao mundo,
  de graça, quem é cliente da oficina — ver L7 em `requisitos-para-o-time.md`.

### 5.2 Correlação entre requisições

1. O API Gateway **encaminha, sem modificar**, os headers `traceparent`, `tracestate`,
   `X-Request-Id` e `X-Correlation-Id` recebidos do cliente; se algum não vier, quem gera é a
   Lambda ou a aplicação — o Gateway não valida nem gera nenhum deles.
2. Todo componente **propaga** `traceparent` e `tracestate` nas chamadas que faz adiante.
3. A aplicação expõe um middleware que:
   - lê `traceparent`, `X-Request-Id` e `X-Correlation-Id` da requisição (gera UUIDv4 se
     ausente);
   - guarda ambos em `contextvars`, para o formatter de log injetar sem passar parâmetro;
   - devolve `X-Request-Id` e `X-Correlation-Id` no header da resposta, para o cliente citar
     num suporte e para o laço entre os dois fluxos sobreviver. A Lambda faz o mesmo (L9b de
     `requisitos-para-o-time.md`): sem o valor de volta, o cliente não tem o que reusar.
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
| `statusAnterior` | string | `RECEBIDA`, `DIAGNOSTICO`, `AGUARDANDO`, `EXECUCAO`, `FINALIZADA`, `ENTREGUE`, `CANCELADA` |
| `statusNovo` | string | idem |
| `duracaoStatusSegundos` | float | Tempo que a OS permaneceu em `statusAnterior` |
| `erroTipo` | string | Preenchido só quando `evento = FALHA` |
| `traceId` | string | Liga o evento ao trace e ao log |
| `service.environment` | string | `homologacao` \| `producao` — filtro obrigatório (§4) |

Os valores de status são **exatamente** os `StatusOrdemServico` de
`atendimento/domain/enums.py`. Nada de `AGUARDANDO_APROVACAO`: o domínio usa `AGUARDANDO`
(o rótulo "Aguardando aprovação" é só o *display* do `STATUS_CHOICES`). Inventar um nome aqui
faria D2 devolver vazio sem erro nenhum.

O cálculo de `duracaoStatusSegundos` exige registrar o instante da transição anterior.
**Isso é uma mudança de modelo** — ver §8, item 6.

**`unidade` não existe** — nem no modelo, nem no contrato da API, nem em lugar nenhum do
código hoje (conferido em `atendimento/`). A premissa multi-unidade é do enunciado, não da
aplicação. Consequências:

- o atributo **não** entra em `OrdemServicoEvento` enquanto não houver campo de origem;
- D1 não faceta por unidade (§6);
- o gerador de carga carrega a unidade sorteada no campo livre `origem` das transições
  (`gerador-carga/<unidade>`, constante ao longo da OS), o que serve para diferenciar tráfego
  sintético, **não** para alimentar painel;
- se o grupo quiser a quebra por unidade, é campo novo na `OrdemServico` + migration — ver §8,
  item 9, marcado como opcional.

### 5.5 Healthchecks e uptime

A aplicação já expõe `GET /health/live/` e `GET /health/ready/` (`app/urls.py`).

- `live`: processo respondendo — usado pelo `livenessProbe` do K8s.
- `ready`: dependências OK (banco acessível) — usado pelo `readinessProbe`.
- **Uptime externo:** monitor Synthetics do tipo *Ping* contra a URL pública de cada ambiente,
  a cada 1 minuto, de 2 regiões. É o que produz o número de uptime para o dashboard e o vídeo.

---

## 6. Dashboards

Um dashboard "Oficina — Operação", com 3 páginas. Consultas NRQL de referência — todas na
versão de **produção**; a de homologação é a mesma com a troca da §4.

**D1 — Volume diário de ordens de serviço** *(exigido)*
```sql
SELECT count(*) FROM OrdemServicoEvento
WHERE evento = 'ABERTURA' AND service.environment = 'producao'
TIMESERIES 1 day SINCE 30 days ago
```
Sem `FACET unidade`: o campo não existe no domínio (§5.4). Se entrar como campo de verdade,
a facet volta aqui.

**D2 — Tempo médio de execução por status** *(exigido)*
```sql
SELECT average(duracaoStatusSegundos) / 60 AS 'Minutos médios'
FROM OrdemServicoEvento
WHERE evento IN ('TRANSICAO', 'CONCLUSAO') AND `service.environment` = 'producao'
  AND statusAnterior IN ('RECEBIDA', 'DIAGNOSTICO', 'AGUARDANDO', 'EXECUCAO', 'FINALIZADA')
FACET statusAnterior SINCE 7 days ago
```
**`CONCLUSAO` precisa entrar no filtro.** A transição `FINALIZADA → ENTREGUE` é emitida como
`CONCLUSAO` (§5.4), então filtrar só `TRANSICAO` exclui em silêncio o tempo gasto no último
status: o painel mostra quatro faixas onde deveria mostrar cinco, e nada indica a falta.
Conferido contra dado real em 2026-08-23.

**D3 — Erros e falhas nas integrações** *(exigido)*
```sql
SELECT count(*) FROM Log
WHERE level = 'ERROR' AND integracao IS NOT NULL
  AND service.environment = 'producao'
FACET integracao, error.type TIMESERIES SINCE 24 hours ago
```

**D4 — Latência das APIs**
```sql
SELECT percentile(duration, 50, 95, 99) FROM Transaction
WHERE appName = 'oficina-api-prd' FACET name TIMESERIES SINCE 6 hours ago
```
`LIKE 'oficina-api%'` casaria com `-hml` e misturaria os dois ambientes no mesmo percentil.

**D5 — Kubernetes e disponibilidade**
```sql
SELECT average(cpuUsedCores), average(memoryWorkingSetBytes) / 1e6 AS 'MB'
FROM K8sContainerSample WHERE clusterName = 'oficina-prd'
FACET podName TIMESERIES SINCE 3 hours ago
```

**D6 — Fluxo de autenticação** (liga a frente do Lucas)
```sql
SELECT count(*) FROM AwsLambdaInvocation
WHERE entityName = 'oficina-auth-cpf-prd' FACET error TIMESERIES SINCE 24 hours ago
```
O nome leva o sufixo de ambiente (L8). Para separar recusa legítima de falha nossa, o widget
irmão faceta por `auth.motivo` no `Log` da Lambda — atributo interno, nunca resposta HTTP
(§7, A7, e L7 de `requisitos-para-o-time.md`).

---

## 7. Alertas

Política `Oficina — Produção`, com notificação em canal do grupo (e-mail e/ou webhook).

**Toda condição desta política filtra produção na própria NRQL** (§4). Sem isso, um teste em
homologação — inclusive o gerador de carga com `--falhas` — dispara alerta de produção, e o
alerta perde credibilidade justamente no dia da gravação. A coluna "Filtro de ambiente" abaixo
é obrigatória, não decorativa.

| # | Alerta | Condição | Filtro de ambiente | Severidade |
|---|---|---|---|---|
| **A1** | **Falha no processamento de ordens de serviço** *(exigido)* | `SELECT count(*) FROM OrdemServicoEvento WHERE evento = 'FALHA'` > 0 por 5 min | `AND service.environment = 'producao'` | Crítico |
| A2 | Taxa de erro da API | `percentage(count(*), WHERE error IS true) FROM Transaction` > 5% por 5 min | `WHERE appName = 'oficina-api-prd'` | Crítico |
| A3 | Latência degradada | p95 de `Transaction.duration` > 1,5 s por 10 min | `WHERE appName = 'oficina-api-prd'` | Aviso |
| A4 | Endpoint fora do ar | Monitor Synthetics falhando em 2 localidades | monitor da URL de produção | Crítico |
| A5 | Saturação de pod | `K8sContainerSample.memoryWorkingSetBytes` > 90% do limite por 10 min | `WHERE clusterName = 'oficina-prd'` | Aviso |
| A6 | Pod em CrashLoop | `restartCount` cresce mais de 3 vezes em 15 min | `WHERE clusterName = 'oficina-prd'` | Crítico |
| A7 | Falha de autenticação sistêmica | Taxa de erro da Lambda de auth > 10% por 5 min | `WHERE entityName = 'oficina-auth-cpf-prd'` | Crítico |
| A8 | Banco saturado | Conexões do RDS > 80% do máximo por 10 min | `WHERE Environment = 'prd'` | Aviso |

A7 mede **erro da function** (5xx, timeout, exceção), não recusa de autenticação: CPF que não
autentica é resposta 401 esperada, e contá-la como falha faria o alerta tocar sempre que
alguém digitasse errado. A separação vem do atributo interno `auth.motivo` no log (L7).

Cada alerta precisa de um **runbook** de uma página: o que significa, onde olhar, o que fazer.
Isso conta como documentação arquitetural e é rápido de produzir.

---

## 8. Mudanças necessárias na aplicação

Estas entram como PR no repositório `tech-challenge-oficina`:

1. `requirements.txt`: `newrelic`. O formatter JSON usa a stdlib `json` — o schema desta
   seção é fixo e pequeno, e uma biblioteca a menos é uma a menos na CI e na imagem.
2. `app/observabilidade/logging.py` — formatter JSON + filtro que injeta `trace.id`,
   `span.id`, `request.id` a partir de `contextvars`.
3. `app/observabilidade/middleware.py` — `CorrelationIdMiddleware` (§5.2), registrado como o
   **primeiro** item de `MIDDLEWARE`. É ele que cumpre a parte da **aplicação** no contrato de
   `X-Correlation-Id` (L9b de `requisitos-para-o-time.md`), e são quatro coisas, não uma:
   **aceitar** o header do cliente, **gerar** um UUIDv4 quando vier ausente ou inválido,
   **registrar** em `correlation.id` no log de cada requisição, e **devolver** o valor no header
   da resposta. O mesmo vale para `X-Request-Id`. Sem o item "devolver", o cliente que não gerou
   o valor não tem o que reusar na segunda chamada e o laço entre os dois fluxos não fecha —
   então o L9 não se resolve só no Gateway e na Lambda.
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
9. **Opcional, fora do mínimo:** campo `unidade` na `OrdemServico` (+ migration, + serializer de
   abertura). Só se o grupo quiser a quebra por unidade em D1 — o enunciado não exige. Enquanto
   não existir, `unidade` não é atributo de `OrdemServicoEvento` (§5.4).

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
| ADR — escolha da ferramenta de observabilidade (D-01/D-02) | ✅ `docs/adrs/adr-005-observabilidade-new-relic.md` |
| ADR — estratégia de correlação W3C Trace Context (D-03) | ✅ `docs/adrs/adr-006-correlacao-w3c-trace-context.md` |
| RFC — padrão de logs estruturados JSON | ✅ `docs/rfcs/rfc-004-logs-estruturados-json.md` |
| Camada de instrumentação da aplicação | PR em `tech-challenge-oficina` |
| Instrumentação da Lambda | PR em `tech-challenge-oficina-auth` (com Lucas) |
| Agente e secret no cluster | PR em `tech-challenge-oficina-k8s` (com Sophia) |
| Monitoramento do banco | PR em `tech-challenge-oficina-database` (com Sophia) |
| Dashboards como código (JSON exportado do New Relic) | `observabilidade/dashboards/` no repo da app |
| Alertas e runbooks | `observabilidade/alertas/` |
| Visão de monitoramento no Diagrama de Componentes | doc arquitetural do grupo |
| Roteiro das duas cenas do vídeo (dashboard ao vivo; logs e traces) | doc do grupo |

---

## 9.1 Gerador de carga — `scripts/gerar_carga_observabilidade.py`

Os três dashboards exigidos são **históricos**: volume diário, tempo médio por status e erros
de integração só existem sobre dados acumulados. Como o ambiente é efêmero (sobe e desce para
caber no orçamento da AWS Academy), não há tráfego orgânico — sem gerador, o dashboard aparece
vazio no dia da gravação.

São **714 linhas** de Python de biblioteca padrão — não adiciona dependência ao projeto. O
script dirige a API real respeitando o grafo de `domain/policies.py`, com tempos de permanência
realistas comprimidos por `--aceleracao` (padrão 3600: uma hora de oficina por segundo, ciclo
completo em ~20 s). Testes em `scripts/tests/` (275 linhas), rodados pela CI junto da suíte da
aplicação — validam as transições contra a policy real do domínio, entre outras coisas.

```bash
# tráfego contínuo enquanto se trabalha
python scripts/gerar_carga_observabilidade.py --duracao 600 --taxa 12

# rajada para popular o painel antes de gravar
python scripts/gerar_carga_observabilidade.py --ordens 80 --aceleracao 7200
```

O que ele produz, e para qual painel:

| Comportamento | Alimenta |
|---|---|
| Abertura de OS em ritmo configurável (`--taxa`) | D1 (volume diário) |
| Ciclo completo com permanência variável por status | D2 (tempo médio por status) |
| Recusa de orçamento devolvendo a OS para `DIAGNOSTICO` | D2 — retrabalho visível |
| `--falhas` (8%): transição proibida, OS inexistente, integração fora de hora | D3 e alerta A1 |
| Threads de leitura consultando a fila | D4 — latência de leitura, senão a mediana distorce |
| `traceparent` W3C e `X-Request-Id` em toda requisição | §5.2 — correlação |

**A aceleração distorce o D2 — não grave o vídeo com valor alto.** O campo
`duracaoStatusSegundos` mede tempo de parede entre duas transições, e nesse tempo
está o round-trip HTTP do próprio gerador. O custo é *fixo* (~58 ms medidos), mas
o valor simulado encolhe com a aceleração, então quanto maior a aceleração, mais
o overhead domina — e domina primeiro os status curtos, que são justamente os que
o painel precisa distinguir.

Medido em 2026-08-23 com `--aceleracao 150000`, contra o perfil de permanência
configurado:

| Status | Esperado | Medido | Excesso |
|---|---|---|---|
| `RECEBIDA` | 0,6 h | 3,27 h | +2,67 h (64 ms reais) |
| `DIAGNOSTICO` | 3,2 h | 5,62 h | +2,37 h (57 ms reais) |
| `FINALIZADA` | 2,2 h | 4,44 h | +2,19 h (53 ms reais) |
| `EXECUCAO` | 6,5 h | 8,45 h | +1,95 h (47 ms reais) |
| `AGUARDANDO` | 9,0 h | 11,80 h | +2,80 h (67 ms reais) |

O excesso real é o mesmo em todos (média 58 ms, contra p50 de 49 ms de latência
medida), o que confirma a causa. `RECEBIDA` fica 5× acima da faixa configurada.

Para o excesso ficar abaixo de 10% do status mais curto, a aceleração precisa
ficar **abaixo de ~3750** — e o padrão do gerador é **3600**. Use o padrão para
gravar; a aceleração alta serve para encher o painel rápido, não para medir.

Ao encerrar (fim de `--duracao`, cota de `--ordens` ou Ctrl+C), o script para primeiro as
threads de leitura e depois deixa as OS em andamento fecharem o ciclo, até `--espera-final`
(padrão: o pior caso do ciclo na aceleração escolhida). Um segundo Ctrl+C aborta na hora, e o
resumo diz quantos ciclos ficaram pela metade — OS abortada no meio vira buraco em D2.

**Rodar sempre contra homologação.** As falhas de `--falhas` são erros de verdade na aplicação;
em produção acionariam A1. É o outro lado da regra de filtro de ambiente da §4.

**Limite importante:** o gerador produz *tráfego*, não eventos de negócio. `OrdemServicoEvento`
(§5.4) é emitido pela aplicação instrumentada — rodar o gerador antes de §8 item 6 popula APM,
logs e banco, mas **não** D1 e D2. A ordem correta é instrumentar e depois gerar.

O passo a passo operacional — criar a conta, ligar o agente local, subir no
`kind` e conferir que o dado chegou — está em
[`runbook-ligar-observabilidade.md`](runbook-ligar-observabilidade.md).

## 10. Ordem de execução sugerida

1. Criar conta New Relic e a chave de licença; guardar em Secrets Manager/SSM (não em repo).
2. **Enviar `requisitos-para-o-time.md` para Sophia e Lucas** — é o que destrava a infra deles.
   ✅ Enviado no grupo em 13/08.
3. Instrumentar a aplicação localmente (kind + Docker) e validar que trace e log chegam.
4. Emitir os custom events e montar D1/D2/D3 com dados sintéticos.
5. Ligar o cluster real e o RDS quando a Sophia entregar.
6. Ligar a Lambda com o Lucas e provar o trace de autenticação (Gateway → Lambda → banco) e o trace da aplicação (Gateway → Django → banco).
7. Alertas, runbooks, ADRs/RFC.
8. Ensaiar as cenas do vídeo.

---

## 11. Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| Infra da Sophia atrasar e não haver cluster real para monitorar | Alto — o vídeo exige dashboard ao vivo | Desenvolver e demonstrar contra `kind` local + agente New Relic; o cluster real vira só troca de endpoint |
| Estourar o free tier de 100 GB/mês | Médio — corte de ingestão | `log_level=INFO` em produção, *sampling* de trace em 100% só em homologação, sem log de body |
| CPF vazar em log da Lambda | Alto — reprovação em segurança e LGPD | Regra de hash em §5.1 acordada por escrito com Lucas antes dele codar |
| Nomes de status divergirem do domínio | Médio — D2 devolve vazio sem erro nenhum | Conferido (§8, item 6). O teste `test_status_usados_existem_no_dominio` trava isso na CI; a mesma regra vale para as NRQL, que ninguém testa — revisar §6 se o enum mudar |
| Alerta de produção disparado por tráfego de homologação | Médio — alerta perde credibilidade justo na gravação | Filtro de ambiente obrigatório em toda condição (§4, §7); gerador de carga só contra homologação |
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
