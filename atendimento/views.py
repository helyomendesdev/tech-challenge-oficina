from rest_framework import viewsets
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter # Adicionado OpenApiParameter
from .models import Cliente, Veiculo, OrdemServico, Servico, Peca, ItemPecaOS
from .serializers import (
    ClienteSerializer, 
    VeiculoSerializer, 
    OrdemServicoSerializer, 
    ServicoSerializer, 
    PecaSerializer,
    ItemPecaOSSerializer
)
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny 
from rest_framework.response import Response
from django.db.models import Q

@extend_schema_view(
    list=extend_schema(description="Retorna a lista de todos os clientes cadastrados."),
    create=extend_schema(description="Cadastra um novo cliente no sistema da oficina.")
)
class ClienteViewSet(viewsets.ModelViewSet):
    queryset = Cliente.objects.all()
    serializer_class = ClienteSerializer

class VeiculoViewSet(viewsets.ModelViewSet):
    queryset = Veiculo.objects.all()
    serializer_class = VeiculoSerializer

class ServicoViewSet(viewsets.ModelViewSet):
    queryset = Servico.objects.all()
    serializer_class = ServicoSerializer

@extend_schema_view(
    list=extend_schema(description="Lista todas as peças em estoque."),
    retrieve=extend_schema(description="Busca detalhes de uma peça específica e seu saldo atual.")
)
class PecaViewSet(viewsets.ModelViewSet):
    queryset = Peca.objects.all()
    serializer_class = PecaSerializer

@extend_schema_view(
    list=extend_schema(description="Lista todas as Ordens de Serviço. [cite: 39]"),
    create=extend_schema(description="Abre uma nova OS. O valor total inicial será calculado automaticamente. [cite: 19, 23]"),
    retrieve=extend_schema(description="Busca detalhes da OS, incluindo o valor total atualizado (Serviços + Peças).")
)
class OrdemServicoViewSet(viewsets.ModelViewSet):
    queryset = OrdemServico.objects.all()
    serializer_class = OrdemServicoSerializer

    # Endpoint para o cliente acompanhar o progresso (Requisito 33 do PDF) [cite: 33]
    @extend_schema(
        description="Permite que o cliente consulte o status da OS usando a Placa ou CPF/CNPJ. [cite: 33]",
        parameters=[
            OpenApiParameter(
                name='identificador', 
                description='Placa do veículo ou CPF/CNPJ do cliente [cite: 20, 21]', 
                required=True, 
                type=str
            )
        ],
        responses={200: OrdemServicoSerializer},
        auth=[] # Acesso público para o cliente [cite: 33]
    )
    @action(detail=False, methods=['get'], url_path='consulta-cliente', permission_classes=[AllowAny])
    def consulta_cliente(self, request):
        identificador = request.query_params.get('identificador')
        
        if not identificador:
            return Response({"erro": "Informe a placa ou o CPF/CNPJ para consulta."}, status=400)

        # Busca por Placa do Veículo ou Documento do Cliente (Requisitos 20 e 21) [cite: 20, 21]
        os_cliente = OrdemServico.objects.filter(
            Q(veiculo__placa=identificador.upper()) | 
            Q(cliente__documento=identificador)
        ).order_by('-data_abertura').first()

        if not os_cliente:
            return Response({"erro": "Nenhuma Ordem de Serviço encontrada para este identificador."}, status=404)

        serializer = self.get_serializer(os_cliente)
        return Response(serializer.data)

@extend_schema_view(
    create=extend_schema(description="Adiciona uma peça à OS. Isso aciona a baixa automática no estoque e recalcula o total da OS. [cite: 38]")
)
class ItemPecaOSViewSet(viewsets.ModelViewSet):
    queryset = ItemPecaOS.objects.all()
    serializer_class = ItemPecaOSSerializer