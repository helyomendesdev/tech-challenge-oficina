from rest_framework import serializers
from .models import Cliente, Veiculo, OrdemServico, ItemPecaOS, Servico, Peca
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
            'data_finalizacao', 'valor_total', 'created_by',
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
