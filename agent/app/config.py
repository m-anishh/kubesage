"""All settings come from environment variables (set in the Helm chart). No secrets here."""

import os
from pathlib import Path


def _list(name: str, default: str) -> list[str]:
    return [v.strip() for v in os.getenv(name, default).split(",") if v.strip()]


AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
MODEL_ID = os.getenv("MODEL_ID", "apac.amazon.nova-lite-v1:0")
EMBED_MODEL_ID = os.getenv("EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")
EMBED_DIMENSIONS = 512

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
RUNBOOK_DIR = Path(os.getenv("RUNBOOK_DIR", Path(__file__).resolve().parent.parent / "runbooks"))
RUNBOOK_COLLECTION = "runbooks"

ISSUES_REPO = os.getenv("ISSUES_REPO", "m-anishh/kubesage")
GITOPS_REPO = os.getenv("GITOPS_REPO", "m-anishh/kubesage-gitops")
GITOPS_VALUES_PATH = os.getenv("GITOPS_VALUES_PATH", "envs/dev/values-{app}.yaml")
GITHUB_TOKEN_FILE = Path(os.getenv("GITHUB_TOKEN_FILE", "/var/run/secrets/github/token"))

# The agent may only look at these namespaces, even though RBAC allows reading more.
ALLOWED_NAMESPACES = _list("ALLOWED_NAMESPACES", "dev")

MAX_TURNS = int(os.getenv("MAX_TURNS", "6"))
MAX_TOOL_OUTPUT = int(os.getenv("MAX_TOOL_OUTPUT", "4000"))
MAX_CONCURRENT_INVESTIGATIONS = int(os.getenv("MAX_CONCURRENT_INVESTIGATIONS", "2"))

# DRY_RUN=true: investigate and log the result, but don't open GitHub issues.
DRY_RUN = os.getenv("DRY_RUN", "false").lower() in ("1", "true", "yes")


def github_token() -> str | None:
    """Read the token at call time, so a rotated Secret is picked up without a restart."""
    if GITHUB_TOKEN_FILE.exists():
        token = GITHUB_TOKEN_FILE.read_text().strip()
        return token or None
    return os.getenv("GITHUB_TOKEN") or None
