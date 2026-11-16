# 5xx error spike

## Symptoms
The alert KubeSageHigh5xxRate fires when more than 20% of a service's requests return HTTP 5xx for two minutes. Pods are usually Running and Ready: the process is alive, but requests fail.

## Diagnosis
1. List the pods of the service and read their logs: look for ERROR lines and the reason on each failed request.
2. A 502 from orders-api usually means payments-api is failing or unreachable: check payments-api too.
3. Errors on a fixed fraction of requests, with no stack trace and no dependency failure, point to a configuration change rather than a bug under load.
4. Check recent GitOps changes for a new version, a changed dependency URL or an error-injection switch such as FAULT_ERROR_RATE.

## Fix
Revert the commit that introduced the errors. If the cause is a dependency, fix the dependency first. Watch the error-rate panel in Grafana return to zero.
