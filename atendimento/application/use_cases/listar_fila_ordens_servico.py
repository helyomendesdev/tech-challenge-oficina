"""Use case de listagem da fila operacional de ordens de servico.

Camada de aplicacao: delega consulta e ordenacao ao port de repository e
transforma os resultados em DTOs de fila, sem regras de interface.
"""

from typing import Any

from atendimento.application.dtos import (
    FilaOrdemServicoItemDTO,
    ListarFilaOrdensServicoInputDTO,
)
from atendimento.application.ports.ordem_servico_repository import (
    OrdemServicoFilaPort,
)


def _campo(objeto: Any, nome: str) -> Any:
    """Busca um campo em objetos simples ou dicionarios."""
    if isinstance(objeto, dict):
        return objeto.get(nome)
    return getattr(objeto, nome)


class ListarFilaOrdensServicoUseCase:
    """Orquestra a listagem da fila operacional de ordens de servico."""

    def __init__(self, ordem_servico_repository: OrdemServicoFilaPort):
        self.ordem_servico_repository = ordem_servico_repository

    def execute(
        self, input_dto: ListarFilaOrdensServicoInputDTO
    ) -> list[FilaOrdemServicoItemDTO]:
        """Executa a listagem da fila operacional."""
        ordens_servico = self.ordem_servico_repository.listar_fila_operacional(
            input_dto.usuario_id,
            input_dto.usuario_is_staff,
        )

        return [
            FilaOrdemServicoItemDTO(
                ordem_servico_id=_campo(ordem_servico, "id"),
                cliente_nome=_campo(_campo(ordem_servico, "cliente"), "nome"),
                veiculo_placa=_campo(_campo(ordem_servico, "veiculo"), "placa"),
                status=_campo(ordem_servico, "status"),
                data_abertura=_campo(ordem_servico, "data_abertura"),
                valor_total=_campo(ordem_servico, "valor_total"),
            )
            for ordem_servico in ordens_servico
        ]
