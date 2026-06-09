"""DTOs da camada de aplicacao.

Transportam dados entre interfaces, use cases e ports. Mantêm os fluxos de
aplicacao independentes de serializers DRF, request, response e models Django.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class ClienteInputDTO:
    """Dados de entrada para criar ou identificar um cliente."""

    nome: str
    documento: str
    email: str
    telefone: str


@dataclass(frozen=True)
class VeiculoInputDTO:
    """Dados de entrada para criar ou identificar um veiculo."""

    placa: str
    marca: str
    modelo: str
    ano: int


@dataclass(frozen=True)
class PecaOrdemServicoInputDTO:
    """Peca solicitada para uma ordem de servico."""

    peca_id: int
    quantidade: int


@dataclass(frozen=True)
class AbrirOrdemServicoInputDTO:
    """Entrada do fluxo de abertura de ordem de servico."""

    cliente: ClienteInputDTO
    veiculo: VeiculoInputDTO
    servicos: list[int] = field(default_factory=list)
    pecas: list[PecaOrdemServicoInputDTO] = field(default_factory=list)
    usuario_id: int | None = None
    usuario_is_staff: bool = False


@dataclass(frozen=True)
class AbrirOrdemServicoOutputDTO:
    """Saida do fluxo de abertura de ordem de servico."""

    ordem_servico_id: int
    status: str
    valor_total: Decimal
    mensagem: str


@dataclass(frozen=True)
class ConsultarStatusOrdemServicoInputDTO:
    """Entrada do fluxo de consulta de status de ordem de servico."""

    ordem_servico_id: int
    usuario_id: int | None = None
    usuario_is_staff: bool = False


@dataclass(frozen=True)
class ConsultarStatusOrdemServicoOutputDTO:
    """Saida do fluxo de consulta de status de ordem de servico."""

    ordem_servico_id: int
    status: str
    descricao: str
    data_abertura: datetime
    data_inicio_execucao: datetime | None
    data_finalizacao: datetime | None
    valor_total: Decimal


@dataclass(frozen=True)
class ProcessarRespostaOrcamentoInputDTO:
    """Entrada do fluxo de processamento de resposta do orcamento."""

    ordem_servico_id: int
    decisao: str
    origem: str
    token: str | None = None
    motivo: str = ""
    usuario_id: int | None = None
    usuario_is_staff: bool = False


@dataclass(frozen=True)
class ProcessarRespostaOrcamentoOutputDTO:
    """Saida do fluxo de processamento de resposta do orcamento."""

    ordem_servico_id: int
    status_anterior: str
    status_atual: str
    mensagem: str


@dataclass(frozen=True)
class ListarFilaOrdensServicoInputDTO:
    """Entrada do fluxo de listagem da fila operacional."""

    usuario_id: int | None = None
    usuario_is_staff: bool = False


@dataclass(frozen=True)
class FilaOrdemServicoItemDTO:
    """Item apresentado na fila operacional de ordens de servico."""

    ordem_servico_id: int
    cliente_nome: str
    veiculo_placa: str
    status: str
    data_abertura: datetime
    valor_total: Decimal


@dataclass(frozen=True)
class AtualizarStatusNotificacaoInputDTO:
    """Entrada do fluxo de atualizacao de status por notificacao."""

    ordem_servico_id: int
    novo_status: str
    origem: str
    observacao: str
    usuario_id: int | None = None
    usuario_is_staff: bool = False


@dataclass(frozen=True)
class AtualizarStatusNotificacaoOutputDTO:
    """Saida do fluxo de atualizacao de status por notificacao."""

    ordem_servico_id: int
    status_anterior: str
    status_atual: str
    mensagem: str


@dataclass(frozen=True)
class IniciarServicoInputDTO:
    """Entrada do fluxo de inicio de execucao de um servico da OS."""

    ordem_servico_id: int
    item_servico_id: int
    data_inicio: datetime
    pecas: list[dict] = field(default_factory=list)
    usuario_id: int | None = None
    usuario_is_staff: bool = False


@dataclass(frozen=True)
class FinalizarServicoInputDTO:
    """Entrada do fluxo de finalizacao de um servico da OS."""

    ordem_servico_id: int
    item_servico_id: int
    data_finalizacao: datetime
    usuario_id: int | None = None
    usuario_is_staff: bool = False
