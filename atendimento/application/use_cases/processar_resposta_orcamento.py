"""Use case de processamento de resposta externa do orcamento.

Camada de aplicacao: aplica o fluxo de aprovacao/recusa usando policies de
dominio, ports e transacao, sem depender do adapter HTTP.
"""

from datetime import datetime, timezone
from typing import Any

from atendimento.application.dtos import (
    ProcessarRespostaOrcamentoInputDTO,
    ProcessarRespostaOrcamentoOutputDTO,
)
from atendimento.application.ports.ordem_servico_repository import (
    OrdemServicoConsultaPort,
    OrdemServicoEscritaPort,
)
from atendimento.application.ports.transaction_manager import TransactionManagerPort
from atendimento.domain.enums import DecisaoOrcamento, StatusOrdemServico
from atendimento.domain.exceptions import (
    DomainError,
    OrcamentoNaoPodeSerProcessadoError,
)
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


class ProcessarRespostaOrcamentoUseCase:
    """Orquestra aprovacao ou recusa externa de um orcamento."""

    def __init__(
        self,
        ordem_servico_repository: OrdemServicoConsultaPort | OrdemServicoEscritaPort,
        transaction_manager: TransactionManagerPort,
    ):
        self.ordem_servico_repository = ordem_servico_repository
        self.transaction_manager = transaction_manager

    def execute(
        self, input_dto: ProcessarRespostaOrcamentoInputDTO
    ) -> ProcessarRespostaOrcamentoOutputDTO:
        """Executa o processamento da decisao externa de orcamento.

        O endpoint permanece autenticado por JWT. O token recebido no DTO e
        apenas metadado da simulacao atual; validacao real de webhook externo
        por assinatura ou token pode ser adicionada em uma etapa futura.
        """
        with self.transaction_manager.atomic():
            ordem_servico = self.ordem_servico_repository.get_by_id_for_user(
                input_dto.ordem_servico_id,
                input_dto.usuario_id,
                input_dto.usuario_is_staff,
            )
            status_anterior = _campo(ordem_servico, "status")

            if status_anterior != StatusOrdemServico.AGUARDANDO.value:
                raise OrcamentoNaoPodeSerProcessadoError(
                    "O orcamento so pode ser processado quando a OS esta AGUARDANDO."
                )

            if input_dto.decisao == DecisaoOrcamento.APROVADO.value:
                status_atual = StatusOrdemServico.EXECUCAO.value
                OrdemServicoStatusPolicy.validar_transicao(
                    status_anterior,
                    status_atual,
                )
                _definir_campo(ordem_servico, "status", status_atual)
                if not _campo(ordem_servico, "data_inicio_execucao"):
                    _definir_campo(
                        ordem_servico,
                        "data_inicio_execucao",
                        datetime.now(timezone.utc),
                    )
                mensagem = "Orcamento aprovado com sucesso."
            elif input_dto.decisao == DecisaoOrcamento.RECUSADO.value:
                status_atual = StatusOrdemServico.DIAGNOSTICO.value
                OrdemServicoStatusPolicy.validar_transicao(
                    status_anterior,
                    status_atual,
                )
                _definir_campo(ordem_servico, "status", status_atual)
                mensagem = "Orcamento recusado. OS retornou para diagnostico."
            else:
                raise DomainError(
                    f"Decisao de orcamento invalida: {input_dto.decisao}."
                )

            ordem_servico = self.ordem_servico_repository.save(ordem_servico)

        return ProcessarRespostaOrcamentoOutputDTO(
            ordem_servico_id=_campo(ordem_servico, "id"),
            status_anterior=status_anterior,
            status_atual=_campo(ordem_servico, "status"),
            mensagem=mensagem,
        )
