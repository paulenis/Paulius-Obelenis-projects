"""Norfa: 'praktiški pasiūlymai' – one HTML page with every current offer."""

import re
from datetime import date

from ..models import Product, RawPage, parse_price, unit_price_from_name

NAME = "norfa"
LABEL = "Norfa"
MIN_COUNT = 50
URL = "https://www.norfa.lt/akciju-puslapiai/praktiski-pasiulymai/"
_CARD_SPLIT = 'class="c-product c-product--compact"'
_VALID_RE = re.compile(r"Galioja\s+(\d{2})\.(\d{2})\s*-\s*(\d{2})\.(\d{2})")


def _text(fragment):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment or "")).strip()


def _search(pattern, text):
    m = re.search(pattern, text, re.S)
    return m.group(1) if m else None


def fetch(client):
    return [RawPage("page_001.html", client.get(URL))]


def _dates(info, today):
    """'Galioja 10.29-11.11 d.' has no year: pick the year that puts it nearest today."""
    m = _VALID_RE.search(info)
    if not m:
        return None, None
    m1, d1, m2, d2 = (int(x) for x in m.groups())
    year = today.year
    if m1 == 12 and today.month == 1:
        year -= 1
    elif m1 == 1 and today.month == 12:
        year += 1
    start = date(year, m1, d1)
    end = date(year + (1 if m2 < m1 else 0), m2, d2)
    return start, end


def parse(pages, today=None):
    today = today or date.today()
    products = {}
    for page in pages:
        for card in page.content.split(_CARD_SPLIT)[1:]:
            name = _text(_search(r'class="c-product__name">(.*?)</div>', card))
            price = parse_price(_text(_search(r'class="c-product__price">(.*?)</div>', card)))
            info = _text(_search(r'class="c-more-info__content">(.*?)</div>', card))
            start, end = _dates(info, today)
            if not name or price is None:
                continue  # '-40 % guašui' style offers have no price to compare
            if end and end < today:
                continue  # the page also lists the previous period
            old = parse_price(_text(_search(r'class="c-product__old-price">(.*?)</div>', card)))
            discount = _text(_search(r'class="c-product__discount">(.*?)</div>', card))
            unit_price, unit = unit_price_from_name(price, name)
            note = re.sub(r"\s*Galioja.*$", "", info).strip() or None
            key = f"{name}|{start}"
            products[key] = Product(
                chain=NAME, source_id=key, name=name, price=price,
                old_price=old if old and old > price else None,
                unit_price=unit_price, unit=unit, promo=discount or None,
                valid_from=start.isoformat() if start else None,
                valid_to=end.isoformat() if end else None,
                url=URL, extra={"note": note} if note else {},
            )
    return list(products.values())
