# ImagePullBackOff

## Symptoms
The pod stays in Pending or ContainerCreating with waiting reason ErrImagePull or ImagePullBackOff. The alert KubeSageImagePullBackOff fires after two minutes. The old ReplicaSet usually keeps serving traffic, so users may not notice yet.

## Diagnosis
1. Read the pod events: "manifest unknown" or "not found" means the tag does not exist in ECR. "no basic auth credentials" or "403" means a permission problem.
2. Read the deployment image and compare the tag with the tags CI pushed. ECR tags are the full Git commit SHA of the kubesage repo.
3. Check recent GitOps changes: a hand-edited image.tag, a typo, or a tag bump for an image whose CI build failed are the common causes.

## Fix
Revert the commit that set the bad tag, or set image.tag to a tag that exists in ECR. Nodes pull from ECR with their IAM role (AmazonEC2ContainerRegistryReadOnly), so no pull secret is needed.
