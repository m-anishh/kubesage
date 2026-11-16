# OOMKilled

## Symptoms
The container's last termination reason is OOMKilled with exit code 137, and the pod restarts. The alert KubeSageOOMKilled fires on the restart. Between restarts, memory usage climbs steadily until it reaches the container memory limit.

## Diagnosis
1. Confirm with the pod status: last termination reason OOMKilled, exit code 137.
2. Read the deployment: compare the memory limit with what the app normally needs.
3. Read the previous container's logs. Repeated lines such as "cache grew to N MB" show unbounded memory growth, which is a leak, not a limit that is too small.
4. Check recent GitOps changes: a fault switch like FAULT_MEMORY_LEAK=true, a new feature flag or a lowered memory limit right before the incident is the usual cause.

## Fix
If a commit turned on the leaking behaviour or lowered the limit, revert it. If the app genuinely needs more memory, raise resources.limits.memory in the values file through Git. Raising the limit does not fix a real leak: it only delays the next OOMKill.
