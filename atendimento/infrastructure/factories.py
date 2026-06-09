"""Composition root simples dos fluxos novos.

Compoem use cases com adapters concretos de repositories, transacoes e
notificacoes. Mantem a injecao manual de dependencias explicita, sem container,
adequada ao monolito Django modular desta fase.
"""

from atendimento.application.use_cases.abrir_ordem_servico import (
    AbrirOrdemServicoUseCase,
)
from atendimento.application.use_cases.atualizar_status_por_notificacao import (
    AtualizarStatusPorNotificacaoUseCase,
)
from atendimento.application.use_cases.consultar_status_os import (
    ConsultarStatusOrdemServicoUseCase,
)
from atendimento.application.use_cases.finalizar_servico import FinalizarServicoUseCase
from atendimento.application.use_cases.iniciar_servico import IniciarServicoUseCase
from atendimento.application.use_cases.listar_fila_ordens_servico import (
    ListarFilaOrdensServicoUseCase,
)
from atendimento.application.use_cases.processar_resposta_orcamento import (
    ProcessarRespostaOrcamentoUseCase,
)
from atendimento.infrastructure.notifications.fake_notification_adapter import (
    FakeNotificationAdapter,
)
from atendimento.infrastructure.repositories.django_cliente_repository import (
    DjangoClienteRepository,
)
from atendimento.infrastructure.repositories.django_ordem_servico_repository import (
    DjangoOrdemServicoRepository,
)
from atendimento.infrastructure.repositories.django_servico_repository import (
    DjangoServicoRepository,
)
from atendimento.infrastructure.repositories.django_veiculo_repository import (
    DjangoVeiculoRepository,
)
from atendimento.infrastructure.transactions.django_transaction_manager import (
    DjangoTransactionManager,
)


def build_abrir_ordem_servico_use_case() -> AbrirOrdemServicoUseCase:
    """Monta o use case de abertura de ordem de servico."""
    return AbrirOrdemServicoUseCase(
        cliente_repository=DjangoClienteRepository(),
        veiculo_repository=DjangoVeiculoRepository(),
        servico_repository=DjangoServicoRepository(),
        ordem_servico_repository=DjangoOrdemServicoRepository(),
        transaction_manager=DjangoTransactionManager(),
        notification_port=FakeNotificationAdapter(),
    )


def build_consultar_status_ordem_servico_use_case():
    """Monta o use case de consulta de status de OS."""
    return ConsultarStatusOrdemServicoUseCase(
        ordem_servico_repository=DjangoOrdemServicoRepository(),
    )


def build_listar_fila_ordens_servico_use_case():
    """Monta o use case de listagem da fila operacional."""
    return ListarFilaOrdensServicoUseCase(
        ordem_servico_repository=DjangoOrdemServicoRepository(),
    )


def build_processar_resposta_orcamento_use_case():
    """Monta o use case de resposta do orcamento."""
    return ProcessarRespostaOrcamentoUseCase(
        ordem_servico_repository=DjangoOrdemServicoRepository(),
        transaction_manager=DjangoTransactionManager(),
    )


def build_atualizar_status_por_notificacao_use_case():
    """Monta o use case de atualizacao via notificacao simulada."""
    return AtualizarStatusPorNotificacaoUseCase(
        ordem_servico_repository=DjangoOrdemServicoRepository(),
        transaction_manager=DjangoTransactionManager(),
    )


def build_iniciar_servico_use_case():
    """Monta o use case de inicio de servico."""
    return IniciarServicoUseCase(
        ordem_servico_repository=DjangoOrdemServicoRepository(),
        transaction_manager=DjangoTransactionManager(),
    )


def build_finalizar_servico_use_case():
    """Monta o use case de finalizacao de servico."""
    return FinalizarServicoUseCase(
        ordem_servico_repository=DjangoOrdemServicoRepository(),
        transaction_manager=DjangoTransactionManager(),
    )
