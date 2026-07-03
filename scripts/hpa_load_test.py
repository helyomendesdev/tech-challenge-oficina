#!/usr/bin/env python3
"""Gera carga e comprova scale-up e scale-down do HPA no Kind."""

import concurrent.futures
import os
import socket
import subprocess
import threading
import time
import urllib.request


NAMESPACE = os.getenv("K8S_NAMESPACE", "oficina")
DEPLOYMENT = "oficina-app"
HPA = "oficina-app-hpa"
LOCAL_PORT = int(os.getenv("LOAD_LOCAL_PORT", "18001"))
WORKERS = int(os.getenv("HPA_LOAD_WORKERS", "48"))
LOAD_SECONDS = int(os.getenv("HPA_LOAD_SECONDS", "180"))
SCALE_DOWN_TIMEOUT = int(os.getenv("HPA_SCALE_DOWN_TIMEOUT", "420"))
INITIAL_STABLE_TIMEOUT = int(os.getenv("HPA_INITIAL_STABLE_TIMEOUT", "420"))
URL = f"http://127.0.0.1:{LOCAL_PORT}/api/schema/"


def kubectl(*args, check=True):
    result = subprocess.run(
        ["kubectl", *args], check=check, text=True, capture_output=True
    )
    return result.stdout.strip()


def replicas():
    value = kubectl(
        "get", "deployment", DEPLOYMENT, "-n", NAMESPACE,
        "-o", "jsonpath={.status.replicas}",
    )
    return int(value or "0")


def min_replicas():
    return int(
        kubectl(
            "get", "hpa", HPA, "-n", NAMESPACE,
            "-o", "jsonpath={.spec.minReplicas}",
        )
    )


def snapshot(label):
    current_replicas = replicas()
    print(f"\n=== {label} replicas={current_replicas} ===", flush=True)
    print(kubectl("get", "hpa", HPA, "-n", NAMESPACE), flush=True)
    print(kubectl("top", "pods", "-n", NAMESPACE), flush=True)
    return current_replicas


def wait_for_port(process, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError("kubectl port-forward terminou inesperadamente")
        try:
            with socket.create_connection(("127.0.0.1", LOCAL_PORT), timeout=1):
                return
        except OSError:
            time.sleep(0.5)
    raise TimeoutError("timeout aguardando port-forward")


def load_worker(stop_event, counters, lock):
    while not stop_event.is_set():
        try:
            with urllib.request.urlopen(URL, timeout=15) as response:
                response.read()
                ok = response.status == 200
        except Exception:
            ok = False
        with lock:
            counters["ok" if ok else "error"] += 1


def main():
    port_forward = subprocess.Popen(
        [
            "kubectl", "port-forward", "-n", NAMESPACE,
            "service/oficina-app", f"{LOCAL_PORT}:8000",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    stop_event = threading.Event()
    counters = {"ok": 0, "error": 0}
    lock = threading.Lock()
    try:
        wait_for_port(port_forward)
        minimum = min_replicas()
        stable_deadline = time.time() + INITIAL_STABLE_TIMEOUT
        while replicas() != minimum and time.time() < stable_deadline:
            snapshot("AGUARDANDO HPA ESTABILIZAR NO MINIMO")
            time.sleep(15)
        if replicas() != minimum:
            raise AssertionError(
                f"HPA nao estabilizou em minReplicas={minimum} antes da carga"
            )
        initial = snapshot("HPA ANTES DA CARGA")
        maximum = initial
        print(f"Iniciando carga: workers={WORKERS}, duracao={LOAD_SECONDS}s", flush=True)

        with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as executor:
            futures = [
                executor.submit(load_worker, stop_event, counters, lock)
                for _ in range(WORKERS)
            ]
            deadline = time.time() + LOAD_SECONDS
            while time.time() < deadline:
                time.sleep(15)
                maximum = max(maximum, snapshot("HPA DURANTE A CARGA"))
            stop_event.set()
            for future in futures:
                future.result(timeout=30)

        print(f"Carga encerrada: respostas={counters}", flush=True)
        scale_down_deadline = time.time() + SCALE_DOWN_TIMEOUT
        final = replicas()
        while time.time() < scale_down_deadline:
            final = snapshot("HPA APOS A CARGA")
            if final == minimum:
                break
            time.sleep(15)

        print(
            f"HPA_RESULT initial={initial} maximum={maximum} final={final}",
            flush=True,
        )
        if maximum <= initial:
            raise AssertionError("HPA nao aumentou o numero de replicas")
        if final != minimum:
            raise AssertionError(
                f"HPA nao retornou a minReplicas={minimum} dentro do timeout"
            )
        print("HPA_TEST=PASS", flush=True)
    finally:
        stop_event.set()
        port_forward.terminate()
        try:
            port_forward.wait(timeout=5)
        except subprocess.TimeoutExpired:
            port_forward.kill()


if __name__ == "__main__":
    main()
