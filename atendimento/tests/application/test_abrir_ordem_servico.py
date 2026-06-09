from atendimento.tests.phase2_helpers import *


class AbrirOrdemServicoUseCaseFlowTest(Phase2TestBase):

    def test_abertura_completa_cria_os_itens_baixa_estoque_uma_vez_e_totaliza(self):
        servico = self.criar_servico(self.usuario, valor="150.00")
        peca = self.criar_peca(self.usuario, valor="35.50", estoque=10)

        response = self.api(self.usuario).post(
            self.ABRIR_URL,
            self.payload_abertura(servico, peca),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ordem_servico = OrdemServico.objects.get(id=response.data["ordem_servico_id"])
        peca.refresh_from_db()

        self.assertEqual(ordem_servico.status, StatusOrdemServico.RECEBIDA.value)
        self.assertEqual(ordem_servico.created_by, self.usuario)
        self.assertEqual(ordem_servico.cliente.documento, "52998224725")
        self.assertEqual(ordem_servico.veiculo.placa, "ABC1D23")
        self.assertEqual(ordem_servico.itens_servico.count(), 1)
        self.assertEqual(ordem_servico.itens_pecas.count(), 1)
        self.assertEqual(peca.estoque_atual, 8)
        self.assertEqual(ordem_servico.valor_total, Decimal("221.00"))
        self.assertEqual(response.data["valor_total"], "221.00")
        self.assertEqual(response.data["status"], StatusOrdemServico.RECEBIDA.value)

    def test_abertura_valida_documento_invalido(self):
        servico = self.criar_servico(self.usuario)
        peca = self.criar_peca(self.usuario)
        payload = self.payload_abertura(servico, peca, documento="12345678900")

        response = self.api(self.usuario).post(self.ABRIR_URL, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(OrdemServico.objects.count(), 0)

    def test_abertura_valida_placa_invalida(self):
        servico = self.criar_servico(self.usuario)
        peca = self.criar_peca(self.usuario)
        payload = self.payload_abertura(servico, peca, placa="ABC123")

        response = self.api(self.usuario).post(self.ABRIR_URL, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(OrdemServico.objects.count(), 0)

    def test_abertura_valida_quantidade_negativa(self):
        servico = self.criar_servico(self.usuario)
        peca = self.criar_peca(self.usuario)
        payload = self.payload_abertura(servico, peca, quantidade=-1)

        response = self.api(self.usuario).post(self.ABRIR_URL, payload, format="json")

        peca.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(peca.estoque_atual, 10)
        self.assertEqual(OrdemServico.objects.count(), 0)

    def test_abertura_falha_para_servico_inexistente(self):
        servico = self.criar_servico(self.usuario)
        peca = self.criar_peca(self.usuario)
        payload = self.payload_abertura(servico, peca)
        payload["servicos"] = [999999]

        response = self.api(self.usuario).post(self.ABRIR_URL, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(OrdemServico.objects.count(), 0)

    def test_abertura_falha_para_peca_inexistente(self):
        servico = self.criar_servico(self.usuario)
        peca = self.criar_peca(self.usuario)
        payload = self.payload_abertura(servico, peca)
        payload["pecas"] = [{"peca_id": 999999, "quantidade": 2}]

        response = self.api(self.usuario).post(self.ABRIR_URL, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(OrdemServico.objects.count(), 0)

    def test_abertura_nao_permite_servico_de_outro_usuario(self):
        servico_outro_usuario = self.criar_servico(self.outro_usuario)
        peca = self.criar_peca(self.usuario)

        response = self.api(self.usuario).post(
            self.ABRIR_URL,
            self.payload_abertura(servico_outro_usuario, peca),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(OrdemServico.objects.count(), 0)

    def test_abertura_nao_permite_peca_de_outro_usuario(self):
        servico = self.criar_servico(self.usuario)
        peca_outro_usuario = self.criar_peca(self.outro_usuario)

        response = self.api(self.usuario).post(
            self.ABRIR_URL,
            self.payload_abertura(servico, peca_outro_usuario),
            format="json",
        )

        peca_outro_usuario.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(peca_outro_usuario.estoque_atual, 10)
        self.assertEqual(OrdemServico.objects.count(), 0)

    def test_abertura_nao_reutiliza_cliente_de_outro_usuario(self):
        self.criar_cliente(
            usuario=self.outro_usuario,
            documento="11144477735",
            nome="Cliente de outro usuario",
        )
        servico = self.criar_servico(self.usuario)
        peca = self.criar_peca(self.usuario)

        response = self.api(self.usuario).post(
            self.ABRIR_URL,
            self.payload_abertura(
                servico,
                peca,
                documento="111.444.777-35",
                placa="CLI1E23",
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(OrdemServico.objects.count(), 0)

    def test_abertura_staff_pode_usar_servico_e_peca_de_outro_usuario(self):
        servico = self.criar_servico(self.usuario, valor="120.00")
        peca = self.criar_peca(self.usuario, valor="40.00", estoque=5)

        response = self.api(self.staff).post(
            self.ABRIR_URL,
            self.payload_abertura(
                servico,
                peca,
                documento="935.411.347-80",
                placa="STF1A23",
                quantidade=2,
            ),
            format="json",
        )

        peca.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ordem_servico = OrdemServico.objects.get(
            id=response.data["ordem_servico_id"]
        )
        self.assertEqual(ordem_servico.created_by, self.staff)
        self.assertEqual(peca.estoque_atual, 3)
        self.assertEqual(ordem_servico.valor_total, Decimal("200.00"))

    def test_abertura_use_case_notifica_orcamento_via_port(self):
        servico = self.criar_servico(self.usuario, valor="120.00")
        peca = self.criar_peca(self.usuario, valor="40.00", estoque=5)
        notification_adapter = SpyNotificationAdapter()
        use_case = AbrirOrdemServicoUseCase(
            cliente_repository=DjangoClienteRepository(),
            veiculo_repository=DjangoVeiculoRepository(),
            servico_repository=DjangoServicoRepository(),
            ordem_servico_repository=DjangoOrdemServicoRepository(),
            transaction_manager=DjangoTransactionManager(),
            notification_port=notification_adapter,
        )

        output = use_case.execute(
            AbrirOrdemServicoInputDTO(
                cliente=ClienteInputDTO(
                    nome="Helio Teste",
                    documento="52998224725",
                    email="helio@example.com",
                    telefone="11999999999",
                ),
                veiculo=VeiculoInputDTO(
                    placa="ABC1D23",
                    marca="Volkswagen",
                    modelo="Golf",
                    ano=2024,
                ),
                servicos=[servico.id],
                pecas=[
                    PecaOrdemServicoInputDTO(
                        peca_id=peca.id,
                        quantidade=2,
                    )
                ],
                usuario_id=self.usuario.id,
            )
        )

        self.assertEqual(len(notification_adapter.orcamentos), 1)
        notificacao = notification_adapter.orcamentos[0]
        self.assertEqual(notificacao["ordem_servico_id"], output.ordem_servico_id)
        self.assertEqual(notificacao["email"], "helio@example.com")
        self.assertEqual(notificacao["valor_total"], Decimal("200.00"))

    def test_abertura_falha_para_estoque_insuficiente_sem_baixar_estoque(self):
        servico = self.criar_servico(self.usuario)
        peca = self.criar_peca(self.usuario, estoque=1)
        payload = self.payload_abertura(servico, peca, quantidade=2)

        response = self.api(self.usuario).post(self.ABRIR_URL, payload, format="json")

        peca.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(peca.estoque_atual, 1)
        self.assertEqual(OrdemServico.objects.count(), 0)

    def test_abertura_falha_quando_placa_ja_pertence_a_outro_cliente(self):
        cliente_existente = self.criar_cliente(
            usuario=self.outro_usuario,
            documento="11144477735",
            nome="Outro Cliente",
        )
        self.criar_veiculo(
            cliente_existente,
            usuario=self.outro_usuario,
            placa="ABC1D23",
        )
        servico = self.criar_servico(self.usuario)
        peca = self.criar_peca(self.usuario)

        response = self.api(self.usuario).post(
            self.ABRIR_URL,
            self.payload_abertura(servico, peca),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(OrdemServico.objects.count(), 0)
