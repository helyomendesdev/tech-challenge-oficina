# Matriz de requisitos — Fases 1 e 2

Data da evidência local mais recente: 6 de julho de 2026.

Números consolidados: 210 testes e 3 subtests passando, cobertura total de
94,52%, 34 caminhos/60 operações OpenAPI e 76 requests na collection.
Resultados externos não são inferidos a partir da existência dos arquivos.

| Fase | Requisito | Implementação | Endpoint ou arquivo relacionado | Teste relacionado | Comando utilizado como evidência | Resultado observado | Status | Observação |
|---|---|---|---|---|---|---|---|---|
| 1 | RF001/RF002 — clientes | Validação CPF/CNPJ, ViewSet, filtros e isolamento | `ClienteSerializer`, `/api/v1/clientes/` | `test_clientes_api.py`, `test_isolamento_usuario_api.py` | `pytest --cov=atendimento --cov-report=term-missing --cov-fail-under=80` | Suíte completa passou | conforme | Usuário comum vê apenas seus registros |
| 1 | RF003/RF004 — veículos | Serializer, ViewSet e validação de placa | `/api/v1/veiculos/` | `test_veiculos_api.py` | mesmo comando de pytest | Suíte completa passou | conforme | Formatos antigo e Mercosul |
| 1 | RF005 — serviços | CRUD administrativo | `/api/v1/servicos/` | `test_servicos_api.py` | mesmo comando de pytest | Suíte completa passou | conforme | Isolamento aplicado |
| 1 | RF006/RF007 — peças e estoque | CRUD, filtros e movimentação de estoque | `/api/v1/pecas/` | `test_pecas_api.py`, `test_estoque_api.py` | mesmo comando de pytest | Suíte completa passou | conforme | Baixa e devolução testadas |
| 1 | RF008 — abertura de OS | Fluxo legado e abertura completa | `/api/v1/ordens-servico/`, `/abrir/` | `test_ordens_servico_api.py`, `test_abrir_ordem_servico.py` | mesmo comando de pytest | Suíte completa passou | conforme | Contratos legados preservados |
| 1 | RF009 — status da OS | Policies, actions e consulta | `/ordens-servico/{id}/status/` | `test_consultar_status_os.py`, `test_ordens_servico_api.py` | mesmo comando de pytest | Suíte completa passou | conforme | Status não é alterado por PATCH |
| 1 | RF010 — valor total | Domain service, model e signals legados | `OrdemServico.calcular_total()` | `test_estoque_api.py` | mesmo comando de pytest | Suíte completa passou | conforme | Arquitetura incremental |
| 1 | RF011 — consulta pública | Action pública com throttle | `/ordens-servico/consulta-cliente/` | `test_consulta_publica_api.py` | mesmo comando de pytest | Suíte completa passou | conforme | Placa ou CPF/CNPJ |
| 1 | RF012–RF014 — serviços da OS | Rotas aninhadas e use cases | `/ordens-servico/{os_id}/servicos/` | `test_iniciar_servico.py`, `test_finalizar_servico.py` | mesmo comando de pytest | Suíte completa passou | conforme | Ciclo do item testado |
| 1 | RF015/RF016 — peças na OS | Reserva e consumo rastreável | `ItemPecaOS`, `ConsumoItemServico` | `test_estoque_api.py`, `test_iniciar_servico.py` | mesmo comando de pytest | Suíte completa passou | conforme | Sem consumo acima da reserva |
| 1/2 | RF017 — métricas | Métrica por OS e média agrupada | `/{id}/metricas/`, `/metricas/tempo-medio/` | `test_metricas_api.py`, `test_tempo_medio_servicos_api.py` | mesmo comando de pytest | Testes direcionados e suíte completa passaram | conforme | Média ignora execuções inválidas |
| 1/2 | Autenticação e isolamento | JWT global e filtro por dono | `app/settings.py`, `OwnedQuerySetMixin` | `test_auth_api.py`, `test_isolamento_usuario_api.py` | mesmo comando de pytest | Suíte completa passou | conforme | Consulta pública é exceção intencional |
| 1/2 | OpenAPI | drf-spectacular, Swagger e ReDoc | `/api/schema/`, `/swagger-ui/`, `/redoc/` | teste OpenAPI da média | `python manage.py spectacular --validate --file schema.yml --settings=app.settings_test` | 34 caminhos, 60 operações, sem erro | conforme | Contagem derivada do schema |
| 1/2 | Collection Postman | Collection e environment versionados | `postman_collection.json` | Validação JSON | `python -m json.tool postman_collection.json` | JSON válido, 76 requests | conforme | Publicação externa pendente |
| 2 | Arquitetura híbrida incremental | Camadas novas coexistem com legado | `atendimento/`, ADR-005 | suíte completa | `python manage.py check` | Nenhum issue de sistema | conforme | Não é Clean Architecture pura |
| 2 | Docker local | Imagem não root, healthchecks e Compose | `Dockerfile`, `docker-compose.yml` | testes de health | `docker compose config` | Configuração validada anteriormente | conforme | Não representa produção cloud |
| 2 | Kubernetes/Kind | Namespace, banco, app, probes, Services e migrations | `k8s/`, `scripts/kind-deploy.ps1` | smoke test | `kubectl get pods,services,deployments,statefulsets -n oficina` | App 2/2 e PostgreSQL 1/1 Ready na validação local | conforme | Cluster removido após o teste |
| 2 | Metrics Server | Instalação versionada e patch Kind | `metrics-server-kind-patch.yaml` | validação de métricas | `kubectl top pods -n oficina` | Métricas numéricas observadas | conforme | TLS inseguro somente no Kind |
| 2 | HPA configurado | autoscaling/v2, CPU 50%, 2–6 réplicas | `k8s/hpa.yaml` | `scripts/hpa_load_test.py` | `kubectl get hpa -n oficina` | HPA recebeu métrica numérica | conforme | Configuração e Metrics API comprovadas |
| 2 | HPA scale-up/scale-down | Gerador de carga com assertivas | `scripts/hpa_load_test.py` | próprio script | `python scripts/hpa_load_test.py` | Sem execução atual registrada nesta matriz | parcial | Guardar `HPA_TEST=PASS` antes da entrega |
| 2 | Terraform | Kind, K8s, migrations e HPA | `infra/`, `infra/deploy.ps1` | smoke do orquestrador | `terraform plan`, `.\deploy.ps1`, `terraform destroy` | 10 criados e 10 destruídos localmente | conforme | Build/load e Metrics Server são imperativos |
| 2 | CI | Check, testes, Docker build e JUnit | `.github/workflows/ci.yml` | execução remota | Revisão do YAML local | Workflow coerente; status remoto não consultado | parcial | Confirmar pipeline verde |
| 2 | CD | Kind, deploy, migrations, smoke e HPA | `.github/workflows/cd.yml` | execução remota | Revisão do YAML local | Workflow coerente; status remoto não consultado | parcial | Carga HPA somente no gatilho manual |
| 2 | RNF008 — cobertura mínima | pytest-cov com limite de 80% | testes | suíte completa | `pytest --cov=atendimento --cov-report=term-missing --cov-fail-under=80` | 210 testes, 3 subtests, 94,52% | conforme | Última execução local |
| 2 | RNF001/RNF002 — latência/throughput | Requisitos documentados | requisitos não funcionais | sem ensaio dedicado | Nenhum comando comprovante | Sem evidência atual | não conforme | Não declarar metas como atingidas |
| 2 | RNF003 — disponibilidade | Healthchecks e probes | Docker/K8s | health tests | Checks locais | Readiness funcional; uptime mensal não medido | parcial | Meta de 99,5% não comprovada |
| 2 | Entrega externa | PR, organização, publicação, vídeo e PDF | checklist final | ação humana | N/A | Pendente | parcial | Ver checklist de entrega |

## Documentos desatualizados identificados

| Documento | Situação | Proposta |
|---|---|---|
| `docs/superpowers/plans/2026-05-03-terraform-iac.md` | Plano histórico anterior ao Terraform final; contém HPA e ordem de deploy superados | Arquivar como histórico de planejamento; não usar como instrução operacional |
| `docs/superpowers/specs/2026-05-03-terraform-iac-design.md` | Especificação histórica com valores antigos do HPA | Arquivar como decisão preliminar e apontar para `infra/README.md` |
| `docs/design/lld.md` | Árvore de testes e alguns fluxos anteriores à estrutura atual | Atualizar em revisão arquitetural futura; usar README e matriz nesta entrega |
| `docs/das/design-approval-sheet.md` | DAS da Fase 1, preservado por rastreabilidade | Manter como histórico, sem tratá-lo como checklist final da Fase 2 |
| `docs/relatorio_qualidade_seguranca.md` | Relatório histórico Sonar/OWASP; métricas consolidadas foram atualizadas | Manter; nova análise Sonar exige execução própria antes de alterar resultados de SAST |

Nenhum desses documentos foi removido. A fonte operacional atual para
Terraform é `infra/README.md`; para entrega, esta matriz e o checklist final.
