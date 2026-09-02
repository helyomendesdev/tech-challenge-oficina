from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import F
from validate_docbr import CPF, CNPJ
import re
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
import logging

from atendimento.domain.enums import StatusItemServico, StatusOrdemServico
from atendimento.domain.exceptions import DomainError
from atendimento.domain.policies import (
    FinalizacaoOrdemServicoPolicy,
    OrdemServicoStatusPolicy,
)
from atendimento.domain.services import OrcamentoDomainService

# ---------------------------------------------------------------------------
# Logger de auditoria de segurança (OWASP A09)
# ---------------------------------------------------------------------------
logger_security = logging.getLogger('security')

_CRIADO_POR = 'Criado por'


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
    pattern = r'^[A-Z]{3}\d[A-Z\d]\d{2}$'
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
    ativo = models.BooleanField(default=True, help_text="Clientes inativos não podem fazer login")
    criado_em = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='clientes_criados', verbose_name=_CRIADO_POR
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
        related_name='veiculos_criados', verbose_name=_CRIADO_POR
    )

    def __str__(self):
        return f"{self.placa} - {self.modelo}"


class Servico(models.Model):
    descricao = models.CharField(max_length=255)
    valor_mao_de_obra = models.DecimalField(max_digits=10, decimal_places=2)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='servicos_criados', verbose_name=_CRIADO_POR
    )

    def __str__(self):
        return self.descricao


class Peca(models.Model):
    nome = models.CharField(max_length=255)
    valor_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    estoque_atual = models.IntegerField(default=0)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pecas_criadas', verbose_name=_CRIADO_POR
    )

    def __str__(self):
        return self.nome


class OrdemServico(models.Model):
    """Modelo legado de OS mantido como ancora Django.

    Algumas regras permanecem aqui temporariamente para preservar migrations,
    admin, serializers antigos e endpoints da Fase 1 durante a refatoracao
    incremental para use cases.
    """

    STATUS_CHOICES = [
        (StatusOrdemServico.RECEBIDA.value, 'Recebida'),
        (StatusOrdemServico.DIAGNOSTICO.value, 'Em diagnóstico'),
        (StatusOrdemServico.AGUARDANDO.value, 'Aguardando aprovação'),
        (StatusOrdemServico.EXECUCAO.value, 'Em execução'),
        (StatusOrdemServico.FINALIZADA.value, 'Finalizada'),
        (StatusOrdemServico.ENTREGUE.value, 'Entregue'),
        (StatusOrdemServico.CANCELADA.value, 'Cancelada'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT)
    veiculo = models.ForeignKey(Veiculo, on_delete=models.PROTECT)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=StatusOrdemServico.RECEBIDA.value,
    )
    servicos = models.ManyToManyField(Servico, through='ItemServicoOS', blank=True)
    data_abertura = models.DateTimeField(auto_now_add=True)
    data_inicio_execucao = models.DateTimeField(null=True, blank=True)
    data_finalizacao = models.DateTimeField(null=True, blank=True)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ordens_criadas', verbose_name=_CRIADO_POR
    )

    def calcular_total(self):
        """Recalcula e persiste o valor_total da OS de forma segura (sem recursão)."""
        # Recalculo mantido no model para compatibilidade com signals e
        # endpoints antigos enquanto os fluxos legados ainda existem.
        # TODO: migrar recalculo de total para use cases/repositories quando
        # todos os fluxos de escrita de OS estiverem fora dos models legados.
        if not self.pk:
            return

        novo_total = OrcamentoDomainService.calcular_total(
            servicos=self.servicos.all(),
            pecas=self.itens_pecas.select_related("peca").all(),
        ).valor
        OrdemServico.objects.filter(pk=self.pk).update(valor_total=novo_total)
        self.valor_total = novo_total

    def save(self, *args, **kwargs):
        # TODO: mover preenchimento automatico de datas de status para use
        # cases. Mantido aqui por compatibilidade com endpoints legados.
        if (
            self.status == StatusOrdemServico.EXECUCAO.value
            and not self.data_inicio_execucao
        ):
            self.data_inicio_execucao = timezone.now()

        if (
            self.status == StatusOrdemServico.FINALIZADA.value
            and not self.data_finalizacao
        ):
            self.data_finalizacao = timezone.now()

        super().save(*args, **kwargs)
        self.calcular_total()

    def __str__(self):
        return f"OS {self.id} - {self.status}"

    def _transicionar(self, status_esperado, novo_status, mensagem_erro):
        """Transicao legada validada pela policy de dominio."""
        if self.status != status_esperado:
            raise ValidationError(mensagem_erro)
        try:
            OrdemServicoStatusPolicy.validar_transicao(self.status, novo_status)
        except DomainError:
            raise ValidationError(mensagem_erro)
        self.status = novo_status
        self.save()

    def iniciar_diagnostico(self):
        self._transicionar(
            StatusOrdemServico.RECEBIDA.value,
            StatusOrdemServico.DIAGNOSTICO.value,
            "A OS precisa estar com status RECEBIDA para iniciar o diagnóstico."
        )

    def finalizar_diagnostico(self):
        self._transicionar(
            StatusOrdemServico.DIAGNOSTICO.value,
            StatusOrdemServico.AGUARDANDO.value,
            "A OS precisa estar em DIAGNOSTICO para finalizar o diagnóstico."
        )

    def aprovar_orcamento(self):
        self._transicionar(
            StatusOrdemServico.AGUARDANDO.value,
            StatusOrdemServico.EXECUCAO.value,
            "A OS precisa estar AGUARDANDO aprovação para aprovar o orçamento."
        )

    def recusar_orcamento(self):
        self._transicionar(
            StatusOrdemServico.AGUARDANDO.value,
            StatusOrdemServico.DIAGNOSTICO.value,
            "A OS precisa estar AGUARDANDO aprovação para recusar o orçamento."
        )

    def finalizar(self):
        """Finalizacao legada validada pelas policies de dominio."""
        # TODO: remover validacoes abaixo quando as actions legadas de OS
        # forem totalmente migradas para use cases.
        if self.status != StatusOrdemServico.EXECUCAO.value:
            raise ValidationError(
                "A OS precisa estar em EXECUCAO para ser finalizada."
            )
        tem_servico_nao_concluido = self.itens_servico.exclude(
            status=StatusItemServico.CONCLUIDO.value
        ).exists()
        if tem_servico_nao_concluido:
            raise ValidationError(
                "Não é possível finalizar a OS: existem serviços não concluídos."
            )
        tem_peca_nao_utilizada = self.itens_pecas.exclude(
            quantidade_utilizada=F('quantidade')
        ).exists()
        if tem_peca_nao_utilizada:
            raise ValidationError(
                "Não é possível finalizar a OS: existem peças não utilizadas."
            )
        try:
            FinalizacaoOrdemServicoPolicy.validar_finalizacao(
                self.status,
                self.itens_servico.all(),
                self.itens_pecas.all(),
            )
            OrdemServicoStatusPolicy.validar_transicao(
                self.status,
                StatusOrdemServico.FINALIZADA.value,
            )
        except DomainError as exc:
            raise ValidationError(str(exc))

        self.status = StatusOrdemServico.FINALIZADA.value
        self.save()

    def entregar(self):
        self._transicionar(
            StatusOrdemServico.FINALIZADA.value, StatusOrdemServico.ENTREGUE.value,
            "A OS precisa estar FINALIZADA para ser entregue."
        )

    def cancelar(self):
        self._transicionar(
            StatusOrdemServico.AGUARDANDO.value, StatusOrdemServico.CANCELADA.value,
            "A OS precisa estar AGUARDANDO aprovação para ser cancelada."
        )


def recalcular_total_ordem_servico(ordem_servico_id):
    """Recalcula o total a partir de uma instancia fresca da OS."""
    ordem_servico = OrdemServico.objects.filter(pk=ordem_servico_id).first()
    if ordem_servico:
        ordem_servico.calcular_total()


class ItemPecaOS(models.Model):
    """Item de peca da OS com reserva legada de estoque.

    A movimentacao no save/delete e temporaria, mas segue como fonte da
    verdade para compatibilidade com endpoints antigos.
    """

    os = models.ForeignKey(OrdemServico, related_name='itens_pecas', on_delete=models.CASCADE)
    peca = models.ForeignKey(Peca, on_delete=models.PROTECT)
    quantidade = models.PositiveIntegerField(default=1)
    quantidade_utilizada = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='itens_pecas_criados', verbose_name=_CRIADO_POR
    )

    @property
    def total_item(self):
        return self.peca.valor_unitario * self.quantidade

    def save(self, *args, **kwargs):
        # TODO: migrar movimentacao de estoque totalmente para use cases e
        # repositories. Mantido aqui temporariamente por compatibilidade com
        # endpoints legados que ainda persistem ItemPecaOS diretamente.
        if self.quantidade_utilizada > self.quantidade:
            raise ValidationError(
                "Quantidade utilizada nao pode ser maior que a quantidade reservada."
            )

        if self.pk:
            item_original = ItemPecaOS.objects.get(pk=self.pk)
            if self.peca_id != item_original.peca_id:
                if self.peca.estoque_atual < self.quantidade:
                    raise ValidationError(
                        f"Estoque insuficiente para a peca '{self.peca.nome}'. "
                        f"Disponivel: {self.peca.estoque_atual}, Solicitado: {self.quantidade}"
                    )
                item_original.peca.estoque_atual += item_original.quantidade
                item_original.peca.save()
                self.peca.estoque_atual -= self.quantidade
                self.peca.save()
                super().save(*args, **kwargs)
                recalcular_total_ordem_servico(self.os_id)
                return

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
        recalcular_total_ordem_servico(self.os_id)

    def delete(self, *args, **kwargs):
        # Devolve a reserva ao estoque no caminho legado de remocao de peca.
        ordem_servico_id = self.os_id
        self.peca.estoque_atual += self.quantidade
        self.peca.save()
        super().delete(*args, **kwargs)
        recalcular_total_ordem_servico(ordem_servico_id)

    def __str__(self):
        return f"{self.quantidade}x {self.peca.nome} (OS {self.os_id})"


class ItemServicoOS(models.Model):
    STATUS_CHOICES = [
        (StatusItemServico.PENDENTE.value, 'Pendente'),
        (StatusItemServico.EM_EXECUCAO.value, 'Em Execução'),
        (StatusItemServico.CONCLUIDO.value, 'Concluído'),
    ]
    ordem_servico = models.ForeignKey(
        OrdemServico, on_delete=models.CASCADE, related_name='itens_servico'
    )
    servico = models.ForeignKey(
        Servico, on_delete=models.PROTECT, related_name='itens_servico'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=StatusItemServico.PENDENTE.value,
    )
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
    # TODO: manter signal apenas enquanto endpoints legados ainda criam
    # ItemServicoOS diretamente via ModelSerializer.
    recalcular_total_ordem_servico(instance.ordem_servico_id)


@receiver(post_delete, sender=ItemServicoOS)
def atualizar_total_os_item_servico_delete(sender, instance, **kwargs):
    # TODO: manter signal apenas enquanto endpoints legados ainda removem
    # ItemServicoOS diretamente via ViewSet.
    recalcular_total_ordem_servico(instance.ordem_servico_id)


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
