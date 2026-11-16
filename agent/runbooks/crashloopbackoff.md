# CrashLoopBackOff

## Symptoms
The pod status is CrashLoopBackOff and the restart count keeps growing. The container starts, exits, and Kubernetes waits longer before each restart (10 s, 20 s, 40 s, up to 5 minutes). The alert KubeSageCrashLooping fires after one minute in this state.

## Diagnosis
1. Read the logs of the crashed container with previous=true: the current container may have no logs yet.
2. Check the last termination reason and exit code. Exit code 1 or 3 means the application exited on its own (bad config, missing setting, failed dependency). Exit code 137 with reason OOMKilled is a memory problem: use the OOMKilled runbook instead.
3. Look for "FATAL", "missing", "cannot load config" or a stack trace in the last lines before exit.
4. Check recent GitOps changes for the app: a new env var, a removed setting or a fault switch such as FAULT_CRASH=true often explains a crash that starts right after a deploy.

## Fix
If a recent commit introduced the bad setting, revert that commit in kubesage-gitops and let ArgoCD sync. If the setting is required but missing, add it to the values file. Never fix it with kubectl edit: ArgoCD self-heal reverts manual changes.
