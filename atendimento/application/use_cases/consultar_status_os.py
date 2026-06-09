"""Use case de consulta de status de ordem de servico.

Camada de aplicacao: consulta a OS por port com isolamento de usuario e monta
DTO de saida sem depender de HTTP, DRF ou Django ORM.
"""

from typing import Any

from atendimento.application.dtos import (
    ConsultarStatusOrdemServicoInputDTO,
    ConsultarStatusOrdemServicoOutputDTO,
)
from atendimento.application.ports.ordem_servico_repository import (
    OrdemServicoConsultaPort,
)


STATUS_DESCRICOES = {
    "RECEBIDA": "Recebida",
    "DIAGNOSTICO": "Em diagnostico",
    "AGUARDANDO": "Aguardando aprovacao",
    "EXECUCAO": "Em execucao",
    "FINALIZADA": "Finalizada",
    "ENTREGUE": "Entregue",
    "CANCELADA": "Cancelada",
}


def _campo(objeto: Any, nome: str) -> Any:
    """Busca um campo em objetos simples ou dicionarios."""
    if isinstance(objeto, dict):
        return objeto.get(nome)
    return getattr(objeto, nome)


def _descricao_status(ordem_servico: Any) -> str:
    """Resolve a descricao do status sem acoplar o use case ao Django."""
    get_status_display = getattr(ordem_servico, "get_status_display", None)
    if callable(get_status_display):
        return get_status_display()

    status = _campo(ordem_servico, "status")
    return STATUS_DESCRICOES.get(status, status)


class ConsultarStatusOrdemServicoUseCase:
    """Orquestra a consulta de status de uma ordem de servico."""

    def __init__(self, ordem_servico_repository: OrdemServicoConsultaPort):
        self.ordem_servico_repository = ordem_servico_repository

    def execute(
        self, input_dto: ConsultarStatusOrdemServicoInputDTO
    ) -> ConsultarStatusOrdemServicoOutputDTO:
        """Executa a consulta de status da ordem de servico."""
        ordem_servico = self.ordem_servico_repository.get_by_id_for_user(
            input_dto.ordem_servico_id,
            input_dto.usuario_id,
            input_dto.usuario_is_staff,
        )

        return ConsultarStatusOrdemServicoOutputDTO(
            ordem_servico_id=_campo(ordem_servico, "id"),
            status=_campo(ordem_servico, "status"),
            descricao=_descricao_status(ordem_servico),
            data_abertura=_campo(ordem_servico, "data_abertura"),
            data_inicio_execucao=_campo(ordem_servico, "data_inicio_execucao"),
            data_finalizacao=_campo(ordem_servico, "data_finalizacao"),
            valor_total=_campo(ordem_servico, "valor_total"),
        )
