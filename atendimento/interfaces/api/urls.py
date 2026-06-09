"""URLs da interface API."""

from django.urls import path

from atendimento.interfaces.api.views import (
    AbrirOrdemServicoAPIView,
    AtualizarStatusPorNotificacaoAPIView,
    ConsultarStatusOrdemServicoAPIView,
    ListarFilaOrdensServicoAPIView,
    ProcessarRespostaOrcamentoAPIView,
)


urlpatterns = [
    path(
        "ordens-servico/abrir/",
        AbrirOrdemServicoAPIView.as_view(),
        name="abrir-ordem-servico",
    ),
    path(
        "ordens-servico/fila/",
        ListarFilaOrdensServicoAPIView.as_view(),
        name="listar-fila-ordens-servico",
    ),
    path(
        "ordens-servico/status-notificacoes/",
        AtualizarStatusPorNotificacaoAPIView.as_view(),
        name="atualizar-status-por-notificacao",
    ),
    path(
        "ordens-servico/<int:ordem_servico_id>/status/",
        ConsultarStatusOrdemServicoAPIView.as_view(),
        name="consultar-status-ordem-servico",
    ),
    path(
        "orcamentos/notificacoes/",
        ProcessarRespostaOrcamentoAPIView.as_view(),
        name="processar-resposta-orcamento",
    ),
]
