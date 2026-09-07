#!/usr/bin/env python3
"""Gera trafego realista de ordens de servico para popular a observabilidade.

Por que este script existe
--------------------------
Os dashboards exigidos pela Fase 3 -- volume diario de OS, tempo medio de
execucao por status e erros nas integracoes -- so tem sentido sobre historico.
O ambiente do Tech Challenge e efemero (sobe e desce para caber no orcamento da
AWS Academy), entao nao existe trafego organico: sem um gerador, o dashboard
aparece vazio na hora da gravacao do video.

Este script dirige a API real, respeitando o grafo de transicoes de
`atendimento/domain/policies.py`:

    RECEBIDA -> DIAGNOSTICO -> AGUARDANDO -+-> EXECUCAO -> FINALIZADA -> ENTREGUE
                                           |
                                           +-> DIAGNOSTICO   (orcamento recusado)
                                           +-> CANCELADA

Cada OS vive esse ciclo com tempos de permanencia realistas, comprimidos pelo
fator `--aceleracao`: com o padrao de 3600, uma hora de oficina passa em um
segundo, e um ciclo completo leva ~20 s.

Escopo: o script gera *trafego*. Os eventos de negocio `OrdemServicoEvento` que
alimentam os paineis de volume diario e tempo medio por status sao emitidos pela
aplicacao instrumentada (ver docs/fase3/observabilidade/README.md, secao 8, item
6). Rodar este gerador antes da instrumentacao produz transacoes de APM, logs e
carga de banco -- mas nao os eventos de negocio.

Uso
---
    python scripts/gerar_carga_observabilidade.py \
        --base-url http://localhost:8000 \
        --usuario admin --senha admin \
        --duracao 600 --taxa 12

    # rajada curta para popular o dashboard antes de uma demo
    python scripts/gerar_carga_observabilidade.py --ordens 80 --aceleracao 7200

Somente biblioteca padrao -- nao adiciona dependencia ao projeto.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import string
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Perfil de permanencia por status, em horas de oficina
# ---------------------------------------------------------------------------

PERMANENCIA_HORAS = {
    "RECEBIDA": (0.2, 1.0),
    "DIAGNOSTICO": (1.5, 5.0),
    "AGUARDANDO": (2.0, 16.0),
    "EXECUCAO": (3.0, 10.0),
    "FINALIZADA": (0.5, 4.0),
}

# Desfecho de uma OS que chegou em AGUARDANDO
DESFECHO_APROVADO = 0.70
DESFECHO_RECUSADO = 0.15
DESFECHO_CANCELADO = 0.10
# o restante (5%) fica parado em AGUARDANDO, imitando cliente que nao responde

UNIDADES_PADRAO = ["centro", "zona-sul", "zona-norte", "abc"]

# Quantas idas e vindas DIAGNOSTICO <-> AGUARDANDO uma OS pode ter antes de
# seguir para EXECUCAO. Usado tambem para calcular a espera de encerramento.
TENTATIVAS_DIAGNOSTICO = 3

# Teto para abortar o que sobrou depois que `parar` foi sinalizado.
ESPERA_ABORTO_SEGUNDOS = 5.0

MARCAS = [
    ("Volkswagen", ["Golf", "Polo", "T-Cross", "Virtus"]),
    ("Fiat", ["Argo", "Toro", "Mobi", "Pulse"]),
    ("Chevrolet", ["Onix", "Tracker", "S10"]),
    ("Toyota", ["Corolla", "Hilux", "Yaris"]),
    ("Honda", ["Civic", "HR-V", "Fit"]),
]

PRIMEIROS_NOMES = [
    "Ana", "Bruno", "Carla", "Diego", "Elisa", "Fabio", "Gabriela",
    "Heitor", "Isabela", "Joao", "Larissa", "Marcos", "Natalia",
    "Otavio", "Paula", "Rafael", "Sofia", "Tiago", "Vanessa", "Wagner",
]
SOBRENOMES = [
    "Almeida", "Barbosa", "Cardoso", "Dias", "Esteves", "Ferreira",
    "Gomes", "Henriques", "Iglesias", "Justino", "Lima", "Moreira",
    "Nunes", "Oliveira", "Pereira", "Queiroz", "Ribeiro", "Santos",
]


# ---------------------------------------------------------------------------
# Geradores de dado valido
# ---------------------------------------------------------------------------

def gerar_cpf(rng: random.Random) -> str:
    """Gera um CPF com digitos verificadores validos (validate_docbr recusa o resto)."""
    while True:
        base = [rng.randint(0, 9) for _ in range(9)]
        if len(set(base)) == 1:
            continue  # CPF de digitos repetidos e recusado pelo validador
        for pesos_iniciais in (10, 11):
            soma = sum(
                (pesos_iniciais - indice) * digito
                for indice, digito in enumerate(base)
            )
            verificador = (soma * 10) % 11
            base.append(0 if verificador == 10 else verificador)
        return "".join(str(digito) for digito in base)


def gerar_placa(rng: random.Random) -> str:
    """Gera placa no padrao Mercosul aceito por validate_placa: LLLNLNN."""
    letras = "".join(rng.choice(string.ascii_uppercase) for _ in range(3))
    quinto = rng.choice(string.ascii_uppercase + string.digits)
    return f"{letras}{rng.randint(0, 9)}{quinto}{rng.randint(0, 9)}{rng.randint(0, 9)}"


def gerar_cliente(rng: random.Random) -> dict:
    nome = f"{rng.choice(PRIMEIROS_NOMES)} {rng.choice(SOBRENOMES)}"
    usuario = nome.lower().replace(" ", ".")
    return {
        "nome": nome,
        "documento": gerar_cpf(rng),
        "email": f"{usuario}.{rng.randint(100, 999)}@example.com",
        "telefone": f"119{rng.randint(10000000, 99999999)}",
    }


def gerar_veiculo(rng: random.Random) -> dict:
    marca, modelos = rng.choice(MARCAS)
    return {
        "placa": gerar_placa(rng),
        "marca": marca,
        "modelo": rng.choice(modelos),
        "ano": rng.randint(2012, 2026),
    }


def gerar_traceparent(rng: random.Random) -> str:
    """Header W3C Trace Context, como um API Gateway entregaria."""
    trace_id = "".join(rng.choice("0123456789abcdef") for _ in range(32))
    span_id = "".join(rng.choice("0123456789abcdef") for _ in range(16))
    return f"00-{trace_id}-{span_id}-01"


# ---------------------------------------------------------------------------
# Metricas do proprio gerador
# ---------------------------------------------------------------------------

@dataclass
class Metricas:
    lock: threading.Lock = field(default_factory=threading.Lock)
    ordens_abertas: int = 0
    transicoes_ok: int = 0
    entregues: int = 0
    canceladas: int = 0
    retrabalho: int = 0
    falhas_injetadas: int = 0
    erros_inesperados: int = 0
    latencias_ms: list = field(default_factory=list)
    por_status_http: dict = field(default_factory=dict)

    def registrar(self, campo: str, valor: int = 1) -> None:
        with self.lock:
            setattr(self, campo, getattr(self, campo) + valor)

    def registrar_resposta(self, codigo: int, latencia_ms: float) -> None:
        with self.lock:
            self.latencias_ms.append(latencia_ms)
            self.por_status_http[codigo] = self.por_status_http.get(codigo, 0) + 1


# ---------------------------------------------------------------------------
# Cliente HTTP
# ---------------------------------------------------------------------------

class ClienteAPI:
    """Cliente minimo da API da oficina, com renovacao de JWT."""

    def __init__(self, base_url: str, usuario: str, senha: str,
                 metricas: Metricas, timeout: int = 20):
        self.base_url = base_url.rstrip("/")
        self.usuario = usuario
        self.senha = senha
        self.metricas = metricas
        self.timeout = timeout
        self._token = None
        self._lock = threading.Lock()

    # -- autenticacao -------------------------------------------------------

    def autenticar(self, correlation_id: str | None = None) -> None:
        codigo, corpo, _ = self._enviar(
            "POST", "/api/token/",
            {"username": self.usuario, "password": self.senha},
            autenticado=False,
            correlation_id=correlation_id,
        )
        if codigo != 200 or not isinstance(corpo, dict) or "access" not in corpo:
            raise RuntimeError(
                f"Falha ao obter token JWT (HTTP {codigo}): {corpo}. "
                "Confira --usuario/--senha e se o usuario existe no ambiente."
            )
        with self._lock:
            self._token = corpo["access"]

    @property
    def token(self) -> str | None:
        with self._lock:
            return self._token

    # -- transporte ---------------------------------------------------------

    def _enviar(self, metodo: str, caminho: str, payload=None,
                autenticado: bool = True, rng: random.Random | None = None,
                correlation_id: str | None = None):
        url = f"{self.base_url}{caminho}"
        dados = json.dumps(payload).encode() if payload is not None else None
        requisicao = urllib.request.Request(url, data=dados, method=metodo)
        requisicao.add_header("Content-Type", "application/json")
        requisicao.add_header("Accept", "application/json")
        # Correlacao: o gerador se comporta como o cliente na ponta do gateway
        gerador = rng or random
        requisicao.add_header("traceparent", gerar_traceparent(gerador))
        requisicao.add_header("X-Request-Id", str(uuid.uuid4()))
        if correlation_id:
            requisicao.add_header("X-Correlation-Id", correlation_id)
        if autenticado and self.token:
            requisicao.add_header("Authorization", f"Bearer {self.token}")

        inicio = time.monotonic()
        try:
            with urllib.request.urlopen(requisicao, timeout=self.timeout) as resposta:
                bruto = resposta.read().decode("utf-8", errors="replace")
                codigo = resposta.status
        except urllib.error.HTTPError as erro:
            bruto = erro.read().decode("utf-8", errors="replace")
            codigo = erro.code
        except (urllib.error.URLError, OSError) as erro:
            latencia = (time.monotonic() - inicio) * 1000
            self.metricas.registrar_resposta(0, latencia)
            return 0, {"erro_transporte": str(erro)}, latencia

        latencia = (time.monotonic() - inicio) * 1000
        self.metricas.registrar_resposta(codigo, latencia)
        try:
            corpo = json.loads(bruto) if bruto else {}
        except json.JSONDecodeError:
            corpo = {"corpo_bruto": bruto[:400]}
        return codigo, corpo, latencia

    def chamar(self, metodo: str, caminho: str, payload=None,
               rng: random.Random | None = None, correlation_id: str | None = None):
        """Envia a requisicao e reautentica uma vez se o token expirou."""
        codigo, corpo, latencia = self._enviar(metodo, caminho, payload, rng=rng,
                                               correlation_id=correlation_id)
        if codigo == 401:
            self.autenticar(correlation_id=correlation_id)
            codigo, corpo, latencia = self._enviar(metodo, caminho, payload, rng=rng,
                                                   correlation_id=correlation_id)
        return codigo, corpo, latencia


# ---------------------------------------------------------------------------
# Ciclo de vida de uma ordem de servico
# ---------------------------------------------------------------------------

class SimuladorOrdemServico:
    """Conduz uma OS pelo grafo de transicoes valido do dominio."""

    def __init__(self, api: ClienteAPI, config: argparse.Namespace,
                 metricas: Metricas, rng: random.Random,
                 clientes_conhecidos: list, lock_clientes: threading.Lock,
                 parar: threading.Event):
        self.api = api
        self.config = config
        self.metricas = metricas
        self.rng = rng
        self.clientes_conhecidos = clientes_conhecidos
        self.lock_clientes = lock_clientes
        self.parar = parar
        # A unidade e da OS, nao da transicao: um carro nao troca de oficina no
        # meio do reparo. Sorteada uma vez, vale para todo o ciclo.
        self.unidade = rng.choice(config.unidades)
        # A correlacao e da OS tambem: autenticacao e chamada de negocio relacionada
        # saem com o mesmo X-Correlation-Id. Sorteada uma vez no ciclo.
        self.correlation_id = str(uuid.uuid4())

    # -- utilitarios --------------------------------------------------------

    def _dormir(self, status: str) -> bool:
        """Espera o tempo de permanencia comprimido. False se mandaram parar."""
        minimo, maximo = PERMANENCIA_HORAS[status]
        segundos = self.rng.uniform(minimo, maximo) * 3600 / self.config.aceleracao
        return not self.parar.wait(segundos)

    def _cliente_e_veiculo(self):
        """Reaproveita cliente conhecido parte das vezes -- oficina tem recorrencia."""
        with self.lock_clientes:
            reaproveitavel = list(self.clientes_conhecidos)
        if reaproveitavel and self.rng.random() < self.config.recorrencia:
            cliente = self.rng.choice(reaproveitavel)
            return cliente, gerar_veiculo(self.rng)
        cliente = gerar_cliente(self.rng)
        with self.lock_clientes:
            if len(self.clientes_conhecidos) < 200:
                self.clientes_conhecidos.append(cliente)
        return cliente, gerar_veiculo(self.rng)

    def _transicionar(self, ordem_id: int, novo_status: str) -> bool:
        codigo, corpo, _ = self.api.chamar(
            "POST", "/api/v1/ordens-servico/status-notificacoes/",
            {
                "ordem_servico_id": ordem_id,
                "novo_status": novo_status,
                "origem": f"gerador-carga/{self.unidade}",
                "observacao": "Trafego sintetico para observabilidade.",
            },
            rng=self.rng,
            correlation_id=self.correlation_id,
        )
        if codigo == 200:
            self.metricas.registrar("transicoes_ok")
            return True
        self.metricas.registrar("erros_inesperados")
        self._log(f"transicao {ordem_id} -> {novo_status} falhou: HTTP {codigo} {corpo}")
        return False

    def _decidir_orcamento(self, ordem_id: int, decisao: str) -> bool:
        """Submete decisao de orcamento via endpoint real de integracao.

        A decisao passa por simulacao/orcamento/, que dispara webhook saindo da
        aplicacao -- e o span de integracao externa que queremos medir.
        Sucesso = HTTP 200 e ausencia de chave 'erro' no corpo.
        """
        # `origem` nao existe no contrato de /simulacao/orcamento/; `motivo` e o
        # unico campo livre, entao e por ele que a unidade chega ao facet.
        motivo = f"gerador-carga/{self.unidade}: orcamento {decisao.lower()}"
        codigo, corpo, _ = self.api.chamar(
            "POST", "/api/v1/simulacao/orcamento/",
            {
                "ordem_servico_id": ordem_id,
                "decisao": decisao,
                "motivo": motivo,
            },
            rng=self.rng,
            correlation_id=self.correlation_id,
        )
        if codigo == 200 and "erro" not in corpo:
            self.metricas.registrar("transicoes_ok")
            return True
        self.metricas.registrar("erros_inesperados")
        self._log(f"orcamento {ordem_id} -> {decisao} falhou: HTTP {codigo} {corpo}")
        return False

    def _log(self, mensagem: str) -> None:
        if self.config.verboso:
            print(f"[{time.strftime('%H:%M:%S')}] {mensagem}", flush=True)

    # -- injecao deliberada de falha ---------------------------------------

    def _injetar_falha(self, ordem_id: int | None) -> None:
        """Produz erro real para alimentar o painel D3 e o alerta A1.

        Sao falhas *legitimas* do ponto de vista da aplicacao: transicao proibida
        pela policy, OS inexistente e integracao externa chamada fora de hora.
        Nenhuma delas corrompe dado.
        """
        modo = self.rng.choice(["transicao_invalida", "os_inexistente", "integracao"])
        self.metricas.registrar("falhas_injetadas")

        if modo == "transicao_invalida" and ordem_id:
            self.api.chamar(
                "POST", "/api/v1/ordens-servico/status-notificacoes/",
                {
                    "ordem_servico_id": ordem_id,
                    "novo_status": "ENTREGUE",  # proibido a partir de RECEBIDA
                    "origem": f"gerador-carga/{self.unidade}/falha-sintetica",
                    "observacao": "Transicao deliberadamente invalida.",
                },
                rng=self.rng,
                correlation_id=self.correlation_id,
            )
        elif modo == "os_inexistente":
            inexistente = self.rng.randint(900_000, 999_999)
            self.api.chamar(
                "GET", f"/api/v1/ordens-servico/{inexistente}/status/",
                rng=self.rng,
                correlation_id=self.correlation_id,
            )
        else:
            # /simulacao/orcamento/ dispara chamada HTTP saindo da aplicacao:
            # e a integracao externa que o painel de falhas de integracao observa
            self.api.chamar(
                "POST", "/api/v1/simulacao/orcamento/",
                {
                    "ordem_servico_id": ordem_id or self.rng.randint(900_000, 999_999),
                    "decisao": "APROVADO",
                    "motivo": "Decisao fora do estado AGUARDANDO.",
                },
                rng=self.rng,
                correlation_id=self.correlation_id,
            )

    # -- ciclo completo -----------------------------------------------------

    def executar(self) -> None:
        cliente, veiculo = self._cliente_e_veiculo()
        codigo, corpo, _ = self.api.chamar(
            "POST", "/api/v1/ordens-servico/abrir/",
            {"cliente": cliente, "veiculo": veiculo, "servicos": [], "pecas": []},
            rng=self.rng,
            correlation_id=self.correlation_id,
        )
        if codigo != 201 or "ordem_servico_id" not in corpo:
            self.metricas.registrar("erros_inesperados")
            self._log(f"abertura falhou: HTTP {codigo} {corpo}")
            return

        ordem_id = corpo["ordem_servico_id"]
        self.metricas.registrar("ordens_abertas")
        self._log(f"OS {ordem_id} aberta (RECEBIDA)")

        if self.rng.random() < self.config.falhas:
            self._injetar_falha(ordem_id)

        if not self._dormir("RECEBIDA"):
            return
        if not self._transicionar(ordem_id, "DIAGNOSTICO"):
            return

        # A OS pode voltar para DIAGNOSTICO quando o orcamento e recusado.
        # Duas idas e vindas bastam para o painel mostrar retrabalho sem
        # deixar OS presa em laco infinito.
        for tentativa in range(TENTATIVAS_DIAGNOSTICO):
            if not self._dormir("DIAGNOSTICO"):
                return
            if not self._transicionar(ordem_id, "AGUARDANDO"):
                return
            if not self._dormir("AGUARDANDO"):
                return

            sorteio = self.rng.random()
            if sorteio < DESFECHO_APROVADO:
                # O proprio endpoint de orcamento ja move AGUARDANDO -> EXECUCAO.
                # Emitir a transicao de novo aqui seria EXECUCAO -> EXECUCAO, que
                # a policy recusa e viraria erro falso em todo ciclo aprovado.
                if not self._decidir_orcamento(ordem_id, "APROVADO"):
                    return
                break
            ultima_tentativa = tentativa >= TENTATIVAS_DIAGNOSTICO - 1
            if sorteio < DESFECHO_APROVADO + DESFECHO_RECUSADO and not ultima_tentativa:
                # A recusa ja devolve a OS para DIAGNOSTICO do lado da aplicacao.
                if not self._decidir_orcamento(ordem_id, "RECUSADO"):
                    return
                self.metricas.registrar("retrabalho")
                self._log(f"OS {ordem_id} recusada, volta para DIAGNOSTICO")
                continue
            if sorteio < DESFECHO_APROVADO + DESFECHO_RECUSADO + DESFECHO_CANCELADO:
                if self._transicionar(ordem_id, "CANCELADA"):
                    self.metricas.registrar("canceladas")
                    self._log(f"OS {ordem_id} cancelada")
                return
            self._log(f"OS {ordem_id} parada em AGUARDANDO (cliente nao respondeu)")
            return  # cliente que nunca responde: a OS fica na fila de proposito
        else:
            return  # sem aprovacao nao existe EXECUCAO: nao seguir adiante

        if not self._dormir("EXECUCAO"):
            return
        # OS aberta sem servicos nem pecas: a policy de finalizacao passa
        if not self._transicionar(ordem_id, "FINALIZADA"):
            return
        if not self._dormir("FINALIZADA"):
            return
        if self._transicionar(ordem_id, "ENTREGUE"):
            self.metricas.registrar("entregues")
            self._log(f"OS {ordem_id} entregue")


# ---------------------------------------------------------------------------
# Trafego de leitura
# ---------------------------------------------------------------------------

def trafego_de_leitura(api: ClienteAPI, config: argparse.Namespace,
                       rng: random.Random, parar_leitura: threading.Event,
                       parar: threading.Event) -> None:
    """Consulta a fila em intervalos, como um painel de recepcao aberto.

    Sem isso o dashboard de latencia so mostra escrita, e a mediana fica
    distorcida para cima.

    Dois eventos de parada, de proposito: `parar_leitura` encerra so a leitura,
    no inicio da drenagem, para que a espera pelas OS em andamento nao fique
    presa nestas threads (que rodam em laco infinito). `parar` e o aborto geral.
    """
    while not parar_leitura.is_set() and not parar.is_set():
        # Trafego de leitura nao tem ciclo de OS nem correlacao com nenhuma chamada
        # de negocio de escrita, entao nao passa correlation_id: nenhuma leitura
        # carrega X-Correlation-Id.
        api.chamar("GET", "/api/v1/ordens-servico/fila/", rng=rng)
        if parar_leitura.wait(rng.uniform(1.0, 4.0)):
            return


# ---------------------------------------------------------------------------
# Encerramento
# ---------------------------------------------------------------------------

def espera_maxima_ciclo(aceleracao: float,
                        tentativas: int = TENTATIVAS_DIAGNOSTICO) -> float:
    """Pior caso, em segundos, para uma OS recem-aberta fechar o ciclo.

    Somatorio do teto de permanencia de cada status no caminho mais longo
    (todas as recusas de orcamento possiveis), comprimido pela aceleracao.
    """
    horas = (
        PERMANENCIA_HORAS["RECEBIDA"][1]
        + tentativas * (
            PERMANENCIA_HORAS["DIAGNOSTICO"][1] + PERMANENCIA_HORAS["AGUARDANDO"][1]
        )
        + PERMANENCIA_HORAS["EXECUCAO"][1]
        + PERMANENCIA_HORAS["FINALIZADA"][1]
    )
    return horas * 3600 / aceleracao


def encerrar(threads_os: list, threads_leitura: list,
             parar_leitura: threading.Event, parar: threading.Event,
             espera_final: float) -> int:
    """Encerra na ordem certa e devolve quantos ciclos ficaram incompletos.

    A ordem importa: os leitores rodam em laco infinito e so terminam por
    evento, entao esperar por eles junto com as OS consumia todo o orcamento de
    drenagem e deixava os ciclos de verdade pela metade. Primeiro os leitores
    saem, depois as OS drenam ate `espera_final`, e so entao vem o aborto geral.
    """
    parar_leitura.set()

    limite = time.monotonic() + max(0.0, espera_final)
    try:
        for thread in threads_os:
            restante = limite - time.monotonic()
            if restante <= 0:
                break
            thread.join(timeout=restante)
    except KeyboardInterrupt:
        print("\nSegundo Ctrl+C: abortando os ciclos ainda em andamento.")

    # Conta ciclos incompletos na hora do corte, nao depois de parar.set()
    incompletos = sum(1 for thread in threads_os if thread.is_alive())

    # Tira do wait quem ainda estiver dormindo entre duas transicoes.
    parar.set()
    limite_aborto = time.monotonic() + ESPERA_ABORTO_SEGUNDOS
    for thread in threads_os + threads_leitura:
        restante = limite_aborto - time.monotonic()
        if restante <= 0:
            break
        thread.join(timeout=restante)

    return incompletos


# ---------------------------------------------------------------------------
# Orquestracao
# ---------------------------------------------------------------------------

def montar_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gera trafego realista de ordens de servico para observabilidade.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--base-url", default=os.getenv("CARGA_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--usuario", default=os.getenv("CARGA_USUARIO", "admin"))
    parser.add_argument("--senha", default=os.getenv("CARGA_SENHA", "admin"))
    parser.add_argument("--duracao", type=int, default=300,
                        help="Segundos de geracao. Ignorado se --ordens for usado.")
    parser.add_argument("--ordens", type=int, default=0,
                        help="Numero fixo de OS a abrir. Sobrepoe --duracao.")
    parser.add_argument("--taxa", type=float, default=10.0,
                        help="Ordens de servico abertas por minuto.")
    parser.add_argument("--aceleracao", type=float, default=3600.0,
                        help="Compressao do tempo. 3600 = 1 hora de oficina por segundo.")
    parser.add_argument("--falhas", type=float, default=0.08,
                        help="Fracao de OS que dispara uma falha deliberada (0 a 1).")
    parser.add_argument("--recorrencia", type=float, default=0.30,
                        help="Fracao de OS abertas para cliente ja conhecido.")
    parser.add_argument("--concorrencia", type=int, default=12,
                        help="Maximo de OS em andamento ao mesmo tempo.")
    parser.add_argument("--unidades", nargs="+", default=UNIDADES_PADRAO,
                        help="Unidades da oficina, usadas como facet nos paineis.")
    parser.add_argument("--leitores", type=int, default=2,
                        help="Threads consultando a fila continuamente.")
    parser.add_argument("--espera-final", type=float, default=None,
                        help="Segundos para as OS em andamento fecharem o ciclo "
                             "no encerramento. Padrao: pior caso do ciclo na "
                             "aceleracao escolhida. Use 0 para sair na hora.")
    parser.add_argument("--semente", type=int, default=None,
                        help="Semente aleatoria, para execucao reproduzivel.")
    parser.add_argument("--verboso", action="store_true")
    return parser.parse_args()


def validar(config: argparse.Namespace) -> None:
    if not 0.0 <= config.falhas <= 1.0:
        raise SystemExit("--falhas precisa estar entre 0 e 1.")
    if not 0.0 <= config.recorrencia <= 1.0:
        raise SystemExit("--recorrencia precisa estar entre 0 e 1.")
    if config.aceleracao <= 0:
        raise SystemExit("--aceleracao precisa ser maior que zero.")
    if config.taxa <= 0:
        raise SystemExit("--taxa precisa ser maior que zero.")
    if config.espera_final is not None and config.espera_final < 0:
        raise SystemExit("--espera-final nao pode ser negativa.")
    if config.concorrencia <= 0:
        raise SystemExit("--concorrencia precisa ser maior que zero.")
    if config.leitores < 0:
        raise SystemExit("--leitores nao pode ser negativo.")
    if config.duracao < 0:
        raise SystemExit("--duracao nao pode ser negativa.")
    if config.ordens < 0:
        raise SystemExit("--ordens nao pode ser negativo.")


def relatorio(metricas: Metricas, segundos: float, incompletos: int = 0) -> None:
    print("\n" + "=" * 62)
    print("RESUMO DA GERACAO DE CARGA")
    print("=" * 62)
    print(f"Duracao real          : {segundos:.1f} s")
    print(f"Ordens abertas        : {metricas.ordens_abertas}")
    print(f"Transicoes aceitas    : {metricas.transicoes_ok}")
    print(f"OS entregues          : {metricas.entregues}")
    print(f"OS canceladas         : {metricas.canceladas}")
    print(f"Retrabalho (recusas)  : {metricas.retrabalho}")
    print(f"Falhas injetadas      : {metricas.falhas_injetadas}")
    print(f"Erros inesperados     : {metricas.erros_inesperados}")
    if incompletos:
        print(
            f"Ciclos incompletos    : {incompletos} "
            "(OS abortadas no meio; use --espera-final maior para drenar tudo)"
        )

    if metricas.latencias_ms:
        amostras = sorted(metricas.latencias_ms)
        def percentil(p: float) -> float:
            indice = min(len(amostras) - 1, int(len(amostras) * p))
            return amostras[indice]
        print(f"\nRequisicoes           : {len(amostras)}")
        print(f"Latencia p50 / p95    : {statistics.median(amostras):.0f} ms / {percentil(0.95):.0f} ms")

    if metricas.por_status_http:
        print("\nRespostas por codigo HTTP:")
        for codigo in sorted(metricas.por_status_http):
            rotulo = "erro de transporte" if codigo == 0 else str(codigo)
            print(f"  {rotulo:>18} : {metricas.por_status_http[codigo]}")

    if metricas.erros_inesperados:
        print(
            "\nATENCAO: houve erro inesperado. Rode com --verboso para ver a causa;"
            "\nfalha injetada e contada separadamente e nao entra nesse numero."
        )


def main() -> int:
    config = montar_argumentos()
    validar(config)

    semente = config.semente if config.semente is not None else random.randrange(2**31)
    print(f"Semente aleatoria: {semente} (use --semente {semente} para repetir)")

    metricas = Metricas()
    api = ClienteAPI(config.base_url, config.usuario, config.senha, metricas)
    try:
        api.autenticar()
    except (RuntimeError, urllib.error.URLError, OSError) as erro:
        print(f"ERRO: {erro}", file=sys.stderr)
        return 1
    print(f"Autenticado em {config.base_url} como '{config.usuario}'.")

    parar = threading.Event()
    parar_leitura = threading.Event()
    clientes_conhecidos: list = []
    lock_clientes = threading.Lock()
    vagas = threading.Semaphore(config.concorrencia)
    threads_os: list[threading.Thread] = []
    threads_leitura: list[threading.Thread] = []

    for indice in range(config.leitores):
        leitor = threading.Thread(
            target=trafego_de_leitura,
            args=(api, config, random.Random(semente + 9000 + indice),
                  parar_leitura, parar),
            daemon=True,
        )
        leitor.start()
        threads_leitura.append(leitor)

    intervalo = 60.0 / config.taxa
    limite_ordens = config.ordens if config.ordens > 0 else None
    fim = None if limite_ordens else time.monotonic() + config.duracao
    alvo = f"{limite_ordens} ordens" if limite_ordens else f"{config.duracao}s"
    print(
        f"Gerando {alvo} | taxa={config.taxa}/min | aceleracao={config.aceleracao}x "
        f"| falhas={config.falhas:.0%} | concorrencia={config.concorrencia}"
    )
    print("Ctrl+C encerra e imprime o resumo parcial.\n")

    inicio = time.monotonic()
    lancadas = 0
    try:
        while True:
            # Verifica limite de ordens primeiro
            if limite_ordens is not None and lancadas >= limite_ordens:
                break
            # Verifica limite de duracao
            if fim is not None and time.monotonic() >= fim:
                break

            # Espera por uma vaga com timeout, revalidando prazo a cada volta
            tempo_restante = None if fim is None else max(0, fim - time.monotonic())
            timeout_vaga = min(intervalo, tempo_restante) if tempo_restante is not None else intervalo

            if not vagas.acquire(timeout=timeout_vaga):
                # Timeout aguardando vaga: verifica se venceu o prazo
                if fim is not None and time.monotonic() >= fim:
                    break
                # Senao continua tentando
                continue

            # Revalidar depois de conseguir a vaga
            if limite_ordens is not None and lancadas >= limite_ordens:
                vagas.release()
                break
            if fim is not None and time.monotonic() >= fim:
                vagas.release()
                break

            rng_os = random.Random(semente + lancadas)
            simulador = SimuladorOrdemServico(
                api, config, metricas, rng_os,
                clientes_conhecidos, lock_clientes, parar,
            )

            def trabalhar(alvo_simulador=simulador):
                try:
                    alvo_simulador.executar()
                except Exception:
                    # Sem isto a thread imprime o traceback e morre sozinha: o
                    # processo principal terminaria com codigo 0 mascarando a quebra.
                    metricas.registrar("erros_inesperados")
                    print(
                        f"[{time.strftime('%H:%M:%S')}] erro inesperado no ciclo da OS: "
                        f"{traceback.format_exc() if config.verboso else sys.exc_info()[1]}",
                        file=sys.stderr, flush=True,
                    )
                finally:
                    vagas.release()

            thread = threading.Thread(target=trabalhar, daemon=True)
            thread.start()
            threads_os.append(thread)
            lancadas += 1

            # So dorme se nao foi a ultima ordem
            if limite_ordens is None or lancadas < limite_ordens:
                tempo_dormir_max = intervalo
                if fim is not None:
                    tempo_restante = fim - time.monotonic()
                    tempo_dormir_max = min(intervalo, max(0, tempo_restante))
                # Sono interrompivel por parar
                parar.wait(tempo_dormir_max)
    except KeyboardInterrupt:
        print("\nInterrompido. Ctrl+C de novo aborta sem drenar.")

    # Deixa as OS ja abertas terminarem o ciclo antes de encerrar,
    # senao o painel de tempo medio por status fica com buracos.
    espera_final = (
        config.espera_final if config.espera_final is not None
        else espera_maxima_ciclo(config.aceleracao)
    )
    em_andamento = sum(1 for thread in threads_os if thread.is_alive())
    if em_andamento and espera_final:
        print(
            f"Aguardando {em_andamento} OS fecharem o ciclo "
            f"(ate {espera_final:.0f}s)..."
        )
    incompletos = encerrar(
        threads_os, threads_leitura, parar_leitura, parar, espera_final
    )

    relatorio(metricas, time.monotonic() - inicio, incompletos)
    return 0 if metricas.erros_inesperados == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
