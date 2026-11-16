import pytest
from kubernetes.client import (
    V1Container,
    V1Deployment,
    V1DeploymentSpec,
    V1DeploymentStatus,
    V1EnvVar,
    V1LabelSelector,
    V1ObjectMeta,
    V1PodSpec,
    V1PodTemplateSpec,
    V1ResourceRequirements,
)

from app import config, rag, tools


def test_mask_secrets():
    raw = "connecting with password=hunter2 token: abc123 key AKIAABCDEFGHIJKLMNOP and ghp_" + "a" * 36
    masked = tools.mask_secrets(raw)
    for secret in ("hunter2", "abc123", "AKIAABCDEFGHIJKLMNOP", "ghp_" + "a" * 36):
        assert secret not in masked
    assert "password=***" in masked


def test_mask_keeps_normal_lines():
    line = "GET /orders 200 in 12ms"
    assert tools.mask_secrets(line) == line


def test_deployment_env_values_are_stripped():
    d = V1Deployment(
        metadata=V1ObjectMeta(name="payments-api", generation=3),
        spec=V1DeploymentSpec(
            replicas=1,
            selector=V1LabelSelector(match_labels={"app": "x"}),
            template=V1PodTemplateSpec(
                spec=V1PodSpec(
                    containers=[
                        V1Container(
                            name="app",
                            image="repo/payments-api:abc",
                            env=[V1EnvVar(name="DB_PASSWORD", value="s3cret"), V1EnvVar(name="FAULT_CRASH", value="1")],
                            resources=V1ResourceRequirements(limits={"memory": "128Mi"}),
                        )
                    ]
                )
            ),
        ),
        status=V1DeploymentStatus(ready_replicas=0),
    )
    summary = tools.summarize_deployment(d)
    assert summary["containers"][0]["env_names"] == ["DB_PASSWORD", "FAULT_CRASH"]
    assert "s3cret" not in str(summary)
    assert summary["containers"][0]["limits"] == {"memory": "128Mi"}


def test_namespace_guard(monkeypatch):
    monkeypatch.setattr(config, "ALLOWED_NAMESPACES", ["dev"])
    with pytest.raises(PermissionError):
        tools.get_pod_status("kube-system", "coredns-123")


def test_recent_changes_rejects_odd_app_names():
    with pytest.raises(ValueError):
        tools.get_recent_changes("../../etc")


def test_every_tool_has_a_spec():
    names = {s["toolSpec"]["name"] for s in tools.TOOL_SPECS}
    assert names == set(tools.TOOLS)


def test_split_runbook_by_heading():
    text = "# OOMKilled\n\n## Symptoms\nexit 137\n\n## Fix\nraise the limit\n"
    chunks = rag.split_runbook("oomkilled.md", text)
    assert [c["heading"] for c in chunks] == ["Symptoms", "Fix"]
    assert chunks[0]["title"] == "OOMKilled"
    assert chunks[1]["text"] == "raise the limit"


def test_real_runbooks_all_have_sections():
    chunks = rag.load_chunks()
    sources = {c["source"] for c in chunks}
    assert len(sources) == 6
    assert len(chunks) >= 18
