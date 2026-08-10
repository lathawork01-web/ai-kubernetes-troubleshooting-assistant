"""
prometheus_tool.py — query Prometheus for metrics evidence.

Used by the agent to check CPU/memory usage trends and correlate them
against pod restarts — e.g. confirming a slow memory climb before an
OOMKilled event, rather than just guessing from the event reason alone.
"""

import os
import requests

PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")


def query_instant(promql: str) -> dict:
    """Run an instant PromQL query and return the raw result."""
    resp = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": promql}, timeout=10)
    resp.raise_for_status()
    return resp.json()


def query_range(promql: str, start: str, end: str, step: str = "60s") -> dict:
    """Run a range query — useful for plotting/inspecting a metric trend over time."""
    resp = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query_range",
        params={"query": promql, "start": start, "end": end, "step": step},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def get_memory_usage_percent(pod_name: str, namespace: str = "default") -> str:
    """Convenience wrapper: memory usage as a percentage of the configured limit."""
    promql = (
        f'(container_memory_working_set_bytes{{namespace="{namespace}", pod="{pod_name}"}} '
        f'/ container_spec_memory_limit_bytes{{namespace="{namespace}", pod="{pod_name}"}}) * 100'
    )
    try:
        result = query_instant(promql)
        values = result.get("data", {}).get("result", [])
        if not values:
            return "No memory metrics found (metrics-server or Prometheus may not be scraping this pod)"
        pct = float(values[0]["value"][1])
        return f"{pct:.1f}% of memory limit"
    except requests.RequestException as e:
        return f"(Prometheus query failed: {e})"


def get_cpu_throttling(pod_name: str, namespace: str = "default") -> str:
    """Check whether a pod is being CPU-throttled — a common hidden cause of slow/flaky services."""
    promql = f'rate(container_cpu_cfs_throttled_seconds_total{{namespace="{namespace}", pod="{pod_name}"}}[5m])'
    try:
        result = query_instant(promql)
        values = result.get("data", {}).get("result", [])
        if not values:
            return "No throttling data found"
        throttled_seconds = float(values[0]["value"][1])
        return f"{throttled_seconds:.3f}s throttled/sec over last 5m"
    except requests.RequestException as e:
        return f"(Prometheus query failed: {e})"
