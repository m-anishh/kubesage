"""Read-only tools the LLM can call. Each one is a plain function plus a Bedrock toolSpec.

Guardrails live here, in code, not in the prompt:
- only namespaces in ALLOWED_NAMESPACES can be read
- env var values are stripped from deployments
- secrets in logs are masked
- every output is truncated
"""

import json
import re
from datetime import UTC, datetime

import httpx
from kubernetes import client as k8s
from kubernetes import config as k8s_config

from app import config, rag

_core: k8s.CoreV1Api | None = None
_apps: k8s.AppsV1Api | None = None


def bridge_bearer_token(cfg: k8s.Configuration) -> k8s.Configuration:
    """The config loaders store the token as api_key['authorization'], but this client version only sends
    api_key['BearerToken']: without this every call goes out with no token and gets 401 Unauthorized.
    Copying it inside the refresh hook keeps the rotating service-account token working."""
    loader_hook = cfg.refresh_api_key_hook

    def refresh(c: k8s.Configuration) -> None:
        if loader_hook:
            loader_hook(c)
        if "authorization" in c.api_key:
            c.api_key["BearerToken"] = c.api_key["authorization"]

    cfg.refresh_api_key_hook = refresh
    refresh(cfg)
    return cfg


def _clients() -> tuple[k8s.CoreV1Api, k8s.AppsV1Api]:
    global _core, _apps
    if _core is None:
        try:
            k8s_config.load_incluster_config()
        except k8s_config.ConfigException:
            k8s_config.load_kube_config()  # local development with your kubeconfig
        api = k8s.ApiClient(bridge_bearer_token(k8s.Configuration.get_default_copy()))
        _core, _apps = k8s.CoreV1Api(api), k8s.AppsV1Api(api)
    return _core, _apps


def _check_namespace(namespace: str) -> None:
    if namespace not in config.ALLOWED_NAMESPACES:
        raise PermissionError(f"namespace '{namespace}' is not allowed; allowed: {config.ALLOWED_NAMESPACES}")


SECRET_PATTERNS = [
    (re.compile(r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key)\b(\s*[=:]\s*)\S+"), r"\1\2***"),
    (re.compile(r"(?i)\b(authorization:\s*)(bearer|basic)\s+\S+"), r"\1\2 ***"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AKIA***"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), "gh*_***"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), "github_pat_***"),
]


def mask_secrets(text: str) -> str:
    for pattern, replacement in SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _ts(value) -> str | None:
    return value.isoformat() if value else None


# ---------------------------------------------------------------- tools


def list_pods(namespace: str, app: str) -> str:
    _check_namespace(namespace)
    core, _ = _clients()
    pods = core.list_namespaced_pod(namespace, label_selector=f"app.kubernetes.io/name={app}").items
    rows = []
    for p in pods:
        statuses = p.status.container_statuses or []
        rows.append(
            {
                "pod": p.metadata.name,
                "phase": p.status.phase,
                "restarts": sum(s.restart_count for s in statuses),
                "ready": all(s.ready for s in statuses) if statuses else False,
            }
        )
    return json.dumps(rows or f"no pods with label app.kubernetes.io/name={app}")


def get_pod_status(namespace: str, pod: str) -> str:
    _check_namespace(namespace)
    core, _ = _clients()
    p = core.read_namespaced_pod(pod, namespace)
    containers = []
    for s in p.status.container_statuses or []:
        info = {"name": s.name, "ready": s.ready, "restarts": s.restart_count, "image": s.image}
        if s.state.waiting:
            info["waiting"] = {"reason": s.state.waiting.reason, "message": s.state.waiting.message}
        if s.state.running:
            info["running_since"] = _ts(s.state.running.started_at)
        last = s.last_state.terminated if s.last_state else None
        if last:
            info["last_termination"] = {
                "reason": last.reason,
                "exit_code": last.exit_code,
                "finished_at": _ts(last.finished_at),
            }
        containers.append(info)
    return json.dumps(
        {"pod": pod, "phase": p.status.phase, "node": p.spec.node_name, "containers": containers}, default=str
    )


def get_pod_logs(namespace: str, pod: str, previous: bool = False) -> str:
    _check_namespace(namespace)
    core, _ = _clients()
    try:
        logs = core.read_namespaced_pod_log(pod, namespace, tail_lines=200, previous=previous)
    except k8s.ApiException as exc:
        if exc.status == 400 and previous:
            return "no previous container logs (the container has not restarted yet)"
        raise
    return mask_secrets(logs) or "(empty log)"


def get_events(namespace: str, name: str) -> str:
    """Events for an object; a deployment name also matches its ReplicaSets and pods (name prefix)."""
    _check_namespace(namespace)
    core, _ = _clients()
    events = [e for e in core.list_namespaced_event(namespace).items if e.involved_object.name.startswith(name)]
    epoch = datetime.min.replace(tzinfo=UTC)
    events.sort(key=lambda e: e.last_timestamp or e.event_time or e.metadata.creation_timestamp or epoch)
    rows = [
        {
            "time": _ts(e.last_timestamp or e.event_time),
            "object": f"{e.involved_object.kind}/{e.involved_object.name}",
            "type": e.type,
            "reason": e.reason,
            "message": (e.message or "")[:300],
            "count": e.count,
        }
        for e in events[-20:]
    ]
    return json.dumps(rows or f"no events for {name}")


def get_deployment(namespace: str, name: str) -> str:
    _check_namespace(namespace)
    _, apps = _clients()
    d = apps.read_namespaced_deployment(name, namespace)
    return json.dumps(summarize_deployment(d), default=str)


def summarize_deployment(d) -> dict:
    """RBAC 'get' returns env values; strip them here so secrets never reach the LLM."""
    containers = []
    for c in d.spec.template.spec.containers:
        res = c.resources
        containers.append(
            {
                "name": c.name,
                "image": c.image,
                "requests": res.requests if res else None,
                "limits": res.limits if res else None,
                "env_names": [e.name for e in (c.env or [])],
            }
        )
    return {
        "name": d.metadata.name,
        "replicas": d.spec.replicas,
        "ready_replicas": d.status.ready_replicas or 0,
        "generation": d.metadata.generation,
        "containers": containers,
        "conditions": [
            {"type": c.type, "status": c.status, "reason": c.reason, "message": c.message}
            for c in (d.status.conditions or [])
        ],
    }


def get_recent_changes(app: str) -> str:
    """Last 5 commits to this app's values file in the GitOps repo, with the diff of that file."""
    if not re.fullmatch(r"[a-z0-9-]{1,40}", app):
        raise ValueError("app must be a lowercase name like 'payments-api'")
    path = config.GITOPS_VALUES_PATH.format(app=app)
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    token = config.github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    base = f"https://api.github.com/repos/{config.GITOPS_REPO}"
    with httpx.Client(timeout=10, headers=headers) as gh:
        resp = gh.get(f"{base}/commits", params={"path": path, "per_page": 5})
        resp.raise_for_status()
        rows = []
        for c in resp.json():
            detail = gh.get(f"{base}/commits/{c['sha']}").json()
            patch = next((f.get("patch", "") for f in detail.get("files", []) if f["filename"] == path), "")
            rows.append(
                {
                    "sha": c["sha"],
                    "date": c["commit"]["author"]["date"],
                    "author": c["commit"]["author"]["name"],
                    "message": c["commit"]["message"].splitlines()[0][:200],
                    "diff": patch[:600],
                }
            )
    return json.dumps(rows or f"no commits touching {path}")


def search_runbooks(query: str) -> str:
    return json.dumps(rag.search(query, limit=3))


# ---------------------------------------------------------------- specs for Bedrock Converse

TOOLS = {
    "list_pods": list_pods,
    "get_pod_status": get_pod_status,
    "get_pod_logs": get_pod_logs,
    "get_events": get_events,
    "get_deployment": get_deployment,
    "get_recent_changes": get_recent_changes,
    "search_runbooks": search_runbooks,
}


def _spec(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "toolSpec": {
            "name": name,
            "description": description,
            "inputSchema": {"json": {"type": "object", "properties": properties, "required": required}},
        }
    }


_NS = {"type": "string", "description": "Kubernetes namespace, e.g. dev"}

TOOL_SPECS = [
    _spec(
        "list_pods",
        "List pods of an app (deployment name) with phase, restarts and readiness. "
        "Use it when the alert names a service but not a pod.",
        {"namespace": _NS, "app": {"type": "string", "description": "App name, e.g. payments-api"}},
        ["namespace", "app"],
    ),
    _spec(
        "get_pod_status",
        "Pod phase, restart count, current waiting reason and last termination reason and exit code.",
        {"namespace": _NS, "pod": {"type": "string"}},
        ["namespace", "pod"],
    ),
    _spec(
        "get_pod_logs",
        "Last 200 log lines of a pod, secrets masked. Set previous=true to read the crashed container.",
        {"namespace": _NS, "pod": {"type": "string"}, "previous": {"type": "boolean"}},
        ["namespace", "pod"],
    ),
    _spec(
        "get_events",
        "Last 20 Kubernetes events for an object. A deployment name also returns events of its pods.",
        {"namespace": _NS, "name": {"type": "string", "description": "Pod or deployment name"}},
        ["namespace", "name"],
    ),
    _spec(
        "get_deployment",
        "Deployment image tag, replicas, resource requests and limits, env var names (no values), conditions.",
        {"namespace": _NS, "name": {"type": "string", "description": "Deployment name, e.g. payments-api"}},
        ["namespace", "name"],
    ),
    _spec(
        "get_recent_changes",
        "Last 5 commits to the app's values file in the GitOps repo, with SHA and diff. "
        "Use it to find which change caused the incident.",
        {"app": {"type": "string", "description": "App name, e.g. payments-api"}},
        ["app"],
    ),
    _spec(
        "search_runbooks",
        "Search the team's runbooks. Returns the 3 best matching sections with their source.",
        {"query": {"type": "string", "description": "What you are looking for, e.g. 'container OOMKilled'"}},
        ["query"],
    ),
]
