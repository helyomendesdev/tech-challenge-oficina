from django.db import models
from django.core.exceptions import ValidationError
from validate_docbr import CPF, CNPJ
import re

# Função de validação de CPF/CNPJ (Segurança - Aula 6)
def validate_documento(value):
    doc = str(value).replace(".", "").replace("-", "").replace("/", "")
    if len(doc) == 11:
        if not CPF().validate(doc):
            raise ValidationError("CPF inválido.")
    elif len(doc) == 14:
        if not CNPJ().validate(doc):
            raise ValidationError("CNPJ inválido.")
    else:
        raise ValidationError("Documento deve ter 11 (CPF) ou 14 (CNPJ) dígitos.")

# Função de validação de Placa (Segurança - Requisito Técnico)
def validate_placa(value):
    pattern = r'^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$' # Padrão Antigo e Mercosul
    if not re.match(pattern, value.upper()):
        raise ValidationError("Placa em formato inválido (Ex: AAA1234 ou ABC1D23).")

class Cliente(models.Model):
    nome = models.CharField(max_length=255)
    documento = models.CharField(max_length=14, unique=True, validators=[validate_documento])
    email = models.EmailField()
    telefone = models.CharField(max_length=20)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nome} ({self.documento})"

class Veiculo(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='veiculos')
    placa = models.CharField(max_length=7, unique=True, validators=[validate_placa])
    marca = models.CharField(max_length=50)
    modelo = models.CharField(max_length=50)
    ano = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.placa} - {self.modelo}"
