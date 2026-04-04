from django.test import TestCase
from .models import Cliente, Veiculo, OrdemServico, Peca, ItemPecaOS

class OrdemServicoTest(TestCase):
    def setUp(self):
        # Setup básico que já validamos que funciona
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
        """Testa se adicionar uma peça de 90.00 atualiza o total da OS para 90.00"""
        ItemPecaOS.objects.create(os=self.os, peca=self.peca, quantidade=1)
        
        self.os.refresh_from_db()
        
        # Se a OS estava em 0 e add uma peça de 90, o total deve ser 90
        self.assertEqual(float(self.os.valor_total), 90.00)

    def test_baixa_estoque_automatica(self):
        """Testa se o estoque cai de 10 para 7 ao usar 3 peças"""
        ItemPecaOS.objects.create(os=self.os, peca=self.peca, quantidade=3)
        self.peca.refresh_from_db()
        
        # 10 - 3 = 7
        self.assertEqual(self.peca.estoque_atual, 7)