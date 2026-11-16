# Design decisions

Short records of why things are built the way they are.

## Two Terraform stacks: `base` and `cluster`
**Decision:** `base` (VPC, ECR, GitHub OIDC roles, secret) is applied once. `cluster` (EKS, node group, Pod Identity) is created and destroyed every session.
**Why:** EKS bills the control plane every hour it exists and has no stop button. Splitting the stacks keeps images, roles and secrets across sessions while the expensive part is rebuilt from code. Every `up.sh` is a tested disaster recovery.

## Public subnets, no NAT gateway
**Decision:** Nodes run in public subnets.
**Why:** A NAT gateway costs about $1/day. In production, nodes would sit in private subnets behind NAT or VPC endpoints.

## Private API endpoint enabled too
**Decision:** `endpoint_private_access = true` alongside the public endpoint limited to my IP.
**Why:** With only a public endpoint restricted to one IP, the node itself cannot reach the API server and never joins the cluster.

## Node type `m7i-flex.large`, not `t3.large`
**Decision:** The node group uses `m7i-flex.large` (2 vCPU, 8 GB).
**Why:** The AWS account is on the Free plan, which only launches Free Tier eligible instance types. `t3.large` launches failed silently: the node group sat in CREATING while the Auto Scaling activity log showed "instance type is not eligible for Free Tier". `m7i-flex.large` has the same size and is allowed.

## Custom alert rules instead of the built-in ones
**Decision:** Five `KubeSage*` rules in `values-monitoring.yaml` with `for:` of 0–2 minutes.
**Why:** The built-in `KubePodCrashLooping` and `KubePodNotReady` wait about 15 minutes before firing, which is too slow for alert-to-issue under 5 minutes. Every rule keeps `namespace` plus `pod` or `service`, because the agent needs them to start its investigation.

## Latency histogram buckets above 1 second
**Decision:** The apps expose `http_request_duration_seconds` with buckets up to 10 s.
**Why:** `histogram_quantile` can never return a value above the largest finite bucket. With the library's default buckets (largest finite bucket 1 s), "P95 > 1 s" could never be true and the latency alert would never fire.

## Alertmanager default receiver is `null`
**Decision:** Only `KubeSage*` alerts from namespace `dev` reach the agent.
**Why:** kube-prometheus-stack always fires `Watchdog`. Sending it (and other platform alerts) to the agent would cost Bedrock tokens for nothing.

## Qdrant as a plain Deployment with emptyDir
**Decision:** Qdrant runs from the agent chart, not the upstream Qdrant chart.
**Why:** The upstream chart always requests a PersistentVolume, which stays Pending because the cluster has no EBS CSI driver (no orphaned volumes after `down.sh`). Runbooks are re-embedded at every agent start, so losing the index is fine.

## The agent is read-only, and rollbacks go through Git
**Decision:** ClusterRole with get/list/watch only. A human comments `/approve-rollback`; a workflow reverts the commit in kubesage-gitops; ArgoCD applies it.
**Why:** LLMs can be wrong or manipulated (prompt injection through logs). Read-only RBAC means a tricked agent cannot change anything. Git makes every change audited and reversible.

## Guardrails in code, not only in the prompt
- Namespace allow-list (`dev`) in every tool, even though RBAC could read more.
- Env var values stripped from deployments; secrets masked in logs; every tool output truncated to 4,000 characters.
- The suspect commit is kept only if a `get_recent_changes` call actually returned that SHA.
- Issue text is sanitized, so the agent cannot write a fake `<!-- kubesage:suspect_commit=... -->` marker; the rollback workflow also requires exactly one marker and a 40-character hex SHA that is on `main`.

## `kubernetes` Python client pinned to 36.x
**Decision:** `kubernetes==36.0.0`.
**Why:** 37.x requires `python-dateutil>=3`, while botocore requires `<3`; pip cannot install both.
