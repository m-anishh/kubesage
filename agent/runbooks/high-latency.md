# High P95 latency

## Symptoms
The alert KubeSageHighP95Latency fires when the 95th percentile request duration of a service stays above 1 second for two minutes. Pods are Running and Ready, so pod status alone looks healthy.

## Diagnosis
1. List the pods of the service and check that none are restarting: restarts point to a different problem.
2. Read the logs for slow dependency calls, timeouts or retries.
3. orders-api calls payments-api. If both are slow, start with payments-api: the slowness of a dependency shows up in its callers too.
4. Check recent GitOps changes for an env var that adds delay (for example FAULT_LATENCY_MS), a lowered CPU limit, or a new version.

## Fix
Revert the commit that introduced the delay or the lower CPU limit. If latency comes from load, scale replicas through the values file. Check the latency panel in Grafana to confirm recovery.
