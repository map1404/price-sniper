"""
tools/crawler.py
Multi-retailer async webcrawler using Crawl4AI + BeautifulSoup fallback.
Crawls Amazon, Best Buy, Walmart, Target, Newegg for live prices + stock.
"""

import asyncio
import re
import random
from typing import List, Optional
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class RetailerResult:
    retailer: str
    price: float
    stock: str          # "in_stock" | "low_stock" | "out_of_stock"
    url: str
    currency: str = "USD"


# ── Retailer search URL builders ───────────────────────────────────────────────

def build_search_urls(product_name: str) -> dict:
    """Build search URLs for each retailer given a product name."""
    query = product_name.replace(" ", "+")
    return {
        "Amazon":   f"https://www.amazon.com/s?k={query}",
        "Best Buy": f"https://www.bestbuy.com/site/searchpage.jsp?st={query}",
        "Walmart":  f"https://www.walmart.com/search?q={query}",
        "Target":   f"https://www.target.com/s?searchTerm={query}",
        "Newegg":   f"https://www.newegg.com/p/pl?d={query}",
    }


def retailer_from_url(url: str) -> Optional[str]:
    host = urlparse(url).netloc.lower()
    if "amazon." in host:
        return "Amazon"
    if "bestbuy." in host:
        return "Best Buy"
    if "walmart." in host:
        return "Walmart"
    if "target." in host:
        return "Target"
    if "newegg." in host:
        return "Newegg"
    return None


def is_specific_product_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(
        marker in path
        for marker in ["/dp/", "/gp/product/", "/site/", "/ip/", "/p/"]
    )


def resolve_result_url(
    retailer: str,
    candidate_url: str,
    product_url: str,
    fallback_url: str,
) -> str:
    if candidate_url and is_specific_product_url(candidate_url):
        return candidate_url
    if retailer_from_url(product_url) == retailer and is_specific_product_url(product_url):
        return product_url
    return product_url if is_specific_product_url(product_url) else fallback_url


# ── Price extractors per retailer ──────────────────────────────────────────────

def extract_amazon_price(html: str) -> Optional[RetailerResult]:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")

    # Try multiple Amazon price selectors
    selectors = [
        ("span", {"class": "a-price-whole"}),
        ("span", {"id": "priceblock_ourprice"}),
        ("span", {"class": "a-offscreen"}),
    ]
    for tag, attrs in selectors:
        el = soup.find(tag, attrs)
        if el:
            raw = el.get_text(strip=True).replace(",", "").replace("$", "")
            try:
                price = float(re.search(r"[\d.]+", raw).group())
                stock_el = soup.find("div", {"id": "availability"})
                stock = "in_stock"
                if stock_el:
                    txt = stock_el.get_text(strip=True).lower()
                    if "only" in txt and "left" in txt:
                        stock = "low_stock"
                    elif "unavailable" in txt or "out of stock" in txt:
                        stock = "out_of_stock"
                return RetailerResult("Amazon", price, stock, "https://amazon.com")
            except Exception:
                continue
    return None


def extract_bestbuy_price(html: str) -> Optional[RetailerResult]:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")

    el = soup.find("div", {"class": re.compile(r"priceView-customer-price")})
    if el:
        raw = el.get_text(strip=True)
        match = re.search(r"\$([\d,]+\.?\d*)", raw)
        if match:
            price = float(match.group(1).replace(",", ""))
            return RetailerResult("Best Buy", price, "in_stock", "https://bestbuy.com")
    return None


def extract_walmart_price(html: str) -> Optional[RetailerResult]:
    import json
    from bs4 import BeautifulSoup

    # Walmart embeds price in JSON-LD
    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.find_all("script", {"type": "application/ld+json"})
    for script in scripts:
        try:
            data = json.loads(script.string)
            if isinstance(data, dict) and "offers" in data:
                offers = data["offers"]
                if isinstance(offers, list):
                    offers = offers[0]
                price = float(offers.get("price", 0))
                if price > 0:
                    avail = offers.get("availability", "").lower()
                    stock = "out_of_stock" if "outofstock" in avail else "in_stock"
                    return RetailerResult("Walmart", price, stock, "https://walmart.com")
        except Exception:
            continue

    # Fallback: regex
    match = re.search(r'"price"\s*:\s*"?([\d.]+)"?', html)
    if match:
        return RetailerResult("Walmart", float(match.group(1)), "in_stock", "https://walmart.com")
    return None


EXTRACTORS = {
    "Amazon":   extract_amazon_price,
    "Best Buy": extract_bestbuy_price,
    "Walmart":  extract_walmart_price,
}


# ── Async crawl with Crawl4AI ──────────────────────────────────────────────────

async def crawl_single(retailer: str, url: str) -> Optional[RetailerResult]:
    """Crawl one retailer page asynchronously."""
    try:
        from crawl4ai import AsyncWebCrawler
        async with AsyncWebCrawler(verbose=False) as crawler:
            result = await crawler.arun(url=url, bypass_cache=True)
            html = result.html or ""
            extractor = EXTRACTORS.get(retailer)
            if extractor and html:
                return extractor(html)
    except ImportError:
        # crawl4ai not installed — use httpx fallback
        return await crawl_fallback(retailer, url)
    except Exception:
        pass
    return None


async def crawl_fallback(retailer: str, url: str) -> Optional[RetailerResult]:
    """Fallback crawler using httpx with browser-like headers."""
    try:
        import httpx
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=15) as client:
            resp = await client.get(url)
            html = resp.text
            extractor = EXTRACTORS.get(retailer)
            if extractor:
                return extractor(html)
    except Exception:
        pass
    return None


# ── Mock data for demo / fallback ──────────────────────────────────────────────

def mock_retailer_prices(product_name: str, product_url: str) -> List[dict]:
    """
    Returns realistic mock data for demo purposes.
    Replace with live crawling in production.
    """
    base = random.uniform(180, 320)
    retailers = [
        {"retailer": "Amazon",   "price": round(base * random.uniform(0.95, 1.05), 2), "stock": "in_stock",    "url": product_url},
        {"retailer": "Best Buy", "price": round(base * random.uniform(0.98, 1.08), 2), "stock": "in_stock",    "url": product_url},
        {"retailer": "Walmart",  "price": round(base * random.uniform(0.93, 1.02), 2), "stock": "low_stock",   "url": product_url},
        {"retailer": "Target",   "price": round(base * random.uniform(1.00, 1.10), 2), "stock": "in_stock",    "url": product_url},
        {"retailer": "Newegg",   "price": round(base * random.uniform(0.90, 1.00), 2), "stock": "out_of_stock","url": product_url},
    ]
    return sorted(retailers, key=lambda x: x["price"])


# ── Public interface ───────────────────────────────────────────────────────────

def crawl_retailers(product_url: str, product_name: str) -> List[dict]:
    """
    Main entry point. Crawls all retailers and returns sorted price list.
    Falls back to mock data if live crawling fails (useful for demo).
    """
    search_urls = build_search_urls(product_name)

    async def run_all():
        tasks = [crawl_single(retailer, url) for retailer, url in search_urls.items()]
        return await asyncio.gather(*tasks)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                results = pool.submit(asyncio.run, run_all()).result()
        else:
            results = loop.run_until_complete(run_all())

        live_results = [
            {
                "retailer": r.retailer,
                "price": r.price,
                "stock": r.stock,
                "url": resolve_result_url(
                    r.retailer,
                    r.url,
                    product_url,
                    search_urls.get(r.retailer, product_url),
                ),
            }
            for r in results if r is not None
        ]

        if len(live_results) >= 2:
            return sorted(live_results, key=lambda x: x["price"])
    except Exception:
        pass

    # Demo fallback
    print("⚠️  Live crawling unavailable — using demo data")
    return mock_retailer_prices(product_name, product_url)
