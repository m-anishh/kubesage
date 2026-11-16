#!/usr/bin/env bash
# Phase 4, every session (called by up.sh): install ArgoCD and hand the cluster over to kubesage-gitops.
set -euo pipefail

kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -

# --server-side: recent ArgoCD CRDs are too large for a client-side kubectl apply.
kubectl apply -n argocd --server-side --force-conflicts \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

kubectl -n argocd rollout status deploy/argocd-server --timeout=300s
kubectl -n argocd rollout status deploy/argocd-repo-server --timeout=300s

kubectl apply -n argocd -f https://raw.githubusercontent.com/m-anishh/kubesage-gitops/main/argocd/root.yaml

echo
echo "ArgoCD is up. Log in with:"
echo "  user:     admin"
echo "  password: $(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d)"
echo "  UI:       kubectl -n argocd port-forward svc/argocd-server 8080:443  ->  https://localhost:8080"
