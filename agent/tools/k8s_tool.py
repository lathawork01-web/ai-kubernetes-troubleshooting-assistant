"""
k8s_tool.py — Kubernetes evidence-gathering functions.

All read-only. This module answers "what is the current state of the
cluster" — it never modifies anything. The agent's job is to reason over
this evidence, not act on it directly.
"""

from kubernetes import client, config


def _get_api():
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    return client.CoreV1Api(), client.AppsV1Api()


def get_pod_status(pod_name: str, namespace: str = "default") -> dict:
    """Return phase, restart count, and container states for a pod."""
    v1, _ = _get_api()
    pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)

    containers = []
    for cs in pod.status.container_statuses or []:
        state = "running"
        reason = None
        if cs.state.waiting:
            state, reason = "waiting", cs.state.waiting.reason
        elif cs.state.terminated:
            state, reason = "terminated", cs.state.terminated.reason
        containers.append({
            "name": cs.name,
            "ready": cs.ready,
            "restart_count": cs.restart_count,
            "state": state,
            "reason": reason,
        })

    return {
        "pod": pod_name,
        "phase": pod.status.phase,
        "containers": containers,
    }


def get_pod_logs(pod_name: str, namespace: str = "default", tail_lines: int = 100, previous: bool = False) -> str:
    """Get recent log lines. Set previous=True to get logs from before the last crash/restart."""
    v1, _ = _get_api()
    try:
        return v1.read_namespaced_pod_log(
            name=pod_name, namespace=namespace, tail_lines=tail_lines, previous=previous
        )
    except client.ApiException as e:
        return f"(could not fetch logs: {e.reason})"


def get_recent_events(namespace: str = "default", involved_object: str = None) -> list:
    """Get recent Kubernetes events, optionally filtered to a specific object name."""
    v1, _ = _get_api()
    events = v1.list_namespaced_event(namespace=namespace)
    items = events.items
    if involved_object:
        items = [e for e in items if e.involved_object.name == involved_object]
    items = sorted(items, key=lambda e: e.last_timestamp or e.event_time or "", reverse=True)
    return [
        {"type": e.type, "reason": e.reason, "message": e.message, "object": e.involved_object.name}
        for e in items[:15]
    ]


def get_deployment_status(deployment_name: str, namespace: str = "default") -> dict:
    """Check replica counts and rollout status for a Deployment."""
    _, apps_v1 = _get_api()
    dep = apps_v1.read_namespaced_deployment(name=deployment_name, namespace=namespace)
    return {
        "deployment": deployment_name,
        "desired": dep.spec.replicas,
        "available": dep.status.available_replicas or 0,
        "updated": dep.status.updated_replicas or 0,
        "unavailable": dep.status.unavailable_replicas or 0,
    }


def get_resource_usage(pod_name: str, namespace: str = "default") -> dict:
    """
    Get resource requests/limits for a pod (actual live usage requires the
    metrics-server API — this returns configured limits, which is often
    enough to spot an OOMKill risk before it happens).
    """
    v1, _ = _get_api()
    pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)
    usage = []
    for c in pod.spec.containers:
        usage.append({
            "container": c.name,
            "requests": c.resources.requests,
            "limits": c.resources.limits,
        })
    return {"pod": pod_name, "resources": usage}
