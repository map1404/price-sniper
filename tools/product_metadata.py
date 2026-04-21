"""
tools/product_metadata.py
Fetch basic product metadata such as the hero image from a product URL.
"""

from __future__ import annotations

import json
from typing import Optional
from urllib.parse import urljoin


def _normalize_image_url(raw_url: str | None, page_url: str) -> Optional[str]:
    if not raw_url:
        return None
    raw_url = raw_url.strip()
    if not raw_url:
        return None
    return urljoin(page_url, raw_url)


def fetch_product_image(product_url: str) -> Optional[str]:
    """Return the best-effort product image URL from a product page."""
    try:
        import httpx
        from bs4 import BeautifulSoup

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        with httpx.Client(headers=headers, timeout=12, follow_redirects=True) as client:
            response = client.get(product_url)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        for selector in [
            ('meta[property="og:image"]', "content"),
            ('meta[name="twitter:image"]', "content"),
            ('meta[property="twitter:image"]', "content"),
            ('link[rel="image_src"]', "href"),
        ]:
            element = soup.select_one(selector[0])
            if element:
                candidate = _normalize_image_url(element.get(selector[1]), product_url)
                if candidate:
                    return candidate

        for script in soup.select('script[type="application/ld+json"]'):
            raw = script.string or script.get_text(strip=True)
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except Exception:
                continue

            queue = data if isinstance(data, list) else [data]
            while queue:
                item = queue.pop(0)
                if isinstance(item, list):
                    queue.extend(item)
                    continue
                if not isinstance(item, dict):
                    continue
                image = item.get("image")
                if isinstance(image, str):
                    candidate = _normalize_image_url(image, product_url)
                    if candidate:
                        return candidate
                if isinstance(image, list):
                    for entry in image:
                        if isinstance(entry, str):
                            candidate = _normalize_image_url(entry, product_url)
                            if candidate:
                                return candidate
                queue.extend(value for value in item.values() if isinstance(value, (dict, list)))

        return None
    except Exception:
        return None
