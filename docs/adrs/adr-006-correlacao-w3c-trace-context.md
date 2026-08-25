# ADR-006 — Estratégia de Correlação entre Requisições

| Informação | Valor |
|---|---|
| **ADR** | 006 |
| **Título** | W3C Trace Context como Padrão de Correlação, com `X-Request-Id` de Negócio |
| **Status** | Aceito |
| **Autores** | Luís Fernando Montes (RM367183) |
| **Data** | 2026-08-23 |
| **Versão** | 1.1 |

---

## 1. Contexto

O enunciado da Fase 3 exige correlação entre requisições. A arquitetura tem dois fluxos distintos saindo do API Gateway — **não** uma cadeia única:

1. **Autenticação:** API Gateway → Lambda (valida CPF, emite JWT) → RDS
2. **Aplicação:** API Gateway → Django em EKS → RDS

Os dois são iniciados pelo cliente de forma independente. Correlacionar *dentro* de cada fluxo é o que o enunciado pede e é o que esta decisão resolve. Correlacionar *entre* os dois é um problema diferente, tratado na §9 abaixo.

A decisão precisa sobreviver à troca de plataforma de observabilidade, porque [ADR-005](adr-005-observabilidade-new-relic.md) escolheu um agente proprietário e assumiu lock-in parcial. Se a correlação também for proprietária, a migração futura fica inviável.

## 2. Decisão

**D-03 — Padrão de correlação:** **W3C Trace Context** (headers `traceparent` e `tracestate`) para o trace técnico, complementado por **`X-Request-Id`** como identificador de negócio.

A aplicação expõe um `CorrelationIdMiddleware`, registrado como **primeiro** item de `MIDDLEWARE`, que:

1. lê `traceparent` e `X-Request-Id` da requisição, gerando quando ausentes;
2. guarda ambos em `contextvars`, para o formatter de log injetar sem passar parâmetro;
3. devolve `X-Request-Id` no header da resposta, para o cliente citar num atendimento.

Chamadas HTTP saintes reinjetam `traceparent` e `tracestate`.

## 3. Justificativa

| Critério | Avaliação |
|---|---|
| **Padrão aberto** | Recomendação W3C, implementada por New Relic, Datadog, OTel, Jaeger e outros |
| **Sobrevive à troca de ferramenta** | Se [ADR-005](adr-005-observabilidade-new-relic.md) for revisto, os headers continuam válidos — o dado de correlação não é proprietário |
| **Suportado pelo agente escolhido** | O agente New Relic participa de W3C Trace Context nativamente, sem código de propagação |
| **Separação de responsabilidades** | `traceparent` é técnico e efêmero; `X-Request-Id` é de negócio, citável por um cliente ao telefone e estável na resposta HTTP |

### Por que dois identificadores, e não um

`traceparent` responde "que caminho esta requisição percorreu no sistema". `X-Request-Id` responde "qual foi aquela requisição que o cliente reclamou". São perguntas diferentes: a primeira é feita por quem depura, a segunda por quem atende. Devolver o `trace.id` ao cliente acoplaria o suporte ao formato interno de tracing, que muda com a ferramenta.

## 4. Consequências

### Positivas

- Trace completo dentro de cada fluxo, ligando borda, aplicação e banco.
- Log e trace correlacionados sem passar parâmetro por assinatura de função — o formatter lê os `contextvars`.
- A correlação não depende de New Relic, o que reduz o custo de reverter [ADR-005](adr-005-observabilidade-new-relic.md).

### Negativas

- Exige disciplina de propagação em toda chamada sainte nova; é fácil esquecer e o esquecimento **não gera erro**, só um trace partido.
- Depende de o API Gateway repassar `traceparent` recebido do cliente (requisito L3 de `requisitos-para-o-time.md`). Sem isso, cada componente inicia um trace próprio.

## 5. Duas armadilhas que custaram bug

Ambas foram encontradas na implementação e viraram teste de regressão. Ficam registradas porque nenhuma das duas produz erro visível — as duas produzem dado **silenciosamente errado**, que é o pior modo de falha para observabilidade.

### 5.1 O `span-id` recebido é do chamador, não nosso

Em W3C Trace Context, o `span-id` que chega no `traceparent` é o **parent-id**: identifica o span de quem chamou. Adotá-lo como `span.id` próprio faz todo log da requisição se apresentar como span alheio, e o `traceparent` propagado adiante declara o chamador como pai no lugar da aplicação.

**Regra:** o `trace-id` é herdado; o `span-id` é sempre gerado localmente. O recebido, quando útil, guarda-se como `parent_span_id`.

### 5.2 Sem agente, o span da borda não é o span corrente

Os `contextvars` do middleware conhecem apenas o span criado na borda da requisição. Com o agente New Relic ativo, ele abre spans internos que o middleware não vê — logar o span da borda quebraria o *logs in context* exatamente nos pontos mais interessantes.

**Regra:** o formatter prefere `newrelic.agent.get_linking_metadata()` quando o agente está presente, e cai para os `contextvars` quando não está. O import do agente é defensivo, para a aplicação subir e a suíte passar sem o pacote instalado.

## 6. Alternativas Consideradas

| Alternativa | Por que não foi escolhida |
|---|---|
| **Só o `X-Request-Id`** | Resolve o atendimento, não o trace: não descreve o caminho nem liga spans entre componentes |
| **Header proprietário do New Relic (`newrelic`)** | Funciona, mas amarra a correlação à plataforma — exatamente o que esta ADR existe para evitar |
| **Só `traceparent`, sem identificador de negócio** | Deixa o suporte sem um identificador estável para citar ao cliente, e acopla o atendimento ao formato de tracing |
| **B3 (Zipkin)** | Padrão anterior, ainda suportado por várias ferramentas, mas W3C é o sucessor formal e o que o agente escolhido usa por padrão |

## 7. Correlação **entre** os dois fluxos — `X-Correlation-Id`

O W3C Trace Context resolve a correlação **dentro** de cada fluxo. Ligar o fluxo de autenticação ao de aplicação é outro problema: os dois saem do API Gateway de forma independente, iniciados pelo cliente, e não há relação de causalidade que o `traceparent` pudesse expressar.

**Decisão, tomada pelo grupo em 2026-08-23:** um **`X-Correlation-Id` gerado pelo cliente**, reutilizado nas duas chamadas, validado e **devolvido** por Gateway, Lambda e aplicação. Recomendado pelo Hélio na revisão do PR #11 e acordado pelo Lucas, que responde pelo Gateway e pela Lambda.

Devolver o header não é detalhe: sem isso o cliente não tem como reusar o mesmo valor na segunda chamada quando ele próprio não o gerou, e o laço deixa de existir. É o requisito L9 de `requisitos-para-o-time.md`.

### Por que não a alternativa por `cliente.ref`

Derivar um identificador comum do hash do CPF pareceria mais simples — o valor já existe nos dois fluxos. Mas exigiria claim estável no JWT, canonicalização acordada entre componentes e um segredo compartilhado para que os hashes coincidissem. Mais superfície de acordo, mais lugares para divergir em silêncio, e ainda assim um identificador que **não distingue duas tentativas do mesmo cliente** — o caso mais comum numa investigação de suporte.

O `cliente.ref` mais janela de tempo permanece como laço fraco, para requisição que chegue sem o header. É de última instância, não substituto.

## 8. Histórico de Revisões

| Versão | Data | Autor | Descrição |
|---|---|---|---|
| 1.0 | 2026-08-23 | Luís Fernando Montes | Versão inicial, formalizando D-03 e registrando as duas armadilhas encontradas na implementação |
| 1.1 | 2026-08-23 | Luís Fernando Montes | §7 deixa de ser ponto em aberto: o grupo fechou no `X-Correlation-Id`, que vira o requisito L9 |
