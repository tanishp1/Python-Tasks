from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any

import requests
from bs4 import BeautifulSoup


class ScraperError(Exception):
    """Raised when the external page cannot be fetched (network/HTTP issues)."""


class ParsingError(Exception):
    """Raised when the supplied HTML document itself cannot be parsed at all."""


@dataclass
class Product:
    title: Optional[str]
    price: Optional[float]
    in_stock: Optional[bool]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


DEFAULT_TIMEOUT = 10


# --------------------------------------------------------------------------
# External dependency boundary
# --------------------------------------------------------------------------
def fetch_html(url: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Fetch raw HTML from *url* and return it as a string."""
    if not url:
        raise ValueError("url must be a non-empty string")

    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise ScraperError(f"Failed to fetch {url}: {exc}") from exc

    return response.text


# --------------------------------------------------------------------------
# Defensive field parsers -- each one degrades to None instead of raising
# --------------------------------------------------------------------------
def _parse_title(product_el) -> Optional[str]:
    el = product_el.select_one(".product-title") or product_el.find("h2")
    if el is None:
        return None
    text = el.get_text(strip=True)
    return text or None


def _parse_price(product_el) -> Optional[float]:
    el = product_el.select_one(".price")
    if el is None:
        return None
    text = el.get_text(strip=True)
    if not text:
        return None
    cleaned = text.replace("$", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        # Malformed / non-numeric price text -> graceful None, no crash
        return None


def _parse_stock(product_el) -> Optional[bool]:
    el = product_el.select_one(".stock")
    if el is None:
        return None
    text = el.get_text(strip=True).lower()
    if not text:
        return None
    if "out of stock" in text or "unavailable" in text:
        return False
    if "in stock" in text or "available" in text:
        return True
    # Unrecognized status text -> unknown, not an error
    return None


def parse_product(product_el) -> Product:
    """Parse a single `.product` container element defensively."""
    return Product(
        title=_parse_title(product_el),
        price=_parse_price(product_el),
        in_stock=_parse_stock(product_el),
    )


def parse_products(html: str) -> List[Product]:
    """Parse all `.product` elements from an HTML string and return a list of Products."""
    if html is None:
        raise ParsingError("HTML content is None")
    if not isinstance(html, str):
        raise ParsingError(f"HTML content must be a string, got {type(html).__name__}")

    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as exc:  # pragma: no cover - html.parser is very lenient
        raise ParsingError(f"Could not parse HTML: {exc}") from exc

    product_elements = soup.select(".product")
    return [parse_product(el) for el in product_elements]


# --------------------------------------------------------------------------
# High level convenience wrapper
# --------------------------------------------------------------------------
def scrape_products(url: str) -> List[Dict[str, Any]]:
    """Fetch a page and return parsed products as plain dicts."""
    html = fetch_html(url)
    products = parse_products(html)
    return [p.to_dict() for p in products]