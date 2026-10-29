"""Lidl: weekly offers embedded as JSON in `data-grid-data` attributes on lidl.lt."""

import html
import json
import re
from datetime import date, datetime

try:
    from zoneinfo import ZoneInfo
    VILNIUS = ZoneInfo("Europe/Vilnius")
except Exception:  # Windows without the tzdata package: fall back to the computer's clock
    VILNIUS = None

from ..models import Product, RawPage, parse_unit_price, unit_price_from_name

NAME = "lidl"
LABEL = "Lidl"
MIN_COUNT = 5
BASE = "https://www.lidl.lt"
# Offer pages that exist today; new ones are also discovered from the home page.
KNOWN_PAGES = [
    "/c/svarbiausios-sios-savaites-akcijos/a10023711",
    "/c/ne-maisto-prekiu-pasiulymai/a10086868",
]
_GRID_RE = re.compile(r'data-grid-data="([^"]*)"')
_OFFER_LINK_RE = re.compile(r'href="(?:https://www\.lidl\.lt)?(/c/[a-z0-9-]+/a\d+)"')


def fetch(client):
    home = client.get(BASE + "/")
    paths = list(dict.fromkeys(KNOWN_PAGES + _OFFER_LINK_RE.findall(home)))
    pages = []
    for i, path in enumerate(paths, 1):
        content = client.get(BASE + path)
        if _GRID_RE.search(content):
            pages.append(RawPage(f"page_{i:02d}.html", content))
    return pages


def _validity(stock, today):
    """Pick the date range that covers today, else the nearest future one."""
    ranges = []
    for entry in (stock or {}).get("badgeInfoV2") or []:
        start, end = entry.get("validFrom"), entry.get("validUntil")
        if start and end:
            ranges.append((
                datetime.fromtimestamp(start, VILNIUS).date(),
                datetime.fromtimestamp(end, VILNIUS).date(),
            ))
    current = [r for r in ranges if r[0] <= today <= r[1]]
    future = sorted(r for r in ranges if r[0] > today)
    chosen = (current or future or [None])[0]
    return (chosen[0].isoformat(), chosen[1].isoformat()) if chosen else (None, None)


def parse(pages, today=None):
    today = today or date.today()
    products = {}
    for page in pages:
        for raw in _GRID_RE.findall(page.content):
            d = json.loads(html.unescape(raw))
            name = (d.get("fullTitle") or d.get("title") or "").strip()
            price_info = d.get("price") or {}
            price = price_info.get("price")
            old = price_info.get("oldPrice")
            card = None
            if price is None and d.get("lidlPlus"):
                plus = (d["lidlPlus"][0] or {}).get("price") or {}
                price, old, card = plus.get("price"), plus.get("oldPrice"), "Lidl Plus"
            if not name or price is None:
                continue
            packaging = (price_info.get("packaging") or {}).get("text") or ""
            full_name = f"{name}, {packaging}" if packaging and packaging not in name else name
            unit = parse_unit_price((price_info.get("basePrice") or {}).get("text"))
            unit_price, unit_name = unit if unit else unit_price_from_name(price, packaging or name)
            discount = (price_info.get("discount") or {}).get("percentageDiscount")
            valid_from, valid_to = _validity(d.get("stockAvailability"), today)
            pid = str(d.get("productId") or d.get("erpNumber") or name)
            products[pid] = Product(
                chain=NAME, source_id=pid, name=full_name, price=float(price),
                old_price=float(old) if old else None,
                unit_price=unit_price, unit=unit_name, card=card,
                promo=f"-{discount} %" if discount else None,
                valid_from=valid_from, valid_to=valid_to,
                url=BASE + d["canonicalUrl"] if d.get("canonicalUrl") else None,
                category=d.get("category"),
            )
    return list(products.values())
