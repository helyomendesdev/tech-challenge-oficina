# RFC-001 — Máquina de Estados da Ordem de Serviço

| Informação | Valor |
|---|---|
| **RFC** | 001 |
| **Título** | Máquina de Estados da Ordem de Serviço (OS) |
| **Status** | Aprovado |
| **Autores** | Afonso Victoriano Franco (RM373563), Hélio Mendes da Silva (RM374170), João Pedro Rodrigues Martins (RM372818), Luís Fernando Montes (RM367183), Sophia Sussa Campos Bastos (RM371864) |
| **Data** | 2026-04-28 |
| **Versão** | 1.0 |

---

## 1. Resumo

Este documento especifica o ciclo de vida completo da **Ordem de Serviço (OS)**, incluindo seus estados, transições permitidas, gates de finalização e o ciclo independente de execução dos serviços vinculados.

---

## 2. Motivação

Uma oficina mecânica precisa rastrear o progresso de cada atendimento desde o recebimento do veículo até a entrega ao cliente. Sem uma máquina de estados formal, corre-se o risco de:
- Transições inválidas (ex: entregar sem finalizar)
- Perda de rastreabilidade do tempo de execução
- Cobrança incorreta por serviços não concluídos

---

## 3. Estados da OS

```
RECEBIDA → DIAGNOSTICO → AGUARDANDO → EXECUCAO → FINALIZADA → ENTREGUE
```

| Estado | Descrição |
|---|---|
| `RECEBIDA` | Veículo chegou à oficina; OS aberta |
| `DIAGNOSTICO` | Mecânico está avaliando o problema |
| `AGUARDANDO` | Aguardando aprovação do orçamento pelo cliente |
| `EXECUCAO` | Serviços estão sendo executados |
| `FINALIZADA` | Todos os serviços concluídos e peças consumidas |
| `ENTREGUE` | Veículo devolvido ao cliente |

---

## 4. Transições Válidas

| Estado Atual | Próximos Estados Permitidos |
|---|---|
| `RECEBIDA` | `DIAGNOSTICO` |
| `DIAGNOSTICO` | `AGUARDANDO` |
| `AGUARDANDO` | `EXECUCAO` |
| `EXECUCAO` | `FINALIZADA` |
| `FINALIZADA` | `ENTREGUE` |
| `ENTREGUE` | *(nenhum — estado final)* |

> Transições fora deste fluxo são **rejeitadas com HTTP 400 Bad Request**.

---

## 5. Gates de Finalização

Para que uma OS avance para `FINALIZADA`, os seguintes gates devem ser satisfeitos:

1. **Todos os serviços vinculados à OS devem estar com status `CONCLUIDO`**
2. **Todas as peças alocadas na OS devem ter sido consumidas** (`quantidade_utilizada == quantidade`)

Se qualquer gate não for satisfeito, a API retorna:

```json
{
  "erro": true,
  "status_code": 400,
  "mensagem": "Erro de validação. Verifique os campos informados.",
  "campos": {
    "status": "Não é possível finalizar a OS: existem serviços não concluídos."
  }
}
```

---

## 6. Estados dos Serviços por OS

Cada serviço adicionado a uma OS possui seu próprio ciclo de vida:

```
PENDENTE → EM_EXECUCAO → CONCLUIDO
```

| Estado | Descrição |
|---|---|
| `PENDENTE` | Serviço agendado, ainda não iniciado |
| `EM_EXECUCAO` | Serviço em andamento; `data_inicio` preenchida |
| `CONCLUIDO` | Serviço finalizado; `data_finalizacao` preenchida |

### 6.1 Transição para EM_EXECUCAO
- Endpoint: `POST /api/v1/ordens-servico/{os_id}/servicos/{id}/iniciar/`
- Efeitos:
  - Status do serviço → `EM_EXECUCAO`
  - `data_inicio` preenchida com timestamp atual (ou informado)
  - Peças informadas são consumidas atomicamente (cria registros em `ConsumoItemServico`)
  - Se for o primeiro serviço a iniciar em OS `AGUARDANDO`, a OS avança automaticamente para `EXECUCAO`

### 6.2 Transição para CONCLUIDO
- Endpoint: `POST /api/v1/ordens-servico/{os_id}/servicos/{id}/finalizar/`
- Efeitos:
  - Status do serviço → `CONCLUIDO`
  - `data_finalizacao` preenchida com timestamp atual (ou informado)
  - Calcula `tempo_execucao_minutos = data_finalizacao - data_inicio`
  - Se for o último serviço ativo e todas as peças foram consumidas, a OS avança automaticamente para `FINALIZADA`

### 6.3 Regras de Negócio
- Um serviço só pode ser finalizado se estiver `EM_EXECUCAO`
- Um serviço em `EM_EXECUCAO` ou `CONCLUIDO` **não pode ser removido** da OS
- Serviços `PENDENTE` podem ser removidos normalmente

---

## 7. Datas Automáticas

| Evento | Campo | Comportamento |
|---|---|---|
| OS muda para `EXECUCAO` | `data_inicio_execucao` | Auto-preenchido com `timezone.now()` |
| OS muda para `FINALIZADA` | `data_finalizacao` | Auto-preenchido com `timezone.now()` |
| Serviço inicia | `data_inicio` | Auto-preenchido (ou aceita valor do payload) |
| Serviço finaliza | `data_finalizacao` | Auto-preenchido (ou aceita valor do payload) |

---

## 8. Decisões de Design

| Decisão | Justificativa |
|---|---|
| Estados definidos como `CharField` com `choices` | Simplicidade, validação nativa do Django ORM, fácil manutenção |
| Validação de transição no Serializer | Centraliza regras de negócio na camada de serialização, reutilizável por qualquer view |
| Gates de finalização no Serializer | Garante consistência transacional independente do canal de entrada (API, admin, etc.) |
| Cascade automático OS → EXECUCAO no primeiro serviço | Reduz passos manuais do mecânico; se há trabalho, a OS está em execução |
| Cascade automático OS → FINALIZADA no último serviço | Garante que a OS não fique pendente após todos os serviços concluídos |

---

## 9. Histórico de Revisões

| Versão | Data | Autor | Descrição |
|---|---|---|---|
| 1.0 | 2026-04-28 | Afonso Victoriano Franco, Hélio Mendes da Silva, João Pedro Rodrigues Martins, Luís Fernando Montes, Sophia Sussa Campos Bastos | Versão inicial aprovada |
