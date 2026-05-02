# ADR-004 — Arquitetura Monolítica para Fase 1

| Informação | Valor |
|---|---|
| **ADR** | 004 |
| **Título** | Arquitetura Monolítica para a Fase 1 |
| **Status** | Aceito |
| **Autores** | Afonso Victoriano Franco (RM373563), Hélio Mendes da Silva (RM374170), João Pedro Rodrigues Martins (RM372818), Luís Fernando Montes (RM367183), Sophia Sussa Campos Bastos (RM371864) |
| **Data** | 2026-04-28 |
| **Versão** | 1.0 |

---

## 1. Contexto

O Tech Challenge Fase 1 exige a entrega de uma API REST funcional em poucas semanas. O time é pequeno e o domínio de negócio está em consolidação (Domain Storytelling e Event Storming realizados).

## 2. Decisão

Adotar uma **arquitetura monolítica modular** para a Fase 1, com a possibilidade de evolução para microsserviços em fases posteriores.

## 3. Justificativa

| Critério | Avaliação |
|---|---|
| **Time-to-market** | Monolito permite entrega rápida com um único deploy |
| **Complexidade** | Menor overhead operacional (um banco, uma aplicação, um container) |
| **Transações** | Operações como "iniciar serviço + consumir peças + atualizar OS" são atomicamente simples em um único banco |
| **Testes** | Testes de integração são mais fáceis de executar localmente |
| **Evolução** | Django apps (`atendimento/`) permitem modularização interna que facilita futura extração |

## 4. Consequências

### Positivas
- Deploy simples e rápido
- Debugging facilitado (tudo em um único processo)
- Refatorações são seguras com testes existentes

### Negativas
- Escalabilidade limitada (escala a aplicação inteira, não apenas gargalos específicos)
- Acoplamento pode aumentar se não houver disciplina de separação de responsabilidades
- Deploy de uma funcionalidade exige deploy de toda a aplicação

## 5. Estratégia de Evolução

Embora a Fase 1 seja um monolito, o código está estruturado para facilitar a extração futura:

- **App Django isolado** (`atendimento/`): pode se tornar um serviço independente
- **Models bem definidos**: cada entidade tem responsabilidade única
- **Serializers com regras de negócio**: centralizam a lógica, facilitando extração para camada de aplicação
- **Eventos via Signals**: base para futura implementação de Event Sourcing ou message broker

## 6. Alternativas Consideradas

| Alternativa | Por que não foi escolhida |
|---|---|
| **Microsserviços desde o início** | Complexidade excessiva para time e prazo; requer infraestrutura de orquestração |
| **Arquitetura Hexagonal / Clean Arch** | Excelente para longo prazo, mas adiciona camadas de indireção que atrasariam a entrega |
| **Serverless (AWS Lambda)** | Cold start problem; vendor lock-in; dificuldade de testes locais |

## 7. Histórico de Revisões

| Versão | Data | Autor | Descrição |
|---|---|---|---|
| 1.0 | 2026-04-28 | Afonso Victoriano Franco, Hélio Mendes da Silva, João Pedro Rodrigues Martins, Luís Fernando Montes, Sophia Sussa Campos Bastos | Versão inicial |
