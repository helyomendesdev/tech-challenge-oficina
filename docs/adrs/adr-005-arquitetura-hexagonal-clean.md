# ADR-005 — Monolito Modular Django com Clean/Hexagonal Pragmática e DDD Tático

| Informação | Valor |
|---|---|
| **ADR** | 005 |
| **Título** | Monolito modular Django com Clean Architecture/Arquitetura Hexagonal pragmática e DDD tático |
| **Status** | Aceito |
| **Data** | 2026-05-24 |
| **Versão** | 1.1 |

---

## 1. Contexto

- A Fase 1 entregou um monolito Django/DRF funcional.
- As regras estavam concentradas em models, serializers, views e signals.
- A Fase 2 exige Clean Code, Clean Architecture ou Hexagonal, testes e evolução da aplicação.
- Era necessário preservar compatibilidade com os endpoints existentes e migrations.

## 2. Decisão

- Adotar um monolito modular Django com camadas `domain`, `application`, `infrastructure` e `interfaces`, inspirado em Clean Architecture/Arquitetura Hexagonal de forma pragmática.
- Manter Django/DRF como adapter HTTP.
- Manter Django ORM como adapter de persistência.
- Criar use cases para fluxos críticos.
- Criar repositories para isolar ORM.
- Criar value objects, enums e policies no domínio.
- Não mover `models.py` neste momento para evitar risco em migrations.
- Não tratar o projeto como Clean Architecture pura; a compatibilidade com a Fase 1 é uma restrição arquitetural explícita.

## 2.1 Estado Atual no Código

- `atendimento/domain/` concentra enums, value objects, exceptions, policies e services puros, sem import de Django/DRF.
- `atendimento/application/` concentra DTOs, ports e use cases; os fluxos novos dependem de ports e não de HTTP/ORM.
- `atendimento/infrastructure/` implementa os ports com repositories Django ORM, transaction manager e adapter fake de notificação.
- `atendimento/interfaces/api/` expõe os endpoints novos via DRF, mantendo views finas e serializers responsáveis por validação de formato/DTOs.
- `atendimento/models.py` permanece por compatibilidade com migrations, admin, serializers antigos, endpoints da Fase 1 e testes existentes.
- Regras legadas permanecem temporariamente em `models.py`, `signals.py`, ModelSerializers antigos e ViewSets antigos.
- Essa permanência é uma decisão consciente de refatoração incremental, não uma falha da arquitetura.
- Validação final: 210 testes passando, 3 subtests passando, 94,52% de cobertura total e schema OpenAPI validado sem erros.

## 3. Consequências Positivas

- Melhor separação de responsabilidades.
- Melhor testabilidade.
- Melhor clareza dos fluxos.
- Domínio mais explícito.
- Preparação para integrações externas e infraestrutura escalável.

## 4. Consequências Negativas

- Mais arquivos.
- Mais disciplina arquitetural.
- Refatoração incremental ainda mantém alguns pontos legados temporários.

## 5. Decisões Futuras

- Migrar actions antigas de ViewSets para use cases.
- Reduzir signals à medida que os fluxos de escrita forem centralizados na aplicação.
- Mover cálculo de orçamento e controle de estoque para services/use cases quando a compatibilidade legada permitir.
- Avaliar entities puras e mappers.
- Reorganizar ports se o projeto crescer e os contratos ficarem grandes demais.
- Evoluir notificação simulada para adapter real de e-mail/webhook.
