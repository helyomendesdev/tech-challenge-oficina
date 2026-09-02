"""Testes de emissão de custom events de observabilidade.

Valida que os 3 use cases emitem eventos corretos com:
- statusAnterior/statusNovo válidos
- duracaoStatusSegundos corresponde ao tempo real
- ENTREGUE produz CONCLUSAO (não TRANSICAO)
- Erros de domínio produzem FALHA
- Adapter preenche traceId e service.environment
- Adapter não quebra sem newrelic
"""

import json
from io import StringIO
from unittest.mock import Mock, patch, MagicMock

from django.test import SimpleTestCase, TestCase
from datetime import datetime, timezone, timedelta
import pytest

from atendimento.application.dtos import (
    AbrirOrdemServicoInputDTO,
    AbrirOrdemServicoOutputDTO,
    AtualizarStatusNotificacaoInputDTO,
    AtualizarStatusNotificacaoOutputDTO,
    ProcessarRespostaOrcamentoInputDTO,
    ProcessarRespostaOrcamentoOutputDTO,
)
from atendimento.application.use_cases.abrir_ordem_servico import AbrirOrdemServicoUseCase
from atendimento.application.use_cases.atualizar_status_por_notificacao import (
    AtualizarStatusPorNotificacaoUseCase,
)
from atendimento.application.use_cases.processar_resposta_orcamento import (
    ProcessarRespostaOrcamentoUseCase,
)
from atendimento.domain.enums import DecisaoOrcamento, StatusOrdemServico
from atendimento.domain.exceptions import OrcamentoNaoPodeSerProcessadoError, DomainError
from atendimento.infrastructure.observabilidade_adapter import ObservabilidadeAdapter
from atendimento.infrastructure.observabilidade_adapter_noop import ObservabilidadeAdapterNoop


class TestAbrirOrdemServicoEvento:
    """Testes de emissão de evento ABERTURA no use case abrir_ordem_servico."""

    def test_evento_abertura_emitido_apos_criacao(self):
        """Valida que ABERTURA é emitido com statusAnterior=None, statusNovo=RECEBIDA."""
        # Mock do port de observabilidade
        obs_port = Mock()

        # Mock dos repositories
        cliente_repo = Mock()
        veiculo_repo = Mock()
        servico_repo = Mock()
        ordem_repo = Mock()
        transaction_manager = Mock()

        # Simular sucesso na criação
        cliente = {'id': 1, 'email': 'test@test.com'}
        veiculo = {'id': 1}
        ordem_criada = {
            'id': 100,
            'status': StatusOrdemServico.RECEBIDA.value,
            'valor_total': 1000.0,
        }

        cliente_repo.get_or_create.return_value = cliente
        veiculo_repo.get_or_create.return_value = veiculo
        servico_repo.get_by_ids.return_value = []
        ordem_repo.create.return_value = ordem_criada
        ordem_repo.adicionar_servicos.return_value = None
        ordem_repo.adicionar_pecas.return_value = None
        ordem_repo.recalcular_total.return_value = ordem_criada
        transaction_manager.atomic.return_value.__enter__ = Mock(return_value=None)
        transaction_manager.atomic.return_value.__exit__ = Mock(return_value=None)

        # Monkeypatch trace

        # Executar use case
        uc = AbrirOrdemServicoUseCase(
            cliente_repository=cliente_repo,
            veiculo_repository=veiculo_repo,
            servico_repository=servico_repo,
            ordem_servico_repository=ordem_repo,
            transaction_manager=transaction_manager,
            observabilidade_port=obs_port,
        )

        input_dto = AbrirOrdemServicoInputDTO(
            cliente={'nome': 'Test', 'documento': '12345678901'},
            veiculo={'placa': 'ABC1234', 'marca': 'Fiat', 'modelo': 'Uno', 'ano': 2020},
            servicos=[],
            pecas=[],
            usuario_id=1,
            usuario_is_staff=True,
        )

        result = uc.execute(input_dto)

        # Validar que o evento foi registrado
        obs_port.registrar_evento_ordem_servico.assert_called_once()
        evento = obs_port.registrar_evento_ordem_servico.call_args[0][0]

        assert evento['evento'] == 'ABERTURA'
        assert evento['osId'] == 100
        assert evento['statusAnterior'] is None
        assert evento['statusNovo'] == StatusOrdemServico.RECEBIDA.value
        assert evento['duracaoStatusSegundos'] == 0.0
        assert evento['erroTipo'] is None
        # O traceId e responsabilidade do adapter: use case nao conhece infra.
        assert 'traceId' not in evento
        # A spec (§5.4) proibe `unidade` no evento: o campo nao existe no modelo
        # nem na API, e um valor fixo faria D1 facetar tudo numa unidade inventada.
        assert 'unidade' not in evento


class TestAtualizarStatusPorNotificacaoEvento:
    """Testes de emissão de eventos TRANSICAO/CONCLUSAO no use case atualizar_status."""

    def test_evento_transicao_emitido(self):
        """Valida que TRANSICAO é emitido com statusAnterior/statusNovo corretos."""
        obs_port = Mock()
        ordem_repo = Mock()
        transaction_manager = Mock()

        # Simular OS com status anterior
        agora = datetime.now(timezone.utc)
        data_ultima_transicao = agora - timedelta(minutes=5)

        ordem_antiga = {
            'id': 100,
            'status': StatusOrdemServico.DIAGNOSTICO.value,
            'data_abertura': agora - timedelta(hours=1),
            'data_ultima_transicao': data_ultima_transicao,
            'data_inicio_execucao': None,
            'data_finalizacao': None,
        }

        ordem_nova = {
            **ordem_antiga,
            'status': StatusOrdemServico.AGUARDANDO.value,
            'data_ultima_transicao': agora,
        }

        ordem_repo.get_by_id_for_user.return_value = ordem_antiga
        ordem_repo.save.return_value = ordem_nova
        transaction_manager.atomic.return_value.__enter__ = Mock(return_value=None)
        transaction_manager.atomic.return_value.__exit__ = Mock(return_value=None)

        with patch('atendimento.application.use_cases.atualizar_status_por_notificacao.datetime') as mock_dt:
            mock_dt.now.return_value = agora
            mock_dt.timezone = timezone

            uc = AtualizarStatusPorNotificacaoUseCase(
                ordem_servico_repository=ordem_repo,
                transaction_manager=transaction_manager,
                observabilidade_port=obs_port,
            )

            input_dto = AtualizarStatusNotificacaoInputDTO(
                ordem_servico_id=100,
                novo_status=StatusOrdemServico.AGUARDANDO.value,
                origem='notificacao_simulada',
                observacao='Transição via teste',
                usuario_id=1,
                usuario_is_staff=True,
            )

            result = uc.execute(input_dto)

        # Validar evento TRANSICAO
        obs_port.registrar_evento_ordem_servico.assert_called_once()
        evento = obs_port.registrar_evento_ordem_servico.call_args[0][0]

        assert evento['evento'] == 'TRANSICAO'
        assert evento['osId'] == 100
        assert evento['statusAnterior'] == StatusOrdemServico.DIAGNOSTICO.value
        assert evento['statusNovo'] == StatusOrdemServico.AGUARDANDO.value
        assert evento['duracaoStatusSegundos'] > 0  # Tempo passado
        assert evento['erroTipo'] is None
        # O traceId e responsabilidade do adapter: use case nao conhece infra.
        assert 'traceId' not in evento

    def test_evento_conclusao_emitido_para_entregue(self):
        """Valida que CONCLUSAO é emitido quando status novo é ENTREGUE."""
        obs_port = Mock()
        ordem_repo = Mock()
        transaction_manager = Mock()

        agora = datetime.now(timezone.utc)
        ordem_antiga = {
            'id': 100,
            'status': StatusOrdemServico.FINALIZADA.value,
            'data_abertura': agora - timedelta(hours=10),
            'data_ultima_transicao': agora - timedelta(minutes=30),
            'data_inicio_execucao': agora - timedelta(hours=9),
            'data_finalizacao': agora - timedelta(minutes=31),
        }

        ordem_nova = {
            **ordem_antiga,
            'status': StatusOrdemServico.ENTREGUE.value,
            'data_ultima_transicao': agora,
        }

        ordem_repo.get_by_id_for_user.return_value = ordem_antiga
        ordem_repo.save.return_value = ordem_nova
        transaction_manager.atomic.return_value.__enter__ = Mock(return_value=None)
        transaction_manager.atomic.return_value.__exit__ = Mock(return_value=None)

        with patch('atendimento.application.use_cases.atualizar_status_por_notificacao.datetime') as mock_dt:
            mock_dt.now.return_value = agora
            mock_dt.timezone = timezone

            uc = AtualizarStatusPorNotificacaoUseCase(
                ordem_servico_repository=ordem_repo,
                transaction_manager=transaction_manager,
                observabilidade_port=obs_port,
            )

            input_dto = AtualizarStatusNotificacaoInputDTO(
                ordem_servico_id=100,
                novo_status=StatusOrdemServico.ENTREGUE.value,
                origem='notificacao_simulada',
                observacao='Conclusão via teste',
                usuario_id=1,
                usuario_is_staff=True,
            )

            result = uc.execute(input_dto)

        # Validar evento CONCLUSAO (não TRANSICAO)
        obs_port.registrar_evento_ordem_servico.assert_called_once()
        evento = obs_port.registrar_evento_ordem_servico.call_args[0][0]

        assert evento['evento'] == 'CONCLUSAO'
        assert evento['statusNovo'] == StatusOrdemServico.ENTREGUE.value


class TestProcessarRespostaOrcamentoEvento:
    """Testes de emissão de eventos TRANSICAO/FALHA no use case processar_orcamento."""

    def test_evento_transicao_aprovacao(self):
        """Valida TRANSICAO quando orcamento é aprovado."""
        obs_port = Mock()
        ordem_repo = Mock()
        transaction_manager = Mock()

        agora = datetime.now(timezone.utc)
        ordem_antiga = {
            'id': 100,
            'status': StatusOrdemServico.AGUARDANDO.value,
            'data_abertura': agora - timedelta(hours=5),
            'data_ultima_transicao': agora - timedelta(minutes=15),
            'data_inicio_execucao': None,
        }

        ordem_nova = {
            **ordem_antiga,
            'status': StatusOrdemServico.EXECUCAO.value,
            'data_ultima_transicao': agora,
            'data_inicio_execucao': agora,
        }

        ordem_repo.get_by_id_for_user.return_value = ordem_antiga
        ordem_repo.save.return_value = ordem_nova
        transaction_manager.atomic.return_value.__enter__ = Mock(return_value=None)
        transaction_manager.atomic.return_value.__exit__ = Mock(return_value=None)

        with patch('atendimento.application.use_cases.processar_resposta_orcamento.datetime') as mock_dt:
            mock_dt.now.return_value = agora
            mock_dt.timezone = timezone

            uc = ProcessarRespostaOrcamentoUseCase(
                ordem_servico_repository=ordem_repo,
                transaction_manager=transaction_manager,
                observabilidade_port=obs_port,
            )

            input_dto = ProcessarRespostaOrcamentoInputDTO(
                ordem_servico_id=100,
                decisao=DecisaoOrcamento.APROVADO.value,
                origem='simulador_orcamento',
                token='dummy',
                usuario_id=1,
                usuario_is_staff=True,
            )

            result = uc.execute(input_dto)

        # Validar evento TRANSICAO
        assert obs_port.registrar_evento_ordem_servico.call_count == 1
        evento = obs_port.registrar_evento_ordem_servico.call_args[0][0]

        assert evento['evento'] == 'TRANSICAO'
        assert evento['statusAnterior'] == StatusOrdemServico.AGUARDANDO.value
        assert evento['statusNovo'] == StatusOrdemServico.EXECUCAO.value
        assert evento['duracaoStatusSegundos'] >= 0

    def test_evento_falha_orcamento_nao_processavel(self):
        """Valida FALHA quando orcamento não pode ser processado."""
        obs_port = Mock()
        ordem_repo = Mock()
        transaction_manager = Mock()

        # OS em status errado para processar orcamento
        ordem = {
            'id': 100,
            'status': StatusOrdemServico.DIAGNOSTICO.value,
            'data_abertura': datetime.now(timezone.utc),
            'data_ultima_transicao': None,
        }

        ordem_repo.get_by_id_for_user.return_value = ordem
        transaction_manager.atomic.return_value.__enter__ = Mock(return_value=None)
        transaction_manager.atomic.return_value.__exit__ = Mock(return_value=None)


        uc = ProcessarRespostaOrcamentoUseCase(
            ordem_servico_repository=ordem_repo,
            transaction_manager=transaction_manager,
            observabilidade_port=obs_port,
        )

        input_dto = ProcessarRespostaOrcamentoInputDTO(
            ordem_servico_id=100,
            decisao=DecisaoOrcamento.APROVADO.value,
            origem='simulador_orcamento',
            token='dummy',
            usuario_id=1,
            usuario_is_staff=True,
        )

        # Deve lançar exceção
        with pytest.raises(OrcamentoNaoPodeSerProcessadoError):
            uc.execute(input_dto)

        # Validar que evento FALHA foi registrado
        assert obs_port.registrar_evento_ordem_servico.call_count == 1
        evento = obs_port.registrar_evento_ordem_servico.call_args[0][0]

        assert evento['evento'] == 'FALHA'
        assert evento['osId'] == 100
        assert evento['erroTipo'] == 'OrcamentoNaoPodeSerProcessadoError'
        # O traceId e responsabilidade do adapter: use case nao conhece infra.
        assert 'traceId' not in evento


class TestObservabilidadeAdapterRealComNewRelic:
    """Testes do adapter real com mock de New Relic."""

    def test_adapter_emite_custom_event(self):
        """Valida que adapter chama record_custom_event quando disponível."""
        with patch('atendimento.infrastructure.observabilidade_adapter.record_custom_event') as mock_nr:
            with patch('atendimento.infrastructure.observabilidade_adapter.trace_e_span') as mock_trace:
                mock_trace.return_value = ('trace-nr', 'span-nr')
                with patch('django.conf.settings.SERVICE_ENVIRONMENT', 'producao'):
                    adapter = ObservabilidadeAdapter()

                    evento = {
                        'evento': 'ABERTURA',
                        'osId': 100,
                        'statusAnterior': None,
                        'statusNovo': 'RECEBIDA',
                        'duracaoStatusSegundos': 0.0,
                        'erroTipo': None,
                        'traceId': 'trace-123',
                    }

                    adapter.registrar_evento_ordem_servico(evento)

            # Validar que record_custom_event foi chamado
            mock_nr.assert_called_once()
            call_args = mock_nr.call_args
            assert call_args[0][0] == 'OrdemServicoEvento'
            evento_enviado = call_args[0][1]
            assert evento_enviado['traceId'] == 'trace-nr'
            assert evento_enviado['service.environment'] == 'producao'

    def test_adapter_sem_newrelic_emite_log(self):
        """Valida que adapter cai para log JSON quando newrelic não disponível."""
        with patch('atendimento.infrastructure.observabilidade_adapter.record_custom_event', None):
            with patch('atendimento.infrastructure.observabilidade_adapter.trace_e_span') as mock_trace:
                mock_trace.return_value = ('trace-log', 'span-log')
                with patch('atendimento.infrastructure.observabilidade_adapter.logger') as mock_logger:
                    adapter = ObservabilidadeAdapter()

                    evento = {
                        'evento': 'TRANSICAO',
                        'osId': 100,
                        'statusAnterior': 'DIAGNOSTICO',
                        'statusNovo': 'EXECUCAO',
                        'duracaoStatusSegundos': 300.0,
                        'erroTipo': None,
                        'traceId': 'trace-456',
                    }

                    adapter.registrar_evento_ordem_servico(evento)

            # Validar que logger.info foi chamado
            mock_logger.info.assert_called_once()


class TestObservabilidadeAdapterNoop:
    """Testes do no-op adapter (desabilitado)."""

    def test_noop_adapter_nao_emite_nada(self):
        """Valida que no-op adapter não faz nada."""
        adapter = ObservabilidadeAdapterNoop()

        evento = {
            'evento': 'ABERTURA',
            'osId': 100,
            'statusAnterior': None,
            'statusNovo': 'RECEBIDA',
            'duracaoStatusSegundos': 0.0,
            'unidade': 'oficina-1',
            'erroTipo': None,
            'traceId': 'trace-789',
        }

        # Não deve lançar exceção
        adapter.registrar_evento_ordem_servico(evento)


class FallbackDoAdapterSemAgenteTest(SimpleTestCase):
    """O caminho que roda hoje: sem o pacote `newrelic`, o evento vira log JSON.

    Os demais testes do adapter mockam `record_custom_event`, entao exercitam so
    o caminho do agente. Este cobre o outro -- que e o unico ativo enquanto o
    agente nao estiver instalado no ambiente.
    """

    EVENTO = {
        'evento': 'FALHA',
        'osId': 42,
        'statusAnterior': 'AGUARDANDO',
        'statusNovo': 'AGUARDANDO',
        'duracaoStatusSegundos': 12.5,
        'erroTipo': 'OrcamentoNaoPodeSerProcessadoError',
    }

    def test_logger_do_adapter_fica_sob_um_namespace_configurado(self):
        """Guarda de regressao: logger de raiz propria nao tem handler nenhum.

        O `LOGGING` de `app/settings.py` configura handler para `django` e
        `atendimento`. Um logger chamado so `observabilidade` propaga para a raiz,
        que nao tem handler, e o evento some em silencio.
        """
        from atendimento.infrastructure import observabilidade_adapter

        nome = observabilidade_adapter.logger.name
        assert nome.startswith('atendimento.') or nome.startswith('django.'), (
            f"logger '{nome}' nao herda handler de nenhum logger configurado"
        )

    def test_fallback_emite_o_evento_inteiro_em_json(self):
        import logging as _logging
        from app.observabilidade.logging import JSONFormatter
        from atendimento.infrastructure import observabilidade_adapter

        fluxo = StringIO()
        handler = _logging.StreamHandler(fluxo)
        handler.setFormatter(JSONFormatter())
        logger = observabilidade_adapter.logger
        logger.addHandler(handler)
        nivel_anterior, propagacao_anterior = logger.level, logger.propagate
        logger.setLevel(_logging.INFO)
        logger.propagate = False
        try:
            # Forcar o caminho do fallback em vez de depender do ambiente: na CI o
            # pacote `newrelic` esta instalado e o adapter tomaria o outro ramo,
            # deixando este teste verde por acidente aqui e vermelho la.
            with patch.object(observabilidade_adapter, 'record_custom_event', None):
                ObservabilidadeAdapter().registrar_evento_ordem_servico(dict(self.EVENTO))
        finally:
            logger.removeHandler(handler)
            logger.setLevel(nivel_anterior)
            logger.propagate = propagacao_anterior

        linha = fluxo.getvalue().strip()
        assert linha, "o fallback nao emitiu nada"
        emitido = json.loads(linha)

        # Sem estes campos D2 nao mede duracao e D3 nao ve o motivo da falha.
        for chave, esperado in self.EVENTO.items():
            assert emitido.get(chave) == esperado, (
                f"campo '{chave}' perdido no fallback: {emitido}"
            )
        assert 'unidade' not in emitido


class ComposicaoDasFactoriesTest(SimpleTestCase):
    """O port precisa chegar ao use case pela composition root.

    Os demais testes constroem o use case a mao e passam um dublê, entao passam
    verdes mesmo com a factory esquecendo de injetar o adapter. Foi o que
    aconteceu: o default e `None`, o use case pula a emissao em silencio, e o
    painel de negocio ficaria vazio sem erro nenhum em lugar nenhum.
    """

    def test_factories_dos_use_cases_de_status_injetam_o_adapter_real(self):
        from atendimento.infrastructure.factories import (
            build_abrir_ordem_servico_use_case,
            build_atualizar_status_por_notificacao_use_case,
            build_processar_resposta_orcamento_use_case,
        )

        construtores = {
            'abrir_ordem_servico': build_abrir_ordem_servico_use_case,
            'atualizar_status_por_notificacao': build_atualizar_status_por_notificacao_use_case,
            'processar_resposta_orcamento': build_processar_resposta_orcamento_use_case,
        }

        for nome, construir in construtores.items():
            port = getattr(construir(), 'observabilidade_port', None)
            assert port is not None, (
                f"factory de {nome} nao injetou observabilidade_port: "
                "o use case pula a emissao de OrdemServicoEvento em silencio"
            )
            assert isinstance(port, ObservabilidadeAdapter), (
                f"factory de {nome} injetou {type(port).__name__}, "
                "nao o adapter real"
            )
