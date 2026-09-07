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
from atendimento.application.ports.observabilidade_port import ObservabilidadePort
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
        observabilidade_port: ObservabilidadePort | None = None,
    ):
        self.ordem_servico_repository = ordem_servico_repository
        self.transaction_manager = transaction_manager
        self.observabilidade_port = observabilidade_port

    def execute(
        self, input_dto: ProcessarRespostaOrcamentoInputDTO
    ) -> ProcessarRespostaOrcamentoOutputDTO:
        """Executa o processamento da decisao externa de orcamento.

        O endpoint permanece autenticado por JWT. O token recebido no DTO e
        apenas metadado da simulacao atual; validacao real de webhook externo
        por assinatura ou token pode ser adicionada em uma etapa futura.
        """
        try:
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

                # Registrar data e calcular duração antes de transicionar
                agora = datetime.now(timezone.utc)
                data_ultima_transicao_anterior = _campo(ordem_servico, "data_ultima_transicao")
                data_abertura = _campo(ordem_servico, "data_abertura")
                duracao_status_segundos = self._calcular_duracao_status(
                    data_ultima_transicao_anterior,
                    data_abertura,
                    agora,
                )

                if input_dto.decisao == DecisaoOrcamento.APROVADO.value:
                    status_atual = StatusOrdemServico.EXECUCAO.value
                    OrdemServicoStatusPolicy.validar_transicao(
                        status_anterior,
                        status_atual,
                    )
                    _definir_campo(ordem_servico, "status", status_atual)
                    _definir_campo(ordem_servico, "data_ultima_transicao", agora)
                    if not _campo(ordem_servico, "data_inicio_execucao"):
                        _definir_campo(
                            ordem_servico,
                            "data_inicio_execucao",
                            agora,
                        )
                    mensagem = "Orcamento aprovado com sucesso."
                elif input_dto.decisao == DecisaoOrcamento.RECUSADO.value:
                    status_atual = StatusOrdemServico.DIAGNOSTICO.value
                    OrdemServicoStatusPolicy.validar_transicao(
                        status_anterior,
                        status_atual,
                    )
                    _definir_campo(ordem_servico, "status", status_atual)
                    _definir_campo(ordem_servico, "data_ultima_transicao", agora)
                    mensagem = "Orcamento recusado. OS retornou para diagnostico."
                else:
                    raise DomainError(
                        f"Decisao de orcamento invalida: {input_dto.decisao}."
                    )

                ordem_servico = self.ordem_servico_repository.save(ordem_servico)

            self._registrar_evento_transicao(
                ordem_servico_id=input_dto.ordem_servico_id,
                status_anterior=status_anterior,
                status_novo=status_atual,
                duracao_status_segundos=duracao_status_segundos,
            )

        except (OrcamentoNaoPodeSerProcessadoError, DomainError) as e:
            # Registrar evento FALHA em caso de erro de domínio
            self._registrar_evento_falha(
                ordem_servico_id=input_dto.ordem_servico_id,
                erro_tipo=type(e).__name__,
            )
            raise

        return ProcessarRespostaOrcamentoOutputDTO(
            ordem_servico_id=_campo(ordem_servico, "id"),
            status_anterior=status_anterior,
            status_atual=_campo(ordem_servico, "status"),
            mensagem=mensagem,
        )

    def _calcular_duracao_status(
        self,
        data_ultima_transicao: Any,
        data_abertura: Any,
        agora: datetime,
    ) -> float:
        """Calcula duracaoStatusSegundos baseado em data_ultima_transicao.

        Regra: usa data_ultima_transicao se definida (OS nova); cai para data_abertura
        para OS legadas (onde data_ultima_transicao é NULL).

        Args:
            data_ultima_transicao: Data da última transição ou None para legadas
            data_abertura: Data de abertura da OS
            agora: Instante atual

        Returns:
            Duração em segundos (float)
        """
        inicio = data_ultima_transicao if data_ultima_transicao else data_abertura
        if inicio is None:
            return 0.0
        delta = agora - inicio
        return delta.total_seconds()

    def _registrar_evento_transicao(
        self,
        ordem_servico_id: int,
        status_anterior: str,
        status_novo: str,
        duracao_status_segundos: float,
    ) -> None:
        """Registra evento TRANSICAO quando adapter configurado.

        Args:
            ordem_servico_id: ID da OS
            status_anterior: Status antes da transição (AGUARDANDO)
            status_novo: Novo status (EXECUCAO ou DIAGNOSTICO)
            duracao_status_segundos: Tempo que OS permaneceu em AGUARDANDO
        """
        if not self.observabilidade_port:
            return


        self.observabilidade_port.registrar_evento_ordem_servico({
            'evento': 'TRANSICAO',
            'osId': ordem_servico_id,
            'statusAnterior': status_anterior,
            'statusNovo': status_novo,
            'duracaoStatusSegundos': duracao_status_segundos,
            'erroTipo': None,
        })

    def _registrar_evento_falha(
        self,
        ordem_servico_id: int,
        erro_tipo: str,
    ) -> None:
        """Registra evento FALHA em caso de erro de domínio.

        Args:
            ordem_servico_id: ID da OS
            erro_tipo: Tipo da exceção (ex: 'OrcamentoNaoPodeSerProcessadoError')
        """
        if not self.observabilidade_port:
            return


        self.observabilidade_port.registrar_evento_ordem_servico({
            'evento': 'FALHA',
            'osId': ordem_servico_id,
            'statusAnterior': None,
            'statusNovo': None,
            'duracaoStatusSegundos': 0.0,
            'erroTipo': erro_tipo,
        })
