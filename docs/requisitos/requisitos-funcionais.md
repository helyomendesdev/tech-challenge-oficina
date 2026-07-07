# Requisitos Funcionais — Oficina Mecânica API

| Informação | Valor |
|---|---|
| **Documento** | Requisitos Funcionais |
| **Versão** | 1.0 |
| **Data** | 2026-04-28 |
| **Autores** | Afonso Victoriano Franco (RM373563), Hélio Mendes da Silva (RM374170), João Pedro Rodrigues Martins (RM372818), Luís Fernando Montes (RM367183), Sophia Sussa Campos Bastos (RM371864) |

---

## 1. Introdução

Este documento descreve os requisitos funcionais do sistema de gerenciamento de oficina mecânica, organizados por domínio e prioridade.

---

## 2. Clientes

### RF001 — Cadastro de Cliente (PF/PJ)
**Prioridade:** Alta

O sistema deve permitir o cadastro de clientes pessoa física (CPF) ou jurídica (CNPJ), validando o dígito verificador do documento. Não deve permitir documentos duplicados.

**Critérios de Aceitação:**
- CPF deve ter 11 dígitos e ser matematicamente válido
- CNPJ deve ter 14 dígitos e ser matematicamente válido
- Documento duplicado deve ser rejeitado com erro estruturado
- Email deve ter formato válido

### RF002 — Consulta de Clientes
**Prioridade:** Alta

O sistema deve permitir listar e buscar clientes com filtros por nome (parcial), documento (exato) e busca geral (nome, documento, email).

---

## 3. Veículos

### RF003 — Cadastro de Veículo
**Prioridade:** Alta

O sistema deve permitir o cadastro de veículos vinculados a um cliente, validando a placa nos formatos antigo (`ABC1234`) e Mercosul (`ABC1D23`).

**Critérios de Aceitação:**
- Placa deve ser única no sistema
- Placa deve ser normalizada para maiúsculas
- Veículo deve estar obrigatoriamente vinculado a um cliente existente

### RF004 — Consulta de Veículos
**Prioridade:** Média

O sistema deve permitir listar veículos com paginação.

---

## 4. Catálogo

### RF005 — Cadastro de Serviços
**Prioridade:** Alta

O sistema deve permitir o cadastro de serviços (mão de obra) com descrição e valor.

### RF006 — Cadastro de Peças
**Prioridade:** Alta

O sistema deve permitir o cadastro de peças com nome, valor unitário e quantidade em estoque.

### RF007 — Consulta de Peças com Estoque
**Prioridade:** Média

O sistema deve listar peças com saldo de estoque atual, permitindo filtros por nome, estoque mínimo e peças zeradas.

---

## 5. Ordens de Serviço (OS)

### RF008 — Abertura de OS
**Prioridade:** Alta

O sistema deve permitir a abertura de uma Ordem de Serviço vinculando um cliente e um veículo. O status inicial deve ser `RECEBIDA`.

### RF009 — Acompanhamento de Status da OS
**Prioridade:** Alta

O sistema deve permitir avançar o status da OS seguindo o fluxo válido: `RECEBIDA → DIAGNOSTICO → AGUARDANDO → EXECUCAO → FINALIZADA → ENTREGUE`.

**Critérios de Aceitação:**
- Transições inválidas devem ser rejeitadas
- Avanço para `EXECUCAO` ocorre após aprovação do orçamento
- Avanço para `FINALIZADA` exige todos os serviços concluídos e peças consumidas

### RF010 — Cálculo Automático do Valor Total
**Prioridade:** Alta

O sistema deve calcular e atualizar automaticamente o valor total da OS:

```
valor_total = Σ(servicos.valor_mao_de_obra) + Σ(pecas.valor_unitario × quantidade)
```

### RF011 — Consulta Pública de OS
**Prioridade:** Alta

O sistema deve fornecer um endpoint público (sem autenticação) para que o cliente consulte o status da OS pela placa do veículo ou pelo CPF/CNPJ.

---

## 6. Serviços por OS

### RF012 — Adicionar Serviços à OS
**Prioridade:** Alta

O sistema deve permitir adicionar serviços do catálogo a uma OS. Cada serviço adicionado inicia com status `PENDENTE`.

### RF013 — Iniciar e Finalizar Serviços
**Prioridade:** Alta

O sistema deve permitir iniciar e finalizar a execução de cada serviço individualmente, registrando data/hora de início e fim.

**Critérios de Aceitação:**
- Iniciar um serviço exige que a OS esteja em `EXECUCAO` e muda o serviço para `EM_EXECUCAO`
- Finalizar um serviço muda seu status para `CONCLUIDO`
- Tempo de execução deve ser calculado automaticamente
- Um serviço só pode ser finalizado se estiver `EM_EXECUCAO`

### RF014 — Remover Serviços da OS
**Prioridade:** Média

O sistema deve permitir remover serviços `PENDENTE` de uma OS. Serviços em execução ou concluídos não podem ser removidos.

---

## 7. Peças por OS

### RF015 — Alocar Peças à OS
**Prioridade:** Alta

O sistema deve permitir alocar peças a uma OS, debitando automaticamente do estoque.

**Critérios de Aceitação:**
- Não deve permitir alocar mais peças do que o estoque disponível
- Deve recalcular o valor total da OS
- Deve permitir atualizar a quantidade alocada (ajustando o estoque pela diferença)
- Deve permitir remover a peça da OS (devolvendo ao estoque)

### RF016 — Consumir Peças por Serviço
**Prioridade:** Alta

O sistema deve permitir informar, no momento de iniciar um serviço, quais peças alocadas serão consumidas por aquele serviço específico.

**Critérios de Aceitação:**
- Consumo deve ser atômico (tudo ou nada)
- Não deve permitir consumir mais do que a quantidade alocada
- Deve rastrear qual peça foi usada em qual serviço

---

## 8. Métricas e Relatórios

### RF017 — Métricas de Serviço por OS
**Prioridade:** Média

O sistema deve fornecer métricas de execução por OS, incluindo tempo de execução de cada serviço e peças consumidas.

O sistema também deve fornecer o tempo médio de execução agrupado por tipo de
serviço, considerando somente execuções concluídas com início, finalização e
duração não negativa. Serviços sem execução válida são omitidos do resultado.

---

## 9. Tabela de Rastreabilidade

| Requisito | Implementado em | Testado |
|---|---|---|
| RF001 | `ClienteSerializer.validate_documento()` | Sim |
| RF002 | `ClienteViewSet` + `ClienteFilter` | Sim |
| RF003 | `VeiculoSerializer.validate_placa()` | Sim |
| RF004 | `VeiculoViewSet` | Sim |
| RF005 | `ServicoViewSet` | Sim |
| RF006 | `PecaViewSet` | Sim |
| RF007 | `PecaViewSet` + `PecaFilter` | Sim |
| RF008 | `OrdemServicoViewSet.create()` | Sim |
| RF009 | `OrdemServicoSerializer.validate_status()` | Sim |
| RF010 | `OrdemServico.calcular_total()` + Signals | Sim |
| RF011 | `OrdemServicoViewSet.consulta_cliente()` | Sim |
| RF012 | `ItemServicoOSViewSet.create()` | Sim |
| RF013 | `ItemServicoOSViewSet.iniciar()` / `finalizar()` | Sim |
| RF014 | `ItemServicoOSViewSet.destroy()` | Sim |
| RF015 | `ItemPecaOSSerializer` + `ItemPecaOS.save()` | Sim |
| RF016 | `ItemServicoOSViewSet.iniciar()` (com `pecas`) | Sim |
| RF017 | `MetricasItemServicoSerializer` + `OrdemServicoViewSet.tempo_medio_servicos()` | Sim |
