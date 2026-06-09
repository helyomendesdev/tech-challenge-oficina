"""Use case de atualizacao de status por notificacao simulada.

Camada de aplicacao: aplica regras de transicao e finalizacao recebidas de um
adapter externo simulado, usando apenas ports, policies e transacao.
"""

from datetime import datetime, timezone
from typing import Any

from atendimento.application.dtos import (
    AtualizarStatusNotificacaoInputDTO,
    AtualizarStatusNotificacaoOutputDTO,
)
from atendimento.application.ports.ordem_servico_repository import (
    OrdemServicoConsultaPort,
    OrdemServicoEscritaPort,
    OrdemServicoFinalizacaoPort,
)
from atendimento.application.ports.transaction_manager import TransactionManagerPort
from atendimento.domain.enums import StatusOrdemServico
from atendimento.domain.policies import OrdemServicoStatusPolicy


def _campo(objeto: Any, nome: str) -> Any:
    """Busca um campo em objetos simples ou dicionarios."""
    if isinstance(objeto, dict):
        return objeto.get(nome)
    return getattr(objeto, nome)


def _definir_campo(objeto: Any, nome: str, valor: Any) -> None:
    """Define um campo em objetos simples ou dicionarios."""
    if isinstance(objeto, dict):
        objeto[nome] = valor
        return
    setattr(objeto, nome, valor)


class AtualizarStatusPorNotificacaoUseCase:
    """Orquestra atualizacao de status recebida por notificacao externa."""

    def __init__(
        self,
        ordem_servico_repository: (
            OrdemServicoConsultaPort
            | OrdemServicoEscritaPort
            | OrdemServicoFinalizacaoPort
        ),
        transaction_manager: TransactionManagerPort,
    ):
        self.ordem_servico_repository = ordem_servico_repository
        self.transaction_manager = transaction_manager

    def execute(
        self, input_dto: AtualizarStatusNotificacaoInputDTO
    ) -> AtualizarStatusNotificacaoOutputDTO:
        """Executa a atualizacao de status por notificacao simulada."""
        with self.transaction_manager.atomic():
            ordem_servico = self.ordem_servico_repository.get_by_id_for_user(
                input_dto.ordem_servico_id,
                input_dto.usuario_id,
                input_dto.usuario_is_staff,
            )
            status_anterior = _campo(ordem_servico, "status")
            novo_status = input_dto.novo_status

            if novo_status == StatusOrdemServico.FINALIZADA.value:
                self.ordem_servico_repository.validar_finalizacao(
                    ordem_servico,
                    status_atual=status_anterior,
                )

            OrdemServicoStatusPolicy.validar_transicao(status_anterior, novo_status)
            _definir_campo(ordem_servico, "status", novo_status)

            if (
                novo_status == StatusOrdemServico.EXECUCAO.value
                and not _campo(ordem_servico, "data_inicio_execucao")
            ):
                _definir_campo(
                    ordem_servico,
                    "data_inicio_execucao",
                    datetime.now(timezone.utc),
                )

            if (
                novo_status == StatusOrdemServico.FINALIZADA.value
                and not _campo(ordem_servico, "data_finalizacao")
            ):
                _definir_campo(
                    ordem_servico,
                    "data_finalizacao",
                    datetime.now(timezone.utc),
                )

            ordem_servico = self.ordem_servico_repository.save(ordem_servico)

        return AtualizarStatusNotificacaoOutputDTO(
            ordem_servico_id=_campo(ordem_servico, "id"),
            status_anterior=status_anterior,
            status_atual=_campo(ordem_servico, "status"),
            mensagem="Status atualizado por notificacao simulada.",
        )
