# ADR-006 — Ferramenta e Estratégia de Instrumentação de Observabilidade

| Informação | Valor |
|---|---|
| **ADR** | 005 |
| **Título** | New Relic como Plataforma de Observabilidade, com Agente Nativo |
| **Status** | Aceito |
| **Autores** | Luís Fernando Montes (RM367183) |
| **Data** | 2026-08-23 |
| **Versão** | 1.0 |

---

## 1. Contexto

A Fase 3 exige monitoramento do ambiente em nuvem com três dashboards obrigatórios — volume diário de ordens de serviço, tempo médio de execução por status e erros nas integrações — além de latência das APIs, consumo de recursos do Kubernetes e correlação entre requisições.

Três restrições moldam a decisão, e nenhuma delas é técnica:

- **Orçamento zero.** O ambiente roda em AWS Academy, com teto de US$ 50/mês já comprometido com RDS e EKS. Não há verba para licença de observabilidade.
- **Prazo em 05/09/2026.** Qualquer ferramenta cujo período gratuito expire antes disso inviabiliza a gravação do vídeo de entrega.
- **Ambiente efêmero.** O cluster sobe e desce para caber no orçamento, então não há histórico orgânico — a plataforma precisa aceitar ingestão de tráfego sintético sem custo adicional.

A arquitetura tem quatro componentes a instrumentar: aplicação Django em EKS, Lambda de autenticação, API Gateway e RDS PostgreSQL.

## 2. Decisão

Duas decisões acopladas, registradas juntas porque a segunda só faz sentido dada a primeira:

- **D-01 — Plataforma:** **New Relic**.
- **D-02 — Estratégia de instrumentação:** **agente nativo** — agente Python na aplicação, New Relic Lambda Layer na function, `nri-bundle` no cluster e integração AWS para RDS e API Gateway.

## 3. Justificativa

### Por que New Relic (D-01)

| Critério | Avaliação |
|---|---|
| **Custo** | Free tier de 100 GB/mês **perpétuo**, 1 usuário full-platform, sem cartão de crédito |
| **Prazo** | Sem data de expiração — o Datadog oferece 14 dias, que vencem antes de 05/09 |
| **Cobertura** | APM, logs, infraestrutura, Kubernetes, Lambda e Synthetics na mesma conta |
| **Volume** | 100 GB/mês é folgado para um ambiente que sobe por horas, mesmo com tráfego sintético |

### Por que agente nativo (D-02)

| Critério | Avaliação |
|---|---|
| **Esforço** | Auto-instrumenta Django, DRF e psycopg2 sem código de aplicação |
| **Logs in context** | O agente correlaciona log e trace automaticamente, via `get_linking_metadata()` |
| **Tracing distribuído** | Suporte a W3C Trace Context pronto, o que preserva a decisão de correlação (ver [ADR-007](adr-007-correlacao-w3c-trace-context.md)) |
| **Kubernetes** | `nri-bundle` entrega CPU, memória, HPA e reinícios por pod sem instrumentar nada |
| **Risco de prazo** | Menor caminho até dashboard com dado real, que é o critério de entrega |

## 4. Consequências

### Positivas

- Custo zero e sem prazo de validade, o que remove a ferramenta da lista de riscos da entrega.
- Métricas técnicas (latência por rota, tempo em banco, saturação de pod) chegam **sem código** — o esforço da frente concentra-se no que só a aplicação sabe: os eventos de negócio (ver [ADR-007](adr-007-correlacao-w3c-trace-context.md) e a §5.4 da especificação).
- Um só painel para os quatro componentes, o que viabiliza a cena de trace ponta a ponta no vídeo.

### Negativas

- **Vendor lock-in parcial.** O agente é proprietário: trocar de plataforma exige reinstrumentar. A mitigação é a decisão de correlação, que é padrão aberto — ver [ADR-007](adr-007-correlacao-w3c-trace-context.md).
- **Um usuário só.** O free tier dá uma conta full-platform; o restante do grupo vê os dashboards por compartilhamento, não com login próprio.
- **Teto de 100 GB.** Tráfego sintético em volume alto pode aproximar-se do limite. Mitigado rodando o gerador de carga contra homologação e por janelas curtas.
- **A imagem passa a conhecer o agente.** Tratado no [RFC-004](../rfcs/rfc-004-logs-estruturados-json.md) e resolvido com wrapper condicional, para não exigir credencial de quem roda o projeto localmente.

## 5. Alternativas Consideradas

| Alternativa | Por que não foi escolhida |
|---|---|
| **Datadog** | Trial de 14 dias, que expira antes da entrega de 05/09. Tecnicamente equivalente; o impedimento é de prazo, não de capacidade. |
| **Grafana Cloud (free tier)** | Free tier perpétuo e boa stack, mas APM Python é menos maduro e a correlação log↔trace exige mais montagem manual. Custaria prazo. |
| **OpenTelemetry puro + backend próprio** | Portabilidade máxima e sem lock-in, mas exige instrumentação manual de propagação em cada componente e subir/manter o backend. Risco de prazo incompatível com 05/09, e o backend consumiria o orçamento de AWS reservado para RDS e EKS. |
| **Prometheus + Grafana auto-hospedados no EKS** | Sem custo de licença, mas consome recursos do próprio cluster que se quer medir, não cobre APM nem trace distribuído sem componentes adicionais (Tempo, Loki), e a operação disso é uma frente inteira por si só. |
| **Amazon CloudWatch** | Já existe na conta e cobre Lambda e API Gateway bem, mas trace distribuído exige X-Ray, o custo sai do mesmo teto de US$ 50, e os dashboards de negócio exigidos pelo enunciado ficariam pobres. |

## 6. Histórico de Revisões

| Versão | Data | Autor | Descrição |
|---|---|---|---|
| 1.0 | 2026-08-23 | Luís Fernando Montes | Versão inicial, formalizando D-01 e D-02 da especificação da frente de Observabilidade |
