import django_filters
from .models import OrdemServico, Cliente, Peca


class OrdemServicoFilter(django_filters.FilterSet):
    """
    Filtros disponíveis para o endpoint /api/v1/ordens-servico/

    Exemplos de uso:
        ?status=EXECUCAO
        ?status=RECEBIDA&status=DIAGNOSTICO   (múltiplos via IN)
        ?data_abertura_after=2026-01-01
        ?data_abertura_before=2026-12-31
        ?cliente=5
        ?veiculo=3
        ?valor_total_min=500
        ?valor_total_max=2000
    """

    status = django_filters.MultipleChoiceFilter(
        choices=OrdemServico.STATUS_CHOICES,
        label='Status (pode repetir para múltiplos valores)',
    )

    data_abertura_after = django_filters.DateTimeFilter(
        field_name='data_abertura',
        lookup_expr='gte',
        label='Aberta após (YYYY-MM-DD)',
    )

    data_abertura_before = django_filters.DateTimeFilter(
        field_name='data_abertura',
        lookup_expr='lte',
        label='Aberta antes de (YYYY-MM-DD)',
    )

    data_finalizacao_after = django_filters.DateTimeFilter(
        field_name='data_finalizacao',
        lookup_expr='gte',
        label='Finalizada após (YYYY-MM-DD)',
    )

    data_finalizacao_before = django_filters.DateTimeFilter(
        field_name='data_finalizacao',
        lookup_expr='lte',
        label='Finalizada antes de (YYYY-MM-DD)',
    )

    valor_total_min = django_filters.NumberFilter(
        field_name='valor_total',
        lookup_expr='gte',
        label='Valor total mínimo',
    )

    valor_total_max = django_filters.NumberFilter(
        field_name='valor_total',
        lookup_expr='lte',
        label='Valor total máximo',
    )

    class Meta:
        model = OrdemServico
        fields = ['status', 'cliente', 'veiculo']


class ClienteFilter(django_filters.FilterSet):
    """
    Filtros para /api/v1/clientes/

    Exemplos:
        ?nome=João          (busca parcial, case-insensitive)
        ?documento=12345678901
    """

    nome = django_filters.CharFilter(
        lookup_expr='icontains',
        label='Nome (parcial, sem distinção de maiúsculas)',
    )

    class Meta:
        model = Cliente
        fields = ['nome', 'documento']


class PecaFilter(django_filters.FilterSet):
    """
    Filtros para /api/v1/pecas/

    Exemplos:
        ?nome=pastilha
        ?estoque_min=5      (apenas peças com estoque >= 5)
        ?estoque_zerado=true
    """

    nome = django_filters.CharFilter(
        lookup_expr='icontains',
        label='Nome da peça (parcial)',
    )

    estoque_min = django_filters.NumberFilter(
        field_name='estoque_atual',
        lookup_expr='gte',
        label='Estoque mínimo',
    )

    estoque_zerado = django_filters.BooleanFilter(
        method='filter_estoque_zerado',
        label='Apenas peças sem estoque (true/false)',
    )

    def filter_estoque_zerado(self, queryset, name, value):
        if value:
            return queryset.filter(estoque_atual=0)
        return queryset.filter(estoque_atual__gt=0)

    class Meta:
        model = Peca
        fields = ['nome']
