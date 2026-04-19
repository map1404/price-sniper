"""
tools/price_history.py
Fetches 90-day price history via CamelCamelCamel scraping or synthetic generation.
"""

import re
import random
import math
from datetime import datetime, timedelta
from typing import List, Optional


def fetch_camelcamelcamel(asin: str) -> Optional[List[dict]]:
    """
    Scrape CamelCamelCamel for Amazon price history.
    Returns list of {date, price} dicts or None if unavailable.
    """
    try:
        import httpx
        from bs4 import BeautifulSoup

        url = f"https://camelcamelcamel.com/product/{asin}"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; PriceSniperBot/1.0)"}

        with httpx.Client(headers=headers, timeout=10, follow_redirects=True) as client:
            resp = client.get(url)
            soup = BeautifulSoup(resp.text, "html.parser")

            # Extract embedded chart data from script tags
            scripts = soup.find_all("script")
            for script in scripts:
                text = script.string or ""
                if "amazon_price" in text and "data" in text:
                    matches = re.findall(r'\[(\d+),\s*([\d.]+)\]', text)
                    if matches:
                        history = []
                        for ts, price in matches[-90:]:  # last 90 points
                            date = datetime.fromtimestamp(int(ts) / 1000)
                            history.append({
                                "date": date.strftime("%Y-%m-%d"),
                                "price": float(price)
                            })
                        return history
    except Exception:
        pass
    return None


def extract_asin(url: str) -> Optional[str]:
    """Extract Amazon ASIN from URL."""
    match = re.search(r"/dp/([A-Z0-9]{10})", url)
    return match.group(1) if match else None


def generate_realistic_history(current_price: float, days: int = 90) -> List[dict]:
    """
    Generate realistic price history with:
    - Gradual trends (up/down cycles)
    - Occasional sale events (flash drops)
    - Weekend/seasonal effects
    - Realistic noise
    """
    history = []
    price = current_price * random.uniform(1.05, 1.25)  # start higher
    today = datetime.now()

    for i in range(days, 0, -1):
        date = today - timedelta(days=i)

        # Slow downward trend
        trend = -0.001 * price

        # Random walk noise
        noise = random.gauss(0, price * 0.008)

        # Flash sale events (5% chance per day, drop 15-25%)
        flash_sale = 0
        if random.random() < 0.05:
            flash_sale = -price * random.uniform(0.15, 0.25)

        # Recovery after sale
        if history and history[-1]["price"] < price * 0.85:
            trend = price * 0.02  # bounce back

        # Weekend slight uptick (retailers reduce discounts)
        if date.weekday() >= 5:
            noise += price * 0.005

        price = max(price * 0.5, price + trend + noise + flash_sale)
        price = round(price, 2)

        history.append({
            "date": date.strftime("%Y-%m-%d"),
            "price": price
        })

    # Ensure last entry reflects current price
    history[-1]["price"] = round(current_price, 2)
    return history


def compute_history_stats(history: List[dict]) -> dict:
    """Compute key statistics from price history."""
    prices = [h["price"] for h in history]
    if not prices:
        return {}

    current = prices[-1]
    all_time_low = min(prices)
    all_time_high = max(prices)
    avg_30d = sum(prices[-30:]) / min(30, len(prices))
    avg_90d = sum(prices) / len(prices)

    # Days since last sale (price below avg)
    days_since_sale = 0
    for p in reversed(prices[:-1]):
        if p < avg_90d * 0.9:
            break
        days_since_sale += 1

    return {
        "current": current,
        "all_time_low": all_time_low,
        "all_time_high": all_time_high,
        "avg_30d": round(avg_30d, 2),
        "avg_90d": round(avg_90d, 2),
        "pct_above_atl": round((current - all_time_low) / all_time_low * 100, 1),
        "pct_below_ath": round((all_time_high - current) / all_time_high * 100, 1),
        "days_since_sale": days_since_sale,
        "is_near_atl": current <= all_time_low * 1.05,
        "is_near_ath": current >= all_time_high * 0.95,
    }


def fetch_price_history(product_url: str, product_name: str) -> List[dict]:
    """
    Main entry point.
    Tries CamelCamelCamel first, falls back to synthetic history.
    """
    # Try CamelCamelCamel for Amazon ASINs
    asin = extract_asin(product_url)
    if asin:
        history = fetch_camelcamelcamel(asin)
        if history:
            return history

    # Synthetic history for demo / non-Amazon products
    base_price = random.uniform(200, 400)
    return generate_realistic_history(base_price, days=90)
