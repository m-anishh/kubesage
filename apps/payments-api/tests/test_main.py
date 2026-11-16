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


def test_pay(client):
    body = client.post("/pay", json={"order_id": 1, "amount": 5.0}).json()
    assert body["status"] == "paid"
    assert body["order_id"] == 1


def test_pay_rejects_bad_input(client):
    assert client.post("/pay", json={"order_id": "abc"}).status_code == 422


def test_error_rate_fault(client, monkeypatch):
    monkeypatch.setenv("FAULT_ERROR_RATE", "1")
    assert client.post("/pay", json={"order_id": 1, "amount": 5.0}).status_code == 500


def test_metrics_count_5xx(client, monkeypatch):
    monkeypatch.setenv("FAULT_ERROR_RATE", "1")
    client.post("/pay", json={"order_id": 1, "amount": 5.0})
    assert 'status="5xx"' in client.get("/metrics").text


def test_crash_fault_exits(monkeypatch):
    monkeypatch.setenv("FAULT_CRASH", "true")
    with pytest.raises(SystemExit):
        faults.check_crash()
