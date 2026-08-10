# ai-kubernetes-troubleshooting-assistant

An AI agent that investigates Kubernetes incidents the way an experienced engineer would: gather evidence from the cluster, monitoring, and logs; check it against known failure patterns; then reason to a root cause — instead of guessing from a one-line question alone.

## Architecture

```
User: "Why is payment-api crashing?"
   │
   ▼
LangGraph workflow
   │
   ├── gather_evidence
   │     ├── Kubernetes tool  → pod status, restarts, events, current + previous logs
   │     └── Prometheus tool  → memory usage %, CPU throttling
   │
   ├── retrieve_knowledge
   │     └── RAG (TF-IDF)     → matches evidence against known failure patterns
   │                             (OOMKilled, CrashLoopBackOff, ImagePullBackOff)
   │
   └── analyze
         └── Claude synthesizes: Root Cause / Evidence / Recommendation
```

## Example

```bash
$ python agent/main.py --pod payment-api-7d9f8c --namespace production \
    --question "Why is this pod crashing?"

Root Cause: OOMKilled
Evidence: Container memory usage was at 98.3% of its 512Mi limit
(from Prometheus) immediately before termination. Pod events confirm
"Reason: OOMKilled" and previous logs show no graceful shutdown —
consistent with a hard kernel OOM kill rather than an application crash.
Recommendation: Increase the memory limit from 512Mi to 1Gi as an
immediate fix, and add memory usage monitoring/alerting at 80% of
limit to catch this before it recurs.
```

## Why this design

**Evidence before reasoning.** The agent doesn't ask the LLM to guess a root cause from a question — it gathers pod status, events, current and previous logs, and Prometheus metrics *first*, then gives the LLM that evidence to reason over. This is the difference between an LLM that sounds plausible and one that's actually diagnosing your specific incident.

**RAG grounds the analysis in known patterns.** The knowledge base (`agent/rag/knowledge_docs/`) contains structured writeups of common failure modes — OOMKilled, CrashLoopBackOff, ImagePullBackOff — each with symptoms, common causes, diagnostic steps, and typical fixes. Retrieval matches the live evidence against these patterns so the model's reasoning is grounded, not just improvised.

**Retrieval uses TF-IDF, not a neural embedding model — deliberately.** An earlier version used ChromaDB's default embedding function, which downloads a ~90MB ONNX model from an external CDN on first run. That's a real fragility: it fails in any network-restricted environment (corporate proxy, air-gapped CI, sandboxed dev environment) — I hit exactly this failure while testing it. For a knowledge base of a few dozen curated documents, classic TF-IDF + cosine similarity retrieves just as effectively, has zero runtime network dependency, and is fully deterministic. This is the kind of tradeoff worth naming explicitly rather than defaulting to "use a vector DB" because it sounds more modern — the simpler tool was actually the more production-appropriate choice here. Worth revisiting if the knowledge base grows into the thousands of documents.

**Previous logs matter.** `get_pod_logs(..., previous=True)` is deliberately included — after a crash, `kubectl logs` on the new pod shows nothing useful. The previous instance's logs are where the actual crash reason usually lives.

## Repo structure

```
agent/
├── graph.py                    # LangGraph workflow definition
├── main.py                     # CLI entrypoint
├── tools/
│   ├── k8s_tool.py              # Pod status, events, logs, deployment status
│   ├── prometheus_tool.py       # Memory usage, CPU throttling queries
│   └── logs_tool.py             # Loki queries (falls back gracefully if not configured)
└── rag/
    ├── knowledge_base.py        # Offline TF-IDF + cosine similarity retrieval (no external model download)
    └── knowledge_docs/          # Curated failure-pattern docs (OOMKilled, CrashLoopBackOff, etc.)
tests/
└── test_knowledge_base.py       # Runs without a live cluster — safe for CI
```

## Run it

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key_here

# Point at a real cluster via your normal kubeconfig, then:
cd agent
python main.py --pod <your-pod-name> --namespace default \
    --question "Why is this pod having issues?"
```

No live cluster handy? The knowledge base and RAG retrieval work standalone:

```bash
python tests/test_knowledge_base.py
```

## What I'd add next

- More knowledge docs — network policy blocks, PVC mount failures, node pressure evictions
- A Slack bot front-end so the agent can be invoked directly from an incident channel
- Feedback loop: let engineers mark a diagnosis as correct/incorrect, and use that to refine retrieval over time

## Stack

Python · LangGraph · Anthropic Claude · scikit-learn (TF-IDF RAG) · Kubernetes Python client · Prometheus · Loki

---
*Part of my DevOps/AI portfolio while job hunting for roles in Germany/Netherlands. More at [linkedin.com/in/latha-s-devops](https://linkedin.com/in/latha-s-devops).*
