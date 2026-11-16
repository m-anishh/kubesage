# KubeSage — AI Incident Copilot on AWS

When a Prometheus alert fires, KubeSage investigates the failing pod by itself and opens a GitHub issue with the root cause, the evidence and a suggested fix. A human approves any rollback, and the rollback goes through Git.

**Flow:** alert fires → agent reads pod logs, events and recent deploys → searches runbooks (RAG) → LLM reasons over the evidence → GitHub issue with root cause + fix → human comments `/approve-rollback` → ArgoCD applies the revert.

![Architecture](docs/architecture.png)

## Tech stack

| Layer | Tool |
|---|---|
| Infrastructure as code | Terraform (two stacks: `base` and `cluster`), state in S3 |
| Cloud | Amazon EKS, ECR, Secrets Manager, Amazon Bedrock |
| CI | GitHub Actions with OIDC (no stored AWS keys), Trivy |
| CD | ArgoCD (app-of-apps), Helm |
| Monitoring | Prometheus, Alertmanager, Grafana |
| AI | Bedrock Converse tool calling, Titan embeddings, Qdrant (RAG) |
| Apps and agent | Python 3.12, FastAPI |

## Repositories

This project uses two repos, the standard GitOps split: CI writes to the GitOps repo, ArgoCD reads from it.

### `kubesage` (this repo): code and infrastructure

```
kubesage/
├── infra/terraform/
│   ├── base/               # lives all project: VPC, ECR, GitHub OIDC roles, secret
│   └── cluster/            # created + destroyed each session: EKS, node group, Pod Identity
├── Makefile                # make up / make down
├── scripts/                # up.sh, down.sh, bootstrap-argocd.sh
├── apps/
│   ├── orders-api/         # demo service with fault switches
│   └── payments-api/       # demo service with fault switches
├── agent/
│   ├── app/main.py         # FastAPI: /webhook/alertmanager, /chat, /healthz, /metrics
│   ├── app/tools.py        # kubectl-style read-only tools
│   ├── app/rag.py          # runbook ingest + search (Qdrant, Titan embeddings)
│   ├── app/agent.py        # Bedrock Converse tool-calling loop
│   ├── app/config.py       # settings from environment variables
│   ├── app/github_issues.py# create, comment on and close GitHub issues
│   ├── app/metrics.py      # Prometheus metrics for the agent
│   ├── runbooks/*.md       # CrashLoopBackOff, OOMKilled, ImagePullBackOff, latency, 5xx, failed deploy
│   └── tests/              # unit tests + saved Alertmanager payloads
├── .github/workflows/      # ci-apps.yml, ci-agent.yml, terraform.yml, rollback.yml
└── docs/                   # architecture.png, demo.gif, decisions.md, eval.md, learning/
```

### `kubesage-gitops`: what runs in the cluster

Public repo, so ArgoCD reads it with no credentials. It holds no secrets.

```
kubesage-gitops/
├── argocd/                 # root.yaml + apps/ (app-of-apps)
├── charts/kubesage-agent/  # Helm chart for the agent (read-only RBAC)
├── charts/demo-app/        # Helm chart for orders-api and payments-api
├── manifests/              # External Secrets config, Grafana dashboard
└── envs/dev/values-*.yaml  # image tags CI updates, fault switches
```

## Security model

- **No stored keys.** People log in with SSO, GitHub Actions with OIDC, pods with EKS Pod Identity.
- **Read-only agent.** Its ClusterRole only allows get, list and watch. It cannot delete, patch or exec.
- **Human in the loop.** Rollbacks need `/approve-rollback` from the repo owner, and they happen through Git.

## Cost

About $0.20 per hour while the cluster is up. Every session ends with `make down`, which destroys the cluster.

## Progress

- [ ] AWS Budget and Bedrock test
- [ ] Phase 1: Terraform base and cluster stacks
- [ ] Phase 2: Demo apps with fault switches
- [ ] Phase 3: CI with GitHub Actions
- [ ] Phase 4: GitOps with ArgoCD
- [ ] Phase 5: Monitoring and alert routing
- [ ] Phase 6: The AI agent
- [ ] Phase 7: GitHub issues and human-approved rollback
- [ ] Scorecard in [docs/eval.md](docs/eval.md)

## Learning notes

Step-by-step lessons (what, why, how, when, for what) are in [docs/learning/](docs/learning/).
