# ADR-003 — Containerização com Docker e Docker Compose

| Informação | Valor |
|---|---|
| **ADR** | 003 |
| **Título** | Containerização com Docker e Docker Compose |
| **Status** | Aceito |
| **Autores** | Afonso Victoriano Franco (RM373563), Hélio Mendes da Silva (RM374170), João Pedro Rodrigues Martins (RM372818), Luís Fernando Montes (RM367183), Sophia Sussa Campos Bastos (RM371864) |
| **Data** | 2026-04-28 |
| **Versão** | 1.0 |

---

## 1. Contexto

A aplicação precisa ser executada de forma consistente em diferentes ambientes (desenvolvimento local, avaliação do professor, CI/CD futuro). É necessário garantir que todos os serviços (API + banco) subam com um único comando.

## 2. Decisão

Utilizar **Docker** para containerização da aplicação e **Docker Compose** para orquestração local dos serviços.

## 3. Justificativa

| Critério | Avaliação |
|---|---|
| **Reprodutibilidade** | O ambiente de desenvolvimento é idêntico ao de produção futura |
| **Onboarding** | Novos desenvolvedores rodam `docker-compose up` e têm tudo funcionando |
| **Isolamento** | Dependências do Python não conflitam com o sistema operacional do host |
| **Healthcheck** | Docker Compose suporta `healthcheck` para garantir que a API só suba quando o PostgreSQL estiver pronto |
| **Infraestrutura como Código** | `docker-compose.yml` documenta a infraestrutura necessária |

## 4. Consequências

### Positivas
- Deploy simplificado para qualquer ambiente com Docker instalado
- Fácil rollback de versões via tags de imagem
- Integração direta com plataformas de cloud (AWS ECS, Azure Container Instances)

### Negativas
- Overhead de recursos (containers consomem mais memória que processos nativos)
- Curva de aprendizado inicial para quem não conhece Docker
- Volumes precisam ser gerenciados corretamente para não perder dados

## 5. Arquitetura dos Containers

```
docker-compose.yml
├── db (PostgreSQL 15)
│   └── volume persistente para dados
└── app (Django/Gunicorn)
    ├── porta 8000 exposta
    └── depende do healthcheck do db
```

## 6. Alternativas Consideradas

| Alternativa | Por que não foi escolhida |
|---|---|
| **Rodar nativo (Python + PostgreSQL local)** | Dificuldade de garantir versões idênticas entre máquinas |
| **Vagrant** | Mais pesado e lento que Docker; menos popular na comunidade Python |
| **Kubernetes** | Overkill para um monolito em Fase 1; complexidade desnecessária |

## 7. Histórico de Revisões

| Versão | Data | Autor | Descrição |
|---|---|---|---|
| 1.0 | 2026-04-28 | Afonso Victoriano Franco, Hélio Mendes da Silva, João Pedro Rodrigues Martins, Luís Fernando Montes, Sophia Sussa Campos Bastos | Versão inicial |
