from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets, mixins, status as drf_status
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from .models import Cliente, Veiculo, OrdemServico, Servico, Peca, ItemPecaOS, ItemServicoOS, ConsumoItemServico
from .serializers import (
    ClienteSerializer,
    VeiculoSerializer,
    OrdemServicoSerializer,
    ServicoSerializer,
    PecaSerializer,
    ItemPecaOSSerializer,
    ItemServicoOSSerializer,
    IniciarServicoSerializer,
    FinalizarServicoSerializer,
    MetricasItemServicoSerializer,
)
from .filters import OrdemServicoFilter, ClienteFilter, PecaFilter
from .throttles import ConsultaClienteThrottle
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db.models import F, Q


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

    @action(detail=True, methods=['get'], url_path='metricas')
    def metricas(self, request, pk=None):
        os = self.get_object()
        qs = (
            ItemServicoOS.objects
            .filter(ordem_servico=os)
            .select_related('servico')
            .prefetch_related('consumos__item_peca_os__peca')
            .order_by('id')
        )
        servico_id = request.query_params.get('servico')
        if servico_id is not None:
            try:
                qs = qs.filter(servico_id=int(servico_id))
            except (ValueError, TypeError):
                return Response({'erro': "'servico' deve ser um inteiro."}, status=drf_status.HTTP_400_BAD_REQUEST)
        serializer = MetricasItemServicoSerializer(qs, many=True)
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


class ItemServicoOSViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ItemServicoOSSerializer

    def _get_os(self):
        user = self.request.user
        qs = OrdemServico.objects.all()
        if not user.is_staff:
            qs = qs.filter(created_by=user)
        return get_object_or_404(qs, pk=self.kwargs['os_pk'])

    def get_queryset(self):
        os = self._get_os()
        return ItemServicoOS.objects.filter(
            ordem_servico=os
        ).select_related('servico', 'ordem_servico').order_by('id')

    def perform_create(self, serializer):
        os = self._get_os()
        serializer.save(ordem_servico=os, created_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status != 'PENDENTE':
            return Response(
                {'erro': 'Não é possível remover serviço em execução ou concluído'},
                status=drf_status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def iniciar(self, request, os_pk=None, pk=None):
        item = self.get_object()

        if item.status != 'PENDENTE':
            return Response(
                {'erro': 'Serviço já foi iniciado ou concluído'},
                status=drf_status.HTTP_400_BAD_REQUEST,
            )

        serializer = IniciarServicoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data_inicio = serializer.validated_data.get('data_inicio') or timezone.now()
        pecas_input = serializer.validated_data.get('pecas', [])

        consumos_a_criar = []
        for entrada in pecas_input:
            try:
                item_peca = ItemPecaOS.objects.get(
                    pk=entrada['item_peca_os_id'], os=item.ordem_servico
                )
            except ItemPecaOS.DoesNotExist:
                return Response(
                    {'erro': f"Peça {entrada['item_peca_os_id']} não pertence a esta OS"},
                    status=drf_status.HTTP_400_BAD_REQUEST,
                )

            disponivel = item_peca.quantidade - item_peca.quantidade_utilizada
            if entrada['quantidade'] > disponivel:
                return Response(
                    {
                        'erro': (
                            f"Quantidade indisponível para '{item_peca.peca.nome}'. "
                            f"Disponível: {disponivel}, solicitado: {entrada['quantidade']}"
                        )
                    },
                    status=drf_status.HTTP_400_BAD_REQUEST,
                )
            consumos_a_criar.append((item_peca, entrada['quantidade']))

        for item_peca, quantidade in consumos_a_criar:
            ConsumoItemServico.objects.create(
                item_servico_os=item,
                item_peca_os=item_peca,
                quantidade=quantidade,
            )
            ItemPecaOS.objects.filter(pk=item_peca.pk).update(
                quantidade_utilizada=F('quantidade_utilizada') + quantidade
            )

        ItemServicoOS.objects.filter(pk=item.pk).update(
            status='EM_EXECUCAO',
            data_inicio=data_inicio,
        )
        item.refresh_from_db()

        os = item.ordem_servico
        if os.status == 'AGUARDANDO':
            nenhum_outro_ativo = not ItemServicoOS.objects.filter(
                ordem_servico=os, status__in=['EM_EXECUCAO', 'CONCLUIDO']
            ).exclude(pk=item.pk).exists()
            if nenhum_outro_ativo:
                OrdemServico.objects.filter(pk=os.pk).update(
                    status='EXECUCAO',
                    data_inicio_execucao=timezone.now(),
                )

        return Response(self.get_serializer(item).data)

    @action(detail=True, methods=['post'])
    def finalizar(self, request, os_pk=None, pk=None):
        item = self.get_object()

        if item.status != 'EM_EXECUCAO':
            return Response(
                {'erro': 'Serviço não está em execução'},
                status=drf_status.HTTP_400_BAD_REQUEST,
            )

        serializer = FinalizarServicoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data_finalizacao = serializer.validated_data.get('data_finalizacao') or timezone.now()
        os = item.ordem_servico

        ainda_ha_ativo = ItemServicoOS.objects.filter(
            ordem_servico=os, status__in=['PENDENTE', 'EM_EXECUCAO']
        ).exclude(pk=item.pk).exists()

        if not ainda_ha_ativo:
            pecas_nao_utilizadas = os.itens_pecas.exclude(
                quantidade_utilizada=F('quantidade')
            ).exists()
            if pecas_nao_utilizadas:
                return Response(
                    {'erro': 'Existem peças não utilizadas na OS'},
                    status=drf_status.HTTP_400_BAD_REQUEST,
                )

        ItemServicoOS.objects.filter(pk=item.pk).update(
            status='CONCLUIDO',
            data_finalizacao=data_finalizacao,
        )
        item.refresh_from_db()

        # item is already CONCLUIDO in the DB (updated above), so no need to exclude(pk=item.pk)
        todos_concluidos = not ItemServicoOS.objects.filter(
            ordem_servico=os
        ).exclude(status='CONCLUIDO').exists()

        if todos_concluidos:
            OrdemServico.objects.filter(pk=os.pk).update(
                status='FINALIZADA',
                data_finalizacao=data_finalizacao,
            )

        return Response(self.get_serializer(item).data)
