from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone  # C1: import que estava faltando (causava NameError)
from validate_docbr import CPF, CNPJ
import re
from django.db.models.signals import m2m_changed
from django.dispatch import receiver


# ---------------------------------------------------------------------------
# Validadores de campos
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Modelos de domínio
# ---------------------------------------------------------------------------

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
    data_inicio_execucao = models.DateTimeField(null=True, blank=True)
    data_finalizacao = models.DateTimeField(null=True, blank=True)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def calcular_total(self):
        """Recalcula e persiste o valor_total da OS de forma segura (sem recursão)."""
        total_servicos = sum(s.valor_mao_de_obra for s in self.servicos.all())
        total_pecas = sum(item.total_item for item in self.itens_pecas.all())
        novo_total = total_servicos + total_pecas
        # Usa update() para evitar disparar save() recursivamente
        OrdemServico.objects.filter(pk=self.pk).update(valor_total=novo_total)

    def save(self, *args, **kwargs):
        # C1 CORRIGIDO: timezone agora está importado corretamente
        if self.status == 'EXECUCAO' and not self.data_inicio_execucao:
            self.data_inicio_execucao = timezone.now()

        if self.status == 'FINALIZADA' and not self.data_finalizacao:
            self.data_finalizacao = timezone.now()

        super().save(*args, **kwargs)
        self.calcular_total()

    def __str__(self):
        return f"OS {self.id} - {self.status}"


class ItemPecaOS(models.Model):
    os = models.ForeignKey(OrdemServico, related_name='itens_pecas', on_delete=models.CASCADE)
    peca = models.ForeignKey(Peca, on_delete=models.PROTECT)
    quantidade = models.PositiveIntegerField(default=1)

    @property
    def total_item(self):
        return self.peca.valor_unitario * self.quantidade

    def save(self, *args, **kwargs):
        if self.pk:
            # UPDATE: ajusta a diferença de estoque entre a quantidade antiga e a nova
            item_original = ItemPecaOS.objects.get(pk=self.pk)
            diferenca = self.quantidade - item_original.quantidade
            if diferenca != 0:
                if self.peca.estoque_atual < diferenca:
                    raise ValidationError(
                        f"Estoque insuficiente para a peça '{self.peca.nome}'. "
                        f"Disponível: {self.peca.estoque_atual}, Incremento solicitado: {diferenca}"
                    )
                self.peca.estoque_atual -= diferenca
                self.peca.save()
        else:
            # INSERT: valida e debita o estoque completo
            if self.peca.estoque_atual < self.quantidade:
                raise ValidationError(
                    f"Estoque insuficiente para a peça '{self.peca.nome}'. "
                    f"Disponível: {self.peca.estoque_atual}, Solicitado: {self.quantidade}"
                )
            self.peca.estoque_atual -= self.quantidade
            self.peca.save()

        super().save(*args, **kwargs)
        self.os.calcular_total()

    def delete(self, *args, **kwargs):
        # Devolve ao estoque quando a peça é removida da OS
        self.peca.estoque_atual += self.quantidade
        self.peca.save()
        super().delete(*args, **kwargs)
        self.os.calcular_total()

    def __str__(self):
        return f"{self.quantidade}x {self.peca.nome} (OS {self.os_id})"


# ---------------------------------------------------------------------------
# Signals — C2 CORRIGIDO: um único receiver para m2m_changed (sem duplicatas)
# ---------------------------------------------------------------------------

@receiver(m2m_changed, sender=OrdemServico.servicos.through)
def atualizar_total_os_servicos(sender, instance, action, **kwargs):
    """Recalcula o total da OS sempre que um serviço é adicionado ou removido."""
    if action in ["post_add", "post_remove", "post_clear"]:
        instance.calcular_total()