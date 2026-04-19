"""
tools/reasoner.py
LLM-powered verdict engine with chain-of-thought reasoning.
Uses few-shot prompting to produce structured BUY / WAIT / AVOID decisions.
"""

import json
import os
from typing import List


# ── Few-shot examples ──────────────────────────────────────────────────────────

FEW_SHOT_EXAMPLES = """
EXAMPLE 1:
Product: Sony WH-1000XM5 Headphones
Current best price: $248
All-time low: $245 | 90-day avg: $298 | Trending: DOWN (-8% over 14 days)
Stock: Low stock at Walmart | Flash sale: YES (dropped 12% today)
Seasonal: No major sale nearby

Reasoning:
1. Current price ($248) is within 1.2% of the all-time low ($245) — essentially at rock bottom.
2. A flash sale is active — 12% drop from yesterday signals a limited-time discount.
3. Low stock at Walmart creates urgency; if this sells out, prices will recover.
4. Price has been trending down 8% over 14 days — the discount appears intentional.
5. No better sale event is coming soon that would push prices lower.
Conclusion: All signals point to this being a genuine buying opportunity.

Output: {"verdict": "BUY NOW", "confidence": 91, "reasoning_steps": ["Within 1.2% of all-time low", "Active flash sale detected (-12% today)", "Low stock warning at Walmart creates real urgency", "14-day downtrend confirms intentional markdown", "No major sale event coming that would beat this price"]}

---

EXAMPLE 2:
Product: Apple AirPods Pro 2nd Gen
Current best price: $219
All-time low: $179 | 90-day avg: $224 | Trending: FLAT
Stock: In stock everywhere | Flash sale: NO
Seasonal: Black Friday is 18 days away

Output: {"verdict": "WAIT", "confidence": 84, "reasoning_steps": ["Currently $40 above all-time low (22% premium) — not a good deal", "Black Friday is only 18 days away — Apple AirPods historically drop to ATL during this event", "No urgency signal: in stock everywhere, no flash sale", "Flat trend means price is unlikely to drop further before Black Friday", "Patient buyer will likely save $30-40 by waiting 2-3 weeks"]}

---

EXAMPLE 3:
Product: Instant Pot Duo 7-in-1
Current best price: $89
All-time low: $49 | 90-day avg: $69 | Trending: UP (+15% over 14 days)
Stock: In stock | Flash sale: NO
Seasonal: No major sale nearby

Output: {"verdict": "AVOID", "confidence": 78, "reasoning_steps": ["Current price ($89) is 81% above all-time low ($49) — significantly overpriced", "Price is also above the 90-day average ($69), suggesting a temporary spike", "Upward trend (+15% over 14 days) means price is moving in the wrong direction", "No flash sale or urgency signal to justify buying at a premium", "Recommendation: set a price alert at $60 and wait for a correction"]}
"""


# ── System prompt ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert shopping analyst and price intelligence agent. 
Your job is to analyze price data for a product across multiple retailers and make a clear, 
confident buying recommendation.

You reason step by step, weighing:
1. Current price vs all-time low and historical averages
2. Active flash sales or sudden price drops
3. Stock level urgency (low stock = potential price recovery)
4. Upcoming sale events that might offer better prices
5. Price trend direction (rising = buy sooner, falling = wait)

You always output ONLY valid JSON with this exact structure:
{
  "verdict": "BUY NOW" | "WAIT" | "AVOID",
  "confidence": <integer 0-100>,
  "reasoning_steps": [<list of 4-6 concise reasoning strings>]
}

No preamble. No explanation outside the JSON. Only the JSON object."""


# ── Main reasoning function ────────────────────────────────────────────────────

def generate_verdict(
    product_name: str,
    retailer_prices: List[dict],
    price_history: List[dict],
    signals: dict,
    retrieved_context: List[dict] | None = None,
) -> dict:
    """
    Send data to LLM and get a structured verdict back.
    Falls back to rule-based verdict if API unavailable.
    """
    prompt = _build_prompt(product_name, retailer_prices, price_history, signals, retrieved_context or [])

    # Try OpenAI first, then Anthropic, then rule-based fallback
    result = _call_openai(prompt) or _call_anthropic(prompt) or _rule_based_verdict(signals, retrieved_context or [])
    return result


def _build_prompt(product_name, retailer_prices, price_history, signals, retrieved_context: List[dict]) -> str:
    best_price = signals.get("best_price", "N/A")
    atl = signals.get("all_time_low", "N/A")
    avg_90d = signals.get("avg_90d", "N/A")
    avg_30d = signals.get("avg_30d", "N/A")
    trend = signals.get("14d_trend_pct", 0)
    trend_str = f"UP +{trend}%" if trend > 0 else f"DOWN {trend}%"
    flash = "YES" if signals.get("flash_sale_detected") else "NO"
    low_stock = signals.get("low_stock_retailers", [])
    stock_str = f"Low stock at: {', '.join(low_stock)}" if low_stock else "In stock at most retailers"
    seasonal = signals.get("seasonal_context", "No major event nearby")

    prices_str = "\n".join([
        f"  - {r['retailer']}: ${r['price']} ({r['stock']})"
        for r in sorted(retailer_prices, key=lambda x: x["price"])
    ]) if retailer_prices else "  No retailer data available"
    context_str = "\n".join([
        f"  - {item['title']}: {item['content']}"
        for item in retrieved_context
    ]) if retrieved_context else "  No additional retrieved context"

    return f"""{FEW_SHOT_EXAMPLES}

---

NOW ANALYZE THIS PRODUCT:
Product: {product_name}
Current best price: ${best_price}
All-time low: ${atl} | 90-day avg: ${avg_90d} | 30-day avg: ${avg_30d}
Price trend (14 days): {trend_str}
Flash sale detected: {flash}
Stock status: {stock_str}
Seasonal context: {seasonal}

Retailer breakdown:
{prices_str}

Retrieved market context:
{context_str}

Produce your verdict as JSON only."""


def _call_openai(prompt: str) -> dict | None:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=500,
        )
        raw = response.choices[0].message.content.strip()
        return _parse_json(raw)
    except Exception:
        return None


def _call_anthropic(prompt: str) -> dict | None:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        return _parse_json(raw)
    except Exception:
        return None


def _parse_json(raw: str) -> dict | None:
    try:
        # Strip markdown fences if present
        clean = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean)
        # Validate required fields
        assert "verdict" in data and "confidence" in data and "reasoning_steps" in data
        return data
    except Exception:
        return None


def _rule_based_verdict(signals: dict, retrieved_context: List[dict]) -> dict:
    """
    Deterministic fallback when no LLM API is available.
    Uses signal thresholds to produce a verdict.
    """
    score = 50  # neutral starting point
    reasons = []

    pct_above_atl = signals.get("pct_above_atl", 20)
    is_near_atl = signals.get("is_near_all_time_low", False)
    flash_sale = signals.get("flash_sale_detected", False)
    low_stock = signals.get("has_low_stock_warning", False)
    trending_down = signals.get("price_trending_down", False)
    trending_up = signals.get("price_trending_up", False)
    near_event = signals.get("near_major_sale_event", False)
    seasonal = signals.get("seasonal_context", "")
    pct_vs_avg = signals.get("pct_vs_avg_90d", 0)

    if is_near_atl:
        score += 25
        reasons.append(f"Price is within 5% of all-time low — historically a strong buying signal")
    elif pct_above_atl > 30:
        score -= 20
        reasons.append(f"Price is {pct_above_atl}% above all-time low — significantly overpriced")

    if flash_sale:
        score += 20
        reasons.append(f"Flash sale detected — price dropped {signals.get('flash_sale_drop_pct', 0)}% today")

    if low_stock:
        score += 10
        reasons.append(f"Low stock at {', '.join(signals.get('low_stock_retailers', []))} — prices likely to recover")

    if trending_down:
        score -= 10
        reasons.append("Price trending down over 14 days — waiting may yield a better deal")

    if trending_up:
        score += 10
        reasons.append("Price trending up — buying now avoids paying more tomorrow")

    if near_event and not flash_sale:
        score -= 15
        reasons.append(f"Major sale event upcoming — {seasonal}")

    if pct_vs_avg < -10:
        score += 15
        reasons.append(f"Price is {abs(pct_vs_avg):.0f}% below 90-day average — genuine discount")

    context_text = " ".join(item.get("content", "").lower() for item in retrieved_context)
    if "within 5 percent of the all-time low" in context_text and is_near_atl:
        score += 5
    if "waiting is often rewarded" in context_text and near_event and not flash_sale:
        score -= 5
        reasons.append("Retrieved guidance suggests sale timing may reward patience")
    if "rebound quickly after retailer stock tightens" in context_text and low_stock:
        score += 5
        reasons.append("Retrieved guidance suggests low stock can shorten the deal window")

    # Determine verdict
    if score >= 70:
        verdict = "BUY NOW"
    elif score >= 45:
        verdict = "WAIT"
    else:
        verdict = "AVOID"

    if not reasons:
        reasons.append("Insufficient data for detailed analysis — consider checking manually")

    return {
        "verdict": verdict,
        "confidence": min(95, max(40, score)),
        "reasoning_steps": reasons[:5],
    }
