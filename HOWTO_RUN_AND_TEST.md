# HOW TO RUN — ai-kubernetes-troubleshooting-assistant

Step-by-step: from zero to the agent diagnosing a real (deliberately broken) pod.

---

## Prerequisites

| Tool | Check installed | Install if missing |
|---|---|---|
| Python ≥ 3.10 | `python3 --version` | https://www.python.org/downloads/ |
| kind (local Kubernetes) | `kind --version` | https://kind.sigs.k8s.io/docs/user/quick-start/ |
| kubectl | `kubectl version --client` | https://kubernetes.io/docs/tasks/tools/ |
| An Anthropic API key | — | https://console.anthropic.com/ |

You do **not** need a real cloud cluster — this whole guide runs on a local `kind` cluster, free. You also do **not** need any external vector DB or model download — retrieval is self-contained TF-IDF (see README for why).

---

## Step 1 — Clone and install dependencies

```bash
git clone https://github.com/<your-username>/ai-kubernetes-troubleshooting-assistant.git
cd ai-kubernetes-troubleshooting-assistant
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Step 2 — Verify the RAG knowledge base works (no cluster, no network needed)

```bash
python tests/test_knowledge_base.py
```
Expected output: `All tests passed.`

This confirms the TF-IDF retriever correctly matches symptoms to the right knowledge doc — entirely offline, no external model download, no cluster required. Good first checkpoint before anything else.

**Optional — see the actual relevance scores:**
```bash
python3 -c "
import sys; sys.path.insert(0, 'agent')
from rag.knowledge_base import retrieve_relevant_knowledge
for r in retrieve_relevant_knowledge('pod restarting, OOMKilled, memory climbing', n_results=2):
    print(r['source'], r['relevance_score'])
"
```
You should see `oomkilled.md` ranked first with a clearly higher score than the second result.

## Step 3 — Spin up a local cluster

```bash
kind create cluster --name troubleshoot-demo
kubectl cluster-info
```

## Step 4 — Deploy something that's deliberately broken

We'll create a pod that will OOMKill itself, so you have a real incident to investigate.

```bash
kubectl create namespace demo

cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: memory-hog
  namespace: demo
spec:
  replicas: 1
  selector:
    matchLabels: { app: memory-hog }
  template:
    metadata:
      labels: { app: memory-hog }
    spec:
      containers:
      - name: memory-hog
        image: polinux/stress
        command: ["stress"]
        args: ["--vm", "1", "--vm-bytes", "150M", "--vm-hang", "1"]
        resources:
          limits:
            memory: "50Mi"
EOF
```

This container tries to allocate 150Mi against a 50Mi limit — guaranteed OOMKill within seconds.

## Step 5 — Confirm it's actually broken

```bash
kubectl get pods -n demo -w
```
Wait until `RESTARTS` climbs to 2+, then Ctrl+C.

## Step 6 — Get the exact pod name and run the agent

```bash
kubectl get pods -n demo
# copy the full pod name, e.g. memory-hog-7d9f8c6b5-xk2pq

export ANTHROPIC_API_KEY=your_key_here
cd agent
python main.py --pod memory-hog-7d9f8c6b5-xk2pq --namespace demo \
    --question "Why is this pod crashing?"
```

Expected output shape:
```
Investigating demo/memory-hog-7d9f8c6b5-xk2pq...

Root Cause: OOMKilled
Evidence: ...
Recommendation: Increase the memory limit from 50Mi to at least 200Mi...
```

## Step 7 — Try a second scenario (CrashLoopBackOff)

```bash
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: crash-app
  namespace: demo
spec:
  replicas: 1
  selector:
    matchLabels: { app: crash-app }
  template:
    metadata:
      labels: { app: crash-app }
    spec:
      containers:
      - name: crash-app
        image: busybox
        command: ["sh", "-c", "echo 'Error: DATABASE_URL not set' && exit 1"]
EOF
```

```bash
kubectl get pods -n demo   # find the crash-app pod name
python main.py --pod <crash-app-pod-name> --namespace demo \
    --question "Why is this pod crash looping?"
```

The agent should identify `CrashLoopBackOff` caused by a missing environment variable, citing the previous-logs evidence specifically.

## Step 8 — Clean up

```bash
kind delete cluster --name troubleshoot-demo
```

---

## Testing checklist

- [ ] `python tests/test_knowledge_base.py` passes standalone (no cluster, no network needed)
- [ ] Retrieval scores show a clear gap between the correct match and everything else (not near-ties — that would suggest the corpus needs more distinguishing content)
- [ ] Agent correctly identifies OOMKilled for the memory-hog scenario
- [ ] Agent correctly identifies CrashLoopBackOff for the crash-app scenario, specifically citing the "DATABASE_URL not set" evidence from previous logs
- [ ] Recommendations are specific (an actual memory number), not generic ("check your configuration")
- [ ] Setting `PROMETHEUS_URL`/`LOKI_URL` env vars actually changes which endpoint the tools query (verify with a dummy value and confirm the connection error message references your dummy URL, not localhost)

## Common issues

| Problem | Likely cause | Fix |
|---|---|---|
| `ModuleNotFoundError: sklearn` | Dependencies not installed in the active venv | Re-run `pip install -r requirements.txt` with the venv activated |
| Agent can't reach the cluster | kubeconfig not pointing at the kind cluster | `kubectl config current-context` should show `kind-troubleshoot-demo` |
| Prometheus tool errors in evidence | No Prometheus installed on this kind cluster | Expected — this demo doesn't include a Prometheus install; the agent should still work using pod status/events/logs alone, just with a "(error)" note in that one evidence field |
| Agent gives a vague/generic answer | Check retrieval directly (Step 2's optional command) to confirm the right doc is actually being matched | If scores are all near-zero, your question wording may not overlap enough with the knowledge doc content — try including the actual K8s reason string (e.g. "OOMKilled") in the question |

---
*Companion to the main [README.md](./README.md) — this file is the step-by-step execution guide; the README explains the design decisions.*
