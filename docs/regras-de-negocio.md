# Regras de Negócio — Detalhamento

Este documento traz o detalhamento completo das regras de negócio da API. A visão resumida
(diagrama de estados e principais bullets) está no [`README.md`](../README.md#regras-de-negócio).

## Máquina de estados da Ordem de Serviço

O status da OS **não pode ser alterado via `PATCH`**. Cada transição é acionada por um endpoint
dedicado (`atendimento/models.py`, `atendimento/views.py`):

| Endpoint | Transição |
|---|---|
| `POST /api/v1/ordens-servico/{id}/iniciar-diagnostico/` | `RECEBIDA` → `DIAGNOSTICO` |
| `POST /api/v1/ordens-servico/{id}/finalizar-diagnostico/` | `DIAGNOSTICO` → `AGUARDANDO` |
| `POST /api/v1/ordens-servico/{id}/aprovar-orcamento/` | `AGUARDANDO` → `EXECUCAO` |
| `POST /api/v1/ordens-servico/{id}/recusar-orcamento/` | `AGUARDANDO` → `DIAGNOSTICO` |
| `POST /api/v1/ordens-servico/{id}/finalizar/` | `EXECUCAO` → `FINALIZADA` |
| `POST /api/v1/ordens-servico/{id}/entregar/` | `FINALIZADA` → `ENTREGUE` |
| `POST /api/v1/ordens-servico/{id}/cancelar/` | `AGUARDANDO` → `CANCELADA` |

Transições fora dessa lista são rejeitadas com `HTTP 400`.

## Validações de entrada

| Campo | Regra |
|---|---|
| `documento` (Cliente) | CPF válido (11 dígitos) ou CNPJ válido (14 dígitos), com validação de dígito verificador (`validate_documento`, `atendimento/models.py`) |
| `placa` (Veículo) | Formato antigo `ABC1234` ou Mercosul `ABC1D23` (regex `^[A-Z]{3}\d[A-Z\d]\d{2}$`, `validate_placa`) |
| `quantidade` (ItemPecaOS) | Não pode exceder o `estoque_atual` da peça |
| `status` (OrdemServico) | Apenas transições do fluxo definido são permitidas; campo é somente leitura no serializer |

## Automações

| Evento | Efeito automático |
|---|---|
| OS muda para `EXECUCAO` | `data_inicio_execucao` preenchida com o timestamp atual |
| OS muda para `FINALIZADA` | `data_finalizacao` preenchida com o timestamp atual |
| Peça **adicionada** a uma OS | `estoque_atual` decrementado; `valor_total` recalculado |
| Peça **atualizada** em uma OS | Diferença de quantidade ajustada no estoque; `valor_total` recalculado |
| Peça **removida** de uma OS | `estoque_atual` devolvido; `valor_total` recalculado |
| Serviço adicionado/removido de uma OS | `valor_total` da OS recalculado |
| **Serviço iniciado** (`/iniciar/`) | Permitido somente quando a OS está em `EXECUCAO`; status do serviço → `EM_EXECUCAO`; peças informadas são consumidas atomicamente sem nova baixa de estoque |
| **Serviço finalizado** (`/finalizar/`) | Status do serviço → `CONCLUIDO`; se for o último serviço ativo e todas as peças da OS foram consumidas, a OS avança automaticamente para `FINALIZADA` |

## Gates de finalização

| Condição bloqueante | HTTP |
|---|---|
| Tentar avançar OS para `FINALIZADA` via `PATCH` com serviços não concluídos | `400` |
| Tentar avançar OS para `FINALIZADA` via `PATCH` com peças não consumidas | `400` |
| Chamar `/finalizar/` em serviço que não está `EM_EXECUCAO` | `400` |
| Último serviço tenta finalizar mas há peças não consumidas na OS | `400` |

## Cálculo do valor total

```
valor_total = Σ(servicos.valor_mao_de_obra) + Σ(itens_pecas.peca.valor_unitario × quantidade)
```

## Isolamento por usuário (OWASP A01)

`OwnedQuerySetMixin` (`atendimento/views.py`) filtra o queryset de cada ViewSet:

- Usuários staff/superuser enxergam todos os registros.
- Usuários comuns (funcionários) só enxergam o que criaram (`created_by`).
- Cliente JWT (`ClientPrincipal`) só enxerga veículos e OS do próprio `cliente_id`, e só pode
  usar as actions listadas em `cliente_jwt_allowed_actions` de cada ViewSet — qualquer outra
  action (criar cliente, editar veículo, transicionar status etc.) recebe `403`.

## Simulação de aprovação/recusa de orçamento

Um simulador representa um sistema externo responsável por aprovar ou recusar um orçamento,
para demonstrar uma integração real via HTTP (diferente do `FakeNotificationAdapter` usado nos
fluxos internos):

```
Cliente
  → POST /api/v1/simulacao/orcamento/         (SimuladorOrcamentoService)
  → POST /api/v1/orcamentos/notificacoes/     (ProcessarRespostaOrcamentoUseCase)
```

- `/api/v1/simulacao/orcamento/`: simula o sistema externo.
- `/api/v1/orcamentos/notificacoes/`: recebe a notificação e processa a mudança de status.
- O simulador reutiliza o token JWT da requisição original para autenticar a chamada ao webhook
  interno, reproduzindo uma integração protegida.
- `WEBHOOK_ORCAMENTO_URL`: URL usada pelo simulador para notificar. Em desenvolvimento o padrão é
  `http://localhost:8000/api/v1/orcamentos/notificacoes/`; em Docker Compose, Kubernetes ou
  produção, configure para o endereço real da API (ver
  [`docs/variaveis-de-ambiente.md`](variaveis-de-ambiente.md)).

## Rate limiting

| Tipo de acesso | Limite |
|---|---|
| Usuários autenticados | 600 requisições/hora |
| Acessos anônimos (geral) | 60 requisições/hora |
| Endpoint público `/consulta-cliente` | 30 requisições/hora por IP |

Ao exceder o limite, a API retorna `HTTP 429 Too Many Requests`.
