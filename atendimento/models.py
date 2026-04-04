from django.db import models
from django.core.exceptions import ValidationError
from validate_docbr import CPF, CNPJ
import re

def validate_documento(value):
    doc = str(value).replace(".", "").replace("-", "").replace("/", "")
    if len(doc) == 11:
        if not CPF().validate(doc):
            raise ValidationError("CPF inválido.")
    elif len(doc) == 14:
        if not CNPJ().validate(doc):
            raise ValidationError("CNPJ inválido.")
    else:
        raise ValidationError("Documento deve ter 11 ou 14 dígitos.")

def validate_placa(value):
    pattern = r'^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$'
    if not re.match(pattern, value.upper()):
        raise ValidationError("Placa em formato inválido.")

class Cliente(models.Model):
    nome = models.CharField(max_length=255)
    documento = models.CharField(max_length=14, unique=True, validators=[validate_documento])
    email = models.EmailField()
    telefone = models.CharField(max_length=20)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome

class Veiculo(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='veiculos')
    placa = models.CharField(max_length=7, unique=True, validators=[validate_placa])
    marca = models.CharField(max_length=50)
    modelo = models.CharField(max_length=50)
    ano = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.placa} - {self.modelo}"

class Servico(models.Model):
    descricao = models.CharField(max_length=255)
    valor_mao_de_obra = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.descricao

class Peca(models.Model):
    nome = models.CharField(max_length=255)
    valor_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    estoque_atual = models.IntegerField(default=0)

    def __str__(self):
        return self.nome

class OrdemServico(models.Model):
    STATUS_CHOICES = [
        ('RECEBIDA', 'Recebida'),
        ('DIAGNOSTICO', 'Em diagnóstico'),
        ('AGUARDANDO', 'Aguardando aprovação'),
        ('EXECUCAO', 'Em execução'),
        ('FINALIZADA', 'Finalizada'),
        ('ENTREGUE', 'Entregue'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT)
    veiculo = models.ForeignKey(Veiculo, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='RECEBIDA')
    servicos = models.ManyToManyField(Servico, blank=True)
    data_abertura = models.DateTimeField(auto_now_add=True)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def calcular_total(self):
        total_servicos = sum(s.valor_mao_de_obra for s in self.servicos.all())
        total_pecas = sum(item.total_item for item in self.itens_pecas.all())
        self.valor_total = total_servicos + total_pecas
        self.save()

    def __str__(self):
        return f"OS {self.id} - {self.status}"

class ItemPecaOS(models.Model):
    os = models.ForeignKey(OrdemServico, related_name='itens_pecas', on_delete=models.CASCADE)
    peca = models.ForeignKey(Peca, on_delete=models.PROTECT)
    quantidade = models.PositiveIntegerField(default=1)
    
    @property
    def total_item(self):
        return self.peca.valor_unitario * self.quantidade