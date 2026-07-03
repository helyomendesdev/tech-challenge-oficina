#!/usr/bin/env python3
"""Smoke test reproduzivel contra a aplicacao implantada no Kubernetes."""

import json
import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request


NAMESPACE = os.getenv("K8S_NAMESPACE", "oficina")
LOCAL_PORT = int(os.getenv("SMOKE_LOCAL_PORT", "18000"))
BASE_URL = f"http://127.0.0.1:{LOCAL_PORT}"
USERNAME = f"smoke_{secrets.token_hex(5)}"
PASSWORD = secrets.token_urlsafe(24)


def run(command, *, check=True):
    printable = [
        "SMOKE_PASSWORD=<redacted>" if arg.startswith("SMOKE_PASSWORD=") else arg
        for arg in command
    ]
    print("+", " ".join(printable))
    return subprocess.run(command, check=check, text=True, capture_output=True)


def wait_for_port(process, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError("kubectl port-forward terminou antes de ficar pronto")
        try:
            with socket.create_connection(("127.0.0.1", LOCAL_PORT), timeout=1):
                return
        except OSError:
            time.sleep(0.5)
    raise TimeoutError("timeout aguardando kubectl port-forward")


def request(path, *, method="GET", payload=None, token=None):
    headers = {"Accept": "application/json"}
    body = None
    if payload is not None:
        body = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE_URL + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return response.status, response.read(), response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        raise AssertionError(f"{method} {path} retornou {exc.code}: {exc.read().decode()}") from exc


def main():
    user_code = (
        "import os; "
        "from django.contrib.auth import get_user_model; "
        "User=get_user_model(); "
        "u,_=User.objects.get_or_create(username=os.environ['SMOKE_USERNAME']); "
        "u.set_password(os.environ['SMOKE_PASSWORD']); u.is_staff=True; u.save()"
    )
    delete_code = (
        "import os; from django.contrib.auth import get_user_model; "
        "get_user_model().objects.filter(username=os.environ['SMOKE_USERNAME']).delete()"
    )
    exec_prefix = [
        "kubectl", "exec", "-n", NAMESPACE, "deployment/oficina-app", "--", "env",
        f"SMOKE_USERNAME={USERNAME}", f"SMOKE_PASSWORD={PASSWORD}",
        "python", "manage.py", "shell", "-c",
    ]

    run(exec_prefix + [user_code])
    port_forward = subprocess.Popen(
        [
            "kubectl", "port-forward", "-n", NAMESPACE,
            "service/oficina-app", f"{LOCAL_PORT}:8000",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_for_port(port_forward)

        status, body, _ = request("/health/live/")
        assert status == 200 and json.loads(body) == {"status": "ok"}
        print("OK GET /health/live/")

        status, body, _ = request("/health/ready/")
        assert status == 200 and json.loads(body) == {"status": "ready"}
        print("OK GET /health/ready/")

        status, body, content_type = request("/api/schema/")
        assert status == 200 and len(body) > 1000 and "openapi" in body.decode().lower()
        assert content_type
        print(f"OK GET /api/schema/ content-type={content_type}")

        status, body, _ = request(
            "/api/token/",
            method="POST",
            payload={"username": USERNAME, "password": PASSWORD},
        )
        token_data = json.loads(body)
        access_token = token_data.get("access")
        assert status == 200 and access_token
        print("OK POST /api/token/")

        status, body, _ = request("/api/v1/clientes/", token=access_token)
        api_data = json.loads(body)
        assert status == 200 and (isinstance(api_data, list) or "results" in api_data)
        print("OK GET /api/v1/clientes/ autenticado")
        print("SMOKE_TEST=PASS")
    finally:
        port_forward.terminate()
        try:
            port_forward.wait(timeout=5)
        except subprocess.TimeoutExpired:
            port_forward.kill()
        run(exec_prefix + [delete_code], check=False)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"SMOKE_TEST=FAIL: {exc}", file=sys.stderr)
        raise
