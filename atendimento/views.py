from rest_framework import viewsets
# 1. Importação da ferramenta de documentação
from drf_spectacular.utils import extend_schema, extend_schema_view
from .models import Cliente, Veiculo, OrdemServico, Servico, Peca, ItemPecaOS
from .serializers import (
    ClienteSerializer, 
    VeiculoSerializer, 
    OrdemServicoSerializer, 
    ServicoSerializer, 
    PecaSerializer,
    ItemPecaOSSerializer
)

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
    list=extend_schema(description="Lista todas as Ordens de Serviço."),
    create=extend_schema(description="Abre uma nova OS. O valor total inicial será calculado automaticamente."),
    retrieve=extend_schema(description="Busca detalhes da OS, incluindo o valor total atualizado (Serviços + Peças).")
)
class OrdemServicoViewSet(viewsets.ModelViewSet):
    queryset = OrdemServico.objects.all()
    serializer_class = OrdemServicoSerializer

@extend_schema_view(
    create=extend_schema(description="Adiciona uma peça à OS. Isso aciona a baixa automática no estoque e recalcula o total da OS.")
)
class ItemPecaOSViewSet(viewsets.ModelViewSet):
    queryset = ItemPecaOS.objects.all()
    serializer_class = ItemPecaOSSerializer