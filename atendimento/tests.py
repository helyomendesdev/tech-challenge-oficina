from django.test import TestCase
from .models import Cliente, Veiculo, OrdemServico, Peca, ItemPecaOS

class OrdemServicoTest(TestCase):
    def setUp(self):
        # O setUp funciona como um "Global Arrange"
        self.cliente = Cliente.objects.create(nome="Hélio Teste", email="helio@teste.com")
        self.veiculo = Veiculo.objects.create(
            modelo="Golf GTI", 
            placa="GTI2026", 
            ano=2026, 
            cliente=self.cliente
        )
        self.os = OrdemServico.objects.create(cliente=self.cliente, veiculo=self.veiculo)
        self.peca = Peca.objects.create(nome="Pastilha", valor_unitario=90.00, estoque_atual=10)

    def test_calculo_total_os_com_peca(self):
        # 1. Arrange (O setup já criou a OS e a Peça)
        quantidade = 1
        valor_esperado = 90.00

        # 2. Act (Executa a ação de adicionar a peça)
        ItemPecaOS.objects.create(os=self.os, peca=self.peca, quantidade=quantidade)
        self.os.refresh_from_db()
        
        # 3. Assert (Verifica o resultado)
        self.assertEqual(float(self.os.valor_total), valor_esperado)

    def test_baixa_estoque_automatica(self):
        # 1. Arrange
        quantidade_usada = 3
        estoque_esperado = 7 # 10 inicial - 3 usado
        
        # 2. Act
        ItemPecaOS.objects.create(os=self.os, peca=self.peca, quantidade=quantidade_usada)
        self.peca.refresh_from_db()
        
        # 3. Assert
        self.assertEqual(self.peca.estoque_atual, estoque_esperado)