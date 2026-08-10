# ImagePullBackOff / ErrImagePull

## Symptoms
- Pod stuck in `Pending` or `ImagePullBackOff` state
- Container never starts at all (this is different from CrashLoopBackOff, which starts and then crashes)

## Root Cause
Kubernetes cannot pull the specified container image from the registry.

## Common Underlying Causes
1. **Wrong image tag** — typo, or a tag that was never actually pushed (common after a failed CI build that still triggered a deploy)
2. **Registry authentication failure** — missing or expired `imagePullSecrets`
3. **Registry rate limiting** — especially common with Docker Hub's anonymous pull limits
4. **Network policy blocking egress** to the registry from the node

## Diagnostic Steps
1. `kubectl describe pod <pod>` — the Events section usually states the exact error (e.g. "manifest unknown", "unauthorized", "429 Too Many Requests")
2. Verify the image tag actually exists in the registry (check the CI pipeline's last successful push)
3. Check the pod's `imagePullSecrets` reference a valid, non-expired credential
4. Check whether this started right after a credential rotation — expired registry credentials are a very common trigger

## Recommended Fix
- This should almost never be auto-remediated by restarting the pod — restarting doesn't fix a bad tag or bad credentials, it just wastes time and can mask a real deployment mistake
- Fix the underlying tag/credential issue, then let the Deployment naturally recreate the pod
