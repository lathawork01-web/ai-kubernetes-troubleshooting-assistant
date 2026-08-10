"""
Basic smoke test for the RAG knowledge base — doesn't require a live
cluster, so it's safe to run in CI.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))

from rag.knowledge_base import retrieve_relevant_knowledge


def test_oomkilled_retrieval():
    results = retrieve_relevant_knowledge("pod keeps restarting, terminated reason OOMKilled")
    assert len(results) > 0
    assert any("oomkilled" in r["source"].lower() for r in results)


def test_crashloop_retrieval():
    results = retrieve_relevant_knowledge("CrashLoopBackOff container keeps exiting on startup")
    assert len(results) > 0
    assert any("crashloop" in r["source"].lower() for r in results)


if __name__ == "__main__":
    test_oomkilled_retrieval()
    test_crashloop_retrieval()
    print("All tests passed.")
