"""Rimi: promotions from the e-shop list (server-rendered HTML product cards)."""

import re

from ..models import Product, RawPage, parse_price, parse_unit_price, unit_price_from_name

NAME = "rimi"
LABEL = "Rimi"
MIN_COUNT = 50
BASE = "https://www.rimi.lt"
LIST_URL = BASE + "/e-parduotuve/lt/akcijos?currentPage={page}&pageSize=80"
MAX_PAGES = 80
_CARD_SPLIT = 'class="product-grid__item"'


def _text(fragment):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment or "")).strip()


def fetch(client):
    pages, seen = [], set()
    for n in range(1, MAX_PAGES + 1):
        content = client.get(LIST_URL.format(page=n))
        codes = set(re.findall(r'data-product-code="(\d+)"', content))
        if not codes or codes <= seen:
            break
        seen |= codes
        pages.append(RawPage(f"page_{n:03d}.html", content))
    return pages


def _search(pattern, text):
    m = re.search(pattern, text, re.S)
    return m.group(1) if m else None


def parse(pages, today=None):
    products = {}
    for page in pages:
        for card in page.content.split(_CARD_SPLIT)[1:]:
            code = _search(r'data-product-code="(\d+)"', card)
            name = _text(_search(r'<p class="card__name">(.*?)</p>', card))
            # Regular shelf price, e.g. "0.72 € už kg" (the gtm JSON price is unreliable).
            regular = parse_price(_search(r'class="price-tag card__price">\s*<span class="sr-only">(.*?)</span>', card))
            if not code or not name or regular is None:
                continue
            per = parse_unit_price(_text(_search(r'class="card__price-per">(.*?)</p>', card)))
            old = parse_price(_search(r"Įprasta kaina:\s*([\d.,]+)", card))
            price, card_name, promo = regular, None, None
            label = _search(r'class="price-label__body">(.*?)</div>\s*</div>\s*</div>', card)
            if label:
                major = _search(r'class="major">(\d+)<', label)
                cents = _search(r'class="cents">(\d+)<', label)
                if major is not None and cents is not None:
                    label_price = float(f"{major}.{cents}")
                    if label_price < regular:
                        old, price = regular, label_price
                        card_name = "Mano Rimi" if "rimi-card" in label else None
                        per = parse_unit_price(_text(_search(r'class="price-per-unit">(.*?)</div>', label))) or (
                            (round(per[0] * price / regular, 2), per[1]) if per else None)
            if old and old > price and not promo:
                promo = f"-{round((1 - price / old) * 100)} %"
            unit_price, unit = per if per else unit_price_from_name(price, name)
            href = _search(r'class="card__url[^"]*" href="([^"]+)"', card)
            products[code] = Product(
                chain=NAME, source_id=code, name=name, price=price,
                old_price=old if old and old > price else None,
                unit_price=unit_price, unit=unit, card=card_name, promo=promo,
                url=BASE + href if href else None,
            )
    return list(products.values())
