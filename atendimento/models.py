from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth.models import User
from validate_docbr import CPF, CNPJ
import re
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
import logging

# ---------------------------------------------------------------------------
# Logger de auditoria de segurança (OWASP A09)
# ---------------------------------------------------------------------------
logger_security = logging.getLogger('security')


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
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='clientes_criados', verbose_name='Criado por'
    )

    def __str__(self):
        return self.nome


class Veiculo(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='veiculos')
    placa = models.CharField(max_length=7, unique=True, validators=[validate_placa])
    marca = models.CharField(max_length=50)
    modelo = models.CharField(max_length=50)
    ano = models.PositiveIntegerField()
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='veiculos_criados', verbose_name='Criado por'
    )

    def __str__(self):
        return f"{self.placa} - {self.modelo}"


class Servico(models.Model):
    descricao = models.CharField(max_length=255)
    valor_mao_de_obra = models.DecimalField(max_digits=10, decimal_places=2)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='servicos_criados', verbose_name='Criado por'
    )

    def __str__(self):
        return self.descricao


class Peca(models.Model):
    nome = models.CharField(max_length=255)
    valor_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    estoque_atual = models.IntegerField(default=0)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pecas_criadas', verbose_name='Criado por'
    )

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
    servicos = models.ManyToManyField(Servico, through='ItemServicoOS', blank=True)
    data_abertura = models.DateTimeField(auto_now_add=True)
    data_inicio_execucao = models.DateTimeField(null=True, blank=True)
    data_finalizacao = models.DateTimeField(null=True, blank=True)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ordens_criadas', verbose_name='Criado por'
    )

    def calcular_total(self):
        """Recalcula e persiste o valor_total da OS de forma segura (sem recursão)."""
        total_servicos = sum(s.valor_mao_de_obra for s in self.servicos.all())
        total_pecas = sum(item.total_item for item in self.itens_pecas.all())
        novo_total = total_servicos + total_pecas
        OrdemServico.objects.filter(pk=self.pk).update(valor_total=novo_total)

    def save(self, *args, **kwargs):
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
    quantidade_utilizada = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='itens_pecas_criados', verbose_name='Criado por'
    )

    @property
    def total_item(self):
        return self.peca.valor_unitario * self.quantidade

    def save(self, *args, **kwargs):
        if self.pk:
            item_original = ItemPecaOS.objects.get(pk=self.pk)
            diferenca = self.quantidade - item_original.quantidade
            if diferenca != 0:
                if self.peca.estoque_atual < diferenca:
                    raise ValidationError(
                        f"Estoque insuficiente para a peça '{self.peca.nome}'. "
                        f"Disponível para incremento: {self.peca.estoque_atual}, solicitado: {diferenca}"
                    )
                self.peca.estoque_atual -= diferenca
                self.peca.save()
        else:
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
        self.peca.estoque_atual += self.quantidade
        self.peca.save()
        super().delete(*args, **kwargs)
        self.os.calcular_total()

    def __str__(self):
        return f"{self.quantidade}x {self.peca.nome} (OS {self.os_id})"


class ItemServicoOS(models.Model):
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('EM_EXECUCAO', 'Em Execução'),
        ('CONCLUIDO', 'Concluído'),
    ]
    ordem_servico = models.ForeignKey(
        OrdemServico, on_delete=models.CASCADE, related_name='itens_servico'
    )
    servico = models.ForeignKey(
        Servico, on_delete=models.PROTECT, related_name='itens_servico'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE')
    data_inicio = models.DateTimeField(null=True, blank=True)
    data_finalizacao = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='itens_servico_criados'
    )

    class Meta:
        unique_together = [('ordem_servico', 'servico')]

    @property
    def tempo_execucao_minutos(self):
        if self.data_inicio and self.data_finalizacao:
            delta = self.data_finalizacao - self.data_inicio
            return round(delta.total_seconds() / 60, 2)
        return None

    def __str__(self):
        return f"OS {self.ordem_servico_id} - {self.servico.descricao} ({self.status})"


class ConsumoItemServico(models.Model):
    item_servico_os = models.ForeignKey(
        ItemServicoOS, on_delete=models.CASCADE, related_name='consumos'
    )
    item_peca_os = models.ForeignKey(
        ItemPecaOS, on_delete=models.PROTECT, related_name='consumos'
    )
    quantidade = models.PositiveIntegerField()

    class Meta:
        unique_together = [('item_servico_os', 'item_peca_os')]

    def __str__(self):
        return f"{self.quantidade}x {self.item_peca_os.peca.nome} → {self.item_servico_os}"


# ---------------------------------------------------------------------------
# Signals — recalculate OS total when a service item is added or removed
# ---------------------------------------------------------------------------

@receiver(post_save, sender=ItemServicoOS)
def atualizar_total_os_item_servico(sender, instance, **kwargs):
    instance.ordem_servico.calcular_total()


@receiver(post_delete, sender=ItemServicoOS)
def atualizar_total_os_item_servico_delete(sender, instance, **kwargs):
    instance.ordem_servico.calcular_total()


# ---------------------------------------------------------------------------
# Signals de auditoria de segurança (OWASP A09)
# ---------------------------------------------------------------------------

@receiver(post_save, sender=OrdemServico)
def audit_log_os_save(sender, instance, created, **kwargs):
    """Loga criação e alterações de status de Ordens de Serviço."""
    if created:
        logger_security.info(
            "os_created",
            extra={
                "os_id": instance.id,
                "status": instance.status,
                "user_id": instance.created_by_id,
                "cliente_id": instance.cliente_id,
                "veiculo_id": instance.veiculo_id,
            }
        )
    else:
        logger_security.info(
            "os_updated",
            extra={
                "os_id": instance.id,
                "status": instance.status,
                "user_id": instance.created_by_id,
            }
        )


@receiver(post_save, sender=ItemPecaOS)
def audit_log_item_peca_save(sender, instance, created, **kwargs):
    """Loga adição e alteração de peças em OS (movimentação de estoque)."""
    acao = "item_peca_created" if created else "item_peca_updated"
    logger_security.info(
        acao,
        extra={
            "item_id": instance.id,
            "os_id": instance.os_id,
            "peca_id": instance.peca_id,
            "quantidade": instance.quantidade,
            "user_id": instance.created_by_id,
        }
    )


@receiver(post_delete, sender=ItemPecaOS)
def audit_log_item_peca_delete(sender, instance, **kwargs):
    """Loga remoção de peças da OS (devolução de estoque)."""
    logger_security.info(
        "item_peca_deleted",
        extra={
            "item_id": instance.id,
            "os_id": instance.os_id,
            "peca_id": instance.peca_id,
            "quantidade": instance.quantidade,
            "user_id": instance.created_by_id,
        }
    )
