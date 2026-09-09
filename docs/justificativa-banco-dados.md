# Justificativa Formal do Banco de Dados

## 1. Escolha do Banco: PostgreSQL

### 1.1 Por que PostgreSQL?

| Critério | PostgreSQL | MySQL | SQL Server |
|---|---|---|---|
| **Custo** | Gratuito (open source) | Gratuito (community) | Pago (licença) |
| **JSON nativo** | `JSONB` com indexação | JSON limitado | JSON limitado |
| **Extensões** | pg_stat_statements, PostGIS | Poucas | Poucas |
| **Performance** | Excelente para leituras | Excelente para escritas | Balanceado |
| **AWS** | RDS gerenciado | RDS gerenciado | RDS gerenciado |
| **Comunidade** | Grande | Grande | Microsoft |

### 1.2 Justificativa para o projeto

1. **JSONB**: permite armazenar metadados flexíveis (ex: dados de veículos, serviços) sem schema rígido
2. **pg_stat_statements**: essential para monitoramento de performance (requisito do Tech Challenge)
3. **Performance Insights**: nativo no RDS, permite identificar queries lentas
4. **Custo**: gratuito, essencial para projeto acadêmico
5. **Django ORM**: suporte nativo e robusto

## 2. Modelo ER

### 2.1 Entidades e Relacionamentos

```
┌─────────────────┐     ┌─────────────────────┐     ┌─────────────────┐
│   Cliente       │     │   Veiculo           │     │   OrdemServico  │
├─────────────────┤     ├─────────────────────┤     ├─────────────────┤
│ id (PK)         │────<│ id (PK)             │────<│ id (PK)         │
│ cpf (unique)    │     │ cliente_id (FK)     │     │ cliente_id (FK) │
│ nome            │     │ placa (unique)      │     │ veiculo_id (FK) │
│ email           │     │ marca               │     │ status          │
│ telefone        │     │ modelo              │     │ data_abertura   │
│ ativo           │     │ ano                 │     │ data_conclusao  │
│ created_at      │     │ created_at          │     │ created_at      │
└─────────────────┘     └─────────────────────┘     └─────────────────┘
                                                            │
                                                            │
                                                            ▼
                                                    ┌─────────────────┐
                                                    │   Servico       │
                                                    ├─────────────────┤
                                                    │ id (PK)         │
                                                    │ ordem_id (FK)   │
                                                    │ descricao       │
                                                    │ tempo_estimado  │
                                                    │ status          │
                                                    │ created_at      │
                                                    └─────────────────┘
```

### 2.2 Relacionamentos

| Relacionamento | Tipo | Descrição |
|---|---|---|
| Cliente → Veiculo | 1:N | Um cliente pode ter vários veículos |
| Veiculo → OrdemServico | 1:N | Um veículo pode ter várias OS |
| Cliente → OrdemServico | 1:N | Um cliente pode ter várias OS |
| OrdemServico → Servico | 1:N | Uma OS pode ter vários serviços |

### 2.3 Tabelas e Campos

#### atendimento_cliente
| Campo | Tipo | Restrição | Descrição |
|---|---|---|---|
| id | SERIAL | PK | Identificador único |
| cpf | VARCHAR(11) | UNIQUE, NOT NULL | CPF apenas dígitos |
| nome | VARCHAR(255) | NOT NULL | Nome completo |
| email | VARCHAR(255) | UNIQUE | E-mail para notificações |
| telefone | VARCHAR(20) | | Telefone de contato |
| ativo | BOOLEAN | DEFAULT TRUE | Status do cliente |
| created_at | TIMESTAMP | DEFAULT NOW() | Data de criação |

#### atendimento_veiculo
| Campo | Tipo | Restrição | Descrição |
|---|---|---|---|
| id | SERIAL | PK | Identificador único |
| cliente_id | INTEGER | FK → cliente.id | Dono do veículo |
| placa | VARCHAR(8) | UNIQUE, NOT NULL | Placa do veículo |
| marca | VARCHAR(100) | | Marca |
| modelo | VARCHAR(100) | | Modelo |
| ano | INTEGER | | Ano de fabricação |
| created_at | TIMESTAMP | DEFAULT NOW() | Data de criação |

#### atendimento_ordemservico
| Campo | Tipo | Restrição | Descrição |
|---|---|---|---|
| id | SERIAL | PK | Identificador único |
| cliente_id | INTEGER | FK → cliente.id | Cliente da OS |
| veiculo_id | INTEGER | FK → veiculo.id | Veículo da OS |
| status | VARCHAR(20) | DEFAULT 'ABERTA' | ABERTA/DIAGNOSTICO/EXECUCAO/CONCLUIDA/CANCELADA |
| data_abertura | TIMESTAMP | DEFAULT NOW() | Data de abertura |
| data_conclusao | TIMESTAMP | | Data de conclusão |
| data_ultima_transicao | TIMESTAMP | | Última mudança de status |
| created_at | TIMESTAMP | DEFAULT NOW() | Data de criação |

#### atendimento_servico
| Campo | Tipo | Restrição | Descrição |
|---|---|---|---|
| id | SERIAL | PK | Identificador único |
| ordem_id | INTEGER | FK → ordemservico.id | OS pai |
| descricao | TEXT | NOT NULL | Descrição do serviço |
| tempo_estimado | INTEGER | | Tempo estimado (minutos) |
| status | VARCHAR(20) | DEFAULT 'PENDENTE' | PENDENTE/EM_EXECUCAO/CONCLUIDO |
| created_at | TIMESTAMP | DEFAULT NOW() | Data de criação |

### 2.4 Índices

| Tabela | Índice | Motivo |
|---|---|---|
| atendimento_cliente | cpf (UNIQUE) | Busca por CPF na autenticação |
| atendimento_veiculo | placa (UNIQUE) | Busca por placa |
| atendimento_veiculo | cliente_id | Listar veículos do cliente |
| atendimento_ordemservico | cliente_id + status | Listar OS do cliente por status |
| atendimento_ordemservico | data_abertura | Relatórios por período |
| atendimento_servico | ordem_id + status | Listar serviços da OS |

### 2.5 Queries Principais

```sql
-- Autenticação (Lambda)
SELECT id, ativo FROM atendimento_cliente WHERE cpf = %s OR cpf = %s;

-- Abertura de OS
INSERT INTO atendimento_ordemservico (cliente_id, veiculo_id, status)
VALUES (%s, %s, 'ABERTA') RETURNING id;

-- Consulta de OS por cliente (com isolamento)
SELECT * FROM atendimento_ordemservico WHERE cliente_id = %s;

-- Tempo médio por status (dashboard)
SELECT status, AVG(EXTRACT(EPOCH FROM data_conclusao - data_abertura))
FROM atendimento_ordemservico
WHERE status = 'CONCLUIDO' AND data_conclusao IS NOT NULL
GROUP BY status;
```

## 3. Performance e Monitoramento

### 3.1 Performance Insights (RDS)

| Configuração | Valor | Motivo |
|---|---|---|
| retention_period | 7 | Tier gratuito |
| log_min_duration_statement | 1000 | Logar queries > 1s |
| pg_stat_statements.track | all | Rastrear todas as queries |
| track_io_timing | 1 | Medir I/O |

### 3.2 Consultas Lentas Identificadas

| Query | Solução |
|---|---|
| SELECT * FROM ordens WHERE cliente_id = ? | Índice em cliente_id |
| COUNT(*) por status | Índice composto (cliente_id, status) |
| Relatórios por período | Índice em data_abertura |

## 4. Histórico de Revisões

| Versão | Data | Autor | Descrição |
|---|---|---|---|
| 1.0 | 2026-09-08 | Hélio Mendes | Versão inicial |
