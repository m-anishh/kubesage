from prometheus_client import Counter, Histogram

INVESTIGATIONS = Counter("kubesage_investigations_total", "Investigations finished", ["alertname", "outcome"])
INVESTIGATION_SECONDS = Histogram(
    "kubesage_investigation_duration_seconds",
    "Time from alert received to result",
    buckets=(5, 10, 20, 30, 60, 90, 120, 180, 300),
)
LLM_TOKENS = Counter("kubesage_llm_tokens_total", "Bedrock tokens used", ["kind"])
TOOL_CALLS = Counter("kubesage_tool_calls_total", "Tool calls made by the model", ["tool", "status"])
TOOL_CALLS_PER_INVESTIGATION = Histogram(
    "kubesage_tool_calls_per_investigation", "Tool calls in one investigation", buckets=(0, 1, 2, 3, 5, 8, 13, 20)
)
ISSUES = Counter("kubesage_github_issues_total", "GitHub issue actions", ["action"])
