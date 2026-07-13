from rest_framework import serializers
from drf_spectacular.utils import OpenApiTypes, extend_schema_field

from atendimento.domain.exceptions import DomainError
from atendimento.domain.value_objects import (
    Dinheiro,
    DocumentoCliente,
    PlacaVeiculo,
    Quantidade,
)

from .models import (
    Cliente,
    ConsumoItemServico,
    ItemPecaOS,
    ItemServicoOS,
    OrdemServico,
    Peca,
    Servico,
    Veiculo,
)


CLIENTE_INACESSIVEL = "Cliente nao encontrado ou inacessivel."
ORDEM_SERVICO_INACESSIVEL = "Ordem de servico nao encontrada ou inacessivel."
PECA_INACESSIVEL = "Peca nao encontrada ou inacessivel."
SERVICO_INACESSIVEL = "Servico nao encontrado ou inacessivel."
VEICULO_INACESSIVEL = "Veiculo nao encontrado ou inacessivel."


def _validar_value_object(value_object_class, value):
    """Converte erros do dominio em erros de validacao do DRF."""
    try:
        return value_object_class(value).valor
    except DomainError as exc:
        raise serializers.ValidationError(str(exc)) from exc


def _usuario_pode_acessar(objeto, request):
    """Verifica se o usuario autenticado pode usar um objeto relacionado."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    return getattr(objeto, "created_by_id", None) == user.id


def _validar_objeto_do_usuario(objeto, request, mensagem):
    """Bloqueia FK para registros de outro usuario nos endpoints legados."""
    if objeto is not None and not _usuario_pode_acessar(objeto, request):
        raise serializers.ValidationError(mensagem)
    return objeto


def _documento_formatado(documento):
    if len(documento) == 11:
        return f"{documento[:3]}.{documento[3:6]}.{documento[6:9]}-{documento[9:]}"
    if len(documento) == 14:
        return (
            f"{documento[:2]}.{documento[2:5]}.{documento[5:8]}/"
            f"{documento[8:12]}-{documento[12:]}"
        )
    return documento


class ClienteSerializer(serializers.ModelSerializer):
    documento = serializers.CharField(max_length=18)

    class Meta:
        model = Cliente
        fields = [
            'id', 'nome', 'documento', 'email', 'telefone',
            'criado_em', 'created_by',
        ]
        read_only_fields = ['id', 'criado_em', 'created_by']

    def validate_documento(self, value):
        """Normaliza e valida CPF/CNPJ usando o value object do dominio."""
        doc = _validar_value_object(DocumentoCliente, value)

        documentos_equivalentes = {doc, _documento_formatado(doc)}
        qs = Cliente.objects.filter(documento__in=documentos_equivalentes)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            # TODO: migrar verificacao de unicidade para use case/repository quando
            # o endpoint legado de cliente for movido para application.
            raise serializers.ValidationError(
                "Ja existe um cliente cadastrado com este documento."
            )

        return doc


class VeiculoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Veiculo
        fields = ['id', 'cliente', 'placa', 'marca', 'modelo', 'ano', 'created_by']
        read_only_fields = ['id', 'created_by']

    def validate_placa(self, value):
        """Normaliza e valida placa usando o value object do dominio."""
        return _validar_value_object(PlacaVeiculo, value)

    def validate_cliente(self, value):
        """Garante que usuario comum use apenas clientes proprios."""
        return _validar_objeto_do_usuario(
            value,
            self.context.get("request"),
            CLIENTE_INACESSIVEL,
        )


class ServicoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Servico
        fields = ['id', 'descricao', 'valor_mao_de_obra', 'created_by']
        read_only_fields = ['id', 'created_by']

    def validate_valor_mao_de_obra(self, value):
        """Valida valor monetario nao negativo."""
        return _validar_value_object(Dinheiro, value)


class PecaSerializer(serializers.ModelSerializer):
    estoque_atual = serializers.IntegerField(min_value=0)

    class Meta:
        model = Peca
        fields = ['id', 'nome', 'valor_unitario', 'estoque_atual', 'created_by']
        read_only_fields = ['id', 'created_by']

    def validate_valor_unitario(self, value):
        """Valida valor monetario nao negativo."""
        return _validar_value_object(Dinheiro, value)


class OrdemServicoSerializer(serializers.ModelSerializer):
    valor_total = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = OrdemServico
        fields = [
            'id', 'cliente', 'veiculo', 'status', 'servicos',
            'data_abertura', 'data_inicio_execucao', 'data_finalizacao',
            'valor_total', 'created_by',
        ]
        read_only_fields = [
            'id', 'status', 'data_abertura', 'data_inicio_execucao',
            'data_finalizacao', 'valor_total', 'created_by', 'servicos',
        ]

    def validate_cliente(self, value):
        """Garante que usuario comum use apenas clientes proprios."""
        return _validar_objeto_do_usuario(
            value,
            self.context.get("request"),
            CLIENTE_INACESSIVEL,
        )

    def validate_veiculo(self, value):
        """Garante que usuario comum use apenas veiculos proprios."""
        return _validar_objeto_do_usuario(
            value,
            self.context.get("request"),
            VEICULO_INACESSIVEL,
        )

    def validate(self, data):
        """Garante consistencia entre cliente e veiculo da OS legada."""
        cliente = data.get("cliente", getattr(self.instance, "cliente", None))
        veiculo = data.get("veiculo", getattr(self.instance, "veiculo", None))
        if cliente and veiculo and veiculo.cliente_id != cliente.id:
            raise serializers.ValidationError(
                "Veiculo nao pertence ao cliente informado."
            )
        return data


class VeiculoPublicoSerializer(serializers.ModelSerializer):
    """Dados de veiculo seguros para consulta publica da OS."""

    class Meta:
        model = Veiculo
        fields = ['placa', 'marca', 'modelo', 'ano']


class ServicoOSPublicoSerializer(serializers.ModelSerializer):
    """Dados de servicos solicitados seguros para o cliente."""

    descricao = serializers.CharField(source='servico.descricao', read_only=True)
    valor_mao_de_obra = serializers.DecimalField(
        source='servico.valor_mao_de_obra',
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = ItemServicoOS
        fields = [
            'id', 'descricao', 'valor_mao_de_obra', 'status',
            'data_inicio', 'data_finalizacao',
        ]


class PecaOSPublicoSerializer(serializers.ModelSerializer):
    """Dados de pecas reservadas seguros para o cliente."""

    nome = serializers.CharField(source='peca.nome', read_only=True)
    valor_unitario = serializers.DecimalField(
        source='peca.valor_unitario',
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    total_item = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = ItemPecaOS
        fields = [
            'id', 'nome', 'valor_unitario', 'quantidade',
            'quantidade_utilizada', 'total_item',
        ]


class OrdemServicoPublicaSerializer(serializers.ModelSerializer):
    """Resposta publica da OS sem dados administrativos ou pessoais internos."""

    veiculo = VeiculoPublicoSerializer(read_only=True)
    servicos = ServicoOSPublicoSerializer(
        source='itens_servico',
        many=True,
        read_only=True,
    )
    pecas = PecaOSPublicoSerializer(
        source='itens_pecas',
        many=True,
        read_only=True,
    )

    class Meta:
        model = OrdemServico
        fields = [
            'id', 'status', 'data_abertura', 'data_inicio_execucao',
            'data_finalizacao', 'valor_total', 'veiculo', 'servicos', 'pecas',
        ]


class ItemPecaOSSerializer(serializers.ModelSerializer):
    total_item = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = ItemPecaOS
        fields = ['id', 'os', 'peca', 'quantidade', 'total_item', 'created_by']
        read_only_fields = ['id', 'total_item', 'created_by']

    def validate_quantidade(self, value):
        """Valida quantidade positiva usando o value object do dominio."""
        return _validar_value_object(Quantidade, value)

    def validate_os(self, value):
        """Garante que usuario comum adicione pecas apenas em OS propria."""
        return _validar_objeto_do_usuario(
            value,
            self.context.get("request"),
            ORDEM_SERVICO_INACESSIVEL,
        )

    def validate_peca(self, value):
        """Garante que usuario comum use apenas pecas proprias."""
        return _validar_objeto_do_usuario(
            value,
            self.context.get("request"),
            PECA_INACESSIVEL,
        )

    def validate(self, data):
        """
        Valida estoque no endpoint legado de pecas da OS.

        TODO: migrar essa regra para use case/domain policy quando ItemPecaOS
        deixar de ser criado diretamente pelo ModelSerializer legado.
        """
        peca = data.get('peca', getattr(self.instance, 'peca', None))
        quantidade_nova = data.get(
            'quantidade',
            getattr(self.instance, 'quantidade', 0),
        )

        if self.instance:
            self._validar_atualizacao_quantidade(peca, quantidade_nova)
        else:
            self._validar_reserva_inicial(peca, quantidade_nova)

        return data

    def _validar_atualizacao_quantidade(self, peca, quantidade_nova):
        if quantidade_nova < self.instance.quantidade_utilizada:
            raise serializers.ValidationError(
                "Quantidade nao pode ser menor que a quantidade ja utilizada."
            )

        if peca and peca.pk != self.instance.peca_id:
            self._validar_reserva_inicial(peca, quantidade_nova)
            return

        diferenca = quantidade_nova - self.instance.quantidade
        if diferenca > 0 and peca.estoque_atual < diferenca:
            raise serializers.ValidationError(
                f"Estoque insuficiente para '{peca.nome}'. "
                f"Disponivel para incremento: {peca.estoque_atual}, "
                f"solicitado: {diferenca}"
            )

    def _validar_reserva_inicial(self, peca, quantidade):
        if peca and quantidade > peca.estoque_atual:
            raise serializers.ValidationError(
                f"Estoque insuficiente para '{peca.nome}'. "
                f"Disponivel: {peca.estoque_atual}, "
                f"solicitado: {quantidade}"
            )


class ItemServicoOSSerializer(serializers.ModelSerializer):
    tempo_execucao_minutos = serializers.SerializerMethodField()

    class Meta:
        model = ItemServicoOS
        fields = [
            'id', 'servico', 'status',
            'data_inicio', 'data_finalizacao', 'tempo_execucao_minutos',
            'created_by',
        ]
        read_only_fields = [
            'id', 'status', 'data_inicio', 'data_finalizacao',
            'tempo_execucao_minutos', 'created_by',
        ]

    @extend_schema_field(OpenApiTypes.FLOAT)
    def get_tempo_execucao_minutos(self, obj):
        return obj.tempo_execucao_minutos

    def validate_servico(self, value):
        """Garante que usuario comum use apenas servicos proprios."""
        return _validar_objeto_do_usuario(
            value,
            self.context.get("request"),
            SERVICO_INACESSIVEL,
        )


class ConsumoInputSerializer(serializers.Serializer):
    item_peca_os_id = serializers.IntegerField()
    quantidade = serializers.IntegerField()

    def validate_quantidade(self, value):
        """Valida quantidade positiva usando o value object do dominio."""
        return _validar_value_object(Quantidade, value)


class IniciarServicoSerializer(serializers.Serializer):
    data_inicio = serializers.DateTimeField(required=False, allow_null=True)
    pecas = ConsumoInputSerializer(many=True, required=False, default=list)


class FinalizarServicoSerializer(serializers.Serializer):
    data_finalizacao = serializers.DateTimeField(required=False, allow_null=True)


class ConsumoItemServicoSerializer(serializers.ModelSerializer):
    peca = serializers.CharField(source='item_peca_os.peca.nome', read_only=True)

    class Meta:
        model = ConsumoItemServico
        fields = ['peca', 'quantidade']


class MetricasItemServicoSerializer(serializers.ModelSerializer):
    descricao = serializers.CharField(source='servico.descricao', read_only=True)
    tempo_execucao_minutos = serializers.SerializerMethodField()
    pecas_consumidas = ConsumoItemServicoSerializer(
        source='consumos',
        many=True,
        read_only=True,
    )

    class Meta:
        model = ItemServicoOS
        fields = [
            'id', 'servico', 'descricao', 'status',
            'data_inicio', 'data_finalizacao',
            'tempo_execucao_minutos', 'pecas_consumidas',
        ]

    def get_tempo_execucao_minutos(self, obj):
        return obj.tempo_execucao_minutos


class TempoMedioServicoSerializer(serializers.Serializer):
    servico_id = serializers.IntegerField()
    descricao = serializers.CharField(source='servico__descricao')
    quantidade_execucoes = serializers.IntegerField()
    tempo_medio_minutos = serializers.SerializerMethodField()

    @extend_schema_field(OpenApiTypes.FLOAT)
    def get_tempo_medio_minutos(self, obj):
        duracao_media = obj['duracao_media']
        return round(duracao_media.total_seconds() / 60, 2)
