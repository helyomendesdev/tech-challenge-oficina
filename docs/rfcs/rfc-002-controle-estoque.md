# RFC-002 — Controle de Estoque e Consumo de Peças

| Informação | Valor |
|---|---|
| **RFC** | 002 |
| **Título** | Controle de Estoque e Consumo de Peças por Serviço |
| **Status** | Aprovado |
| **Autores** | Afonso Victoriano Franco (RM373563), Hélio Mendes da Silva (RM374170), João Pedro Rodrigues Martins (RM372818), Luís Fernando Montes (RM367183), Sophia Sussa Campos Bastos (RM371864) |
| **Data** | 2026-04-28 |
| **Versão** | 1.0 |

---

## 1. Resumo

Este documento especifica o comportamento do controle de estoque de peças, incluindo baixa automática na alocação à OS, devolução na remoção, consumo atômico por serviço e cálculo automático do valor total.

---

## 2. Motivação

Em uma oficina mecânica, o estoque de peças é um ativo crítico. É necessário garantir:
- Rastreabilidade de cada peça (onde foi usada, em qual serviço)
- Impedimento de venda de peças sem estoque suficiente
- Cálculo preciso do custo de cada OS

---

## 3. Fluxo de Estoque

### 3.1 Alocação de Peças à OS

Quando uma peça é adicionada a uma OS (`ItemPecaOS`):

1. Valida se `peca.estoque_atual >= quantidade`
2. Se sim: decrementa o estoque da peça em `quantidade`
3. Cria o registro `ItemPecaOS` com `quantidade_utilizada = 0`
4. Recalcula o `valor_total` da OS

```python
# Pseudocódigo
if peca.estoque_atual < quantidade:
    raise EstoqueInsuficiente()
peca.estoque_atual -= quantidade
peca.save()
```

### 3.2 Atualização de Quantidade

Quando a quantidade de uma peça na OS é alterada:

1. Calcula `diferenca = nova_quantidade - quantidade_anterior`
2. Se `diferenca > 0`: valida se há estoque suficiente para o incremento
3. Se `diferenca < 0`: devolve a diferença ao estoque
4. Recalcula o `valor_total` da OS

### 3.3 Remoção de Peça da OS

Quando uma peça é removida da OS:

1. Devolve `quantidade` inteira ao `peca.estoque_atual`
2. Remove o registro `ItemPecaOS`
3. Recalcula o `valor_total` da OS

### 3.4 Consumo por Serviço

Quando um serviço é iniciado (`/iniciar/`), o mecânico informa quais peças serão consumidas:

```json
{
  "data_inicio": "2026-04-28T10:00:00Z",
  "pecas": [
    {"item_peca_os_id": 1, "quantidade": 2},
    {"item_peca_os_id": 2, "quantidade": 1}
  ]
}
```

1. Valida se cada `item_peca_os_id` pertence à OS
2. Valida se `quantidade <= (ItemPecaOS.quantidade - ItemPecaOS.quantidade_utilizada)`
3. Cria registros em `ConsumoItemServico`
4. Incrementa `ItemPecaOS.quantidade_utilizada`
5. Tudo ocorre em uma transação atômica (all-or-nothing)

---

## 4. Modelo de Dados

```
Peca
├── nome
├── valor_unitario
└── estoque_atual

ItemPecaOS
├── os (FK OrdemServico)
├── peca (FK Peca)
├── quantidade          # quantidade alocada na OS
└── quantidade_utilizada # quantidade já consumida por serviços

ConsumoItemServico
├── item_servico_os (FK ItemServicoOS)
├── item_peca_os (FK ItemPecaOS)
└── quantidade          # quantidade consumida neste serviço específico
```

---

## 5. Regras de Negócio

| ID | Regra | Implementação |
|---|---|---|
| R1 | Não é possível alocar mais peças do que o estoque disponível | Validação em `ItemPecaOS.save()` e `ItemPecaOSSerializer.validate()` |
| R2 | Não é possível consumir mais peças do que alocadas | Validação em `ConsumoItemServico` (quantidade <= saldo) |
| R3 | Uma peça consumida por um serviço não pode ser "desconsumida" individualmente | Restrição de negócio; remoção do serviço só é permitida em `PENDENTE` |
| R4 | A OS só pode ser finalizada se `quantidade_utilizada == quantidade` para todas as peças | Gate em `OrdemServicoSerializer.validate_status()` |
| R5 | A remoção de uma peça da OS devolve todo o estoque alocado | `ItemPecaOS.delete()` incrementa `peca.estoque_atual` |

---

## 6. Cálculo do Valor Total da OS

```
valor_total = Σ(servicos.valor_mao_de_obra) + Σ(itens_pecas.peca.valor_unitario × quantidade)
```

O recálculo ocorre automaticamente via:
- `OrdemServico.save()` (ao criar/atualizar OS)
- `ItemPecaOS.save()` e `ItemPecaOS.delete()` (baixa/devolução)
- `post_save` e `post_delete` signals de `ItemServicoOS` (adição/remoção de serviços)

A persistência usa `OrdemServico.objects.filter(pk=self.pk).update(valor_total=novo_total)` para **evitar recursão**.

---

## 7. Decisões de Design

| Decisão | Justificativa |
|---|---|
| Baixa no `save()` do modelo | Garante consistência independente do canal (API, admin, script) |
| `quantidade_utilizada` separada de `quantidade` | Permite alocar peças na OS e consumir gradualmente por serviço |
| Tabela `ConsumoItemServico` (N:N com payload) | Rastreabilidade completa: qual peça foi usada em qual serviço |
| Transação atômica no consumo | Evita estado inconsistente se uma peça falhar |
| Recálculo via `.update()` | Evita recursão infinita de signals |

---

## 8. Histórico de Revisões

| Versão | Data | Autor | Descrição |
|---|---|---|---|
| 1.0 | 2026-04-28 | Afonso Victoriano Franco, Hélio Mendes da Silva, João Pedro Rodrigues Martins, Luís Fernando Montes, Sophia Sussa Campos Bastos | Versão inicial aprovada |
