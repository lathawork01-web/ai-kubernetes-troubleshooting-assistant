"""
graph.py — LangGraph workflow for Kubernetes incident investigation.

Flow:
    User question
        -> gather_evidence   (calls k8s_tool, prometheus_tool, logs_tool)
        -> retrieve_knowledge (RAG over known failure patterns)
        -> analyze            (LLM synthesizes root cause from evidence + knowledge)
        -> END (returns root cause, evidence, and recommendation)

This mirrors how an experienced engineer actually debugs an incident:
gather facts first, check them against known patterns, then reason about
what's actually happening — rather than asking an LLM to guess from the
question alone.
"""

from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END
from anthropic import Anthropic

from tools import k8s_tool, prometheus_tool, logs_tool
from rag.knowledge_base import retrieve_relevant_knowledge

anthropic_client = Anthropic()


class InvestigationState(TypedDict):
    question: str
    pod_name: Optional[str]
    namespace: str
    evidence: dict
    knowledge: list
    root_cause: Optional[str]


def gather_evidence(state: InvestigationState) -> InvestigationState:
    pod_name = state["pod_name"]
    namespace = state["namespace"]

    evidence = {}
    try:
        evidence["pod_status"] = k8s_tool.get_pod_status(pod_name, namespace)
    except Exception as e:
        evidence["pod_status"] = f"(error: {e})"

    try:
        evidence["recent_events"] = k8s_tool.get_recent_events(namespace, involved_object=pod_name)
    except Exception as e:
        evidence["recent_events"] = f"(error: {e})"

    try:
        evidence["current_logs"] = k8s_tool.get_pod_logs(pod_name, namespace, tail_lines=50)
        evidence["previous_logs"] = k8s_tool.get_pod_logs(pod_name, namespace, tail_lines=50, previous=True)
    except Exception as e:
        evidence["current_logs"] = f"(error: {e})"

    try:
        evidence["memory_usage"] = prometheus_tool.get_memory_usage_percent(pod_name, namespace)
        evidence["cpu_throttling"] = prometheus_tool.get_cpu_throttling(pod_name, namespace)
    except Exception as e:
        evidence["memory_usage"] = f"(error: {e})"

    state["evidence"] = evidence
    return state


def retrieve_knowledge(state: InvestigationState) -> InvestigationState:
    # Use the pod status + events as the query — richer signal than the raw question alone
    query = f"{state['question']} {state['evidence'].get('pod_status')} {state['evidence'].get('recent_events')}"
    state["knowledge"] = retrieve_relevant_knowledge(query, n_results=2)
    return state


def analyze(state: InvestigationState) -> InvestigationState:
    knowledge_text = "\n\n".join(
        f"[{k['source']}]\n{k['content']}" for k in state["knowledge"]
    )

    prompt = f"""You are a Kubernetes incident investigator. Analyze the evidence below and
determine the root cause. Be specific and evidence-based — cite which piece of evidence
supports your conclusion. Then give one concrete, actionable recommendation.

QUESTION: {state['question']}

EVIDENCE:
{state['evidence']}

RELEVANT KNOWLEDGE BASE ENTRIES:
{knowledge_text}

Respond in this exact format:
Root Cause: <one line>
Evidence: <2-3 sentences citing specific data points from above>
Recommendation: <one concrete action>
"""

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    state["root_cause"] = response.content[0].text
    return state


def build_graph():
    graph = StateGraph(InvestigationState)
    graph.add_node("gather_evidence", gather_evidence)
    graph.add_node("retrieve_knowledge", retrieve_knowledge)
    graph.add_node("analyze", analyze)

    graph.set_entry_point("gather_evidence")
    graph.add_edge("gather_evidence", "retrieve_knowledge")
    graph.add_edge("retrieve_knowledge", "analyze")
    graph.add_edge("analyze", END)

    return graph.compile()


def investigate(question: str, pod_name: str, namespace: str = "default") -> str:
    app = build_graph()
    result = app.invoke({
        "question": question,
        "pod_name": pod_name,
        "namespace": namespace,
        "evidence": {},
        "knowledge": [],
        "root_cause": None,
    })
    return result["root_cause"]
