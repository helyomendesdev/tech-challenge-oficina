from rest_framework import viewsets
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from .models import Cliente, Veiculo, OrdemServico, Servico, Peca, ItemPecaOS
from .serializers import (
    ClienteSerializer,
    VeiculoSerializer,
    OrdemServicoSerializer,
    ServicoSerializer,
    PecaSerializer,
    ItemPecaOSSerializer,
)
from .filters import OrdemServicoFilter, ClienteFilter, PecaFilter
from .throttles import ConsultaClienteThrottle
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db.models import Q


# ---------------------------------------------------------------------------
# Mixin de isolamento por usuário (OWASP A01)
# ---------------------------------------------------------------------------

class OwnedQuerySetMixin:
    """
    Filtra o queryset para retornar apenas objetos criados pelo usuário logado.
    Superusuários (staff) enxergam todos os registros.
    """

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user and user.is_authenticated and not user.is_staff:
            qs = qs.filter(created_by=user)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


@extend_schema_view(
    list=extend_schema(description=(
        "Lista clientes cadastrados pelo usuário logado. "
        "Filtros: ?nome=joão (parcial) · ?documento=12345678901. "
        "Busca: ?search=<texto>. Ordem: ?ordering=nome,-criado_em."
    )),
    create=extend_schema(description="Cadastra um novo cliente no sistema da oficina.")
)
class ClienteViewSet(OwnedQuerySetMixin, viewsets.ModelViewSet):
    queryset = Cliente.objects.all()
    serializer_class = ClienteSerializer
    filterset_class = ClienteFilter
    search_fields = ['nome', 'documento', 'email']
    ordering_fields = ['nome', 'criado_em']
    ordering = ['nome']


class VeiculoViewSet(OwnedQuerySetMixin, viewsets.ModelViewSet):
    queryset = Veiculo.objects.select_related('cliente').all()
    serializer_class = VeiculoSerializer
    search_fields = ['placa', 'marca', 'modelo']
    ordering_fields = ['placa', 'ano', 'modelo']
    ordering = ['placa']


class ServicoViewSet(OwnedQuerySetMixin, viewsets.ModelViewSet):
    queryset = Servico.objects.all()
    serializer_class = ServicoSerializer
    search_fields = ['descricao']
    ordering_fields = ['descricao', 'valor_mao_de_obra']
    ordering = ['descricao']


@extend_schema_view(
    list=extend_schema(description=(
        "Lista peças em estoque cadastradas pelo usuário logado. "
        "Filtros: ?nome=pastilha · ?estoque_min=5 · ?estoque_zerado=true. "
        "Busca: ?search=<texto>. Ordem: ?ordering=nome,-estoque_atual."
    )),
    retrieve=extend_schema(description="Busca detalhes de uma peça específica e seu saldo atual.")
)
class PecaViewSet(OwnedQuerySetMixin, viewsets.ModelViewSet):
    queryset = Peca.objects.all()
    serializer_class = PecaSerializer
    filterset_class = PecaFilter
    search_fields = ['nome']
    ordering_fields = ['nome', 'valor_unitario', 'estoque_atual']
    ordering = ['nome']


@extend_schema_view(
    list=extend_schema(description=(
        "Lista Ordens de Serviço do usuário logado. "
        "Filtros: ?status=EXECUCAO · ?status=RECEBIDA&status=DIAGNOSTICO · "
        "?cliente=5 · ?veiculo=3 · ?data_abertura_after=2026-01-01 · "
        "?valor_total_min=500 · ?valor_total_max=2000. "
        "Ordem: ?ordering=-data_abertura,valor_total."
    )),
    create=extend_schema(description="Abre uma nova OS. O valor total inicial será calculado automaticamente."),
    retrieve=extend_schema(description="Busca detalhes da OS, incluindo o valor total atualizado (Serviços + Peças).")
)
class OrdemServicoViewSet(OwnedQuerySetMixin, viewsets.ModelViewSet):
    queryset = (
        OrdemServico.objects
        .select_related('cliente', 'veiculo')
        .prefetch_related('servicos', 'itens_pecas__peca')
        .all()
    )
    serializer_class = OrdemServicoSerializer
    filterset_class = OrdemServicoFilter
    ordering_fields = ['data_abertura', 'data_finalizacao', 'valor_total', 'status']
    ordering = ['-data_abertura']

    @extend_schema(
        description=(
            "Endpoint público — consulta OS pela placa do veículo ou CPF/CNPJ do cliente. "
            "Não requer autenticação. Limitado a 30 requisições/hora por IP."
        ),
        parameters=[
            OpenApiParameter(
                name='identificador',
                description='Placa do veículo (ex.: ABC1D23) ou CPF/CNPJ do cliente',
                required=True,
                type=str
            )
        ],
        responses={200: OrdemServicoSerializer},
        auth=[]
    )
    @action(
        detail=False,
        methods=['get'],
        url_path='consulta-cliente',
        permission_classes=[AllowAny],
        throttle_classes=[ConsultaClienteThrottle],
    )
    def consulta_cliente(self, request):
        identificador = request.query_params.get('identificador')

        if not identificador:
            return Response(
                {"erro": "Informe a placa ou o CPF/CNPJ para consulta."},
                status=400
            )

        os_list = (
            OrdemServico.objects
            .select_related('cliente', 'veiculo')
            .prefetch_related('servicos', 'itens_pecas__peca')
            .filter(
                Q(veiculo__placa=identificador.upper()) |
                Q(cliente__documento=identificador)
            )
            .order_by('-data_abertura')
        )

        if not os_list.exists():
            return Response(
                {"erro": "Nenhuma Ordem de Serviço encontrada para este identificador."},
                status=404
            )

        page = self.paginate_queryset(os_list)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(os_list, many=True)
        return Response(serializer.data)


@extend_schema_view(
    create=extend_schema(
        description="Adiciona uma peça à OS. Aciona a baixa automática no estoque e recalcula o total da OS."
    )
)
class ItemPecaOSViewSet(OwnedQuerySetMixin, viewsets.ModelViewSet):
    queryset = ItemPecaOS.objects.select_related('peca', 'os').all()
    serializer_class = ItemPecaOSSerializer
    ordering_fields = ['quantidade', 'peca__nome']
    ordering = ['peca__nome']
