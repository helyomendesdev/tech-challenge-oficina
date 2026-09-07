"""Migration 0007: Adiciona campo data_ultima_transicao à OrdemServico.

Este campo registra o instante da última transição de status, permitindo calcular
duracaoStatusSegundos para os custom events de observabilidade (§5.4 da spec).

Valores NULL indicam OS legadas criadas antes desta mudança. Para medir tempo até
um status antigo, o cálculo cai para data_abertura nesse caso (ver use cases).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('atendimento', '0006_add_status_cancelada'),
    ]

    operations = [
        migrations.AddField(
            model_name='ordemservico',
            name='data_ultima_transicao',
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text="Instante da última transição de status. NULL para OS legadas (criadas antes desta mudança). Usado para calcular duração do status anterior."
            ),
        ),
    ]
