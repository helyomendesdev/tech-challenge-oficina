# ADR-002 — Uso do PostgreSQL como Banco de Dados

| Informação | Valor |
|---|---|
| **ADR** | 002 |
| **Título** | Uso do PostgreSQL 15 como SGBD Principal |
| **Status** | Aceito |
| **Autores** | Afonso Victoriano Franco (RM373563), Hélio Mendes da Silva (RM374170), João Pedro Rodrigues Martins (RM372818), Luís Fernando Montes (RM367183), Sophia Sussa Campos Bastos (RM371864) |
| **Data** | 2026-04-28 |
| **Versão** | 1.0 |

---

## 1. Contexto

O sistema necessita de um banco de dados relacional para armazenar dados estruturados com consistência ACID, suporte a transações complexas e evolução controlada do schema.

## 2. Decisão

Utilizar **PostgreSQL 15** como banco de dados relacional principal.

## 3. Justificativa

| Critério | Avaliação |
|---|---|
| **ACID** | Transações completas, essenciais para controle de estoque e ordens de serviço |
| **Maturidade** | SGBD open-source com 30+ anos de desenvolvimento ativo |
| **JSONB** | Suporte a dados semi-estruturados para extensões futuras (ex: histórico de alterações) |
| **Migrations** | Integração nativa com Django ORM (`makemigrations`, `migrate`) |
| **Performance** | Índices avançados (B-tree, GIN, GiST), query planner sofisticado |
| **Docker** | Imagem oficial estável e leve para desenvolvimento local |

## 4. Consequências

### Positivas
- Consistência garantida em operações críticas (baixa de estoque, criação de OS)
- Facilidade de backup e replicação para ambientes de produção futuros
- Suporte a `SELECT FOR UPDATE` para locks pessimistas em operações concorrentes

### Negativas
- Requer provisionamento e manutenção do servidor PostgreSQL
- Escrita horizontal (sharding) mais complexa que bancos NoSQL (não é problema na Fase 1)

## 5. Alternativas Consideradas

| Alternativa | Por que não foi escolhida |
|---|---|
| **MySQL / MariaDB** | Menor conformidade com padrões SQL; recursos avançados (CTEs, window functions) menos maduros |
| **SQLite** | Não suporta concorrência adequada para produção; usado apenas em testes (`settings_test.py`) |
| **MongoDB** | Consistência eventual não é adequada para controle de estoque e transações financeiras |

## 6. Histórico de Revisões

| Versão | Data | Autor | Descrição |
|---|---|---|---|
| 1.0 | 2026-04-28 | Afonso Victoriano Franco, Hélio Mendes da Silva, João Pedro Rodrigues Martins, Luís Fernando Montes, Sophia Sussa Campos Bastos | Versão inicial |
