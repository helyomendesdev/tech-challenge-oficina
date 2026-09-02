"""Use case de finalizacao de um item de servico da OS.

Camada de aplicacao: finaliza um item e, quando possivel, a OS completa usando
ports e regras de dominio, sem conhecer HTTP ou ORM.
"""

from typing import Any

from datetime import datetime, timezone

from atendimento.application.dtos import FinalizarServicoInputDTO
from atendimento.application.ports.observabilidade_port import ObservabilidadePort
from atendimento.application.ports.ordem_servico_repository import (
    ItemServicoRepositoryPort,
    OrdemServicoFinalizacaoPort,
)
from atendimento.application.ports.transaction_manager import TransactionManagerPort
from atendimento.domain.enums import StatusItemServico, StatusOrdemServico
from atendimento.domain.exceptions import TransicaoStatusInvalidaError


def _campo(objeto: Any, nome: str) -> Any:
    """Busca um campo em objetos simples ou dicionarios."""
    if isinstance(objeto, dict):
        return objeto.get(nome)
    return getattr(objeto, nome)


class FinalizarServicoUseCase:
    """Orquestra a finalizacao de um item de servico da OS."""

    def __init__(
        self,
        ordem_servico_repository: (
            ItemServicoRepositoryPort | OrdemServicoFinalizacaoPort
        ),
        transaction_manager: TransactionManagerPort,
        observabilidade_port: ObservabilidadePort | None = None,
    ):
        self.ordem_servico_repository = ordem_servico_repository
        self.transaction_manager = transaction_manager
        self.observabilidade_port = observabilidade_port

    def execute(self, input_dto: FinalizarServicoInputDTO) -> Any:
        """Executa a finalizacao do servico preservando as regras atuais."""
        with self.transaction_manager.atomic():
            item_servico = self.ordem_servico_repository.get_item_servico(
                input_dto.ordem_servico_id,
                input_dto.item_servico_id,
                usuario_id=input_dto.usuario_id,
                usuario_is_staff=input_dto.usuario_is_staff,
            )

            if _campo(item_servico, "status") != StatusItemServico.EM_EXECUCAO.value:
                raise TransicaoStatusInvalidaError(
                    "Servico nao esta em execucao."
                )

            data_inicio = _campo(item_servico, "data_inicio")
            if not data_inicio:
                raise TransicaoStatusInvalidaError(
                    "Servico precisa ser iniciado antes de ser finalizado."
                )

            if input_dto.data_finalizacao < data_inicio:
                raise TransicaoStatusInvalidaError(
                    "Data de finalizacao nao pode ser anterior ao inicio."
                )

            ordem_servico = _campo(item_servico, "ordem_servico")
            if _campo(ordem_servico, "status") != StatusOrdemServico.EXECUCAO.value:
                raise TransicaoStatusInvalidaError(
                    "A OS precisa estar em EXECUCAO para finalizar servicos."
                )

            item_servico = self.ordem_servico_repository.finalizar_item_servico(
                item_servico,
                input_dto.data_finalizacao,
            )
            ordem_servico = _campo(item_servico, "ordem_servico")

            if not self.ordem_servico_repository.possui_servico_nao_concluido(
                ordem_servico
            ):
                status_anterior = _campo(ordem_servico, "status")
                self.ordem_servico_repository.finalizar_ordem_servico(
                    ordem_servico,
                    input_dto.data_finalizacao,
                )
                if self.observabilidade_port:
                    agora = datetime.now(timezone.utc)
                    data_ultima_transicao_anterior = _campo(ordem_servico, "data_ultima_transicao")
                    data_abertura = _campo(ordem_servico, "data_abertura")
                    duracao_status_segundos = (agora - (data_ultima_transicao_anterior or data_abertura)).total_seconds()
                    self.observabilidade_port.registrar_evento_ordem_servico({
                        'evento': 'TRANSICAO',
                        'osId': _campo(ordem_servico, "id"),
                        'statusAnterior': status_anterior,
                        'statusNovo': StatusOrdemServico.FINALIZADA.value,
                        'duracaoStatusSegundos': duracao_status_segundos,
                        'erroTipo': None,
                    })

            return item_servico
