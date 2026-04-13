from rest_framework import serializers
from .models import Cliente, Veiculo, OrdemServico, ItemPecaOS, Servico, Peca
from validate_docbr import CPF, CNPJ

class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = '__all__'

    def validate_documento(self, value):
        # 1. Limpeza de dados (Linguagem Ubíqua: tratar o dado bruto)
        # Remove pontos, traços e barras para validar apenas os números
        doc = "".join(filter(str.isdigit, str(value)))

        # 2. Validação de Formato (Confiabilidade)
        if len(doc) not in [11, 14]:
            raise serializers.ValidationError("O documento deve ter 11 dígitos (CPF) ou 14 dígitos (CNPJ).")

        # 3. Validação de Regra de Negócio (Dígito Verificador)
        if len(doc) == 11 and not CPF().validate(doc):
            raise serializers.ValidationError("Este número de CPF é inválido.")
        
        if len(doc) == 14 and not CNPJ().validate(doc):
            raise serializers.ValidationError("Este número de CNPJ é inválido.")

        # 4. Verificação de Duplicidade (Prevenção de Erro de Banco)
        # O campo 'documento' no model tem unique=True, mas validamos aqui para evitar o Erro 500
        exists = Cliente.objects.filter(documento=doc).exclude(id=self.instance.id if self.instance else None).exists()
        if exists:
            raise serializers.ValidationError("Já existe um cliente cadastrado com este documento.")

        return doc

class VeiculoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Veiculo
        fields = '__all__'

    def validate_placa(self, value):
        # Padroniza a placa para maiúsculas antes de salvar
        return value.upper()

class ServicoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Servico
        fields = '__all__'

class PecaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Peca
        fields = '__all__'

class OrdemServicoSerializer(serializers.ModelSerializer):
    valor_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = OrdemServico
        fields = '__all__'

class ItemPecaOSSerializer(serializers.ModelSerializer):
    total_item = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = ItemPecaOS
        fields = ['id', 'os', 'peca', 'quantidade', 'total_item']