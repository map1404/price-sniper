"""
Price Drop Sniper Agent
LangGraph-powered autonomous price intelligence agent
"""

from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, END
from tools.crawler import crawl_retailers
from tools.price_history import fetch_price_history
from tools.product_metadata import fetch_product_image
from tools.analyzer import analyze_signals
from tools.reasoner import generate_verdict
from tools.retriever import retrieve_context


# ── State ──────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    product_url: str
    product_name: str
    product_image_url: Optional[str]
    product_model: str
    category: str
    retailer_prices: List[dict]       # [{retailer, price, stock, url}]
    price_history: List[dict]         # [{date, price}]
    signals: dict                     # {flash_sale, near_all_time_low, low_stock, ...}
    retrieved_context: List[dict]     # [{title, content, score}]
    verdict: str                      # "BUY NOW" | "WAIT" | "AVOID"
    confidence: int                   # 0-100
    reasoning: List[str]              # step-by-step reasoning chain
    best_deal: Optional[dict]         # {retailer, price, url}
    error: Optional[str]


# ── Nodes ──────────────────────────────────────────────────────────────────────

def identify_product(state: AgentState) -> AgentState:
    """Extract product name and category from URL."""
    import re
    url = state["product_url"]

    # Detect retailer and extract product slug
    retailer_patterns = {
        "amazon": r"amazon\.com/([^/]+)/dp/",
        "bestbuy": r"bestbuy\.com/site/([^/]+)/",
        "walmart": r"walmart\.com/ip/([^/]+)/",
        "target": r"target\.com/p/([^/]+)/-/",
        "newegg": r"newegg\.com/([^/]+)/p/",
    }

    product_name = "Unknown Product"
    for retailer, pattern in retailer_patterns.items():
        match = re.search(pattern, url)
        if match:
            raw = match.group(1).replace("-", " ").replace("_", " ")
            product_name = raw[:80].title()
            break

    return {
        **state,
        "product_name": product_name,
        "product_image_url": fetch_product_image(url),
        "product_model": "",
        "category": "electronics",  # default; LLM can refine
    }


def crawl_prices(state: AgentState) -> AgentState:
    """Crawl all retailers for current prices and stock."""
    try:
        prices = crawl_retailers(state["product_url"], state["product_name"])
        return {**state, "retailer_prices": prices}
    except Exception as e:
        return {**state, "retailer_prices": [], "error": str(e)}


def fetch_history(state: AgentState) -> AgentState:
    """Fetch 90-day price history."""
    try:
        history = fetch_price_history(state["product_url"], state["product_name"])
        return {**state, "price_history": history}
    except Exception as e:
        return {**state, "price_history": [], "error": str(e)}


def analyze(state: AgentState) -> AgentState:
    """Detect signals: flash sale, near ATL, low stock, seasonal."""
    signals = analyze_signals(
        retailer_prices=state["retailer_prices"],
        price_history=state["price_history"],
    )
    return {**state, "signals": signals}


def retrieve_supporting_context(state: AgentState) -> AgentState:
    """Pull supporting knowledge snippets for the final verdict prompt."""
    context = retrieve_context(
        product_name=state["product_name"],
        category=state["category"],
        product_url=state["product_url"],
        signals=state["signals"],
    )
    return {**state, "retrieved_context": context}


def reason_and_decide(state: AgentState) -> AgentState:
    """LLM reasoning agent — produces verdict + confidence + reasoning chain."""
    result = generate_verdict(
        product_name=state["product_name"],
        retailer_prices=state["retailer_prices"],
        price_history=state["price_history"],
        signals=state["signals"],
        retrieved_context=state.get("retrieved_context", []),
    )
    best = min(state["retailer_prices"], key=lambda x: x["price"]) if state["retailer_prices"] else None
    return {
        **state,
        "verdict": result["verdict"],
        "confidence": result["confidence"],
        "reasoning": result["reasoning_steps"],
        "best_deal": best,
    }


def should_continue(state: AgentState) -> str:
    if state.get("error") and not state.get("retailer_prices"):
        return "end"
    return "analyze"


# ── Graph ──────────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("identify_product", identify_product)
    graph.add_node("crawl_prices", crawl_prices)
    graph.add_node("fetch_history", fetch_history)
    graph.add_node("analyze", analyze)
    graph.add_node("retrieve_supporting_context", retrieve_supporting_context)
    graph.add_node("reason_and_decide", reason_and_decide)

    graph.set_entry_point("identify_product")
    graph.add_edge("identify_product", "crawl_prices")
    graph.add_edge("crawl_prices", "fetch_history")
    graph.add_conditional_edges("fetch_history", should_continue, {
        "analyze": "analyze",
        "end": END,
    })
    graph.add_edge("analyze", "retrieve_supporting_context")
    graph.add_edge("retrieve_supporting_context", "reason_and_decide")
    graph.add_edge("reason_and_decide", END)

    return graph.compile()


# ── Entry point ────────────────────────────────────────────────────────────────

def run_agent(product_url: str) -> AgentState:
    graph = build_graph()
    initial_state: AgentState = {
        "product_url": product_url,
        "product_name": "",
        "product_image_url": None,
        "product_model": "",
        "category": "",
        "retailer_prices": [],
        "price_history": [],
        "signals": {},
        "retrieved_context": [],
        "verdict": "",
        "confidence": 0,
        "reasoning": [],
        "best_deal": None,
        "error": None,
    }
    return graph.invoke(initial_state)


if __name__ == "__main__":
    import json
    url = input("Enter a product URL: ").strip()
    result = run_agent(url)
    print(json.dumps({
        "product": result["product_name"],
        "verdict": result["verdict"],
        "confidence": result["confidence"],
        "best_deal": result["best_deal"],
        "reasoning": result["reasoning"],
    }, indent=2))
