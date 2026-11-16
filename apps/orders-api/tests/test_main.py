import httpx
import pytest
from fastapi.testclient import TestClient

from app import faults
from app.main import app


@pytest.fixture
def client(monkeypatch):
    for var in ("FAULT_CRASH", "FAULT_MEMORY_LEAK", "FAULT_LATENCY_MS", "FAULT_ERROR_RATE", "FAULT_LOG_INJECTION"):
        monkeypatch.delenv(var, raising=False)
    with TestClient(app) as c:
        yield c


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_orders_calls_payments(client, monkeypatch):
    real_client = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/pay"
        return httpx.Response(200, json={"status": "paid"})

    monkeypatch.setattr(
        "app.main.httpx.AsyncClient",
        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
    )
    body = client.get("/orders").json()
    assert body["orders"][0]["payment"] == {"status": "paid"}


def test_orders_returns_502_when_payments_down(client, monkeypatch):
    real_client = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    monkeypatch.setattr(
        "app.main.httpx.AsyncClient",
        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
    )
    assert client.get("/orders").status_code == 502


def test_error_rate_fault(client, monkeypatch):
    monkeypatch.setenv("FAULT_ERROR_RATE", "1")
    assert client.get("/orders").status_code == 500


def test_metrics_exposed(client):
    client.get("/healthz")
    text = client.get("/metrics").text
    assert "http_request_duration_seconds_bucket" in text
    assert 'le="2.5"' in text


def test_crash_fault_exits(monkeypatch):
    monkeypatch.setenv("FAULT_CRASH", "true")
    with pytest.raises(SystemExit):
        faults.check_crash()
