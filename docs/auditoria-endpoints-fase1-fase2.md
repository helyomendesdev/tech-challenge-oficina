# Auditoria de endpoints - Fase 1 e Fase 2

Data da auditoria: 2026-06-07.

## Conclusao curta

Os endpoints antigos da Fase 1 e os novos da Fase 2 estao mapeados sob `/api/v1/`, preservando contratos antigos e evitando conflito de rotas porque as URLs especificas da Fase 2 sao incluidas antes do `DefaultRouter`.

Nao foi identificado problema simples obrigatorio de roteamento, nome ou autenticacao para corrigir agora. As fragilidades encontradas sao principalmente de regra de negocio e isolamento em escritas legadas ou em repositories ainda nao escopados por usuario, portanto devem ser tratadas em uma etapa incremental sem alterar contratos.

## Use cases existentes

| Use case | Arquivo | Usado por endpoint |
|---|---|---|
| `AbrirOrdemServicoUseCase` | `atendimento/application/use_cases/abrir_ordem_servico.py` | `POST /api/v1/ordens-servico/abrir/` |
| `ConsultarStatusOrdemServicoUseCase` | `atendimento/application/use_cases/consultar_status_os.py` | `GET /api/v1/ordens-servico/{id}/status/` |
| `ListarFilaOrdensServicoUseCase` | `atendimento/application/use_cases/listar_fila_ordens_servico.py` | `GET /api/v1/ordens-servico/fila/` |
| `ProcessarRespostaOrcamentoUseCase` | `atendimento/application/use_cases/processar_resposta_orcamento.py` | `POST /api/v1/orcamentos/notificacoes/` |
| `AtualizarStatusPorNotificacaoUseCase` | `atendimento/application/use_cases/atualizar_status_por_notificacao.py` | `POST /api/v1/ordens-servico/status-notificacoes/` |
| `IniciarServicoUseCase` | `atendimento/application/use_cases/iniciar_servico.py` | `POST /api/v1/ordens-servico/{os_pk}/servicos/{id}/iniciar/` |
| `FinalizarServicoUseCase` | `atendimento/application/use_cases/finalizar_servico.py` | `POST /api/v1/ordens-servico/{os_pk}/servicos/{id}/finalizar/` |

## Repositories existentes

| Repository | Arquivo | Responsabilidade |
|---|---|---|
| `DjangoClienteRepository` | `atendimento/infrastructure/repositories/django_cliente_repository.py` | Buscar/criar cliente por documento |
| `DjangoVeiculoRepository` | `atendimento/infrastructure/repositories/django_veiculo_repository.py` | Buscar/criar veiculo por placa e validar conflito de placa |
| `DjangoServicoRepository` | `atendimento/infrastructure/repositories/django_servico_repository.py` | Buscar servicos por ids |
| `DjangoPecaRepository` | `atendimento/infrastructure/repositories/django_peca_repository.py` | Buscar/reservar peca avulsa |
| `DjangoOrdemServicoRepository` | `atendimento/infrastructure/repositories/django_ordem_servico_repository.py` | Criar OS, adicionar itens, consultar status, fila, transicoes e itens |

## Matriz de endpoints

Legenda: "Parcial" significa que a rota funciona, mas ainda depende de regra legada, cobertura incompleta ou validacao de vinculo por usuario incompleta.

### Autenticacao

| Metodo | Path | Auth | Camada usada | Use case | Isolamento por usuario | Erro tratado | Coberto por teste |
|---|---|---|---|---|---|---|---|
| POST | `/api/token/` | Publico | `atendimento.auth_views.TokenObtainPairView` | Nao | N/A | Sim, SimpleJWT + handler DRF | Nao direto |
| POST | `/api/token/refresh/` | Publico | `atendimento.auth_views.TokenRefreshView` | Nao | N/A | Sim, SimpleJWT + handler DRF | Nao direto |

### Administrativos - CRUD base

| Metodo | Path | Auth | Camada usada | Use case | Isolamento por usuario | Erro tratado | Coberto por teste |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/clientes/` | JWT | `atendimento.views.ClienteViewSet` | Nao | Sim, `OwnedQuerySetMixin` | Sim via DRF | Sim |
| POST | `/api/v1/clientes/` | JWT | `ClienteViewSet` + `ClienteSerializer` | Nao | Sim para `created_by`; unicidade global por documento | Sim via serializer/DRF | Sim |
| GET | `/api/v1/clientes/{id}/` | JWT | `ClienteViewSet` | Nao | Sim | Sim, 404 tratado | Sim |
| PUT/PATCH | `/api/v1/clientes/{id}/` | JWT | `ClienteViewSet` + `ClienteSerializer` | Nao | Sim | Sim via serializer/DRF | Parcial |
| DELETE | `/api/v1/clientes/{id}/` | JWT | `ClienteViewSet` | Nao | Sim | Parcial, depende de constraints do ORM | Nao direto |
| GET | `/api/v1/veiculos/` | JWT | `atendimento.views.VeiculoViewSet` | Nao | Sim, `OwnedQuerySetMixin` | Sim via DRF | Parcial |
| POST | `/api/v1/veiculos/` | JWT | `VeiculoViewSet` + `VeiculoSerializer` | Nao | Parcial: `created_by` e leitura filtrada, mas cliente informado nao e escopado | Sim via DRF | Sim |
| GET | `/api/v1/veiculos/{id}/` | JWT | `VeiculoViewSet` | Nao | Sim | Sim, 404 tratado | Nao direto |
| PUT/PATCH | `/api/v1/veiculos/{id}/` | JWT | `VeiculoViewSet` | Nao | Parcial: objeto filtrado, relacao `cliente` nao validada por dono | Sim via DRF | Nao direto |
| DELETE | `/api/v1/veiculos/{id}/` | JWT | `VeiculoViewSet` | Nao | Sim | Parcial, depende de constraints do ORM | Nao direto |
| GET | `/api/v1/servicos/` | JWT | `atendimento.views.ServicoViewSet` | Nao | Sim, `OwnedQuerySetMixin` | Sim via DRF | Nao direto |
| POST | `/api/v1/servicos/` | JWT | `ServicoViewSet` + `ServicoSerializer` | Nao | Sim para `created_by` | Sim via DRF | Nao direto |
| GET | `/api/v1/servicos/{id}/` | JWT | `ServicoViewSet` | Nao | Sim | Sim, 404 tratado | Nao direto |
| PUT/PATCH | `/api/v1/servicos/{id}/` | JWT | `ServicoViewSet` | Nao | Sim | Sim via DRF | Nao direto |
| DELETE | `/api/v1/servicos/{id}/` | JWT | `ServicoViewSet` | Nao | Sim | Parcial, depende de constraints do ORM | Nao direto |
| GET | `/api/v1/pecas/` | JWT | `atendimento.views.PecaViewSet` | Nao | Sim, `OwnedQuerySetMixin` | Sim via DRF | Sim, filtros |
| POST | `/api/v1/pecas/` | JWT | `PecaViewSet` + `PecaSerializer` | Nao | Sim para `created_by` | Sim via DRF | Nao direto |
| GET | `/api/v1/pecas/{id}/` | JWT | `PecaViewSet` | Nao | Sim | Sim, 404 tratado | Nao direto |
| PUT/PATCH | `/api/v1/pecas/{id}/` | JWT | `PecaViewSet` | Nao | Sim | Sim via DRF | Nao direto |
| DELETE | `/api/v1/pecas/{id}/` | JWT | `PecaViewSet` | Nao | Sim | Parcial, depende de constraints do ORM | Nao direto |

### Administrativos - OS, pecas e servicos da OS

| Metodo | Path | Auth | Camada usada | Use case | Isolamento por usuario | Erro tratado | Coberto por teste |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/ordens-servico/` | JWT | `atendimento.views.OrdemServicoViewSet` | Nao | Sim, `OwnedQuerySetMixin` | Sim via DRF | Sim |
| POST | `/api/v1/ordens-servico/` | JWT | `OrdemServicoViewSet` + `OrdemServicoSerializer` | Nao | Parcial: `created_by`, mas `cliente`/`veiculo` nao sao escopados por dono | Sim via DRF | Sim |
| GET | `/api/v1/ordens-servico/{id}/` | JWT | `OrdemServicoViewSet` | Nao | Sim | Sim, 404 tratado | Parcial |
| PUT/PATCH | `/api/v1/ordens-servico/{id}/` | JWT | `OrdemServicoViewSet` | Nao | Parcial: objeto filtrado, relacoes nao escopadas; `status` read-only | Sim via DRF | Parcial |
| DELETE | `/api/v1/ordens-servico/{id}/` | JWT | `OrdemServicoViewSet` | Nao | Sim | Parcial, depende de constraints do ORM | Nao direto |
| POST | `/api/v1/ordens-servico/{id}/iniciar-diagnostico/` | JWT | `OrdemServicoViewSet` | Model legado + policy | Sim | Sim, `ValidationError` vira 400 | Sim |
| POST | `/api/v1/ordens-servico/{id}/finalizar-diagnostico/` | JWT | `OrdemServicoViewSet` | Model legado + policy | Sim | Sim, `ValidationError` vira 400 | Sim |
| POST | `/api/v1/ordens-servico/{id}/aprovar-orcamento/` | JWT | `OrdemServicoViewSet` | Model legado + policy | Sim | Sim, `ValidationError` vira 400 | Sim |
| POST | `/api/v1/ordens-servico/{id}/recusar-orcamento/` | JWT | `OrdemServicoViewSet` | Model legado + policy | Sim | Sim, `ValidationError` vira 400 | Sim |
| POST | `/api/v1/ordens-servico/{id}/finalizar/` | JWT | `OrdemServicoViewSet` | Model legado + policy | Sim | Sim, `ValidationError` vira 400 | Sim |
| POST | `/api/v1/ordens-servico/{id}/entregar/` | JWT | `OrdemServicoViewSet` | Model legado + policy | Sim | Sim, `ValidationError` vira 400 | Sim |
| POST | `/api/v1/ordens-servico/{id}/cancelar/` | JWT | `OrdemServicoViewSet` | Model legado + policy | Sim | Sim, `ValidationError` vira 400 | Sim |
| GET | `/api/v1/ordens-servico/{id}/metricas/` | JWT | `OrdemServicoViewSet.metricas` | Nao | Sim | Sim para parametro invalido/404 | Sim |
| GET | `/api/v1/itens-pecas/` | JWT | `atendimento.views.ItemPecaOSViewSet` | Nao | Sim por `created_by`; nao por OS | Sim via DRF | Nao direto |
| POST | `/api/v1/itens-pecas/` | JWT | `ItemPecaOSViewSet` + `ItemPecaOSSerializer` | Nao | Parcial: `os` e `peca` informados nao sao escopados | Parcial: serializer cobre estoque comum; model save pode gerar erro fora do handler | Sim |
| GET | `/api/v1/itens-pecas/{id}/` | JWT | `ItemPecaOSViewSet` | Nao | Sim por `created_by` | Sim, 404 tratado | Nao direto |
| PUT/PATCH | `/api/v1/itens-pecas/{id}/` | JWT | `ItemPecaOSViewSet` | Nao | Parcial: objeto filtrado; relacoes nao escopadas | Parcial | Sim |
| DELETE | `/api/v1/itens-pecas/{id}/` | JWT | `ItemPecaOSViewSet` | Nao | Sim por `created_by` | Parcial | Nao direto |
| GET | `/api/v1/ordens-servico/{os_pk}/servicos/` | JWT | `atendimento.views.ItemServicoOSViewSet` | Nao | Sim por OS em `_get_os` | Sim, 404 tratado | Sim |
| POST | `/api/v1/ordens-servico/{os_pk}/servicos/` | JWT | `ItemServicoOSViewSet` + `ItemServicoOSSerializer` | Nao | Parcial: OS escopada; `servico` informado nao e escopado | Sim via DRF | Sim |
| GET | `/api/v1/ordens-servico/{os_pk}/servicos/{id}/` | JWT | `ItemServicoOSViewSet` | Nao | Sim por OS | Sim, 404 tratado | Sim |
| DELETE | `/api/v1/ordens-servico/{os_pk}/servicos/{id}/` | JWT | `ItemServicoOSViewSet` | Nao | Sim por OS | Sim, bloqueia se nao PENDENTE | Sim |
| POST | `/api/v1/ordens-servico/{os_pk}/servicos/{id}/iniciar/` | JWT | `ItemServicoOSViewSet` | `IniciarServicoUseCase` | Sim por OS | Sim, DomainError 400/404 | Sim |
| POST | `/api/v1/ordens-servico/{os_pk}/servicos/{id}/finalizar/` | JWT | `ItemServicoOSViewSet` | `FinalizarServicoUseCase` | Sim por OS | Sim, DomainError 400/404 | Sim |

### Publicos

| Metodo | Path | Auth | Camada usada | Use case | Isolamento por usuario | Erro tratado | Coberto por teste |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/ordens-servico/consulta-cliente/?identificador=...` | Publico, throttle `consulta_cliente` | `OrdemServicoViewSet.consulta_cliente` | Nao | N/A, publico por requisito | Sim, 400 sem identificador e 404 sem OS | Sim |

### Novos da Fase 2

| Metodo | Path | Auth | Camada usada | Use case | Isolamento por usuario | Erro tratado | Coberto por teste |
|---|---|---|---|---|---|---|---|
| POST | `/api/v1/ordens-servico/abrir/` | JWT via config global DRF | `atendimento.interfaces.api.views.AbrirOrdemServicoAPIView` | `AbrirOrdemServicoUseCase` | Parcial: OS criada com usuario; servicos/pecas/cliente reutilizados nao sao escopados por usuario | Sim, DomainError vira 400/404 | Sim |
| GET | `/api/v1/ordens-servico/{id}/status/` | JWT via config global DRF | `ConsultarStatusOrdemServicoAPIView` | `ConsultarStatusOrdemServicoUseCase` | Sim via `get_by_id_for_user` | Sim, 404 tratado | Sim |
| GET | `/api/v1/ordens-servico/fila/` | JWT via config global DRF | `ListarFilaOrdensServicoAPIView` | `ListarFilaOrdensServicoUseCase` | Sim via repository | Sim | Sim |
| POST | `/api/v1/orcamentos/notificacoes/` | JWT via config global DRF | `ProcessarRespostaOrcamentoAPIView` | `ProcessarRespostaOrcamentoUseCase` | Sim via `get_by_id_for_user` | Sim, 400/404 tratados | Sim |
| POST | `/api/v1/ordens-servico/status-notificacoes/` | JWT via config global DRF | `AtualizarStatusPorNotificacaoAPIView` | `AtualizarStatusPorNotificacaoUseCase` | Sim via `get_by_id_for_user` | Sim, 400/404 tratados | Sim |

### Suporte OpenAPI

| Metodo | Path | Auth | Camada usada | Use case | Isolamento por usuario | Erro tratado | Coberto por teste |
|---|---|---|---|---|---|---|---|
| GET | `/api/schema/` | Configuracao do drf-spectacular | `SpectacularAPIView` | Nao | N/A | Sim | Nao direto |
| GET | `/api/schema/swagger-ui/` | Configuracao do drf-spectacular | `SpectacularSwaggerView` | Nao | N/A | Sim | Nao direto |
| GET | `/api/schema/redoc/` | Configuracao do drf-spectacular | `SpectacularRedocView` | Nao | N/A | Sim | Nao direto |

## Regras de negocio ainda fora das camadas ideais

| Local | Regra encontrada | Observacao |
|---|---|---|
| `atendimento/models.py` | `validate_documento` e `validate_placa` | Validadores Django preservados por compatibilidade; value objects ja existem em `domain/value_objects.py`. |
| `atendimento/models.py` | `OrdemServico.calcular_total` | Recalculo de orcamento/valor total ainda no model para compatibilidade com endpoints legados. |
| `atendimento/models.py` | `OrdemServico.save` | Preenche datas automaticas ao entrar em EXECUCAO/FINALIZADA. |
| `atendimento/models.py` | `OrdemServico.iniciar_diagnostico`, `finalizar_diagnostico`, `aprovar_orcamento`, `recusar_orcamento`, `finalizar`, `entregar`, `cancelar` | Transicoes legadas ainda expostas pelas actions antigas; usam policies, mas ainda ficam no model. |
| `atendimento/models.py` | `ItemPecaOS.save/delete` | Baixa/devolucao de estoque e recalculo de total ainda ficam no model; evita baixa dupla enquanto fluxo legado persiste. |
| `atendimento/models.py` | Signals `post_save/post_delete` de `ItemServicoOS` | Recalculo do total ao adicionar/remover servico ainda depende de signal. |
| `atendimento/models.py` | Signals de auditoria | Logging de criacao/status/itens permanece acoplado a signals Django. |
| `atendimento/views.py` | `OwnedQuerySetMixin` e actions de transicao | Isolamento e orquestracao HTTP legada ainda vivem em viewsets. |
| `atendimento/views.py` | `consulta_cliente` e `metricas` | Consultas ainda montam QuerySets diretamente na view. |
| `atendimento/serializers.py` | `ClienteSerializer.validate_documento` | Valida CPF/CNPJ e unicidade usando ORM diretamente. |
| `atendimento/serializers.py` | `ItemPecaOSSerializer.validate` | Valida estoque no serializer legado. |

## Requisitos da Fase 1

### Ja atendidos ou majoritariamente atendidos

| Requisito | Status |
|---|---|
| CRUD de clientes | Atendido, com testes parciais de CRUD e isolamento |
| CRUD de veiculos | Atendido, teste de criacao; cobertura restante parcial |
| CRUD de servicos | Atendido por router; cobertura direta fragil |
| CRUD de pecas e insumos com estoque | Atendido; estoque coberto em model/item OS; CRUD direto parcialmente testado |
| Criacao de OS | Atendido |
| Identificacao por CPF/CNPJ | Atendido em serializers/value objects; consulta publica pode ser fragil com documento pontuado vs normalizado |
| Cadastro de veiculo com placa, marca, modelo e ano | Atendido |
| Inclusao de servicos solicitados | Atendido por nested endpoint e abertura completa |
| Inclusao de pecas e insumos | Atendido por itens de pecas e abertura completa |
| Orcamento gerado automaticamente | Atendido por recalculo de `valor_total` |
| Envio/simulacao de orcamento | Atendido por actions legadas e notificacao simulada da Fase 2 |
| Status RECEBIDA, DIAGNOSTICO, AGUARDANDO, EXECUCAO, FINALIZADA, ENTREGUE | Atendido; existe tambem CANCELADA |
| Alteracao de status conforme acoes | Atendido em actions legadas e notificacao |
| Consulta publica por placa ou CPF/CNPJ | Atendido |
| Monitoramento de tempo medio/execucao | Atendido por endpoint de metricas por OS/servico |
| Autenticacao JWT administrativa | Atendido via config global DRF e SimpleJWT |
| Validacao de CPF/CNPJ | Atendido |
| Validacao de placa | Atendido |
| Testes dos fluxos criticos | Atendido para fluxos principais |
| Swagger/OpenAPI | Mapeado em `/api/schema/`, `/api/schema/swagger-ui/`, `/api/schema/redoc/` |

### Incompletos ou frageis

| Requisito | Fragilidade |
|---|---|
| CRUD completo | Nem todos os metodos PUT/PATCH/DELETE de todos os recursos tem teste direto. |
| Isolamento por usuario | Leituras sao filtradas, mas algumas escritas aceitam ids relacionados de outro usuario. |
| Consulta publica CPF/CNPJ | A busca nao normaliza o identificador antes de consultar; pode falhar se o documento estiver armazenado em formato diferente. |
| Erros esperados 400/404 | Bons nos fluxos cobertos; ainda ha risco de `ValidationError`/`IntegrityError` do model em caminhos legados virarem 500 em casos nao cobertos. |
| Estoque | Sem baixa dupla no fluxo atual; ainda concentrado no model legado, com risco em concorrencia/race condition. |

## Requisitos da Fase 2

### Ja atendidos ou majoritariamente atendidos

| Requisito | Status |
|---|---|
| Clean Code/refatoracao inicial | Parcialmente atendido; camadas e nomes estao claros |
| Clean Architecture/Hexagonal | Atendido na superficie nova; legado ainda convive |
| Separacao de camadas | Atendida para novos endpoints; models legados mantidos por regra |
| Abertura completa de OS | Atendida e testada |
| Consulta de status da OS | Atendida e testada |
| Aprovacao/recusa por notificacao simulada | Atendida e testada |
| Fila operacional por prioridade de status | Atendida e testada |
| Atualizacao de status via notificacao simulada | Atendida e testada |
| Testes criticos | Atendidos para fluxos novos e parte dos antigos |

### Ainda frageis

| Ponto | Fragilidade |
|---|---|
| Escopo de repositories | `DjangoServicoRepository.get_by_ids` e busca de pecas na abertura nao filtram por usuario. |
| Reuso de cliente/veiculo | Cliente por documento e veiculo por placa sao globais; pode haver acoplamento entre usuarios comuns. |
| APIViews Fase 2 | Protecao vem da configuracao global `IsAuthenticated`; funciona, mas nao esta explicita na classe. |
| Legacy actions | Transicoes de OS antigas ainda chamam metodos do model em vez de use cases. |
| Regras no model/serializer | Estoque, total e algumas validacoes ainda estao fora do dominio/application por compatibilidade. |

## Plano incremental recomendado

1. Adicionar testes de contrato para todos os metodos CRUD ainda nao cobertos diretamente: veiculos, servicos, pecas, itens-pecas e deletes.
2. Tornar permissao dos endpoints novos explicita com `permission_classes = [IsAuthenticated]`, mantendo a configuracao global.
3. Corrigir isolamento de escrita nos serializers/viewsets legados: cliente do veiculo, cliente/veiculo da OS, OS/peca de item de peca e servico de item de servico.
4. Escopar repositories da abertura completa por usuario quando buscar servicos e pecas; definir regra para staff/superuser.
5. Normalizar identificador da consulta publica antes de buscar por documento/placa, preservando compatibilidade com documentos antigos armazenados com pontuacao.
6. Migrar actions legadas de status para use cases sem remover endpoints antigos.
7. Migrar recalculo de total e movimentacao de estoque para application/infrastructure com transacao e testes de concorrencia.
8. Manter `models.py` no lugar, mas reduzir gradualmente as regras para validators simples e compatibilidade ORM.

## Correcoes simples aplicadas nesta auditoria

Nenhuma correcao de rota, nome ou autenticacao foi aplicada. As rotas estao coerentes e a autenticacao administrativa esta ativa via `REST_FRAMEWORK.DEFAULT_PERMISSION_CLASSES = IsAuthenticated`, com excecao intencional do endpoint publico `consulta-cliente` e dos endpoints de token.
