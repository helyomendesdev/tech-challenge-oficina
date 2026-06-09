from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.exceptions import ValidationError
from rest_framework import viewsets, mixins, status as drf_status
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from .models import Cliente, Veiculo, OrdemServico, Servico, Peca, ItemPecaOS, ItemServicoOS
from .serializers import (
    ClienteSerializer,
    VeiculoSerializer,
    OrdemServicoSerializer,
    OrdemServicoPublicaSerializer,
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
from django.db.models import Q
import re
from atendimento.application.dtos import (
    FinalizarServicoInputDTO,
    IniciarServicoInputDTO,
)
from atendimento.exceptions import resposta_erro
from atendimento.domain.enums import StatusItemServico
from atendimento.domain.exceptions import DomainError, OrdemServicoNaoEncontradaError
from atendimento.domain.value_objects import DocumentoCliente, PlacaVeiculo
from atendimento.infrastructure.factories import (
    build_finalizar_servico_use_case,
    build_iniciar_servico_use_case,
)


def _bad_request(mensagem):
    """Resposta padrao para erros de regra em actions legadas."""
    return Response(
        resposta_erro(mensagem, drf_status.HTTP_400_BAD_REQUEST),
        status=drf_status.HTTP_400_BAD_REQUEST,
    )


def _not_found(mensagem):
    """Resposta padrao para recursos inacessiveis ou inexistentes."""
    return Response(
        resposta_erro(mensagem, drf_status.HTTP_404_NOT_FOUND),
        status=drf_status.HTTP_404_NOT_FOUND,
    )


def _normalizar_identificador_publico(identificador):
    """Normaliza placa/CPF/CNPJ usando value objects quando possivel."""
    valor = str(identificador or "").strip()
    documento_digits = re.sub(r'\D', '', valor)
    placas = {valor.upper()}
    documentos = {valor, documento_digits, _formatar_documento(documento_digits)}

    try:
        placas.add(PlacaVeiculo(valor).valor)
    except DomainError:
        pass

    try:
        documentos.add(DocumentoCliente(valor).valor)
    except DomainError:
        pass

    return {
        "placas": {placa for placa in placas if placa},
        "documentos": {documento for documento in documentos if documento},
    }


def _formatar_documento(documento):
    """Retorna CPF/CNPJ pontuado para compatibilidade com registros legados."""
    if len(documento) == 11:
        return (
            f"{documento[:3]}.{documento[3:6]}."
            f"{documento[6:9]}-{documento[9:]}"
        )
    if len(documento) == 14:
        return (
            f"{documento[:2]}.{documento[2:5]}.{documento[5:8]}/"
            f"{documento[8:12]}-{documento[12:]}"
        )
    return ""


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
        if (
            user
            and user.is_authenticated
            and not (user.is_staff or user.is_superuser)
        ):
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

    def _execute_transition(self, method_name):
        """Ponte temporaria para transicoes ainda mantidas no model legado."""
        ordem_servico = self.get_object()
        try:
            getattr(ordem_servico, method_name)()
        except ValidationError as exc:
            return _bad_request(' '.join(exc.messages))
        return Response(self.get_serializer(ordem_servico).data)

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
        responses={200: OrdemServicoPublicaSerializer},
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
                resposta_erro(
                    "Informe a placa ou o CPF/CNPJ para consulta.",
                    drf_status.HTTP_400_BAD_REQUEST,
                ),
                status=drf_status.HTTP_400_BAD_REQUEST,
            )

        identificadores = _normalizar_identificador_publico(identificador)
        os_list = (
            OrdemServico.objects
            .select_related('cliente', 'veiculo')
            .prefetch_related('itens_servico__servico', 'itens_pecas__peca')
            .filter(
                Q(veiculo__placa__in=identificadores["placas"]) |
                Q(cliente__documento__in=identificadores["documentos"])
            )
            .order_by('-data_abertura')
        )

        if not os_list.exists():
            return Response(
                resposta_erro(
                    "Nenhuma Ordem de Serviço encontrada para este identificador.",
                    drf_status.HTTP_404_NOT_FOUND,
                ),
                status=drf_status.HTTP_404_NOT_FOUND,
            )

        page = self.paginate_queryset(os_list)
        if page is not None:
            serializer = OrdemServicoPublicaSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = OrdemServicoPublicaSerializer(os_list, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='metricas')
    def metricas(self, request, pk=None):
        ordem_servico = self.get_object()
        qs = (
            ItemServicoOS.objects
            .filter(ordem_servico=ordem_servico)
            .select_related('servico')
            .prefetch_related('consumos__item_peca_os__peca')
            .order_by('id')
        )
        servico_id = request.query_params.get('servico')
        if servico_id is not None:
            try:
                qs = qs.filter(servico_id=int(servico_id))
            except (ValueError, TypeError):
                return Response(
                    resposta_erro(
                        "'servico' deve ser um inteiro.",
                        drf_status.HTTP_400_BAD_REQUEST,
                    ),
                    status=drf_status.HTTP_400_BAD_REQUEST,
                )
        serializer = MetricasItemServicoSerializer(qs, many=True)
        return Response(serializer.data)

    @extend_schema(description="Inicia o diagnóstico da OS. Transição: RECEBIDA → DIAGNOSTICO.")
    @action(detail=True, methods=['post'], url_path='iniciar-diagnostico')
    def iniciar_diagnostico(self, request, pk=None):
        return self._execute_transition('iniciar_diagnostico')

    @extend_schema(description="Finaliza o diagnóstico e aguarda aprovação do orçamento. Transição: DIAGNOSTICO → AGUARDANDO.")
    @action(detail=True, methods=['post'], url_path='finalizar-diagnostico')
    def finalizar_diagnostico(self, request, pk=None):
        return self._execute_transition('finalizar_diagnostico')

    @extend_schema(description="Registra aprovação do orçamento pelo cliente. Transição: AGUARDANDO → EXECUCAO.")
    @action(detail=True, methods=['post'], url_path='aprovar-orcamento')
    def aprovar_orcamento(self, request, pk=None):
        return self._execute_transition('aprovar_orcamento')

    @extend_schema(description="Registra recusa do orçamento; OS retorna para diagnóstico. Transição: AGUARDANDO → DIAGNOSTICO.")
    @action(detail=True, methods=['post'], url_path='recusar-orcamento')
    def recusar_orcamento(self, request, pk=None):
        return self._execute_transition('recusar_orcamento')

    @extend_schema(description="Finaliza a OS quando todos os serviços estão concluídos. Transição: EXECUCAO → FINALIZADA.")
    @action(detail=True, methods=['post'], url_path='finalizar')
    def finalizar(self, request, pk=None):
        return self._execute_transition('finalizar')

    @extend_schema(description="Registra entrega do veículo ao cliente. Transição: FINALIZADA → ENTREGUE.")
    @action(detail=True, methods=['post'], url_path='entregar')
    def entregar(self, request, pk=None):
        return self._execute_transition('entregar')

    @extend_schema(description="Registra desistência do cliente. Transição: AGUARDANDO → CANCELADA.")
    @action(detail=True, methods=['post'], url_path='cancelar')
    def cancelar(self, request, pk=None):
        return self._execute_transition('cancelar')


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

    def _get_ordem_servico(self):
        user = self.request.user
        queryset = OrdemServico.objects.all()
        if not (user.is_staff or user.is_superuser):
            queryset = queryset.filter(created_by=user)
        return get_object_or_404(queryset, pk=self.kwargs['os_pk'])

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return ItemServicoOS.objects.none()

        ordem_servico = self._get_ordem_servico()
        return ItemServicoOS.objects.filter(
            ordem_servico=ordem_servico
        ).select_related('servico', 'ordem_servico').order_by('id')

    def perform_create(self, serializer):
        ordem_servico = self._get_ordem_servico()
        serializer.save(ordem_servico=ordem_servico, created_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status != StatusItemServico.PENDENTE.value:
            return _bad_request(
                'Não é possível remover serviço em execução ou concluído'
            )
        return super().destroy(request, *args, **kwargs)

    def _usuario_contexto(self):
        user = self.request.user
        return {
            'usuario_id': user.id if user and user.is_authenticated else None,
            'usuario_is_staff': bool(
                user and user.is_authenticated and (user.is_staff or user.is_superuser)
            ),
        }

    @action(detail=True, methods=['post'])
    def iniciar(self, request, os_pk=None, pk=None):
        serializer = IniciarServicoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        input_dto = IniciarServicoInputDTO(
            ordem_servico_id=os_pk,
            item_servico_id=pk,
            data_inicio=(
                serializer.validated_data.get('data_inicio') or timezone.now()
            ),
            pecas=serializer.validated_data.get('pecas', []),
            **self._usuario_contexto(),
        )

        try:
            item = build_iniciar_servico_use_case().execute(input_dto)
        except OrdemServicoNaoEncontradaError as exc:
            return _not_found(str(exc))
        except DomainError as exc:
            return _bad_request(str(exc))

        return Response(self.get_serializer(item).data)

    @action(detail=True, methods=['post'])
    def finalizar(self, request, os_pk=None, pk=None):
        serializer = FinalizarServicoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        input_dto = FinalizarServicoInputDTO(
            ordem_servico_id=os_pk,
            item_servico_id=pk,
            data_finalizacao=(
                serializer.validated_data.get('data_finalizacao') or timezone.now()
            ),
            **self._usuario_contexto(),
        )

        try:
            item = build_finalizar_servico_use_case().execute(input_dto)
        except OrdemServicoNaoEncontradaError as exc:
            return _not_found(str(exc))
        except DomainError as exc:
            return _bad_request(str(exc))

        return Response(self.get_serializer(item).data)
