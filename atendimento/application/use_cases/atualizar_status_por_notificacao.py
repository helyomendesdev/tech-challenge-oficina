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
from atendimento.application.ports.observabilidade_port import ObservabilidadePort
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


def _calcular_duracao_segundos(inicio: datetime, fim: datetime) -> float:
    """Calcula a duração em segundos entre dois instantes.

    Args:
        inicio: Instante inicial (datetime com timezone)
        fim: Instante final (datetime com timezone)

    Returns:
        Duração em segundos (float)
    """
    if inicio is None:
        return 0.0
    delta = fim - inicio
    return delta.total_seconds()


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
        observabilidade_port: ObservabilidadePort | None = None,
    ):
        self.ordem_servico_repository = ordem_servico_repository
        self.transaction_manager = transaction_manager
        self.observabilidade_port = observabilidade_port

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

            # Registrar data e calcular duração do status anterior antes de transicionar
            agora = datetime.now(timezone.utc)
            data_ultima_transicao_anterior = _campo(ordem_servico, "data_ultima_transicao")
            data_abertura = _campo(ordem_servico, "data_abertura")
            duracao_status_segundos = self._calcular_duracao_status(
                data_ultima_transicao_anterior,
                data_abertura,
                agora,
            )

            if novo_status == StatusOrdemServico.FINALIZADA.value:
                self.ordem_servico_repository.validar_finalizacao(
                    ordem_servico,
                    status_atual=status_anterior,
                )

            OrdemServicoStatusPolicy.validar_transicao(status_anterior, novo_status)
            _definir_campo(ordem_servico, "status", novo_status)
            _definir_campo(ordem_servico, "data_ultima_transicao", agora)

            if (
                novo_status == StatusOrdemServico.EXECUCAO.value
                and not _campo(ordem_servico, "data_inicio_execucao")
            ):
                _definir_campo(
                    ordem_servico,
                    "data_inicio_execucao",
                    agora,
                )

            if (
                novo_status == StatusOrdemServico.FINALIZADA.value
                and not _campo(ordem_servico, "data_finalizacao")
            ):
                _definir_campo(
                    ordem_servico,
                    "data_finalizacao",
                    agora,
                )

            ordem_servico = self.ordem_servico_repository.save(ordem_servico)

        self._registrar_evento_transicao(
            ordem_servico_id=input_dto.ordem_servico_id,
            status_anterior=status_anterior,
            status_novo=novo_status,
            duracao_status_segundos=duracao_status_segundos,
        )

        return AtualizarStatusNotificacaoOutputDTO(
            ordem_servico_id=_campo(ordem_servico, "id"),
            status_anterior=status_anterior,
            status_atual=_campo(ordem_servico, "status"),
            mensagem="Status atualizado por notificacao simulada.",
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
        return _calcular_duracao_segundos(inicio, agora)

    def _registrar_evento_transicao(
        self,
        ordem_servico_id: int,
        status_anterior: str,
        status_novo: str,
        duracao_status_segundos: float,
    ) -> None:
        """Registra evento TRANSICAO ou CONCLUSAO quando adapter configurado.

        Args:
            ordem_servico_id: ID da OS
            status_anterior: Status antes da transição
            status_novo: Novo status
            duracao_status_segundos: Tempo que OS permaneceu em status_anterior
        """
        if not self.observabilidade_port:
            return


        # Decidir se é TRANSICAO ou CONCLUSAO
        tipo_evento = (
            'CONCLUSAO' if status_novo == StatusOrdemServico.ENTREGUE.value
            else 'TRANSICAO'
        )

        self.observabilidade_port.registrar_evento_ordem_servico({
            'evento': tipo_evento,
            'osId': ordem_servico_id,
            'statusAnterior': status_anterior,
            'statusNovo': status_novo,
            'duracaoStatusSegundos': duracao_status_segundos,
            'erroTipo': None,
        })
