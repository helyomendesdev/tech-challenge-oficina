"""Testes do gerador de carga de observabilidade.

Cobrem o que as duas revisoes do PR #11 apontaram e o que quebraria em silencio:
o ciclo tem de respeitar o grafo de transicoes do dominio contando as duas rotas
(status generico e fluxo de orcamento), a unidade e da OS e nao da transicao, os
nomes de status tem de existir no dominio, o encerramento nao pode ficar preso
nas threads de leitura nem mentir na contagem de ciclos incompletos, e excecao
dentro do ciclo tem de virar codigo de saida diferente de zero.

Nao sobem servidor: a API e dublada, e os testes de laco dirigem o `main()` real
com argv e ClienteAPI trocados. Os testes de encerramento e de prazo esperam
relogio de verdade, entao a suite leva algumas dezenas de segundos.
"""

import argparse
import json
import re
import threading
import time
import urllib.request
import uuid

import pytest

from atendimento.domain.enums import StatusOrdemServico
from atendimento.domain.policies import OrdemServicoStatusPolicy
from atendimento.domain.exceptions import TransicaoStatusInvalidaError
from scripts.gerar_carga_observabilidade import (
    ESPERA_ABORTO_SEGUNDOS,
    PERMANENCIA_HORAS,
    ClienteAPI,
    Metricas,
    SimuladorOrdemServico,
    encerrar,
    espera_maxima_ciclo,
    gerar_cpf,
    gerar_placa,
    gerar_traceparent,
    trafego_de_leitura,
    validar,
)
import random

ROTA_STATUS = "/api/v1/ordens-servico/status-notificacoes/"
ROTA_ABERTURA = "/api/v1/ordens-servico/abrir/"
ROTA_ORCAMENTO = "/api/v1/simulacao/orcamento/"


# ---------------------------------------------------------------------------
# Dublês
# ---------------------------------------------------------------------------

class APIDublada:
    """Responde como a API da oficina responderia, sem rede."""

    def __init__(self, aceitar_transicoes: bool = True, levantar_excecao: bool = False):
        self.aceitar_transicoes = aceitar_transicoes
        self.levantar_excecao = levantar_excecao
        self.chamadas: list[tuple[str, str, dict | None]] = []
        self._proximo_id = 1000
        self._lock = threading.Lock()

    def chamar(self, metodo, caminho, payload=None, rng=None, correlation_id=None):
        if self.levantar_excecao:
            raise RuntimeError("Erro simulado na API")
        with self._lock:
            self.chamadas.append((metodo, caminho, payload))
            if caminho == ROTA_ABERTURA:
                self._proximo_id += 1
                return 201, {"ordem_servico_id": self._proximo_id}, 1.0
        if caminho == ROTA_STATUS:
            return (200, {}, 1.0) if self.aceitar_transicoes else (400, {}, 1.0)
        if caminho == ROTA_ORCAMENTO:
            return (200, {}, 1.0) if self.aceitar_transicoes else (400, {"erro": "recusado"}, 1.0)
        return 200, {}, 1.0

    # -- consultas de apoio -------------------------------------------------

    def transicoes(self) -> list[dict]:
        """Payloads enviados a rota generica de status."""
        return [
            payload for _, caminho, payload in self.chamadas
            if caminho == ROTA_STATUS and payload
        ]

    def orcamentos(self) -> list[dict]:
        """Payloads enviados ao fluxo real de orcamento."""
        return [
            payload for _, caminho, payload in self.chamadas
            if caminho == ROTA_ORCAMENTO and payload
        ]

    def sequencia_de_status(self) -> list[str]:
        """Status por que a OS passou, na ordem cronologica real.

        Parte das transicoes sai pela rota generica e parte pelo fluxo de
        orcamento, que move a OS do lado da aplicacao: APROVADO leva a EXECUCAO
        e RECUSADO devolve para DIAGNOSTICO. Olhar so uma das rotas esconde
        transicao duplicada -- foi exatamente o defeito que passou batido.
        """
        sequencia = []
        for _, caminho, payload in self.chamadas:
            if caminho == ROTA_STATUS and payload:
                sequencia.append(payload["novo_status"])
            elif caminho == ROTA_ORCAMENTO and payload:
                sequencia.append(
                    "EXECUCAO" if payload["decisao"] == "APROVADO" else "DIAGNOSTICO"
                )
        return sequencia


def configuracao(**ajustes) -> argparse.Namespace:
    """Config minima do gerador, com o tempo praticamente zerado."""
    base = {
        "aceleracao": 10_000_000.0,  # ciclo inteiro em microssegundos
        "unidades": ["centro", "zona-sul", "zona-norte", "abc"],
        "recorrencia": 0.0,
        "falhas": 0.0,
        "verboso": False,
        "taxa": 10.0,
        "duracao": 300,
        "ordens": 0,
        "leitores": 2,
        "concorrencia": 12,
        "espera_final": None,
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


class ClienteAPIComCaptura(ClienteAPI):
    """ClienteAPI que captura os headers realmente montados antes de enviar.

    Usado para testar que X-Correlation-Id e repassado corretamente entre
    autenticacao e chamadas de negocio no mesmo ciclo de OS.
    """

    def __init__(self, base_url: str = "http://localhost:8000", usuario: str = "admin",
                 senha: str = "admin", metricas: Metricas | None = None,
                 timeout: int = 20):
        metricas = metricas or _MetricasFake()
        super().__init__(base_url, usuario, senha, metricas, timeout)
        # (metodo, caminho, headers_capturados, payload)
        self.chamadas_capturadas: list[tuple[str, str, dict, dict | None]] = []
        self._respostas_por_rota = {}

    def _enviar(self, metodo: str, caminho: str, payload=None,
                autenticado: bool = True, rng=None, correlation_id: str | None = None):
        """Captura headers e responde com dados fake."""
        # Monta headers como o original faria
        headers = {}
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "application/json"
        gerador = rng or random
        headers["traceparent"] = gerar_traceparent(gerador)
        headers["X-Request-Id"] = str(uuid.uuid4())
        if correlation_id:
            headers["X-Correlation-Id"] = correlation_id
        if autenticado and self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        # Captura a chamada
        with self._lock:
            self.chamadas_capturadas.append((metodo, caminho, headers.copy(), payload))

        # Retorna respostas fake baseadas na rota
        if caminho == ROTA_ABERTURA:
            id_nova = len([p for _, c, _, p in self.chamadas_capturadas if c == ROTA_ABERTURA]) + 1000
            return 201, {"ordem_servico_id": id_nova}, 1.0
        elif caminho == "/api/token/":
            with self._lock:
                self._token = "token-fake"
            return 200, {"access": "token-fake"}, 1.0
        elif caminho == ROTA_STATUS:
            return 200, {}, 1.0
        elif caminho == ROTA_ORCAMENTO:
            return 200, {}, 1.0
        else:
            return 200, {}, 1.0


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
    """Toda transicao emitida tem de ser aceita pela policy real do dominio.

    A sequencia mistura as duas rotas na ordem cronologica: parte das transicoes
    sai pelo endpoint generico e parte pelo fluxo de orcamento. Olhar so a rota
    generica deixaria passar transicao duplicada -- o orcamento move
    AGUARDANDO -> EXECUCAO e o gerador emitir EXECUCAO -> EXECUCAO logo depois,
    que a policy recusa.
    """
    api = rodar_uma_os(semente)

    status_atual = StatusOrdemServico.RECEBIDA.value
    caminho = [status_atual]
    for novo_status in api.sequencia_de_status():
        try:
            OrdemServicoStatusPolicy.validar_transicao(status_atual, novo_status)
        except TransicaoStatusInvalidaError as erro:
            pytest.fail(
                f"gerador emitiu transicao invalida: {erro} | "
                f"caminho: {' -> '.join(caminho)} -> {novo_status}"
            )
        status_atual = novo_status
        caminho.append(novo_status)


@pytest.mark.parametrize("semente", range(30))

def test_status_usados_existem_no_dominio(semente):
    """Ponto 6 da revisao: nada de AGUARDANDO_APROVACAO."""
    validos = {status.value for status in StatusOrdemServico}
    assert set(rodar_uma_os(semente).sequencia_de_status()) <= validos


def test_permanencia_so_cita_status_do_dominio():
    validos = {status.value for status in StatusOrdemServico}
    assert set(PERMANENCIA_HORAS) <= validos


# ---------------------------------------------------------------------------
# Validacao de argumentos
# ---------------------------------------------------------------------------

def test_validar_rejeita_concorrencia_zero():
    config = configuracao(concorrencia=0)
    with pytest.raises(SystemExit):
        validar(config)


def test_validar_rejeita_concorrencia_negativa():
    config = configuracao(concorrencia=-1)
    with pytest.raises(SystemExit):
        validar(config)


def test_validar_aceita_concorrencia_positiva():
    config = configuracao(concorrencia=1)
    validar(config)  # nao deve lancar excecao


def test_validar_rejeita_taxa_nao_positiva():
    for taxa in (0.0, -1.0):
        with pytest.raises(SystemExit):
            validar(configuracao(taxa=taxa))


def test_validar_rejeita_leitores_negativo():
    config = configuracao(leitores=-1)
    with pytest.raises(SystemExit):
        validar(config)


def test_validar_aceita_leitores_zero():
    config = configuracao(leitores=0)
    validar(config)  # nao deve lancar excecao


def test_validar_rejeita_duracao_negativa():
    config = configuracao(duracao=-1)
    with pytest.raises(SystemExit):
        validar(config)


def test_validar_aceita_duracao_zero():
    config = configuracao(duracao=0)
    validar(config)  # nao deve lancar excecao


def test_validar_rejeita_ordens_negativo():
    config = configuracao(ordens=-1)
    with pytest.raises(SystemExit):
        validar(config)


def test_validar_aceita_ordens_zero():
    config = configuracao(ordens=0)
    validar(config)  # nao deve lancar excecao


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

    assert incompletos == 1, "uma OS interrompida no meio tem de ser contada"
    assert not os_lenta.is_alive()
    assert decorrido < 0.1 + ESPERA_ABORTO_SEGUNDOS


def test_encerrar_com_espera_zero_sai_na_hora():
    parar, parar_leitura = threading.Event(), threading.Event()
    inicio = time.monotonic()
    encerrar([], [], parar_leitura, parar, espera_final=0.0)
    assert time.monotonic() - inicio < 1.0
    assert parar.is_set() and parar_leitura.is_set()


# ---------------------------------------------------------------------------
# Fluxo real de orcamento (defeito 1 da segunda revisao)
# ---------------------------------------------------------------------------

def test_orcamento_nao_e_seguido_de_transicao_para_o_mesmo_status():
    """O endpoint de orcamento ja move a OS -- repetir a transicao vira erro.

    Foi assim que o defeito nasceu: o gerador chamava /simulacao/orcamento/
    (que leva AGUARDANDO -> EXECUCAO do lado da aplicacao) e logo depois emitia
    EXECUCAO -> EXECUCAO na rota generica, recusada pela policy. Contra a API
    real isso somaria um erro falso em todo ciclo aprovado.

    As sementes tambem servem de guarda de cobertura: se o intervalo de
    desfecho mudar e a recusa deixar de ser exercitada, o teste acusa.
    """
    decisoes_vistas = set()
    for semente in range(60):
        api = rodar_uma_os(semente)
        sequencia = api.sequencia_de_status()
        for anterior, seguinte in zip(sequencia, sequencia[1:]):
            assert anterior != seguinte, (
                f"semente {semente} repetiu {anterior}: "
                f"{' -> '.join(sequencia)}"
            )
        decisoes_vistas.update(payload["decisao"] for payload in api.orcamentos())

    assert decisoes_vistas == {"APROVADO", "RECUSADO"}, (
        f"decisao de orcamento nao exercitada nas sementes: {decisoes_vistas}"
    )


def test_aprovacao_e_recusa_passam_pelo_endpoint_de_orcamento():
    """Sem isto o painel de integracao so ve trafego nas falhas deliberadas."""
    rotas_de_saida_do_aguardando = set()
    for semente in range(60):
        api = rodar_uma_os(semente)
        for indice, (_, caminho, payload) in enumerate(api.chamadas):
            anterior = api.chamadas[indice - 1][2] if indice else None
            saiu_de_aguardando = (
                anterior and anterior.get("novo_status") == "AGUARDANDO"
            )
            if saiu_de_aguardando:
                rotas_de_saida_do_aguardando.add(caminho)

    assert ROTA_ORCAMENTO in rotas_de_saida_do_aguardando, (
        "aprovacao/recusa tem de sair pelo fluxo real de orcamento"
    )


def test_orcamento_carrega_a_unidade_no_motivo():
    """`origem` nao existe no contrato de simulacao; o facet vai pelo motivo."""
    motivos = []
    for semente in range(60):
        motivos += [p["motivo"] for p in rodar_uma_os(semente, unidades=["unica"]).orcamentos()]

    assert motivos, "nenhuma decisao de orcamento foi emitida"
    assert all(motivo.startswith("gerador-carga/unica:") for motivo in motivos)


# ---------------------------------------------------------------------------
# Laco de lancamento e codigo de saida (defeitos 4 e 5), dirigindo o main real
# ---------------------------------------------------------------------------

class APIParaMain:
    """Dubla de ClienteAPI para rodar `main()` inteiro, sem rede."""

    def __init__(self, *_args, **_kwargs):
        self.aberturas = 0
        self.levantar_excecao = False
        self._lock = threading.Lock()
        self._proximo_id = 1000

    def autenticar(self):
        return None

    def chamar(self, metodo, caminho, payload=None, rng=None, correlation_id=None):
        if self.levantar_excecao:
            raise RuntimeError("quebra sintetica dentro do ciclo da OS")
        with self._lock:
            if caminho == ROTA_ABERTURA:
                self.aberturas += 1
                self._proximo_id += 1
                return 201, {"ordem_servico_id": self._proximo_id}, 1.0
        return 200, {}, 1.0


def rodar_main(monkeypatch, argumentos: list, api: APIParaMain) -> int:
    """Executa `main()` com argv e ClienteAPI dublados."""
    import sys as _sys
    from scripts import gerar_carga_observabilidade as gerador

    monkeypatch.setattr(_sys, "argv", ["gerar_carga_observabilidade.py"] + argumentos)
    monkeypatch.setattr(gerador, "ClienteAPI", lambda *a, **k: api)
    return gerador.main()


def test_main_abre_exatamente_o_numero_de_ordens_pedido(monkeypatch):
    api = APIParaMain()
    codigo = rodar_main(monkeypatch, [
        "--ordens", "5", "--concorrencia", "2", "--leitores", "0",
        "--taxa", "6000", "--aceleracao", "10000000", "--espera-final", "5",
        "--semente", "1",
    ], api)

    assert codigo == 0
    assert api.aberturas == 5


def test_main_nao_lanca_ordem_depois_de_vencer_a_duracao(monkeypatch):
    """Defeito 4: `vagas.acquire()` sem timeout lancava OS alem do prazo.

    Uma vaga so e um ciclo mais longo que a duracao: com o acquire bloqueante,
    o laco acordava quando a primeira OS liberava a vaga -- ja depois do prazo --
    e lancava a segunda assim mesmo.
    """
    api = APIParaMain()
    inicio = time.monotonic()
    codigo = rodar_main(monkeypatch, [
        "--duracao", "1", "--concorrencia", "1", "--leitores", "0",
        "--taxa", "6000", "--aceleracao", "40000", "--espera-final", "0",
        "--semente", "1",
    ], api)
    decorrido = time.monotonic() - inicio

    assert api.aberturas == 1, "lancou OS depois do prazo vencido"
    assert codigo == 0
    assert decorrido < 5.0, f"encerramento levou {decorrido:.1f}s"


def test_main_devolve_codigo_de_erro_quando_o_ciclo_quebra(monkeypatch):
    """Defeito 5: excecao na thread saia com codigo 0 e mascarava a quebra."""
    api = APIParaMain()
    api.levantar_excecao = True
    codigo = rodar_main(monkeypatch, [
        "--ordens", "3", "--concorrencia", "2", "--leitores", "0",
        "--taxa", "6000", "--aceleracao", "10000000", "--espera-final", "2",
        "--semente", "1",
    ], api)

    assert codigo == 2, "excecao no worker tem de virar codigo de saida diferente de zero"


# ---------------------------------------------------------------------------
# X-Correlation-Id (tarefas 6 e 7)
# ---------------------------------------------------------------------------

def test_autenticacao_e_chamada_de_negocio_compartilham_correlation_id(monkeypatch):
    """Autenticacao e chamada de negocio relacionada saem com o mesmo X-Correlation-Id.

    Testa o caso onde o token expira (401) durante o ciclo: a reautenticacao
    e a chamada refazida tem o mesmo correlation_id. O duble intercepta
    urllib.request.urlopen para capturar o Request real sem remontar headers.
    """
    from io import BytesIO
    from urllib.error import HTTPError
    from unittest.mock import Mock

    requisicoes_capturadas = []

    def urlopen_fake(request, *args, **kwargs):
        """Captura Request real e retorna respostas fake."""
        # Captura o Request real com seus headers
        headers_capturados = dict(request.headers)
        requisicoes_capturadas.append({
            'url': request.full_url,
            'headers': headers_capturados,
        })

        # Retorna respostas fake baseadas na rota
        if "/api/token/" in request.full_url:
            resposta = Mock()
            resposta.status = 200
            resposta.read = lambda: b'{"access": "token-fake"}'
            resposta.__enter__ = lambda s: s
            resposta.__exit__ = lambda s, *a: None
            return resposta
        elif ROTA_STATUS in request.full_url:
            # Primeira tentativa: 401; segunda: 200
            tentativas = len([r for r in requisicoes_capturadas if ROTA_STATUS in r['url']])
            if tentativas == 1:
                raise HTTPError(request.full_url, 401, "Unauthorized", {}, BytesIO(b'{}'))
            else:
                resposta = Mock()
                resposta.status = 200
                resposta.read = lambda: b'{}'
                resposta.__enter__ = lambda s: s
                resposta.__exit__ = lambda s, *a: None
                return resposta
        else:
            resposta = Mock()
            resposta.status = 201
            resposta.read = lambda: b'{"ordem_servico_id": 1001}'
            resposta.__enter__ = lambda s: s
            resposta.__exit__ = lambda s, *a: None
            return resposta

    monkeypatch.setattr(urllib.request, 'urlopen', urlopen_fake)

    api = ClienteAPI("http://localhost:9999", "admin", "admin", _MetricasFake())

    # Executa as chamadas
    correlation_id_teste = str(uuid.uuid4())
    try:
        api.autenticar(correlation_id=correlation_id_teste)
        api.chamar("POST", "/api/v1/ordens-servico/abrir/",
                   {"cliente": {}, "veiculo": {}, "servicos": [], "pecas": []},
                   correlation_id=correlation_id_teste)
        api.chamar("POST", ROTA_STATUS,
                   {"ordem_servico_id": 1001, "novo_status": "DIAGNOSTICO"},
                   correlation_id=correlation_id_teste)
    except (urllib.request.URLError, OSError):
        pass  # esperado, URL fake

    # Extrai autenticacoes e transicoes
    autenticacoes = [r for r in requisicoes_capturadas if "/api/token/" in r['url']]
    transicoes = [r for r in requisicoes_capturadas if ROTA_STATUS in r['url']]

    assert autenticacoes, "nenhuma chamada de autenticacao capturada"
    assert len(transicoes) >= 2, f"esperava 2+ transicoes, encontrou {len(transicoes)}"

    # Helper para busca case-insensitive
    def get_header(headers, name):
        name_lower = name.lower()
        for k, v in headers.items():
            if k.lower() == name_lower:
                return v
        return None

    # Valida presenca do header em todas as chamadas
    for i, auth in enumerate(autenticacoes):
        cid = get_header(auth["headers"], "X-Correlation-Id")
        assert cid, f"autenticacao {i} nao tem X-Correlation-Id ou vazio"

    for i, trans in enumerate(transicoes):
        cid = get_header(trans["headers"], "X-Correlation-Id")
        assert cid, f"transicao {i} nao tem X-Correlation-Id ou vazio"

    # Reauth compartilha correlation_id com transicao
    auth_cid = get_header(autenticacoes[-1]["headers"], "X-Correlation-Id")
    trans_cid = get_header(transicoes[0]["headers"], "X-Correlation-Id")
    assert auth_cid == trans_cid, (
        "autenticacao (reauth em 401) deve compartilhar X-Correlation-Id com transicao"
    )


def test_ciclos_de_os_diferentes_usam_correlation_id_diferente():
    """Cada ciclo de OS tem seu prprio X-Correlation-Id."""
    api = ClienteAPIComCaptura()

    correlation_ids = set()
    for semente in range(5):
        api.chamadas_capturadas.clear()
        simulador = SimuladorOrdemServico(
            api=api,
            config=configuracao(),
            metricas=_MetricasFake(),
            rng=random.Random(semente),
            clientes_conhecidos=[],
            lock_clientes=threading.Lock(),
            parar=threading.Event(),
        )
        # Roda o ciclo completo
        simulador.executar()

        # Extrai o correlation_id desta OS
        chamadas_desta_os = [
            headers for _, _, headers, _ in api.chamadas_capturadas
            if headers.get("X-Correlation-Id")
        ]
        if chamadas_desta_os:
            correlation_id = chamadas_desta_os[0].get("X-Correlation-Id")
            correlation_ids.add(correlation_id)

    assert len(correlation_ids) == 5, (
        f"5 ciclos de OS deveriam gerar 5 correlation_ids diferentes, "
        f"encontrou {len(correlation_ids)} unicos: {correlation_ids}"
    )


def test_todas_as_chamadas_do_ciclo_compartilham_correlation_id():
    """Todas as chamadas de um mesmo ciclo de OS compartilham X-Correlation-Id.

    Valida que abertura, transicoes, orcamento e falhas injetadas dentro
    de um ciclo usam o mesmo correlation_id — nao apenas que ciclos
    diferentes tem ids diferentes.
    """
    api = ClienteAPIComCaptura()

    simulador = SimuladorOrdemServico(
        api=api,
        config=configuracao(),
        metricas=_MetricasFake(),
        rng=random.Random(42),
        clientes_conhecidos=[],
        lock_clientes=threading.Lock(),
        parar=threading.Event(),
    )
    simulador.executar()

    # Extrai todos os correlation_ids capturados neste ciclo
    chamadas_do_ciclo = [
        headers for _, _, headers, _ in api.chamadas_capturadas
        if headers.get("X-Correlation-Id")
    ]

    assert chamadas_do_ciclo, "nenhuma chamada com X-Correlation-Id capturada"

    # Todos os ids devem ser iguais (mesmo ciclo)
    ids_unicos = {
        headers.get("X-Correlation-Id")
        for headers in chamadas_do_ciclo
    }

    assert len(ids_unicos) == 1, (
        f"ciclo unico deveria ter 1 correlation_id, encontrou {len(ids_unicos)}: {ids_unicos}"
    )


def test_correlation_id_no_formato_uuid4():
    """X-Correlation-Id segue o formato de UUIDv4 (versao 4 especificamente)."""
    api = ClienteAPIComCaptura()
    simulador = SimuladorOrdemServico(
        api=api,
        config=configuracao(),
        metricas=_MetricasFake(),
        rng=random.Random(99),
        clientes_conhecidos=[],
        lock_clientes=threading.Lock(),
        parar=threading.Event(),
    )
    simulador.executar()

    correlation_ids = {
        headers.get("X-Correlation-Id")
        for _, _, headers, _ in api.chamadas_capturadas
        if headers.get("X-Correlation-Id")
    }

    assert correlation_ids, "nenhum X-Correlation-Id foi capturado"

    # Valida que todos os IDs sao UUIDv4
    for cid in correlation_ids:
        try:
            parsed_uuid = uuid.UUID(cid)
            assert parsed_uuid.version == 4, (
                f"X-Correlation-Id '{cid}' nao e UUIDv4 (versao: {parsed_uuid.version})"
            )
        except (ValueError, TypeError):
            pytest.fail(f"X-Correlation-Id '{cid}' nao e um UUID valido")
