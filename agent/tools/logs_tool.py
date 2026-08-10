"""
logs_tool.py — query Loki for aggregated application logs.

Separate from k8s_tool's get_pod_logs: this queries Loki, which retains
logs after a pod is gone (kubectl logs can't show you anything once the
pod is deleted). Falls back gracefully if Loki isn't configured, so the
rest of the agent still works using kubectl-sourced logs alone.
"""

import os
import requests

LOKI_URL = os.environ.get("LOKI_URL", "http://localhost:3100")


def query_loki(logql: str, limit: int = 100) -> list:
    """
    Run a LogQL query against Loki, e.g.:
        '{namespace="default", pod="payment-api-7d9f"}'
    """
    try:
        resp = requests.get(
            f"{LOKI_URL}/loki/api/v1/query_range",
            params={"query": logql, "limit": limit},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        return [f"(Loki query failed — is Loki running/configured? {e})"]

    lines = []
    for stream in data.get("data", {}).get("result", []):
        for _, line in stream.get("values", []):
            lines.append(line)
    return lines


def search_error_logs(namespace: str, pod_prefix: str, minutes: int = 30) -> list:
    """Convenience wrapper: search for error-level log lines in the last N minutes."""
    logql = f'{{namespace="{namespace}", pod=~"{pod_prefix}.*"}} |= "error"'
    return query_loki(logql)
