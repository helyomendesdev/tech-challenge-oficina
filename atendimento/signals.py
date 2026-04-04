from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import OrdemServico

@receiver(post_save, sender=OrdemServico)
def baixar_estoque_ao_executar(sender, instance, created, **kwargs):
    # Verificamos se o status mudou para 'EXECUCAO'
    if instance.status == 'EXECUCAO':
        for item in instance.itens_pecas.all():
            peca = item.peca
            # Subtrai a quantidade usada da OS do estoque atual
            peca.estoque_atual -= item.quantidade
            peca.save()
            print(f"DEBUG: Baixa de {item.quantidade} unidade(s) de {peca.nome} realizada.")