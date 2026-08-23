# RFC-004 — Padrão de Logs Estruturados em JSON

| Informação | Valor |
|---|---|
| **RFC** | 004 |
| **Título** | Schema de Log Estruturado JSON para Aplicação, Lambda e API Gateway |
| **Status** | Aprovado |
| **Autores** | Luís Fernando Montes (RM367183) |
| **Data** | 2026-08-23 |
| **Versão** | 1.0 |

---

## 1. Objetivo

Definir um schema único de log para os componentes da Fase 3, de forma que uma consulta só responda por todos eles, e que cada linha seja ligável ao trace que a produziu.

Vale para: aplicação Django, Lambda de autenticação e API Gateway.

## 2. Motivação

O log em texto livre que a aplicação usava até a Fase 2 (`{levelname} {asctime} {module} {message}`) não serve para a Fase 3 por três motivos:

1. **Não é consultável.** Filtrar por status HTTP, rota ou ordem de serviço exige regex sobre texto, que quebra na primeira mensagem escrita diferente.
2. **Não liga log a trace.** Sem `trace.id` na linha, o painel de trace e o de log são duas ilhas — e correlacionar requisição é requisito do enunciado.
3. **Escrevia em arquivo.** Em container, log em arquivo se perde no restart do pod e não é coletado (decisão D-06).

## 3. Schema

Uma linha JSON por evento, em `stdout`.

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

### 3.1 Campos obrigatórios em toda linha

`timestamp`, `level`, `logger`, `message`, `service.name`, `service.environment`, `service.version`.

### 3.2 Obrigatórios dentro de uma requisição

`trace.id`, `span.id`, `request.id`.

### 3.3 Condicionais

| Situação | Campos |
|---|---|
| Erro | `error.type`, `error.message`, `error.stack` |
| Integração externa | `integracao`, `integracao.status` |
| Falha de autenticação | `auth.motivo` (`cpf_invalido` \| `nao_encontrado` \| `inativo`) |
| Contexto HTTP | `http.method`, `http.route`, `http.status_code`, `duration_ms` |
| Ordem de serviço | `os.id`, `os.status_anterior`, `os.status_novo` |

## 4. Regras invioláveis

1. **Nunca logar CPF, e-mail ou telefone em claro.** O cliente entra como `cliente.ref`, SHA-256 com salt de ambiente. Vale especialmente para a Lambda de autenticação, que é justamente quem recebe o CPF.
2. **`trace.id` e `span.id` em toda linha emitida dentro de uma requisição.** Linha sem eles não é ligável a nada.
3. **Erro sempre carrega os três campos de erro.** `error.message` sem `error.type` não permite agrupar.
4. **Detalhe de falha de autenticação vive só no log.** A resposta HTTP é 401 genérica em todos os casos; o motivo vai para `auth.motivo`. Devolver 404 para CPF inexistente e 403 para inativo transformaria o endpoint em oráculo de enumeração: com uma lista de CPFs, qualquer um descobre quem é cliente da oficina e quem está inativo, sem autenticar.

## 5. Destino por componente

O schema lógico é o mesmo; o destino não é.

| Componente | Destino |
|---|---|
| Aplicação Django | `stdout` |
| Lambda de autenticação | `stdout` |
| API Gateway | access log em JSON no CloudWatch |

O access log de **cada stage** do API Gateway precisa incluir um campo estático `service.environment` (`homologacao` \| `producao`). Sem ele, o filtro de ambiente sobre `Log` — obrigatório em todo widget e alerta — não é implementável para o Gateway.

## 6. Decisões de implementação

### 6.1 Sem biblioteca de formatação

O formatter usa a stdlib `json`, não `python-json-logger`. O schema é fixo e pequeno, a biblioteca não acrescenta nada, e é uma dependência a menos na CI e na imagem.

### 6.2 Timestamp com offset de fuso

`timestamp` carrega offset e precisão de milissegundo. Um timestamp ingênuo (sem fuso) faz a plataforma assumir UTC e deslocar a linha em três horas no painel — erro que não gera falha nenhuma e só aparece quando alguém depura um incidente pelo horário errado.

### 6.3 Origem de `trace.id` e `span.id`

Preferência pelo agente de observabilidade quando presente (`get_linking_metadata()`), com queda para os `contextvars` do middleware quando ausente. O motivo está em [ADR-006 §5.2](../adrs/adr-006-correlacao-w3c-trace-context.md): os `contextvars` conhecem só o span da borda, e o agente abre spans internos que o middleware não vê.

### 6.4 O agente não encaminha logs — e não é só por duplicação

`NEW_RELIC_APPLICATION_LOGGING_FORWARDING_ENABLED` fica em `false`. A razão óbvia é
duplicação: os logs já saem em `stdout` e são coletados pela integração de Kubernetes, então
com o forwarding do agente também ligado a mesma linha chega duas vezes e todo painel que
conta linha conta dobrado.

A razão menos óbvia é mais importante, e foi medida em 2026-08-23 com o agente 9.13.0:
**o encaminhamento do agente não usa este formatter.** Ele engancha no `logging` do Python e
monta a linha a partir do `LogRecord`, então `message` chega como a mensagem crua e **nenhum
campo deste RFC vira atributo** — nem `service.environment`, que a §4 exige como filtro
obrigatório em todo widget de log.

Ligar `application_logging.forwarding.context_data.enabled` faz os campos passados via `extra`
chegarem, mas com três problemas:

1. **Chegam com prefixo `context.`** — `context.integracao`, não `integracao`. O caminho do
   cluster (stdout, com a integração fazendo o parse do JSON) entrega os nomes deste RFC. Os
   dois caminhos produzem esquemas diferentes, e o mesmo widget não serve nos dois.
2. **`service.environment` continua ausente**, porque é o formatter que o injeta, não o `extra`.
3. **Vai o `LogRecord` inteiro**: `context.thread`, `context.processName`,
   `context.relativeCreated` e — o que importa — **`context.exc_info` com o traceback completo**.
   Isso é custo de ingestão e é onde a regra 1 da §4 se rompe sem ninguém planejar: mensagem de
   exceção é exatamente o lugar por onde um CPF vaza. Se algum dia for ligado, tem de ser com a
   lista `include` restrita aos campos deste RFC.

**Consequência para quem for verificar localmente:** `docker compose` não tem coletor, então o
log não sai da máquina — e é assim que deve ser. A verificação local do schema se faz lendo o
`stdout` do container, onde a linha JSON está completa. O ambiente que reproduz o comportamento
de produção é o `kind` com a integração de Kubernetes instalada, não o compose.

### 6.5 Logger sob namespace configurado

Todo logger da aplicação vive sob um prefixo que `LOGGING` configura (`django` ou `atendimento`). Um logger de raiz própria propaga para a raiz, que não tem handler, e a linha **desaparece em silêncio** — modo de falha que não gera exceção, não aparece em teste que dubla o log, e só se percebe quando o painel está vazio.

## 7. Impacto

| Área | Mudança |
|---|---|
| `app/settings.py` | Bloco `LOGGING` com handler único de `stdout` e formatter JSON; `FileHandler` removido (D-06) |
| `app/observabilidade/logging.py` | Formatter, helper `cliente_ref` e resolução de trace |
| `app/observabilidade/middleware.py` | `CorrelationIdMiddleware`, primeiro item de `MIDDLEWARE` |
| `k8s/configmap.yaml` | `DJANGO_LOG_FILE` removido — letra morta após D-06 |
| Lambda e API Gateway | Requisitos L4, L5 e L6 de `requisitos-para-o-time.md` |

## 8. Alternativas Consideradas

| Alternativa | Por que não foi escolhida |
|---|---|
| **Manter log em texto e parsear na ingestão** | Regra de parsing quebra quando alguém muda a mensagem, e a quebra é silenciosa |
| **`python-json-logger`** | Dependência que não acrescenta nada para um schema fixo e pequeno |
| **Log em arquivo com sidecar coletor** | Contraria D-06, perde log no restart do pod e adiciona um container por pod |
| **Só `logfmt` em vez de JSON** | Mais legível no terminal, mas campos aninhados e listas ficam desconfortáveis e a plataforma escolhida ingere JSON nativamente |

## 9. Histórico de Revisões

| Versão | Data | Autor | Descrição |
|---|---|---|---|
| 1.0 | 2026-08-23 | Luís Fernando Montes | Versão inicial, formalizando o padrão de logs da frente de Observabilidade |
