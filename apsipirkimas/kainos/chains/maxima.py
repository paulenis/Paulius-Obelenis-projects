"""Maxima: promotions from its e-shop Barbora (`window.b_productList` JSON in the page)."""

import json

from ..models import Product, RawPage, unit_price_from_name

NAME = "maxima"
LABEL = "Maxima"
MIN_COUNT = 50
BASE = "https://barbora.lt"
LIST_URL = BASE + "/aciu-akcijos?page={page}"
MAX_PAGES = 300  # ~130 pages in October 2026; stops at the first empty page
_MARKER = "window.b_productList"


def _product_list(content):
    i = content.find(_MARKER)
    if i < 0:
        return None
    j = content.find("=", i) + 1
    data, _ = json.JSONDecoder().raw_decode(content[j:].lstrip())
    return data


def fetch(client):
    pages, seen = [], set()
    for n in range(1, MAX_PAGES + 1):
        content = client.get(LIST_URL.format(page=n))
        items = _product_list(content) or []
        ids = {p.get("id") for p in items}
        if not items or ids <= seen:
            break  # past the last page Barbora repeats or returns nothing
        seen |= ids
        pages.append(RawPage(f"page_{n:03d}.html", content))
    return pages


def _eur(value):
    return f"{value:.2f}".replace(".", ",") + " €"


def parse(pages, today=None):
    products = {}
    for page in pages:
        for p in _product_list(page.content) or []:
            name, price = (p.get("title") or "").strip(), p.get("price")
            if not name or not price:
                continue
            promo = p.get("promotion") or {}
            old = promo.get("oldPrice")
            retail = p.get("retail_price")
            if old is None and retail and retail > price:
                old = retail
            card = "AČIŪ" if promo.get("loyaltyCardRequired") else None
            promo_text = None
            if promo.get("type") == "X_FOR_Y" and promo.get("quantity"):
                promo_text = f"{promo['quantity']} už {_eur(promo['price'])}"
            elif promo.get("percentage"):
                promo_text = f"-{promo['percentage']} %"
            unit_price = p.get("comparative_unit_price")
            unit = p.get("comparative_unit")
            if not unit_price:
                unit_price, unit = unit_price_from_name(price, name)
            products[p["id"]] = Product(
                chain=NAME, source_id=str(p["id"]), name=name, price=float(price),
                old_price=float(old) if old else None,
                unit_price=float(unit_price) if unit_price else None,
                unit=(unit or None) and ("vnt." if unit.startswith("vnt") else unit),
                card=card, promo=promo_text,
                url=f"{BASE}/produktai/{p['Url']}" if p.get("Url") else None,
                category=p.get("category_name_full_path"),
            )
    return list(products.values())
