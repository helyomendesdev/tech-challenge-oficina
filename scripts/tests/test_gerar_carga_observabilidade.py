"""Testes do gerador de carga de observabilidade.

Cobrem o que a revisao do PR #11 apontou e o que quebraria em silencio:
o ciclo tem de respeitar o grafo de transicoes do dominio, a unidade e da OS
(nao da transicao), os nomes de status tem de existir no dominio, e o
encerramento nao pode ficar preso nas threads de leitura.

Nao sobem servidor: a API e dublada. Rodam em menos de um segundo.
"""

import argparse
import re
import threading
import time

import pytest

from atendimento.domain.enums import StatusOrdemServico
from atendimento.domain.policies import OrdemServicoStatusPolicy
from atendimento.domain.exceptions import TransicaoStatusInvalidaError
from scripts.gerar_carga_observabilidade import (
    ESPERA_ABORTO_SEGUNDOS,
    PERMANENCIA_HORAS,
    SimuladorOrdemServico,
    encerrar,
    espera_maxima_ciclo,
    gerar_cpf,
    gerar_placa,
    gerar_traceparent,
    trafego_de_leitura,
)
import random

ROTA_STATUS = "/api/v1/ordens-servico/status-notificacoes/"
ROTA_ABERTURA = "/api/v1/ordens-servico/abrir/"


# ---------------------------------------------------------------------------
# Dublês
# ---------------------------------------------------------------------------

class APIDublada:
    """Responde como a API da oficina responderia, sem rede."""

    def __init__(self, aceitar_transicoes: bool = True):
        self.aceitar_transicoes = aceitar_transicoes
        self.chamadas: list[tuple[str, str, dict | None]] = []
        self._proximo_id = 1000
        self._lock = threading.Lock()

    def chamar(self, metodo, caminho, payload=None, rng=None):
        with self._lock:
            self.chamadas.append((metodo, caminho, payload))
            if caminho == ROTA_ABERTURA:
                self._proximo_id += 1
                return 201, {"ordem_servico_id": self._proximo_id}, 1.0
        if caminho == ROTA_STATUS:
            return (200, {}, 1.0) if self.aceitar_transicoes else (400, {}, 1.0)
        return 200, {}, 1.0

    # -- consultas de apoio -------------------------------------------------

    def transicoes(self) -> list[dict]:
        return [
            payload for _, caminho, payload in self.chamadas
            if caminho == ROTA_STATUS and payload
        ]


def configuracao(**ajustes) -> argparse.Namespace:
    """Config minima do gerador, com o tempo praticamente zerado."""
    base = {
        "aceleracao": 10_000_000.0,  # ciclo inteiro em microssegundos
        "unidades": ["centro", "zona-sul", "zona-norte", "abc"],
        "recorrencia": 0.0,
        "falhas": 0.0,
        "verboso": False,
    }
    base.update(ajustes)
    return argparse.Namespace(**base)


def rodar_uma_os(semente: int, **ajustes) -> APIDublada:
    api = APIDublada()
    simulador = SimuladorOrdemServico(
        api=api,
        config=configuracao(**ajustes),
        metricas=_MetricasFake(),
        rng=random.Random(semente),
        clientes_conhecidos=[],
        lock_clientes=threading.Lock(),
        parar=threading.Event(),
    )
    simulador.executar()
    return api


class _MetricasFake:
    def registrar(self, campo, valor=1):
        pass

    def registrar_resposta(self, codigo, latencia_ms):
        pass


# ---------------------------------------------------------------------------
# Geradores de dado
# ---------------------------------------------------------------------------

def _digitos_verificadores_batem(cpf: str) -> bool:
    base = [int(digito) for digito in cpf[:9]]
    esperados = []
    for pesos_iniciais in (10, 11):
        soma = sum(
            (pesos_iniciais - indice) * digito
            for indice, digito in enumerate(base + esperados)
        )
        verificador = (soma * 10) % 11
        esperados.append(0 if verificador == 10 else verificador)
    return cpf[9:] == "".join(str(digito) for digito in esperados)


@pytest.mark.parametrize("semente", range(25))
def test_cpf_gerado_passa_na_regra_dos_digitos_verificadores(semente):
    cpf = gerar_cpf(random.Random(semente))
    assert len(cpf) == 11 and cpf.isdigit()
    assert len(set(cpf)) > 1, "CPF de digitos repetidos e recusado pelo validador"
    assert _digitos_verificadores_batem(cpf)


@pytest.mark.parametrize("semente", range(25))
def test_placa_no_padrao_mercosul(semente):
    assert re.fullmatch(r"[A-Z]{3}\d[A-Z0-9]\d{2}", gerar_placa(random.Random(semente)))


@pytest.mark.parametrize("semente", range(10))
def test_traceparent_no_formato_w3c(semente):
    assert re.fullmatch(
        r"00-[0-9a-f]{32}-[0-9a-f]{16}-01", gerar_traceparent(random.Random(semente))
    )


# ---------------------------------------------------------------------------
# Ciclo de vida da OS
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("semente", range(30))
def test_transicoes_respeitam_o_grafo_do_dominio(semente):
    """Toda transicao emitida tem de ser aceita pela policy real do dominio."""
    api = rodar_uma_os(semente)

    status_atual = StatusOrdemServico.RECEBIDA.value
    for payload in api.transicoes():
        novo_status = payload["novo_status"]
        try:
            OrdemServicoStatusPolicy.validar_transicao(status_atual, novo_status)
        except TransicaoStatusInvalidaError as erro:
            pytest.fail(f"gerador emitiu transicao invalida: {erro}")
        status_atual = novo_status


@pytest.mark.parametrize("semente", range(30))
def test_status_usados_existem_no_dominio(semente):
    """Ponto 6 da revisao: nada de AGUARDANDO_APROVACAO."""
    validos = {status.value for status in StatusOrdemServico}
    emitidos = {payload["novo_status"] for payload in rodar_uma_os(semente).transicoes()}
    assert emitidos <= validos


def test_permanencia_so_cita_status_do_dominio():
    validos = {status.value for status in StatusOrdemServico}
    assert set(PERMANENCIA_HORAS) <= validos


@pytest.mark.parametrize("semente", range(30))
def test_unidade_e_a_mesma_em_todo_o_ciclo_da_os(semente):
    """Ponto 4 da revisao: a unidade e da OS, nao da transicao."""
    api = rodar_uma_os(semente, falhas=1.0)

    unidades = {
        payload["origem"].split("/")[1]
        for payload in api.transicoes()
        if payload.get("origem", "").startswith("gerador-carga/")
    }
    assert len(unidades) <= 1, f"a OS trocou de unidade no meio do ciclo: {unidades}"


def test_unidade_sai_do_conjunto_configurado():
    api = rodar_uma_os(7, unidades=["unica"])
    origens = {payload["origem"] for payload in api.transicoes()}
    assert origens and all(origem.startswith("gerador-carga/unica") for origem in origens)


def test_abertura_nao_manda_campo_fora_do_contrato():
    """O contrato de abertura nao tem `unidade` -- nao inventar campo."""
    api = rodar_uma_os(3)
    aberturas = [p for m, c, p in api.chamadas if c == ROTA_ABERTURA]
    assert aberturas
    for payload in aberturas:
        assert set(payload) == {"cliente", "veiculo", "servicos", "pecas"}


def test_ciclo_para_quando_a_transicao_e_recusada():
    api = APIDublada(aceitar_transicoes=False)
    simulador = SimuladorOrdemServico(
        api=api, config=configuracao(), metricas=_MetricasFake(),
        rng=random.Random(1), clientes_conhecidos=[],
        lock_clientes=threading.Lock(), parar=threading.Event(),
    )
    simulador.executar()
    assert len(api.transicoes()) == 1, "erro de transicao nao pode virar laco"


# ---------------------------------------------------------------------------
# Encerramento (ponto 5 da revisao)
# ---------------------------------------------------------------------------

def test_espera_maxima_ciclo_encolhe_com_a_aceleracao():
    assert espera_maxima_ciclo(3600.0) == pytest.approx(
        espera_maxima_ciclo(7200.0) * 2
    )
    assert espera_maxima_ciclo(3600.0) > 0


def _thread_de_os(duracao: float, parar: threading.Event) -> threading.Thread:
    return threading.Thread(target=lambda: parar.wait(duracao), daemon=True)


def test_encerrar_nao_fica_preso_nas_threads_de_leitura():
    """O defeito original: os leitores comiam todo o orcamento de drenagem."""
    parar, parar_leitura = threading.Event(), threading.Event()
    leitores = [
        threading.Thread(
            target=trafego_de_leitura,
            args=(APIDublada(), configuracao(), random.Random(i), parar_leitura, parar),
            daemon=True,
        )
        for i in range(2)
    ]
    for leitor in leitores:
        leitor.start()

    os_rapida = _thread_de_os(0.05, parar)
    os_rapida.start()

    inicio = time.monotonic()
    incompletos = encerrar([os_rapida], leitores, parar_leitura, parar, espera_final=10.0)
    decorrido = time.monotonic() - inicio

    assert incompletos == 0
    assert not os_rapida.is_alive(), "a OS tinha de ter fechado o ciclo"
    assert decorrido < 5.0, f"encerramento levou {decorrido:.1f}s esperando os leitores"
    assert all(not leitor.is_alive() for leitor in leitores)


def test_encerrar_conta_ciclo_incompleto_e_nao_estoura_o_teto():
    parar, parar_leitura = threading.Event(), threading.Event()
    os_lenta = _thread_de_os(30.0, parar)
    os_lenta.start()

    inicio = time.monotonic()
    incompletos = encerrar([os_lenta], [], parar_leitura, parar, espera_final=0.1)
    decorrido = time.monotonic() - inicio

    assert incompletos == 0, "parar.set() tem de tirar a OS do wait"
    assert not os_lenta.is_alive()
    assert decorrido < 0.1 + ESPERA_ABORTO_SEGUNDOS


def test_encerrar_com_espera_zero_sai_na_hora():
    parar, parar_leitura = threading.Event(), threading.Event()
    inicio = time.monotonic()
    encerrar([], [], parar_leitura, parar, espera_final=0.0)
    assert time.monotonic() - inicio < 1.0
    assert parar.is_set() and parar_leitura.is_set()
