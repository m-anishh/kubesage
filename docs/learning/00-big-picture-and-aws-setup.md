# Lesson 0 — The big picture, and setting up AWS safely

Every step in this project is explained with five questions:
**What** is it? **Why** do we need it? **How** does it work? **When** does it run? **For what** (what breaks without it)?

## Part A — One incident, start to finish

1. You push code to `kubesage`. **GitHub Actions** tests it, scans it with **Trivy**, builds a **Docker** image and pushes it to **ECR**.
2. CI writes the new image tag into the `kubesage-gitops` repo. It never touches the cluster.
3. **ArgoCD**, running inside **EKS**, sees the change in Git and updates the pods. Git is the single source of truth.
4. **Prometheus** collects metrics every few seconds. A rule turns "pod is crash-looping" into an alert. **Alertmanager** sends the alert to the agent as JSON.
5. The **KubeSage agent** sends the alert to an LLM on **Amazon Bedrock**. The LLM asks for evidence: pod logs, events, recent Git commits, and matching runbooks from **Qdrant** (RAG).
6. The agent writes a **GitHub issue**: root cause, evidence, fix, suspect commit.
7. A human comments `/approve-rollback`. A workflow reverts that commit in Git, and ArgoCD applies the revert.

## Part B — Technology map

| Technology | What it is | Why it is here | Phase |
|---|---|---|---|
| AWS IAM | Who can do what in AWS | Every service and person gets only the access it needs | 0–1 |
| Terraform | Infrastructure written as code | Rebuild the whole cluster from code every session | 1 |
| S3 (state) | Storage for Terraform's memory | Terraform must remember what it created | 1 |
| VPC | Your private network in AWS | The cluster needs a network to live in | 1 |
| EKS | Managed Kubernetes | Runs all the containers | 1 |
| ECR | Private image registry | Stores the images CI builds | 1, 3 |
| Secrets Manager + External Secrets | Safe secret storage, synced into Kubernetes | The GitHub token never sits in Git | 1, 4 |
| Docker | Packages an app into an image | The same app runs on your laptop and in EKS | 2 |
| Helm | Templates for Kubernetes YAML | One chart, many apps and settings | 2, 4 |
| GitHub Actions + OIDC | CI pipeline that logs in to AWS without keys | Build and push safely | 3 |
| ArgoCD | GitOps controller | The cluster always equals Git | 4 |
| Prometheus, Alertmanager, Grafana | Metrics, alerts, dashboards | Detect problems and call the agent | 5 |
| Amazon Bedrock | LLMs as an AWS API | The agent's "brain", with no API key | 6 |
| Qdrant + Titan Embeddings | Vector database + text-to-numbers model | Find the right runbook by meaning (RAG) | 6 |
| FastAPI + Python | Small web framework | The agent's API and the demo apps | 2, 6 |

## Part C — Three ideas that repeat everywhere

1. **Everything is code.** If it is not in Terraform or Git, it does not exist. That is why we can destroy the cluster every night.
2. **No stored keys.** Short-lived credentials only: SSO for you, OIDC for GitHub Actions, Pod Identity for pods.
3. **Least privilege + a human in the loop.** The agent can only read. Changes go through Git, after a human approves.

## Part D — Step 0: AWS account, safely

### 0.1 Stop using the root user and long-lived access keys

- **What:** The root user owns the account and can do anything, even close it. An IAM user's access key works until someone deletes it.
- **Why:** A leaked root password or access key lets a stranger run servers on your bill. This is the most common way students lose money on AWS.
- **How:** Sign in as root **once**, turn on MFA for root, enable **IAM Identity Center**, create your own admin user, then stop using root.
- **When:** Today, before anything else.
- **For what:** Today your IAM user `manish1` cannot even list EKS versions, so Terraform would fail on its first resource.

Steps in the AWS console:

1. Sign in as root → account menu (top right) → **Security credentials** → assign an **MFA device** (an authenticator app).
2. Switch the region to **Asia Pacific (Mumbai) ap-south-1**.
3. Open **IAM Identity Center** → **Enable**.
4. **Users** → **Add user** (your name and email) → accept the email invite and set up MFA for this user.
5. **Permission sets** → **Create** → predefined **AdministratorAccess** (session duration 8 hours).
6. **AWS accounts** → select your account → **Assign users or groups** → your user + AdministratorAccess.
7. Copy the **AWS access portal URL** from the Identity Center dashboard (it looks like `https://d-xxxxxxxxxx.awsapps.com/start`).
8. Sign out of root.

On your laptop (use **Git Bash** for this whole project):

```bash
aws configure sso
#   SSO session name:     kubesage
#   SSO start URL:        <the portal URL from step 7>
#   SSO region:           ap-south-1
#   Registration scopes:  (press Enter)
#   -> choose your account and the AdministratorAccess role
#   Default client region: ap-south-1
#   Output format:         json
#   Profile name:          kubesage

export AWS_PROFILE=kubesage
aws sts get-caller-identity
# Arn should contain AWSReservedSSO_AdministratorAccess
```

Every day, start with `aws sso login --profile kubesage`. The credentials expire by themselves; that is the point.

When SSO works, delete the old access key of `manish1` (IAM → Users → manish1 → Security credentials).

### 0.2 AWS Budget

- **What:** An alarm on spending. It is **not** a hard limit; AWS keeps billing.
- **Why:** EKS bills every hour it exists. A forgotten cluster costs about $5 a day.
- **How:** Billing console → **Budgets** → **Create budget** → Cost budget, monthly, amount $40 → alerts at **actual** $10, $25 and $40 to your email.
- **When:** Before creating any resource.
- **For what:** You learn about a forgotten `make down` the same day, not at the end of the month.

### 0.3 Check Amazon Bedrock today

- **What:** Bedrock gives you LLMs through an AWS API. Your IAM identity is your "API key".
- **Why on day 1:** Some accounts need approval or a use-case form first, and Phase 6 depends on it.
- **How:**

```bash
aws bedrock-runtime converse --region ap-south-1 \
  --model-id apac.amazon.nova-lite-v1:0 \
  --messages '[{"role":"user","content":[{"text":"Say hi"}]}]'
```

The `apac.` prefix means a **cross-region inference profile**: AWS may run your request in another Asia-Pacific region that has spare capacity.

- **For what:** If you get `AccessDenied` or a "model access" error, fix it now: Bedrock console → **Model catalog** → open the model. Claude models need a short use-case form first; Amazon Nova usually works right away.

## Check yourself

1. Why is an Identity Center user safer than an IAM user with an access key?
2. Does an AWS Budget stop spending when it reaches $40?
3. What does the `apac.` prefix in the model ID mean?
