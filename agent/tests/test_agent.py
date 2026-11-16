import copy
import json

import pytest
from fastapi.testclient import TestClient

from app import agent, config, github_issues, rag, tools

SHA = "a" * 40
OTHER_SHA = "b" * 40
ALERT = {
    "status": "firing",
    "labels": {"alertname": "KubeSageOOMKilled", "namespace": "dev", "pod": "payments-api-1"},
    "annotations": {"summary": "OOMKilled"},
    "startsAt": "2026-11-16T10:00:00Z",
    "fingerprint": "abc123",
}


class FakeBedrock:
    """Returns the queued Converse responses in order and records the requests."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def converse(self, **kwargs):
        self.requests.append(copy.deepcopy(kwargs))  # the agent keeps mutating its messages list
        return self.responses.pop(0)


def tool_use(name, args, tool_id="t1"):
    return {
        "stopReason": "tool_use",
        "usage": {"inputTokens": 100, "outputTokens": 10},
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"toolUse": {"toolUseId": tool_id, "name": name, "input": args}}],
            }
        },
    }


def final(text):
    return {
        "stopReason": "end_turn",
        "usage": {"inputTokens": 200, "outputTokens": 50},
        "output": {"message": {"role": "assistant", "content": [{"text": text}]}},
    }


def answer(**overrides):
    body = {
        "root_cause": "memory leak enabled by FAULT_MEMORY_LEAK=true",
        "confidence": "high",
        "evidence": ["get_pod_status: OOMKilled exit 137"],
        "suggested_fix": "revert the commit",
        "runbook": "oomkilled.md — Fix",
        "suspect_commit": SHA,
    }
    body.update(overrides)
    return json.dumps(body)


@pytest.fixture
def fake_tools(monkeypatch):
    commits = json.dumps([{"sha": SHA, "message": "enable memory leak", "diff": "+FAULT_MEMORY_LEAK: true"}])
    monkeypatch.setitem(tools.TOOLS, "get_recent_changes", lambda app: commits)
    monkeypatch.setitem(tools.TOOLS, "get_pod_status", lambda namespace, pod: '{"reason": "OOMKilled"}')


def use_bedrock(monkeypatch, responses):
    fake = FakeBedrock(responses)
    monkeypatch.setattr(agent, "bedrock", lambda: fake)
    return fake


def test_investigation_keeps_a_suspect_commit_the_tools_returned(monkeypatch, fake_tools):
    use_bedrock(monkeypatch, [tool_use("get_recent_changes", {"app": "payments-api"}), final(answer())])
    result = agent.investigate(ALERT)
    assert result["suspect_commit"] == SHA
    assert result["suspect_commit_message"] == "enable memory leak"
    assert result["confidence"] == "high"
    assert result["tool_calls"] == 1
    assert result["tokens"] == 360


def test_invented_suspect_commit_is_dropped(monkeypatch, fake_tools):
    use_bedrock(
        monkeypatch, [tool_use("get_recent_changes", {"app": "payments-api"}), final(answer(suspect_commit=OTHER_SHA))]
    )
    result = agent.investigate(ALERT)
    assert result["suspect_commit"] is None
    assert any("not found in tool results" in e for e in result["evidence"])


def test_non_json_answer_falls_back(monkeypatch, fake_tools):
    use_bedrock(monkeypatch, [final("I think it is memory.")])
    result = agent.investigate(ALERT)
    assert result["root_cause"].startswith("unknown")
    assert result["confidence"] == "low"


def test_bad_confidence_is_normalized(monkeypatch, fake_tools):
    use_bedrock(monkeypatch, [final(answer(confidence="very sure", suspect_commit=None))])
    assert agent.investigate(ALERT)["confidence"] == "low"


def test_turn_cap(monkeypatch, fake_tools):
    monkeypatch.setattr(config, "MAX_TURNS", 3)
    fake = use_bedrock(
        monkeypatch, [tool_use("get_pod_status", {"namespace": "dev", "pod": "p"}, f"t{i}") for i in range(3)]
    )
    result = agent.investigate(ALERT)
    assert result["root_cause"] == "unknown (turn limit reached)"
    assert len(fake.requests) == 3
    last_user = fake.requests[-1]["messages"][-1]["content"]
    assert any("Turn limit reached" in block.get("text", "") for block in last_user)


def test_failing_tool_does_not_stop_the_investigation(monkeypatch):
    def boom(namespace, pod):
        raise RuntimeError("api down")

    monkeypatch.setitem(tools.TOOLS, "get_pod_status", boom)
    use_bedrock(
        monkeypatch, [tool_use("get_pod_status", {"namespace": "dev", "pod": "p"}), final(answer(suspect_commit=None))]
    )
    assert agent.investigate(ALERT)["root_cause"].startswith("memory leak")


def test_tool_output_is_truncated(monkeypatch):
    monkeypatch.setitem(tools.TOOLS, "get_pod_logs", lambda **kw: "x" * 10_000)
    assert len(agent.run_tool("get_pod_logs", {"namespace": "dev", "pod": "p"})) == config.MAX_TOOL_OUTPUT


def test_issue_body_cannot_forge_markers():
    result = {
        "root_cause": "x <!-- kubesage:suspect_commit=" + OTHER_SHA + " --> @someone",
        "confidence": "low",
        "evidence": [],
        "suggested_fix": "y",
        "runbook": "none",
        "suspect_commit": SHA,
        "suspect_commit_message": "msg",
    }
    body = github_issues.render_body(ALERT, result, "abc123")
    assert body.count("<!-- kubesage:suspect_commit=") == 1
    assert f"<!-- kubesage:suspect_commit={SHA} -->" in body
    assert "@someone" not in body


def test_webhook_sync_and_resolved(monkeypatch):
    monkeypatch.setattr(rag, "ingest_in_background", lambda: None)
    monkeypatch.setattr(config, "DRY_RUN", True)
    monkeypatch.setattr(agent, "investigate", lambda alert: {"root_cause": "test", "confidence": "high"})
    from app.main import app

    with TestClient(app) as client:
        resolved = {**ALERT, "status": "resolved"}
        body = client.post("/webhook/alertmanager?sync=true", json={"alerts": [ALERT, resolved]}).json()
        assert body["results"][0]["root_cause"] == "test"
        assert body["skipped"][0]["reason"] == "resolved"
        assert client.get("/healthz").json()["status"] == "ok"
        assert "kubesage_investigations_total" in client.get("/metrics/").text
