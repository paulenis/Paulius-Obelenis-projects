"""Iki: promotions through LastMile (IKI's e-shop partner) search API.

iki.lt itself is behind a bot challenge; we do not try to get around it.
"""

import json

from ..models import Product, RawPage, unit_price_from_name

NAME = "iki"
LABEL = "Iki"
MIN_COUNT = 50
SEARCH = "https://searchservice-952707942140.europe-north1.run.app"
API = SEARCH + "/v1/frontend-products"
CATEGORIES_API = SEARCH + "/categories"
IKI_CHAIN_ID = "CvKfTzV4TN5U8BTMF1Hl"
PAGE_SIZE = 60
MAX_RESULTS = 2000  # the API never returns more than this per query, so we query per category
HEADERS = {"Origin": "https://www.lastmile.lt", "Referer": "https://www.lastmile.lt/"}


def _payload(offset, category_ids):
    return {
        "params": {
            "type": "view_products", "isActive": True, "isApproved": True,
            "filter": {"showOnlyPromoPrices": True}, "sort": "karma",
            "chainIds": [IKI_CHAIN_ID], "categoryIds": category_ids, "isUsingStock": True,
        },
        "limit": PAGE_SIZE, "fromIndex": offset,
    }


def _main_categories(client):
    content = client.post_json(CATEGORIES_API, {
        "params": {"type": "categories", "show": True, "chainIds": [IKI_CHAIN_ID]},
        "isUsingCache": True, "slim": None,
    }, headers=HEADERS)
    return [c["id"] for c in json.loads(content).get("data") or [] if c.get("parentId") == "0"]


def fetch(client):
    pages = []
    for c, category in enumerate(_main_categories(client), 1):
        offset = 0
        while offset < MAX_RESULTS:
            content = client.post_json(API, _payload(offset, [category]), headers=HEADERS)
            data = json.loads(content)
            if not data.get("products"):
                break
            pages.append(RawPage(f"cat{c:02d}_page_{offset // PAGE_SIZE + 1:03d}.json", content))
            offset += PAGE_SIZE
            if offset >= (data.get("count") or 0):
                break
    return pages


def _name(value):
    if isinstance(value, dict):
        return value.get("lt") or next(iter(value.values()), "")
    return value or ""


def parse(pages, today=None):
    products = {}
    for page in pages:
        for item in json.loads(page.content).get("products") or []:
            p = item.get("frontEndProduct") or {}
            prc = p.get("prc") or {}
            name = _name(p.get("name")).strip()
            regular = prc.get("p")
            if not name or not regular:
                continue
            sale, loyal = prc.get("s"), prc.get("l")
            price, card, valid_to = regular, None, None
            if sale and sale < price:
                price, valid_to = sale, prc.get("still")
            if loyal and loyal < price:
                price, card, valid_to = loyal, "IKI", prc.get("ltill")
            measure = (p.get("conversionMeasure") or "").upper()
            amount = p.get("conversionValue")
            unit_price, unit = None, None
            if measure in ("KG", "L") and amount:
                unit_price, unit = round(price / float(amount), 2), measure.lower()
            elif measure in ("PCS", "VNT") and amount:
                unit_price, unit = round(price / float(amount), 2), "vnt."
            if unit_price is None:
                unit_price, unit = unit_price_from_name(price, name)
            slug = (p.get("slugs") or [None])[0]
            pid = str(p.get("id") or p.get("productId"))
            products[pid] = Product(
                chain=NAME, source_id=pid, name=name, price=float(price),
                old_price=float(regular) if price < regular else None,
                unit_price=unit_price, unit=unit, card=card,
                promo=f"-{round((1 - price / regular) * 100)} %" if price < regular else None,
                valid_to=valid_to[:10] if valid_to else None,
                url=f"https://www.lastmile.lt/chain/IKI/product/{slug}" if slug else None,
            )
    return list(products.values())
