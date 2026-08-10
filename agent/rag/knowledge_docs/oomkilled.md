# OOMKilled — Container Killed Due to Memory Limit

## Symptoms
- Pod restarts repeatedly, `restart_count` climbing
- `kubectl describe pod` shows `Last State: Terminated, Reason: OOMKilled`
- Memory usage graph in Prometheus/Grafana shows a climb to 100% of the limit right before each restart

## Root Cause
The container's memory usage exceeded its configured `resources.limits.memory`, and the kernel's OOM killer terminated the process.

## Common Underlying Causes
1. Memory limit set too low for the actual workload (most common)
2. A memory leak in the application — usage climbs steadily over hours/days rather than stabilizing
3. A traffic spike causing in-memory caching/buffering to grow unbounded
4. JVM/language runtime not respecting the container's cgroup memory limit (older Java versions without `-XX:+UseContainerSupport`)

## Diagnostic Steps
1. Check `container_memory_working_set_bytes` vs `container_spec_memory_limit_bytes` in Prometheus over the hours before the crash
2. Check whether usage climbs steadily (leak) or spikes suddenly (traffic/burst)
3. Check application logs (previous logs, since the pod restarted) for any large batch job, cache warm-up, or unusual request pattern right before the crash

## Recommended Fix
- **Immediate**: increase the memory limit (e.g. 512Mi → 1Gi) to stop the bleeding
- **Follow-up**: if usage climbs steadily over time even after the limit increase, investigate for a memory leak — this is a code-level fix, not an infra one
- **For JVM apps**: verify container-aware memory flags are set
