"""Use case de abertura de ordem de servico.

Camada de aplicacao: orquestra o fluxo usando ports e transacao, sem acessar
Django ORM, serializers, request ou response diretamente.
"""

from typing import Any

from atendimento.application.dtos import (
    AbrirOrdemServicoInputDTO,
    AbrirOrdemServicoOutputDTO,
)
from atendimento.application.ports.cliente_repository import ClienteRepositoryPort
from atendimento.application.ports.notification_port import NotificationPort
from atendimento.application.ports.ordem_servico_repository import (
    OrdemServicoRepositoryPort,
)
from atendimento.application.ports.servico_repository import ServicoRepositoryPort
from atendimento.application.ports.transaction_manager import TransactionManagerPort
from atendimento.application.ports.veiculo_repository import VeiculoRepositoryPort


def _campo(objeto: Any, nome: str) -> Any:
    """Busca um campo em objetos simples ou dicionarios."""
    if isinstance(objeto, dict):
        return objeto.get(nome)
    return getattr(objeto, nome)


class AbrirOrdemServicoUseCase:
    """Orquestra o fluxo de abertura de uma ordem de servico."""

    def __init__(
        self,
        cliente_repository: ClienteRepositoryPort,
        veiculo_repository: VeiculoRepositoryPort,
        servico_repository: ServicoRepositoryPort,
        ordem_servico_repository: OrdemServicoRepositoryPort,
        transaction_manager: TransactionManagerPort,
        notification_port: NotificationPort | None = None,
    ):
        self.cliente_repository = cliente_repository
        self.veiculo_repository = veiculo_repository
        self.servico_repository = servico_repository
        self.ordem_servico_repository = ordem_servico_repository
        self.transaction_manager = transaction_manager
        self.notification_port = notification_port

    def execute(
        self, input_dto: AbrirOrdemServicoInputDTO
    ) -> AbrirOrdemServicoOutputDTO:
        """Executa a abertura da ordem de servico.

        Servicos continuam opcionais por compatibilidade com os fluxos legados.
        Quando informados, os ids sao validados pelo repository de servicos.

        A reserva de pecas passa pelo repository de OS para manter uma unica
        fonte de verdade para a baixa de estoque enquanto ItemPecaOS.save()
        preserva esse comportamento legado.
        """
        servico_ids = list(input_dto.servicos or [])
        pecas_input = list(input_dto.pecas or [])

        with self.transaction_manager.atomic():
            cliente = self.cliente_repository.get_or_create(
                input_dto.cliente,
                usuario_id=input_dto.usuario_id,
                usuario_is_staff=input_dto.usuario_is_staff,
            )
            veiculo = self.veiculo_repository.get_or_create(
                cliente,
                input_dto.veiculo,
                usuario_id=input_dto.usuario_id,
                usuario_is_staff=input_dto.usuario_is_staff,
            )
            servicos = self.servico_repository.get_by_ids(
                servico_ids,
                usuario_id=input_dto.usuario_id,
                usuario_is_staff=input_dto.usuario_is_staff,
            )
            ordem_servico = self.ordem_servico_repository.create(
                cliente,
                veiculo,
                usuario_id=input_dto.usuario_id,
            )

            self.ordem_servico_repository.adicionar_servicos(
                ordem_servico,
                servicos,
                usuario_id=input_dto.usuario_id,
            )
            self.ordem_servico_repository.adicionar_pecas(
                ordem_servico,
                pecas_input,
                usuario_id=input_dto.usuario_id,
                usuario_is_staff=input_dto.usuario_is_staff,
            )
            ordem_servico = self.ordem_servico_repository.recalcular_total(
                ordem_servico
            )

        self._notificar_orcamento(ordem_servico, cliente)

        return AbrirOrdemServicoOutputDTO(
            ordem_servico_id=_campo(ordem_servico, "id"),
            status=_campo(ordem_servico, "status"),
            valor_total=_campo(ordem_servico, "valor_total"),
            mensagem="Ordem de servico aberta com sucesso.",
        )

    def _notificar_orcamento(self, ordem_servico: Any, cliente: Any) -> None:
        """Solicita notificacao de orcamento quando houver adapter configurado."""
        if not self.notification_port:
            return

        self.notification_port.notificar_orcamento(
            ordem_servico_id=_campo(ordem_servico, "id"),
            email=_campo(cliente, "email"),
            valor_total=_campo(ordem_servico, "valor_total"),
        )
