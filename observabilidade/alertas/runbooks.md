# Runbooks dos alertas

Um por condição de `condicoes.json`. Cada um responde três perguntas: **o que
significa**, **onde olhar** e **o que fazer**. A URL de runbook de cada condição
no New Relic aponta para a âncora correspondente.

Especificação dos alertas: §7 de
[`docs/fase3/observabilidade/README.md`](../../docs/fase3/observabilidade/README.md).

> **Antes de qualquer investigação, confirme o ambiente.** Toda condição desta
> política filtra produção na própria NRQL. Se um alerta de produção disparou por
> causa de tráfego de homologação, o filtro furou — e isso é um defeito no alerta,
> não no sistema.

---

## A1 — Falha no processamento de ordens de serviço

**Exigido pelo enunciado. Crítico.**

### O que significa

A aplicação emitiu evento `OrdemServicoEvento` com `evento = 'FALHA'`: um caso de
uso de ordem de serviço levantou erro de domínio. Não é erro de infraestrutura —
é a regra de negócio recusando uma operação, ou o fluxo de orçamento falhando.

### Onde olhar

```sql
SELECT count(*) FROM OrdemServicoEvento
WHERE evento = 'FALHA' AND `service.environment` = 'producao'
FACET erroTipo, statusAnterior SINCE 1 hour ago
```

O `erroTipo` já separa as causas. Para uma OS específica, o `traceId` do evento
leva ao trace e, dele, às linhas de log da mesma requisição.

### O que fazer

| `erroTipo` | Leitura | Ação |
|---|---|---|
| `OrcamentoNaoPodeSerProcessadoError` | Decisão de orçamento chegou com a OS fora de `AGUARDANDO` | Verificar se há corrida entre duas decisões, ou integração externa reenviando |
| `TransicaoStatusInvalidaError` | Alguém tentou transição que a policy não permite | Provável cliente da API mandando status errado; conferir a origem no log |
| Volume alto e súbito de qualquer tipo | Não é caso isolado | Suspeitar de integração externa em laço; ver A2 em paralelo |

### Armadilha conhecida

**O gerador de carga produz `FALHA` de verdade.** `scripts/gerar_carga_observabilidade.py`
com `--falhas` injeta erros legítimos do ponto de vista da aplicação. Rodá-lo
contra produção aciona este alerta com razão. O gerador é para homologação — está
na §9.1 da especificação, e é a razão de o filtro de ambiente ser obrigatório.

---

## A2 — Taxa de erro da API

**Crítico.**

### O que significa

Mais de 5% das transações da aplicação terminaram em erro por 5 minutos. Diferente
de A1: aqui é a camada HTTP/APM, então entra 5xx, exceção não tratada e falha de
dependência.

### Onde olhar

```sql
SELECT count(*) FROM TransactionError
WHERE appName = 'oficina-api-prd' FACET `error.class`, transactionName SINCE 1 hour ago
```

Se concentrar numa rota só, o problema é dela. Se estiver espalhado, suspeitar de
dependência comum — banco, ou o webhook de orçamento.

### O que fazer

1. Confirmar se o banco responde: painel D4 e `DatastoreSample` (ver A8).
2. Ver se coincide com deploy — a label `version` do pod diz qual imagem está no ar.
3. Se for a rota de orçamento, checar a integração externa: o log carrega
   `integracao` e `integracao.status`.
4. Se coincidir com A6, o problema é o pod reiniciando, não a aplicação.

---

## A3 — Latência degradada

**Aviso.**

### O que significa

p95 acima de 1,5 s por 10 minutos. Aviso, não crítico: o sistema responde, mas
mal.

### Onde olhar

```sql
SELECT percentile(duration, 50, 95, 99) FROM Transaction
WHERE appName = 'oficina-api-prd' FACET name TIMESERIES SINCE 3 hours ago
```

Depois, separar aplicação de banco:

```sql
SELECT average(databaseDuration), average(duration) FROM Transaction
WHERE appName = 'oficina-api-prd' TIMESERIES SINCE 3 hours ago
```

### O que fazer

- `databaseDuration` acompanhando `duration`: o gargalo é banco — ver A8 e a query
  lenta no `pg_stat_statements`.
- `duration` sobe e `databaseDuration` não: gargalo na aplicação ou saturação de
  CPU do pod — ver A5.
- p95 sobe e p50 não: cauda longa, não degradação geral. Olhar as rotas mais lentas
  antes de escalar.

---

## A4 — Endpoint fora do ar

**Crítico.**

### O que significa

O monitor Synthetics falhou em **duas** localidades. Duas, e não uma, porque falha
de uma localidade isolada costuma ser da rede da localidade, não do serviço.

### Onde olhar

- Resultado do monitor: qual passo falhou, código HTTP, tempo até o erro.
- `GET /health/ready/` responde? Ele checa o banco, então distingue "aplicação de
  pé sem banco" de "aplicação fora".
- `GET /health/live/` responde mas `ready` não: processo vivo, dependência caída.

### O que fazer

1. `live` OK e `ready` falhando → problema de dependência; ir para A8.
2. Ambos falhando → ver A6 (pod reiniciando) e o estado do Ingress/Service.
3. Ambos OK pelo cluster mas Synthetics falhando → problema de borda: DNS,
   certificado, ou API Gateway. Nesse caso o access log do Gateway é a fonte.

---

## A5 — Saturação de memória do pod

**Aviso.**

### O que significa

Um container passou de 90% do limite de memória por 10 minutos. Antessala do
OOMKill, que aparece como A6.

### Onde olhar

```sql
SELECT max(memoryWorkingSetBytes / memoryLimitBytes) * 100
FROM K8sContainerSample WHERE clusterName = 'oficina-prd'
FACET podName, containerName TIMESERIES SINCE 3 hours ago
```

### O que fazer

- Crescimento contínuo sem platô: suspeitar de vazamento; comparar com a hora do
  último deploy.
- Degrau súbito: alguma requisição carregando volume grande na memória.
- Todos os pods juntos: é carga, não vazamento — ver o HPA.

### Armadilha conhecida

**Sem `limits` no deployment, este alerta nunca dispara.** `memoryLimitBytes` fica
nulo, a divisão não produz valor, e a condição fica em silêncio — parecendo
saudável. É por isso que os `limits` são requisito de infraestrutura, não
recomendação.

---

## A6 — Pod em CrashLoop

**Crítico.**

### O que significa

O contador de reinícios cresceu mais de 3 vezes em 15 minutos. O container está
subindo e morrendo.

### Onde olhar

```sql
SELECT max(restartCount) FROM K8sContainerSample
WHERE clusterName = 'oficina-prd' FACET podName TIMESERIES SINCE 2 hours ago
```

E o motivo, que o Kubernetes guarda: `kubectl describe pod` mostra `Last State` e
`Reason` — `OOMKilled` aponta para A5; `Error` aponta para falha na subida.

### O que fazer

1. `OOMKilled` → é A5; subir o limite ou corrigir o consumo.
2. Falha na subida → ler o log do container anterior (`kubectl logs --previous`).
   Falha de migration e variável de ambiente ausente aparecem aí.
3. Coincidiu com deploy → o `rollingUpdate` está com `maxUnavailable: 0`, então o
   tráfego não deveria ter caído; confirmar antes de reverter.

---

## A7 — Falha de autenticação sistêmica

**Crítico.**

### O que significa

Mais de 10% das invocações da Lambda de autenticação terminaram em **erro da
function** — 5xx, timeout ou exceção.

**Não é recusa de autenticação.** CPF que não autentica devolve 401, que é resposta
esperada e não conta aqui. Se contasse, o alerta tocaria toda vez que alguém
digitasse o CPF errado.

### Onde olhar

```sql
SELECT count(*) FROM AwsLambdaInvocation
WHERE entityName = 'oficina-auth-cpf-prd' FACET error TIMESERIES SINCE 2 hours ago
```

Para separar recusa legítima de falha nossa, o log da Lambda traz `auth.motivo`
(`cpf_invalido`, `nao_encontrado`, `inativo`) — atributo interno, nunca exposto na
resposta HTTP.

### O que fazer

1. Erro concentrado em timeout → a Lambda não está alcançando o banco; ver A8 e as
  regras de rede.
2. Exceção → ler o log da function; o motivo real está em `auth.motivo`.
3. Taxa alta de `auth.motivo = nao_encontrado` **sem** erro de function: não é este
   alerta. Pode ser varredura de CPFs — ver o rate limit do Gateway.

---

## A8 — Banco saturado

**Aviso.**

### O que significa

As conexões do RDS passaram de 80% do máximo por 10 minutos.

### Onde olhar

```sql
SELECT max(databaseConnectionsUsedPercent) FROM DatastoreSample
WHERE provider = 'RdsDbInstance' AND Environment = 'prd' TIMESERIES SINCE 3 hours ago
```

E a query lenta, que costuma ser a causa:

```sql
SELECT average(databaseDuration) FROM Transaction
WHERE appName = 'oficina-api-prd' FACET name SINCE 1 hour ago
```

### O que fazer

1. Conexões subindo junto com réplicas: o HPA escalou e cada réplica abre seu
   próprio pool. É esperado até o teto; se estourar, o problema é dimensionamento.
2. Conexões altas com pouco tráfego: conexão vazando ou transação longa segurando.
3. Query lenta identificada: `pg_stat_statements` dá o texto; é o motivo de ele ser
   requisito de infraestrutura, já que ligar depois exige reboot da instância.
