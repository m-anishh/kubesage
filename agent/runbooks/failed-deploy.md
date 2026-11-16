# Failed deploy

## Symptoms
A rollout does not finish: the deployment's new ReplicaSet has pods that never become Ready, the condition Progressing shows ProgressDeadlineExceeded, or ArgoCD shows the app as Degraded. Any of the other alerts (crash loop, image pull, OOM) can be the visible part of a failed deploy.

## Diagnosis
1. Read the deployment conditions and compare the image of the new pods with the previous one.
2. Read the events of the deployment name: they include the ReplicaSets and pods it created.
3. Use the matching runbook for what the new pods show: CrashLoopBackOff, OOMKilled or ImagePullBackOff.
4. Find the triggering change with the recent GitOps commits: the incident usually starts within minutes of the commit that changed the app's values file.

## Fix
Roll back through Git: revert the suspect commit in kubesage-gitops and let ArgoCD sync. In KubeSage, a human approves this by commenting /approve-rollback on the incident issue. Do not use kubectl rollout undo: ArgoCD would immediately re-apply what is in Git.
