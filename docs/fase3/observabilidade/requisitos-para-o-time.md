# Requisitos de Observabilidade para as demais frentes

**De:** Luís (Observabilidade) · **Para:** Sophia (Infraestrutura) e Lucas (Autenticação)
**Contexto:** resposta ao pedido da Sophia em 11/08 — *"me fala quais configurações você vai
precisar no Kubernetes e no RDS (…) e se você também precisar monitorar a parte do Lucas, pode
alinhar com ele o que será necessário na Lambda/API Gateway"*.
**Ferramenta escolhida:** New Relic (justificativa em `README.md`, §2).

Nada aqui exige que vocês instalem agente ou escrevam código de monitoramento — eu faço isso.
O que peço é que a infraestrutura **já nasça** com estes pontos, para não retrabalhar depois.

---

## Para a Sophia — Cluster Kubernetes (EKS)

| # | Requisito | Por quê |
|---|---|---|
| K1 | Namespace `newrelic` liberado, e permissão para instalar o Helm chart `nri-bundle` (cria DaemonSet, ServiceAccount, ClusterRole e `kube-state-metrics`) | É o coletor de CPU/memória/pods exigido pelo enunciado |
| K2 | Secret `newrelic-license` no namespace da aplicação, populado a partir do Secrets Manager/SSM — **eu passo o valor da chave por canal privado, nunca em repositório** | O agente da aplicação precisa da licença |
| K3 | `metrics-server` instalado no cluster | Já é pré-requisito do HPA; o coletor também usa |
| K4 | Egress HTTPS (443) liberado para `*.newrelic.com`, `otlp.nr-data.net` e `log-api.newrelic.com` | Se houver NAT Gateway ou Security Group restritivo, sem isso nada sai |
| K5 | `clusterName` padronizado: `oficina-hml` e `oficina-prd` | Vira *facet* nos dashboards; renomear depois quebra as consultas salvas |
| K6 | Labels obrigatórias em todo Deployment: `app`, `env`, `version` | Permite correlacionar deploy com degradação |
| K7 | Aplicação com `resources.requests` e `resources.limits` definidos | Sem `limits` não existe "% de saturação" — o alerta A5 fica impossível |
| K8 | Probes separadas: `livenessProbe` → `/health/live/`, `readinessProbe` → `/health/ready/` | Os dois endpoints já existem na aplicação |
| K9 | Endpoint público estável por ambiente (Ingress/ALB) | Necessário para o monitor de uptime (Synthetics) |

## Para a Sophia — Banco gerenciado (RDS PostgreSQL)

| # | Requisito | Por quê |
|---|---|---|
| B1 | **Enhanced Monitoring** ligado, granularidade 30 s | Métricas de SO da instância, coletadas pela integração de RDS do New Relic via CloudWatch Logs (`RDSOSMetrics`) |
| B2 | **`shared_preload_libraries = pg_stat_statements`** no parameter group | **É este o item que entrega query lenta**, não o Performance Insights — ver nota abaixo. Exige reboot |
| B3 | Usuário read-only `newrelic_monitor` com a role `pg_monitor` (que já contém `pg_read_all_stats`), e Security Group permitindo acesso a partir do cluster | Credencial da integração `nri-postgresql`, que é quem lê o `pg_stat_statements` |
| B4 | Restante do parameter group: `log_min_duration_statement = 500`, `log_lock_waits = on` | Query lenta também no log, para correlacionar com o trace |
| B5 | Export do log `postgresql` para o CloudWatch | Origem do log do banco |
| B6 | **Performance Insights** ligado, retenção de 7 dias (faixa gratuita) | Console de análise da própria AWS — útil na investigação, mas **não é fonte do New Relic** |
| B7 | Tags padrão nos recursos: `Project=oficina`, `Environment=hml\|prd` | Agrupa custo e entidades |

> **Correção importante (13/08):** o New Relic **não ingere o Performance Insights**. Query
> lenta vem da host integration `nri-postgresql` com `ENABLE_QUERY_MONITORING=true`, lendo a
> extensão `pg_stat_statements` com um usuário que tenha `pg_read_all_stats`. A documentação
> da integração cita RDS e Aurora nominalmente (com `ENABLE_SSL=true` e
> `TRUST_SERVER_CERTIFICATE=true`). Ou seja: **B2 e B3 são os itens críticos**, e o
> Performance Insights (B6) desceu para "bom ter". Se algum item da lista precisar cair por
> tempo, que caia o B6.

> B1, B2 e B4 são **flags de criação ou exigem reboot**. É por isso que vale decidir agora, e
> não depois que o RDS estiver de pé.

---

## Para o Lucas — Lambda de autenticação e API Gateway

| # | Requisito | Por quê |
|---|---|---|
| L1 | Adicionar a **New Relic Lambda Layer** à function (é uma linha no Terraform/SAM) e as variáveis `NEW_RELIC_LICENSE_KEY`, `NEW_RELIC_ACCOUNT_ID`, `NEW_RELIC_LAMBDA_HANDLER`, `NEW_RELIC_EXTENSION_SEND_FUNCTION_LOGS=true` | Traz duração, erro, cold start e log da function |
| L2 | **Propagar os headers `traceparent` e `tracestate`** que chegarem na requisição em chamadas HTTP ou mensageria que a Lambda faça adiante (ex.: aplicação se um dia chamar). Acesso ao banco aparece como datastore span filho criado pela instrumentação do driver. | Mantém o trace da autenticação inteiro nas chamadas síncronas (HTTP). **Não** é o que ligaria auth e aplicação: são dois fluxos separados que saem do Gateway, cada um com o seu trace — ver `README.md` §3 |
| L3 | API Gateway com `traceparent` na lista de headers repassados (não bloquear no mapping) | Idem |
| L4 | **Access logging do API Gateway em JSON**, no CloudWatch, com pelo menos `requestId`, `path`, `status`, `integrationLatency`, `responseLatency`, `error.message`, `service.environment` (`homologacao` \| `producao`) em ambas as stages | Latência da borda; o enunciado pede latência das APIs; sem o campo de ambiente o access log do Gateway não separa homologação de produção no filtro de `Log` da §4 do `README.md` |
| L5 | Log da Lambda em **JSON**, no mesmo schema de campos de `README.md` §5.1 | Um schema só = uma consulta só nos dashboards |
| L6 | **CPF nunca em log, nem em atributo de trace, nem em mensagem de erro.** Onde precisar identificar o cliente, usar `cliente.ref` = SHA-256 do CPF com salt de ambiente | LGPD, e é o tipo de detalhe que a avaliação da FIAP olha |
| L7 | Resposta de erro padronizada (`{"error": {"type", "message", "requestId"}}`). **Uma resposta só — 401 genérica — para todo caso de "não autentica": CPF inválido, inexistente ou cliente inativo.** O motivo real vai para o log/trace no atributo `auth.motivo` (`cpf_invalido` \| `nao_encontrado` \| `inativo`), nunca para o corpo, o header ou o código HTTP | Diferenciar 404 de 403 na resposta transforma o endpoint em **oráculo de enumeração**: com uma lista de CPFs, qualquer um descobre quem é cliente da oficina e quem está inativo — sem autenticar. O `auth.motivo` no log dá a mesma informação para D6 e A7, e só para quem tem acesso ao New Relic |
| L7b | *Rate limit* por IP no endpoint de autenticação (o throttling do próprio API Gateway já resolve) | A resposta genérica tira o oráculo; o rate limit tira a força bruta de varrer uma lista de CPFs. Vale checar também se o caminho "cliente inexistente" não responde muito mais rápido que o caminho "cliente encontrado" — diferença grande de tempo reabre a enumeração pelo relógio |
| L8 | Nomes das functions padronizados: `oficina-auth-cpf-hml` / `-prd` | Facet nos dashboards |
| L9 | **API Gateway: encaminhar `X-Correlation-Id` sem modificar**, junto de `Authorization`, `X-Request-Id`, `traceparent` e `tracestate`, nas duas integrações (Lambda e VPC Link) | É o único laço entre o fluxo de autenticação e o de aplicação: os dois saem do Gateway de forma independente, cada um com o seu trace, e o `traceparent` não os cruza. Decidido pelo grupo em 2026-08-23 — ver `README.md` §3 e ADR-006. O Gateway não valida nem gera o valor: só não pode perdê-lo no caminho |
| L9b | **Lambda: validar o `X-Correlation-Id` recebido; se vier ausente ou inválido, gerar um UUIDv4.** Registrar no log (campo `correlation.id`) e **devolver o valor no header da resposta** | Responsabilidade acertada com o Lucas em 2026-08-24. Sem devolver o header, o cliente que não gerou o valor não tem como reusá-lo na chamada protegida seguinte, e o laço entre os dois fluxos não existe. A aplicação faz o mesmo do seu lado (`README.md` §5.2) |

---

## O que eu entrego em troca

- Os PRs de instrumentação em cada repositório — vocês só revisam.
- Os dashboards e alertas prontos, com acesso para o grupo todo.
- Os runbooks dos alertas.
- Os ADRs/RFC da escolha da ferramenta e do padrão de correlação.
- As duas cenas do vídeo que são de observabilidade.

## O que ainda depende de vocês me responderem

1. **Nuvem confirmada é AWS?** (as mensagens falam de RDS e EKS, mas quero confirmar por escrito)
2. Existe orçamento/conta AWS compartilhada, ou cada um usa a própria? Isso muda onde a chave
   de licença é guardada.
3. A URL pública de homologação vai existir antes de 05/09? O monitor de uptime depende dela.
4. **Lucas:** a autenticação e a aplicação são dois fluxos separados a partir do Gateway, cada
   um com o seu trace (`README.md` §3). Se quisermos amarrar os dois numa investigação, o
   caminho é o cliente gerar um `X-Correlation-Id` e mandar nas duas chamadas. Não é exigência
   do enunciado — me diz se você acha que vale, senão fico com `cliente.ref` + janela de tempo.

> Já conferido, não precisa responder: os status da OS no modelo atual
> (`DIAGNOSTICO`, `EXECUCAO`, `FINALIZADA`) batem com os nomes do enunciado. Vou precisar
> adicionar um campo `data_ultima_transicao` na `OrdemServico` para medir o tempo em cada
> status — isso entra num PR meu na aplicação, com migration.
