"""
knowledge_base.py — lightweight RAG over a curated set of known Kubernetes
failure patterns.

DESIGN NOTE — why TF-IDF instead of a neural embedding model:
An earlier version of this used ChromaDB's default embedding function,
which downloads an ONNX model (~90MB) from an external CDN the first time
it runs. That's a real reliability problem: it fails outright in any
network-restricted environment (corporate proxies, air-gapped CI runners,
sandboxes) and adds a slow, non-deterministic first-run cost everywhere
else. For a knowledge base of a few dozen curated documents — not millions
— classic TF-IDF + cosine similarity retrieves just as effectively, has
zero runtime network dependency, and is fully deterministic. If you later
grow this to thousands of docs, swapping in a proper embedding model
becomes worth the tradeoff; it isn't yet.
"""

import os
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

KNOWLEDGE_DOCS_DIR = os.path.join(os.path.dirname(__file__), "knowledge_docs")

_vectorizer = None
_doc_vectors = None
_docs = []       # list of {"source": filename, "content": text}


def load_knowledge_base(force_reload: bool = False):
    """Load and vectorize all .md files in knowledge_docs/. Idempotent — safe to call repeatedly."""
    global _vectorizer, _doc_vectors, _docs

    if _vectorizer is not None and not force_reload:
        return  # already loaded

    _docs = []
    for filename in sorted(os.listdir(KNOWLEDGE_DOCS_DIR)):
        if not filename.endswith(".md"):
            continue
        path = os.path.join(KNOWLEDGE_DOCS_DIR, filename)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        _docs.append({"source": filename, "content": content})

    if not _docs:
        raise RuntimeError(f"No knowledge docs found in {KNOWLEDGE_DOCS_DIR}")

    corpus = [d["content"] for d in _docs]
    _vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
    _doc_vectors = _vectorizer.fit_transform(corpus)


def retrieve_relevant_knowledge(query: str, n_results: int = 3) -> list:
    """Return the most relevant known-issue docs for a given symptom description, ranked by cosine similarity."""
    load_knowledge_base()

    query_vector = _vectorizer.transform([query])
    similarities = cosine_similarity(query_vector, _doc_vectors)[0]

    ranked_indices = similarities.argsort()[::-1][:n_results]

    matches = []
    for idx in ranked_indices:
        if similarities[idx] <= 0:
            continue  # no lexical overlap at all — not a real match, don't pad results with noise
        matches.append({
            "source": _docs[idx]["source"],
            "content": _docs[idx]["content"],
            "relevance_score": round(float(similarities[idx]), 3),
        })
    return matches
