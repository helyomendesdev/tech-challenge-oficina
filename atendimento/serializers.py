from rest_framework import serializers
from django.db.models import F
from .models import Cliente, Veiculo, OrdemServico, ItemPecaOS, Servico, Peca, ItemServicoOS, ConsumoItemServico
from validate_docbr import CPF, CNPJ

# ---------------------------------------------------------------------------
# Máquina de transição de estados válidos (M6)
# ---------------------------------------------------------------------------

TRANSICOES_VALIDAS = {
    'RECEBIDA':    ['DIAGNOSTICO'],
    'DIAGNOSTICO': ['AGUARDANDO'],
    'AGUARDANDO':  ['EXECUCAO'],
    'EXECUCAO':    ['FINALIZADA'],
    'FINALIZADA':  ['ENTREGUE'],
    'ENTREGUE':    [],
}


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = ['id', 'nome', 'documento', 'email', 'telefone', 'criado_em', 'created_by']
        read_only_fields = ['id', 'criado_em', 'created_by']

    def validate_documento(self, value):
        doc = "".join(filter(str.isdigit, str(value)))

        if len(doc) not in [11, 14]:
            raise serializers.ValidationError(
                "O documento deve ter 11 dígitos (CPF) ou 14 dígitos (CNPJ)."
            )

        if len(doc) == 11 and not CPF().validate(doc):
            raise serializers.ValidationError("Este número de CPF é inválido.")

        if len(doc) == 14 and not CNPJ().validate(doc):
            raise serializers.ValidationError("Este número de CNPJ é inválido.")

        qs = Cliente.objects.filter(documento=doc)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "Já existe um cliente cadastrado com este documento."
            )

        return doc


class VeiculoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Veiculo
        fields = ['id', 'cliente', 'placa', 'marca', 'modelo', 'ano', 'created_by']
        read_only_fields = ['id', 'created_by']

    def validate_placa(self, value):
        return value.upper()


class ServicoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Servico
        fields = ['id', 'descricao', 'valor_mao_de_obra', 'created_by']
        read_only_fields = ['id', 'created_by']


class PecaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Peca
        fields = ['id', 'nome', 'valor_unitario', 'estoque_atual', 'created_by']
        read_only_fields = ['id', 'created_by']


class OrdemServicoSerializer(serializers.ModelSerializer):
    valor_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = OrdemServico
        fields = [
            'id', 'cliente', 'veiculo', 'status', 'servicos',
            'data_abertura', 'data_inicio_execucao', 'data_finalizacao',
            'valor_total', 'created_by',
        ]
        read_only_fields = [
            'id', 'data_abertura', 'data_inicio_execucao',
            'data_finalizacao', 'valor_total', 'created_by', 'servicos',
        ]

    def validate_status(self, value):
        """M6: valida que a transição de status segue o fluxo permitido."""
        if self.instance:
            status_atual = self.instance.status
            transicoes_permitidas = TRANSICOES_VALIDAS.get(status_atual, [])
            if value != status_atual and value not in transicoes_permitidas:
                raise serializers.ValidationError(
                    f"Transição inválida: '{status_atual}' → '{value}'. "
                    f"Próximos status permitidos: {transicoes_permitidas or ['nenhum']}"
                )

            if value == 'FINALIZADA':
                tem_servico_nao_concluido = self.instance.itens_servico.exclude(
                    status='CONCLUIDO'
                ).exists()
                if tem_servico_nao_concluido:
                    raise serializers.ValidationError(
                        "Não é possível finalizar a OS: existem serviços não concluídos."
                    )
                tem_peca_nao_utilizada = self.instance.itens_pecas.exclude(
                    quantidade_utilizada=F('quantidade')
                ).exists()
                if tem_peca_nao_utilizada:
                    raise serializers.ValidationError(
                        "Não é possível finalizar a OS: existem peças não utilizadas."
                    )
        return value


class ItemPecaOSSerializer(serializers.ModelSerializer):
    total_item = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = ItemPecaOS
        fields = ['id', 'os', 'peca', 'quantidade', 'total_item', 'created_by']
        read_only_fields = ['id', 'total_item', 'created_by']

    def validate(self, data):
        """M7: valida disponibilidade de estoque tanto em criação quanto em update."""
        peca = data.get('peca', getattr(self.instance, 'peca', None))
        quantidade_nova = data.get('quantidade', getattr(self.instance, 'quantidade', 0))

        if self.instance:
            diferenca = quantidade_nova - self.instance.quantidade
            if diferenca > 0 and peca.estoque_atual < diferenca:
                raise serializers.ValidationError(
                    f"Estoque insuficiente para '{peca.nome}'. "
                    f"Disponível para incremento: {peca.estoque_atual}, solicitado: {diferenca}"
                )
        else:
            if peca and quantidade_nova > peca.estoque_atual:
                raise serializers.ValidationError(
                    f"Estoque insuficiente para '{peca.nome}'. "
                    f"Disponível: {peca.estoque_atual}, solicitado: {quantidade_nova}"
                )

        return data


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

    def get_tempo_execucao_minutos(self, obj):
        return obj.tempo_execucao_minutos


class ConsumoInputSerializer(serializers.Serializer):
    item_peca_os_id = serializers.IntegerField()
    quantidade = serializers.IntegerField(min_value=1)


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
        source='consumos', many=True, read_only=True
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
