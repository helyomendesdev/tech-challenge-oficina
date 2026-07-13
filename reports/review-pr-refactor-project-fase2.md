# Code Review — PR Fase 2: Clean/Hexagonal Architecture

**Data:** 2026-06-09
**Branch:** `refactor-project-correto` (commit `cafaf8e`)
**Repositorio:** helyomendesdev/tech-challenge-oficina
**Projeto:** FIAP Tech Challenge - Oficina (Fase 2)

---

## Resumo

| Item | Resultado |
|---|---|
| Arquivos alterados | 90 files |
| Insercoes / Remocoes | +8.940 / -476 |
| Testes | 194/194 passaram (0.92s) |
| Cobertura | ~78% |
| Veredito | **Aprovado com ressaltas** |

---

## Escopo do PR

Migracao da arquitetura monolitica Django para **Arquitetura Hexagonal** (Ports & Adapters / Clean Architecture) na app `atendimento/`.

### Estrutura criada

```
atendimento/
  domain/
    enums.py             -- StatusOS, TipoServico, TipoPessoa
    exceptions.py        -- 12 excecoes de negocio especificas
    value_objects.py     -- DocumentoCliente, PlacaVeiculo, Quantidade, Dinheiro
    services.py          -- OrcamentoDomainService, EstoqueDomainService
    policies.py          -- FinalizacaoOrdemServicoPolicy, OrdemServicoStatusPolicy

  application/
    dtos.py              -- DTOs de entrada/saida (frozen dataclasses)
    ports/               -- Contratos abstratos via Protocol
      cliente_repository.py, veiculo_repository.py, servico_repository.py,
      peca_repository.py, ordem_servico_repository.py (composto de 5 sub-portas),
      notification_port.py, transaction_manager.py
    use_cases/           -- 7 casos de uso (cada um com unica responsabilidade)
      abrir_ordem_servico.py, consultar_status_os.py, iniciar_servico.py,
      finalizar_servico.py, listar_fila_ordens_servico.py,
      processar_resposta_orcamento.py, atualizar_status_por_notificacao.py

  infrastructure/
    factories.py         -- Composicao raiz (DI)
    repositories/        -- Implementacoes Django ORM (5 repos)
    notifications/       -- FakeNotificationAdapter (spy para testes)
    transactions/        -- DjangoTransactionManager

  interfaces/
    api/                 -- Views, serializers, urls (novos)
```

---

## Resultado dos Testes

```
atendimento/tests/domain/test_policies.py ......                         [ 93%]
atendimento/tests/domain/test_services.py ....                           [ 95%]
atendimento/tests/domain/test_value_objects.py ........                  [100%]

============================= 194 passed in 0.92s ==============================
```

Testes de dominio usam `unittest.TestCase` puro (sem dependencia de framework).
Testes de integracao usam `APIClient` e cobrem happy path + erros + isolamento.

---

## Pontos Fortes

### 1. Arquitetura Hexagonal correta

A separacao fisica de diretorios e as regras de dependencia seguem fielmente o
padrao:

```
interfaces -> application -> domain
infrastructure -> application -> domain
```

Nenhum arquivo em `domain/` importa Django/DRF.
Nenhum arquivo em `application/` importa `infrastructure` ou `interfaces`.

### 2. Injecao de dependencia nos use cases

Todos os 7 use cases recebem ports via construtor:

```python
class AbrirOrdemServicoUseCase:
    def __init__(
        self,
        cliente_repository: ClienteRepositoryPort,
        veiculo_repository: VeiculoRepositoryPort,
        ordem_servico_repository: OrdemServicoEscritaPort,
        notification_port: NotificationPort,
        transaction_manager: TransactionManagerPort,
    ):
```

Isso torna cada use case testavel com mocks/stubs.

### 3. Value objects imutaveis e com validacao

`@dataclass(frozen=True)` em todos os 4 VOs, com validacao em `__post_init__`:

- `DocumentoCliente` — normaliza e valida CPF/CNPJ
- `PlacaVeiculo` — valida formato Mercosul (AAA1B11)
- `Quantidade` — rejeita zero, negativos, bool, float
- `Dinheiro` — `Decimal` nao negativo

### 4. Excecoes de negocio especificas

12 tipos de excecao, todas herdando de `DomainError(Exception)`.
Cada uma representa uma violacao de regra de negocio distinta:
`TransicaoStatusInvalidaError`, `EstoqueInsuficienteError`,
`OrcamentoNaoPodeSerProcessadoError`, etc.

### 5. Interface HTTP limpa

As novas views em `interfaces/api/views.py` sao finas:
validam request -> chamam use case -> retornam response.
Nenhuma logica de negocio. Tratamento de erro centralizado via
`handle_domain_error()`.

### 6. Traducao de erros ORM

Cada repositorio converte `DoesNotExist`, `IntegrityError`,
`ValidationError` do Django para excecoes de dominio, isolando
as camadas superiores do framework.

---

## Problemas Encontrados

### CRITICO: Logica de dominio nos Models Django

**Arquivo:** `atendimento/models.py`
**Severidade:** Alta

`OrdemServico` (linhas 109-268) e `ItemPecaOS` (linhas 278-353) contem
metodos de negocio que deveriam estar apenas nos use cases:

- `OrdemServico.iniciar_diagnostico()`, `.finalizar_diagnostico()`,
  `.aprovar_orcamento()`, `.recusar_orcamento()`, `.finalizar()`,
  `.entregar()`, `.cancelar()` — transicoes de status
- `OrdemServico.save()` — logica de timestamp + calculo de total
- `ItemPecaOS.save()` — movimentacao de estoque
- `ItemPecaOS.delete()` — devolucao de reserva ao estoque

O codigo contem `# TODO` comments reconhecendo que isso e temporario
para compatibilidade com os endpoints legados da Fase 1.

**Risco:** Regras de negocio em dois lugares (models + use cases) podem
divergir. Exemplo: `OrdemServico.finalizar()` valida condicoes primeiro
via ORM e depois chama as policies — validacao duplicada.

---

### CRITICO: Policy de dominio chamada no repositorio

**Arquivo:** `atendimento/infrastructure/repositories/django_ordem_servico_repository.py`
**Severidade:** Alta

O repositorio importa e executa policies de dominio diretamente:

```python
from atendimento.domain.policies import (
    FinalizacaoOrdemServicoPolicy,
    OrdemServicoStatusPolicy,
)
```

Chamado em:
- `save()` (linhas 179-186) — valida transicao de status
- `finalizar_ordem_servico()` (linhas 411-415) — valida finalizacao

Isso quebra o principio hexagonal: infraestrutura nao deve decidir/executar
regras de negocio. Trocar o repositorio (ex: para MongoDB) exigiria
reimplementar as policies.

**Solucao sugerida:** Mover `validar_finalizacao` para fora do repositorio.
O use case deve: (1) buscar dados via repository, (2) chamar a policy,
(3) persistir via repository.

---

### MEDIO: DTOs com tipos fracos

**Severidade:** Media

1. `IniciarServicoInputDTO.pecas: list[dict]` — acessado via chave string
   (`entrada["item_peca_os_id"]`). Sem type safety. Sugestao: criar
   `ConsumoPecaDTO` como dataclass tipado.

2. `IniciarServicoUseCase.execute()` retorna `Any` em vez de um DTO de saida.
3. `FinalizarServicoUseCase.execute()` retorna `Any` (o raw `item_servico`).

Os outros 5 use cases seguem o padrao correto de retornar `*OutputDTO`.

---

### MEDIO: Duplicacao de arquivo de teste legado

**Arquivo:** `atendimento/tests.py` (1.120 linhas, 15 classes)
**Severidade:** Media

Este arquivo contem os mesmos testes que os 11 arquivos refatorados em
`atendimento/tests/integration/`. Pode ser excluido com seguranca — as
classes sao identicas (mesmos nomes, mesmos cenarios). Enquanto existir,
causa confusao e risco de dupla execucao se a configuracao do pytest mudar.

---

### BAIXO: Porta com union type sub-otimo

**Arquivo:** `atendimento/application/use_cases/processar_resposta_orcamento.py`
**Severidade:** Baixa

`ordem_servico_repository` tipado como `OrdemServicoConsultaPort | OrdemServicoEscritaPort`
(union). O use case precisa de ambos os comportamentos simultaneamente,
entao o tipo correto seria `OrdemServicoRepositoryPort` (o composite).
A fabrica ja passa o composite, entao e so ajustar a anotacao.

---

### BAIXO: Construcao de DTO inconsistente

**Severidade:** Baixa

Views que usam `serializer.to_dto(**context)`:
- `AbrirOrdemServicoAPIView`
- `ProcessarRespostaOrcamentoAPIView`
- `AtualizarStatusPorNotificacaoAPIView`

Views que usam funcoes soltas em `serializers.py`:
- `ConsultarStatusOrdemServicoAPIView` -> `montar_consultar_status_dto()`
- `ListarFilaOrdensServicoAPIView` -> `montar_listar_fila_dto()`

O padrao `to_dto()` e mais limpo e consistente.

---

### BAIXO: Helpers duplicados em ingles/portugues

**Arquivo:** `atendimento/tests/helpers.py`
**Severidade:** Baixa

Funcoes que fazem a mesma coisa em ingles e portugues:
`create_user` / `criar_usuario`, `create_client` / `criar_cliente`, etc.
(8 wrappers). A funcao `authenticate_client()` tambem nao e usada
(0% cobertura).

---

## Itens Nao Incluidos (esperados para Fase 2)

Os seguintes itens estavam previstos para a Fase 2 mas nao fazem parte
deste PR:

- [ ] Manifestos Kubernetes em `k8s/`
- [ ] IaC (Terraform) em `infra/`
- [ ] CI/CD (GitHub Actions) em `.github/`
- [ ] Ordenacao de OS
- [ ] Aprovacao de orcamento externa

---

## Veredito Final

### Decisao: APROVADO COM RESSALVAS

O PR implementa a Arquitetura Hexagonal/Clean corretamente. A estrutura e
solida, os 194 testes passam, e a separacao de camadas esta bem executada
para uma migracao em andamento.

**Condicoes para aprovacao:**

1. Os `# TODO` nos models (logica de negocio convivendo com ORM) devem
   estar documentados no backlog para resolucao na Fase 3.

2. A duplicacao de chamada de policies no repositorio deve ser registrada
   como divida tecnica e priorizada na Fase 3.

**Sugestoes pos-merge:**

1. Excluir `atendimento/tests.py` (arquivo legado duplicado)
2. Adicionar DTOs de saida tipados para `IniciarServicoUseCase` e
   `FinalizarServicoUseCase`
3. Substituir `list[dict]` por `list[ConsumoPecaDTO]` em `IniciarServicoInputDTO`
4. Adicionar testes unitarios com ports mockados (seguindo o padrao
   `SpyNotificationAdapter` já existente)

---

*Review realizado por Hermes Agent em 2026-06-09*
