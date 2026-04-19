"""
tools/retriever.py
Lightweight local retrieval for decision-support context.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import List


KNOWLEDGE_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "buying_guides.json"
TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> List[str]:
    return TOKEN_RE.findall(text.lower())


@lru_cache(maxsize=1)
def _load_documents() -> list[dict]:
    with KNOWLEDGE_PATH.open("r", encoding="utf-8") as fh:
        docs = json.load(fh)

    processed = []
    total_docs = max(len(docs), 1)
    doc_freq: Counter[str] = Counter()
    tokenized_docs: list[list[str]] = []

    for doc in docs:
        tokens = _tokenize(f"{doc.get('title', '')} {doc.get('category', '')} {doc.get('content', '')}")
        tokenized_docs.append(tokens)
        doc_freq.update(set(tokens))

    for doc, tokens in zip(docs, tokenized_docs):
        tf = Counter(tokens)
        length = math.sqrt(sum(v * v for v in tf.values())) or 1.0
        processed.append({
            **doc,
            "tokens": tokens,
            "tf": tf,
            "norm": length,
            "doc_count": total_docs,
            "doc_freq": doc_freq,
        })

    return processed


def retrieve_context(
    product_name: str,
    category: str,
    product_url: str,
    signals: dict,
    top_k: int = 3,
) -> list[dict]:
    """Return top-k supporting context snippets for the current product."""
    docs = _load_documents()
    if not docs:
        return []

    query_parts = [
        product_name,
        category,
        product_url,
        signals.get("seasonal_context", ""),
        "flash sale" if signals.get("flash_sale_detected") else "",
        "low stock" if signals.get("has_low_stock_warning") else "",
        "near all time low" if signals.get("is_near_all_time_low") else "",
        "trending up" if signals.get("price_trending_up") else "",
        "trending down" if signals.get("price_trending_down") else "",
        "buy now wait avoid pricing heuristic",
    ]
    query_tokens = _tokenize(" ".join(part for part in query_parts if part))
    if not query_tokens:
        return []

    query_tf = Counter(query_tokens)
    query_norm = math.sqrt(sum(v * v for v in query_tf.values())) or 1.0
    doc_freq = docs[0]["doc_freq"]
    total_docs = docs[0]["doc_count"]

    scored = []
    for doc in docs:
        overlap = set(query_tokens) & set(doc["tokens"])
        if not overlap:
            continue

        dot = 0.0
        for token, q_count in query_tf.items():
            if token not in doc["tf"]:
                continue
            idf = math.log((1 + total_docs) / (1 + doc_freq[token])) + 1.0
            dot += (q_count * idf) * (doc["tf"][token] * idf)

        score = dot / (query_norm * doc["norm"])
        if signals.get("has_low_stock_warning") and "stock" in doc["category"]:
            score += 0.15
        if signals.get("near_major_sale_event") and "season" in doc["category"]:
            score += 0.12
        if signals.get("is_near_all_time_low") and "heuristic" in doc["category"]:
            score += 0.10

        scored.append({
            "id": doc["id"],
            "title": doc["title"],
            "content": doc["content"],
            "score": round(score, 3),
        })

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top_k]
