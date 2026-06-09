# Monolito Modular Django com Clean/Hexagonal Pragmática — Fase 2

## 1. Visão Geral

Na Fase 2, a API da oficina mecânica evolui de um monolito Django/DRF tradicional para um **monolito modular Django com Clean Architecture/Arquitetura Hexagonal pragmática e DDD tático**.

O objetivo é preservar a compatibilidade com os endpoints, models e migrations existentes, enquanto os novos fluxos passam a ser organizados em camadas com responsabilidades mais claras. Esta não é uma Clean Architecture pura: Django, DRF, ModelSerializers e ViewSets legados seguem ativos para manter o projeto funcional e compatível.

## 1.1 Decisão Incremental

- `atendimento/models.py` permanece por compatibilidade com migrations, Django Admin, serializers antigos, endpoints da Fase 1 e testes existentes.
- Os fluxos críticos da Fase 2 foram migrados para use cases, DTOs, ports, repositories e APIViews finas.
- Algumas regras legadas permanecem temporariamente em `models.py`, `signals.py`, ModelSerializers antigos e ViewSets antigos.
- Essa combinação é uma decisão consciente de refatoração incremental, não uma falha arquitetural.

## 2. Diagrama Textual das Camadas

```text
HTTP / JSON / JWT
      |
      v
atendimento.interfaces.api
  - APIViews
  - serializers DRF
  - urls
      |
      v
atendimento.application
  - use cases
  - DTOs
  - ports segregados por responsabilidade
      |
      v
atendimento.domain
  - enums
  - policies
  - exceptions
  - value objects
  - services puros
      ^
      |
atendimento.infrastructure
  - repositories Django ORM
  - transaction manager
  - notification adapters
      |
      v
Django ORM -> PostgreSQL
```

## 3. Responsabilidade de Cada Camada

| Camada | Responsabilidade |
|---|---|
| `domain` | Concentrar regras de negócio puras, linguagem do domínio, enums, policies, exceptions e value objects. Não importa Django nem DRF. |
| `application` | Orquestrar fluxos com use cases, DTOs e ports. Não conhece HTTP, serializers DRF nem `Model.objects`. |
| `infrastructure` | Implementar ports usando Django ORM, transações e adapters técnicos, convertendo erros técnicos em erros de domínio/aplicação. |
| `interfaces` | Receber requests HTTP via DRF, validar formato com serializers, montar DTOs, chamar use cases e retornar responses. |

Os ports principais ficam em `atendimento/application/ports/`; os adapters concretos ficam em
`atendimento/infrastructure/repositories/`, `transactions/` e `notifications/`.
As rotas HTTP novas ficam isoladas em `atendimento/interfaces/api/`.

## 4. Fluxo de Requisição

```text
HTTP
  -> Interface DRF
  -> Serializer valida formato e normalizações simples
  -> DTO de entrada
  -> Use Case
  -> Port
  -> Repository concreto
  -> Django ORM
  -> Banco de dados
```

Exemplo no fluxo de abertura completa de OS:

```text
POST /api/v1/ordens-servico/abrir/
  -> AbrirOrdemServicoAPIView
  -> AbrirOrdemServicoInputSerializer
  -> AbrirOrdemServicoInputDTO
  -> AbrirOrdemServicoUseCase
  -> ClienteRepositoryPort / VeiculoRepositoryPort / OrdemServicoRepositoryPort
  -> DjangoClienteRepository / DjangoVeiculoRepository / DjangoOrdemServicoRepository
  -> Models Django
  -> PostgreSQL
```

## 5. Mapeamento dos Principais Use Cases

| Use case | Responsabilidade |
|---|---|
| `AbrirOrdemServicoUseCase` | Abrir OS completa, criando ou reutilizando cliente/veículo, adicionando serviços e peças, recalculando total e preservando a regra de estoque atual. |
| `ConsultarStatusOrdemServicoUseCase` | Consultar status da OS respeitando isolamento por usuário e acesso staff. |
| `ListarFilaOrdensServicoUseCase` | Listar fila operacional com ordenação por prioridade de status e data de abertura. |
| `ProcessarRespostaOrcamentoUseCase` | Processar aprovação ou recusa externa simulada de orçamento. |
| `AtualizarStatusPorNotificacaoUseCase` | Atualizar status por notificação simulada, validando transições e regras de finalização. |
| `IniciarServicoUseCase` | Iniciar item de serviço da OS, registrar consumo de peças e validar saldo disponível. |
| `FinalizarServicoUseCase` | Finalizar item de serviço e, quando possível, finalizar a OS respeitando serviços concluídos e peças utilizadas. |

## 5.1 Endpoints Novos da Fase 2

| Método | Endpoint | Use case |
|---|---|---|
| `POST` | `/api/v1/ordens-servico/abrir/` | `AbrirOrdemServicoUseCase` |
| `GET` | `/api/v1/ordens-servico/{id}/status/` | `ConsultarStatusOrdemServicoUseCase` |
| `GET` | `/api/v1/ordens-servico/fila/` | `ListarFilaOrdensServicoUseCase` |
| `POST` | `/api/v1/orcamentos/notificacoes/` | `ProcessarRespostaOrcamentoUseCase` |
| `POST` | `/api/v1/ordens-servico/status-notificacoes/` | `AtualizarStatusPorNotificacaoUseCase` |

## 6. Como DDD Aparece no Código

- **Linguagem ubíqua:** nomes como `OrdemServico`, `Servico`, `Peca`, `Diagnostico`, `Orcamento`, `Fila`, `Recebida`, `Execucao` e `Finalizada` aparecem no código e nos endpoints.
- **Agregado principal:** `OrdemServico` atua como agregado central do fluxo operacional, agregando serviços, peças, status, datas e valor total.
- **Status como enums:** `StatusOrdemServico`, `StatusItemServico` e `DecisaoOrcamento` reduzem strings soltas e tornam as transições explícitas.
- **Policies de domínio:** `OrdemServicoStatusPolicy`, `FilaOrdemServicoPolicy` e `FinalizacaoOrdemServicoPolicy` concentram regras de transição, fila e finalização.
- **Value Objects:** `DocumentoCliente`, `PlacaVeiculo`, `Quantidade` e `Dinheiro` validam e normalizam conceitos pequenos do domínio sem depender de framework.

## 7. Pontos Legados Mantidos Temporariamente

- `models.py` permanece na raiz do app `atendimento` para preservar migrations, admin, serializers antigos, endpoints da Fase 1 e testes existentes.
- Algumas regras continuam temporariamente em models por compatibilidade com fluxos antigos.
- `ItemPecaOS.save()` e `ItemPecaOS.delete()` ainda são a fonte de verdade da baixa/devolução de estoque para evitar quebra nos endpoints legados.
- `signals.py` foi mantido sem baixa de estoque para evitar duplo débito; o signal de M2M permanece junto ao model para compatibilidade do fluxo legado.
- ModelSerializers e ViewSets antigos continuam ativos para não quebrar contratos públicos da Fase 1.
- Essa permanência é intencional: a migração completa para entidades puras, mappers e use cases em todos os fluxos pode ser feita em etapas futuras.

## 8. Validação Atual

- `python manage.py check --settings=app.settings_test`: sem issues.
- `python manage.py spectacular --settings=app.settings_test --file schema.yml --validate`: 0 erros; 2 warnings não bloqueantes de enum `status`.
- `python -m pytest --cov=atendimento --cov-report=term-missing`: 194 testes passando, 3 subtests passando, 94% de cobertura.

## 9. Próximas Evoluções Possíveis

- Migrar gradualmente regras restantes dos models para use cases, policies e services de domínio.
- Migrar actions antigas de ViewSets para use cases.
- Reduzir signals à medida que os fluxos de escrita forem centralizados na aplicação.
- Mover cálculo de orçamento e controle de estoque para services/use cases quando a compatibilidade legada permitir.
- Introduzir entities puras e mappers entre domínio e persistência quando o ganho justificar a complexidade.
- Evoluir adapters de notificação simulados para integração real por e-mail, webhook ou fila.
- Expandir testes unitários de domínio e aplicação, mantendo testes de integração para contratos HTTP.
- Reorganizar ports se o crescimento do projeto tornar os contratos grandes demais.
- Avaliar separação futura de módulos ou bounded contexts caso o domínio cresça.
