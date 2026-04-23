"""
tools/retriever.py
Hybrid retrieval for decision-support context.

Combines:
- local buying-guide documents bundled with the repo
- optional internet search results plus extracted page snippets
"""

from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


KNOWLEDGE_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "buying_guides.json"
TOKEN_RE = re.compile(r"[a-z0-9]+")
WHITESPACE_RE = re.compile(r"\s+")
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
WEB_SEARCH_TIMEOUT_SECONDS = 8
WEB_FETCH_TIMEOUT_SECONDS = 8


def _tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def _normalize_text(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text or "").strip()


def _build_query_text(product_name: str, category: str, product_url: str, signals: dict) -> str:
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
    return " ".join(part for part in query_parts if part)


def _prepare_documents(docs: list[dict]) -> list[dict]:
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


@lru_cache(maxsize=1)
def _load_local_documents() -> list[dict]:
    with KNOWLEDGE_PATH.open("r", encoding="utf-8") as fh:
        docs = json.load(fh)

    normalized = []
    for doc in docs:
        normalized.append({
            **doc,
            "source_type": "local",
            "source": "Local buying guide",
            "url": "",
        })
    return normalized


def _web_rag_enabled() -> bool:
    value = os.getenv("PRICE_SNIPER_ENABLE_WEB_RAG", "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _decode_result_url(url: str) -> str:
    parsed = urlparse(url)
    if "duckduckgo.com" not in parsed.netloc:
        return url

    target = parse_qs(parsed.query).get("uddg", [""])[0]
    return unquote(target) if target else url


def _search_web(query: str, limit: int = 5) -> list[dict]:
    try:
        import httpx
        from bs4 import BeautifulSoup

        headers = {"User-Agent": USER_AGENT}
        with httpx.Client(headers=headers, follow_redirects=True, timeout=WEB_SEARCH_TIMEOUT_SECONDS) as client:
            response = client.get("https://html.duckduckgo.com/html/", params={"q": query})
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        seen_urls: set[str] = set()

        for item in soup.select(".result"):
            link = item.select_one(".result__title a") or item.select_one("a.result__a")
            snippet_el = item.select_one(".result__snippet")
            if not link:
                continue

            url = _decode_result_url(link.get("href", "").strip())
            title = _normalize_text(link.get_text(" ", strip=True))
            snippet = _normalize_text(snippet_el.get_text(" ", strip=True) if snippet_el else "")
            if not url or not title or url in seen_urls:
                continue

            seen_urls.add(url)
            results.append({
                "id": f"web-search-{len(results) + 1}",
                "title": title,
                "content": snippet,
                "category": "web_search",
                "source_type": "web",
                "source": urlparse(url).netloc or "Web",
                "url": url,
            })
            if len(results) >= limit:
                break

        return results
    except Exception:
        return []


def _extract_relevant_passage(url: str, query_tokens: list[str]) -> str:
    try:
        import httpx
        from bs4 import BeautifulSoup

        headers = {"User-Agent": USER_AGENT}
        with httpx.Client(headers=headers, follow_redirects=True, timeout=WEB_FETCH_TIMEOUT_SECONDS) as client:
            response = client.get(url)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()

        paragraphs = []
        for tag in soup.find_all(["p", "li"]):
            text = _normalize_text(tag.get_text(" ", strip=True))
            if len(text) < 80 or len(text) > 500:
                continue
            paragraphs.append(text)

        if not paragraphs:
            return ""

        best = ""
        best_score = -1
        query_token_set = set(query_tokens)
        for text in paragraphs[:60]:
            tokens = set(_tokenize(text))
            overlap = len(tokens & query_token_set)
            if overlap > best_score:
                best_score = overlap
                best = text

        return best if best_score > 0 else paragraphs[0]
    except Exception:
        return ""


def _build_web_documents(product_name: str, signals: dict) -> list[dict]:
    if not _web_rag_enabled():
        return []

    search_terms = [
        f"{product_name} review buying guide",
        f"{product_name} deal history price drop advice",
    ]
    if signals.get("near_major_sale_event"):
        search_terms.append(f"{product_name} seasonal sale timing advice")

    query_tokens = _tokenize(" ".join(search_terms))
    documents: list[dict] = []
    seen_urls: set[str] = set()

    for term in search_terms:
        for result in _search_web(term, limit=4):
            url = result.get("url", "")
            if not url or url in seen_urls:
                continue

            seen_urls.add(url)
            passage = _extract_relevant_passage(url, query_tokens)
            content = passage or result.get("content", "")
            if not content:
                continue

            documents.append({
                **result,
                "content": content,
                "category": "web_market_context",
            })

            if len(documents) >= 6:
                return documents

    return documents


def _score_documents(docs: list[dict], query_tokens: list[str], signals: dict) -> list[dict]:
    prepared_docs = _prepare_documents(docs)
    if not prepared_docs or not query_tokens:
        return []

    query_tf = Counter(query_tokens)
    query_norm = math.sqrt(sum(v * v for v in query_tf.values())) or 1.0
    doc_freq = prepared_docs[0]["doc_freq"]
    total_docs = prepared_docs[0]["doc_count"]
    seen_content: set[str] = set()
    scored = []

    for doc in prepared_docs:
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
        if signals.get("has_low_stock_warning") and "stock" in doc.get("category", ""):
            score += 0.15
        if signals.get("near_major_sale_event") and "season" in doc.get("category", ""):
            score += 0.12
        if signals.get("is_near_all_time_low") and "heuristic" in doc.get("category", ""):
            score += 0.10
        if doc.get("source_type") == "web":
            score += 0.03

        normalized_content = _normalize_text(doc.get("content", "")).lower()
        if normalized_content in seen_content:
            continue
        seen_content.add(normalized_content)

        scored.append({
            "id": doc["id"],
            "title": doc["title"],
            "content": doc["content"],
            "score": round(score, 3),
            "source_type": doc.get("source_type", "local"),
            "source": doc.get("source", "Local buying guide"),
            "url": doc.get("url", ""),
        })

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored


def retrieve_context(
    product_name: str,
    category: str,
    product_url: str,
    signals: dict,
    top_k: int = 4,
) -> list[dict]:
    """Return supporting context snippets for the current product."""
    query_text = _build_query_text(product_name, category, product_url, signals)
    query_tokens = _tokenize(query_text)
    if not query_tokens:
        return []

    documents = [*_load_local_documents(), *_build_web_documents(product_name, signals)]
    scored = _score_documents(documents, query_tokens, signals)
    return scored[:top_k]
