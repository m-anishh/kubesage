"""GitHub issues: one per firing alert, commented and closed when the alert resolves.

The agent read untrusted logs, so everything it wrote is sanitized before it goes into the issue:
it must not be able to forge the hidden markers that the rollback workflow reads.
"""

import logging
from datetime import UTC, datetime

import httpx

from app import config, metrics

log = logging.getLogger("github")

API = "https://api.github.com"
FP_MARK = "kubesage:fingerprint="
SHA_MARK = "kubesage:suspect_commit="
LABELS = {
    "incident": "d73a4a",
    "confidence:high": "0e8a16",
    "confidence:medium": "fbca04",
    "confidence:low": "c5def5",
}


def _client() -> httpx.Client:
    token = config.github_token()
    if not token:
        raise RuntimeError(f"no GitHub token: {config.GITHUB_TOKEN_FILE} is missing")
    return httpx.Client(
        base_url=API,
        timeout=15,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )


def sanitize(text: str, limit: int = 1000) -> str:
    text = str(text)[:limit]
    text = text.replace("<!--", "&lt;!--").replace("-->", "--&gt;")  # no fake hidden markers
    text = text.replace("@", "@​")  # no @mentions pinging real people
    return text


def ensure_labels() -> None:
    with _client() as gh:
        for name, color in LABELS.items():
            r = gh.post(f"/repos/{config.ISSUES_REPO}/labels", json={"name": name, "color": color})
            if r.status_code not in (201, 422):  # 422 = already exists
                r.raise_for_status()


def target(alert: dict) -> str:
    labels = alert.get("labels", {})
    return f"{labels.get('namespace', '?')}/{labels.get('pod') or labels.get('service') or '?'}"


def render_body(alert: dict, result: dict, fingerprint: str) -> str:
    labels = alert.get("labels", {})
    evidence = "\n".join(f"- {sanitize(e, 400)}" for e in result.get("evidence", [])) or "- none collected"
    sha = result.get("suspect_commit")
    if sha:
        message = sanitize(result.get("suspect_commit_message", ""), 200)
        commit = f"[`{sha[:7]}`](https://github.com/{config.GITOPS_REPO}/commit/{sha}) {message}"
    else:
        commit = "none found"
    lines = [
        f"## [KubeSage] {labels.get('alertname', 'alert')} — {target(alert)}",
        "",
        f"**Root cause:** {sanitize(result['root_cause'], 500)}   **Confidence:** {result['confidence']}",
        "",
        "### Evidence",
        evidence,
        "",
        "### Suggested fix",
        sanitize(result["suggested_fix"], 800),
        "",
        "### Runbook used",
        sanitize(result.get("runbook", "none"), 200),
        "",
        "### Suspect commit",
        commit,
        "",
        f"<sub>Alert started {alert.get('startsAt', '?')} · {result.get('tool_calls', 0)} tool calls · "
        f"{result.get('tokens', 0)} tokens · {result.get('duration_seconds', '?')} s</sub>",
        "",
        f"<!-- {FP_MARK}{fingerprint} -->",
    ]
    if sha:
        lines.append(f"<!-- {SHA_MARK}{sha} -->")
    lines += [
        "---",
        "Reply `/approve-rollback` to revert the suspect commit in kubesage-gitops."
        if sha
        else "No suspect commit: a human needs to fix this manually.",
    ]
    return "\n".join(lines)


def find_open_issue(fingerprint: str) -> int | None:
    marker = f"{FP_MARK}{fingerprint} "
    with _client() as gh:
        r = gh.get(
            f"/repos/{config.ISSUES_REPO}/issues", params={"labels": "incident", "state": "open", "per_page": 100}
        )
        r.raise_for_status()
        for issue in r.json():
            if marker in (issue.get("body") or ""):
                return issue["number"]
    return None


def create_issue(alert: dict, result: dict, fingerprint: str) -> str:
    title = f"[KubeSage] {alert.get('labels', {}).get('alertname', 'alert')} — {target(alert)}"
    with _client() as gh:
        r = gh.post(
            f"/repos/{config.ISSUES_REPO}/issues",
            json={
                "title": title[:200],
                "body": render_body(alert, result, fingerprint),
                "labels": ["incident", f"confidence:{result['confidence']}"],
            },
        )
        r.raise_for_status()
    metrics.ISSUES.labels(action="created").inc()
    url = r.json()["html_url"]
    log.info("opened %s", url)
    return url


def resolve_issue(fingerprint: str) -> int | None:
    number = find_open_issue(fingerprint)
    if number is None:
        return None
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    with _client() as gh:
        gh.post(
            f"/repos/{config.ISSUES_REPO}/issues/{number}/comments", json={"body": f"Resolved at {now}."}
        ).raise_for_status()
        gh.patch(
            f"/repos/{config.ISSUES_REPO}/issues/{number}", json={"state": "closed", "state_reason": "completed"}
        ).raise_for_status()
    metrics.ISSUES.labels(action="closed").inc()
    log.info("closed issue #%s", number)
    return number
