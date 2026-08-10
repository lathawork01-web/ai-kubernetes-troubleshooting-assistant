# CrashLoopBackOff — Container Repeatedly Crashing on Startup

## Symptoms
- Pod status shows `CrashLoopBackOff`
- Restart count increasing, with growing backoff delay between attempts
- Container never reaches `Ready` state

## Root Cause
The container process is exiting (crashing) shortly after starting, and Kubernetes is repeatedly trying to restart it per the pod's restart policy.

## Common Underlying Causes
1. **Missing configuration** — a required environment variable, ConfigMap, or Secret isn't set, so the app fails at startup (look for "X not set" or similar in the logs)
2. **Bad application code** in the latest deployed image — an unhandled exception on startup
3. **Failing liveness probe** too aggressive — the app takes longer to start than the probe's `initialDelaySeconds` allows, so Kubernetes kills it before it's ready
4. **Dependency not available** — the app can't reach its database/downstream service at startup and doesn't retry gracefully

## Diagnostic Steps
1. `kubectl logs <pod> --previous` — this is the single most useful command; it shows logs from the crashed instance, not the new one that just started
2. Check recent Kubernetes events for the pod — often shows the exact reason (`Back-off restarting failed container`)
3. Check if this correlates with a recent deployment (new image tag, new Helm values) — if so, the recent change is very likely the cause
4. Check the liveness/readiness probe configuration against the app's actual startup time

## Recommended Fix
- If it's a missing config value: fix the Helm values/Secret and redeploy
- If it's a probe timing issue: increase `initialDelaySeconds`
- If it's a bad deploy: roll back to the previous known-good image tag immediately, then debug the new code separately
