"""
tools/analyzer.py
Detects buying signals from price data: flash sales, near ATL, low stock, seasonality.
"""

from datetime import datetime
from typing import List


def analyze_signals(retailer_prices: List[dict], price_history: List[dict]) -> dict:
    """
    Analyze all available data and return a signals dict for the reasoning agent.
    """
    signals = {}

    # ── Current price signals ──────────────────────────────────────────────────
    if retailer_prices:
        prices = [r["price"] for r in retailer_prices]
        best_price = min(prices)
        worst_price = max(prices)
        signals["best_price"] = best_price
        signals["worst_price"] = worst_price
        signals["price_spread_pct"] = round((worst_price - best_price) / best_price * 100, 1)
        signals["num_retailers_available"] = len([r for r in retailer_prices if r["stock"] != "out_of_stock"])
        signals["low_stock_retailers"] = [r["retailer"] for r in retailer_prices if r["stock"] == "low_stock"]
        signals["out_of_stock_retailers"] = [r["retailer"] for r in retailer_prices if r["stock"] == "out_of_stock"]
        signals["has_low_stock_warning"] = len(signals["low_stock_retailers"]) > 0
        signals["majority_out_of_stock"] = signals["num_retailers_available"] <= 1

    # ── Historical price signals ───────────────────────────────────────────────
    if price_history and retailer_prices:
        hist_prices = [h["price"] for h in price_history]
        current = min(r["price"] for r in retailer_prices)
        atl = min(hist_prices)
        ath = max(hist_prices)
        avg_90d = sum(hist_prices) / len(hist_prices)
        avg_30d = sum(hist_prices[-30:]) / min(30, len(hist_prices))

        signals["all_time_low"] = round(atl, 2)
        signals["all_time_high"] = round(ath, 2)
        signals["avg_30d"] = round(avg_30d, 2)
        signals["avg_90d"] = round(avg_90d, 2)
        signals["pct_above_atl"] = round((current - atl) / atl * 100, 1)
        signals["pct_vs_avg_90d"] = round((current - avg_90d) / avg_90d * 100, 1)
        signals["is_near_all_time_low"] = current <= atl * 1.05      # within 5% of ATL
        signals["is_below_30d_avg"] = current < avg_30d
        signals["is_below_90d_avg"] = current < avg_90d

        # Detect if this looks like a flash sale (sudden drop vs yesterday)
        if len(hist_prices) >= 2:
            yesterday = hist_prices[-2]
            drop_pct = (yesterday - current) / yesterday * 100
            signals["flash_sale_detected"] = drop_pct >= 10
            signals["flash_sale_drop_pct"] = round(drop_pct, 1) if drop_pct > 0 else 0
        else:
            signals["flash_sale_detected"] = False
            signals["flash_sale_drop_pct"] = 0

        # Trend: is price rising or falling over last 14 days?
        if len(hist_prices) >= 14:
            recent = hist_prices[-14:]
            trend = (recent[-1] - recent[0]) / recent[0] * 100
            signals["14d_trend_pct"] = round(trend, 1)
            signals["price_trending_down"] = trend < -2
            signals["price_trending_up"] = trend > 2
        else:
            signals["14d_trend_pct"] = 0
            signals["price_trending_down"] = False
            signals["price_trending_up"] = False

    # ── Seasonal signals ───────────────────────────────────────────────────────
    now = datetime.now()
    month = now.month
    day = now.day

    signals["seasonal_context"] = _get_seasonal_context(month, day)
    signals["near_major_sale_event"] = _is_near_sale_event(month, day)

    return signals


def _get_seasonal_context(month: int, day: int) -> str:
    """Return human-readable seasonal buying context."""
    if month == 11 and day >= 20:
        return "Black Friday week — historically best prices of the year"
    elif month == 12 and day <= 26:
        return "Holiday season — mixed pricing, some deals available"
    elif month == 1 and day <= 15:
        return "Post-holiday clearance — often good deals on electronics"
    elif month == 7 and 10 <= day <= 20:
        return "Amazon Prime Day period — major discounts expected"
    elif month == 2 and 10 <= day <= 16:
        return "Valentine's Day — prices may be elevated on gifts"
    elif month == 9:
        return "Back-to-school season ending — electronics often discounted"
    elif month == 3 and day >= 15:
        return "Spring refresh cycle — new models incoming, older ones cheaper"
    else:
        return "No major sale event nearby"


def _is_near_sale_event(month: int, day: int) -> bool:
    """Returns True if within 2 weeks of a major retail sale event."""
    sale_windows = [
        (11, 15, 11, 30),   # Black Friday window
        (12, 20, 12, 26),   # Christmas
        (7, 8, 7, 22),      # Prime Day
        (1, 1, 1, 10),      # New Year sales
    ]
    for sm, sd, em, ed in sale_windows:
        start = datetime(datetime.now().year, sm, sd)
        end = datetime(datetime.now().year, em, ed)
        now = datetime.now()
        if start <= now <= end:
            return True
    return False
