"""Serializers da interface API.

Adapters de validacao HTTP/DRF. Validam formato, normalizam entradas simples e
convertem dados para DTOs sem concentrar regras complexas de negocio.
"""

from rest_framework import serializers

from atendimento.application.dtos import (
    AbrirOrdemServicoInputDTO,
    AtualizarStatusNotificacaoInputDTO,
    ClienteInputDTO,
    ConsultarStatusOrdemServicoInputDTO,
    ListarFilaOrdensServicoInputDTO,
    PecaOrdemServicoInputDTO,
    ProcessarRespostaOrcamentoInputDTO,
    VeiculoInputDTO,
)
from atendimento.domain.exceptions import DomainError
from atendimento.domain.enums import DecisaoOrcamento, StatusOrdemServico
from atendimento.domain.value_objects import (
    DocumentoCliente,
    PlacaVeiculo,
    Quantidade,
)


def _validar_value_object(value_object_class, value):
    """Converte erros de dominio em erros de validacao da interface."""
    try:
        return value_object_class(value).valor
    except DomainError as exc:
        raise serializers.ValidationError(str(exc)) from exc


class ClienteInputSerializer(serializers.Serializer):
    """Entrada HTTP para dados de cliente na abertura de OS."""

    nome = serializers.CharField(max_length=255)
    documento = serializers.CharField(max_length=18)
    email = serializers.EmailField()
    telefone = serializers.CharField(max_length=20)

    def validate_documento(self, value):
        """Valida e normaliza CPF/CNPJ para apenas digitos."""
        return _validar_value_object(DocumentoCliente, value)


class VeiculoInputSerializer(serializers.Serializer):
    """Entrada HTTP para dados de veiculo na abertura de OS."""

    placa = serializers.CharField(max_length=8)
    marca = serializers.CharField(max_length=50)
    modelo = serializers.CharField(max_length=50)
    ano = serializers.IntegerField(min_value=1)

    def validate_placa(self, value):
        """Valida e normaliza placa para maiusculas."""
        return _validar_value_object(PlacaVeiculo, value)


class PecaOrdemServicoInputSerializer(serializers.Serializer):
    """Entrada HTTP para peca reservada na abertura de OS."""

    peca_id = serializers.IntegerField(min_value=1)
    quantidade = serializers.IntegerField(min_value=1)

    def validate_quantidade(self, value):
        """Valida quantidade positiva usando value object de dominio."""
        return _validar_value_object(Quantidade, value)


class AbrirOrdemServicoInputSerializer(serializers.Serializer):
    """Entrada HTTP para abertura completa de ordem de servico."""

    cliente = ClienteInputSerializer()
    veiculo = VeiculoInputSerializer()
    servicos = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=True,
        default=list,
        required=False,
    )
    pecas = PecaOrdemServicoInputSerializer(
        many=True,
        default=list,
        required=False,
    )

    def to_dto(
        self,
        usuario_id=None,
        usuario_is_staff: bool = False,
    ) -> AbrirOrdemServicoInputDTO:
        """Converte dados validados em DTO da camada de aplicacao."""
        dados = self.validated_data
        cliente = dados["cliente"]
        veiculo = dados["veiculo"]

        return AbrirOrdemServicoInputDTO(
            cliente=ClienteInputDTO(
                nome=cliente["nome"],
                documento=cliente["documento"],
                email=cliente["email"],
                telefone=cliente["telefone"],
            ),
            veiculo=VeiculoInputDTO(
                placa=veiculo["placa"],
                marca=veiculo["marca"],
                modelo=veiculo["modelo"],
                ano=veiculo["ano"],
            ),
            servicos=dados.get("servicos", []),
            pecas=[
                PecaOrdemServicoInputDTO(
                    peca_id=peca["peca_id"],
                    quantidade=peca["quantidade"],
                )
                for peca in dados.get("pecas", [])
            ],
            usuario_id=usuario_id,
            usuario_is_staff=usuario_is_staff,
        )


def montar_consultar_status_dto(
    ordem_servico_id: int,
    usuario_id: int | None = None,
    usuario_is_staff: bool = False,
) -> ConsultarStatusOrdemServicoInputDTO:
    """Monta DTO de consulta de status a partir do contexto HTTP."""
    return ConsultarStatusOrdemServicoInputDTO(
        ordem_servico_id=ordem_servico_id,
        usuario_id=usuario_id,
        usuario_is_staff=usuario_is_staff,
    )


def montar_listar_fila_dto(
    usuario_id: int | None = None,
    usuario_is_staff: bool = False,
) -> ListarFilaOrdensServicoInputDTO:
    """Monta DTO de fila a partir do contexto HTTP."""
    return ListarFilaOrdensServicoInputDTO(
        usuario_id=usuario_id,
        usuario_is_staff=usuario_is_staff,
    )


class AbrirOrdemServicoOutputSerializer(serializers.Serializer):
    """Saida HTTP para abertura completa de ordem de servico."""

    ordem_servico_id = serializers.IntegerField()
    status = serializers.CharField()
    valor_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    mensagem = serializers.CharField()


class ConsultarStatusOrdemServicoOutputSerializer(serializers.Serializer):
    """Saida HTTP para consulta de status de ordem de servico."""

    ordem_servico_id = serializers.IntegerField()
    status = serializers.CharField()
    descricao = serializers.CharField()
    data_abertura = serializers.DateTimeField()
    data_inicio_execucao = serializers.DateTimeField(allow_null=True)
    data_finalizacao = serializers.DateTimeField(allow_null=True)
    valor_total = serializers.DecimalField(max_digits=10, decimal_places=2)


class FilaOrdemServicoItemOutputSerializer(serializers.Serializer):
    """Saida HTTP para um item da fila operacional de ordens de servico."""

    ordem_servico_id = serializers.IntegerField()
    cliente_nome = serializers.CharField()
    veiculo_placa = serializers.CharField()
    status = serializers.CharField()
    data_abertura = serializers.DateTimeField()
    valor_total = serializers.DecimalField(max_digits=10, decimal_places=2)


class ProcessarRespostaOrcamentoInputSerializer(serializers.Serializer):
    """Entrada HTTP para decisao externa de aprovacao ou recusa de orcamento."""

    ordem_servico_id = serializers.IntegerField(min_value=1)
    decisao = serializers.ChoiceField(
        choices=[
            DecisaoOrcamento.APROVADO.value,
            DecisaoOrcamento.RECUSADO.value,
        ],
    )
    origem = serializers.CharField(max_length=100)
    token = serializers.CharField(
        allow_blank=True,
        allow_null=True,
        default=None,
        max_length=255,
        required=False,
    )
    motivo = serializers.CharField(
        allow_blank=True,
        default="",
        required=False,
    )

    def to_dto(
        self,
        usuario_id: int | None = None,
        usuario_is_staff: bool = False,
    ) -> ProcessarRespostaOrcamentoInputDTO:
        """Converte dados validados em DTO da camada de aplicacao."""
        dados = self.validated_data
        return ProcessarRespostaOrcamentoInputDTO(
            ordem_servico_id=dados["ordem_servico_id"],
            decisao=dados["decisao"],
            origem=dados["origem"],
            token=dados.get("token") or None,
            motivo=dados.get("motivo", ""),
            usuario_id=usuario_id,
            usuario_is_staff=usuario_is_staff,
        )


class ProcessarRespostaOrcamentoOutputSerializer(serializers.Serializer):
    """Saida HTTP para processamento de resposta externa de orcamento."""

    ordem_servico_id = serializers.IntegerField()
    status_anterior = serializers.CharField()
    status_atual = serializers.CharField()
    mensagem = serializers.CharField()


class AtualizarStatusNotificacaoInputSerializer(serializers.Serializer):
    """Entrada HTTP simulada para atualizacao externa de status da OS."""

    ordem_servico_id = serializers.IntegerField(min_value=1)
    novo_status = serializers.ChoiceField(
        choices=[status.value for status in StatusOrdemServico],
    )
    origem = serializers.CharField(max_length=100)
    observacao = serializers.CharField(
        allow_blank=True,
        default="",
        required=False,
    )

    def to_dto(
        self,
        usuario_id: int | None = None,
        usuario_is_staff: bool = False,
    ) -> AtualizarStatusNotificacaoInputDTO:
        """Converte dados validados em DTO da camada de aplicacao."""
        dados = self.validated_data
        return AtualizarStatusNotificacaoInputDTO(
            ordem_servico_id=dados["ordem_servico_id"],
            novo_status=dados["novo_status"],
            origem=dados["origem"],
            observacao=dados.get("observacao", ""),
            usuario_id=usuario_id,
            usuario_is_staff=usuario_is_staff,
        )


class AtualizarStatusNotificacaoOutputSerializer(serializers.Serializer):
    """Saida HTTP para atualizacao externa simulada de status da OS."""

    ordem_servico_id = serializers.IntegerField()
    status_anterior = serializers.CharField()
    status_atual = serializers.CharField()
    mensagem = serializers.CharField()
