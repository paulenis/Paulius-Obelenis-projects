"""Common product model and parsing helpers shared by all chain adapters."""

import re
import unicodedata
from dataclasses import dataclass, asdict, field
from typing import Optional


@dataclass
class Product:
    chain: str
    source_id: str
    name: str
    price: float                      # price the shopper pays (card price if that is lower)
    old_price: Optional[float] = None  # regular price when the product is discounted
    unit_price: Optional[float] = None
    unit: Optional[str] = None         # 'kg', 'l' or 'vnt.'
    card: Optional[str] = None         # loyalty card needed for `price`, e.g. 'AČIŪ'
    promo: Optional[str] = None        # free text, e.g. '2 už 2,79 €' or '-30 %'
    valid_from: Optional[str] = None   # ISO date
    valid_to: Optional[str] = None     # ISO date
    url: Optional[str] = None
    category: Optional[str] = None
    extra: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


@dataclass
class RawPage:
    name: str      # file name inside the run's raw folder, e.g. 'page_003.json'
    content: str


_PRICE_RE = re.compile(r"(\d+(?:[.,]\d+)?)")


def parse_price(text) -> Optional[float]:
    """'1,49 €' -> 1.49, '0.72 € už kg' -> 0.72; None when no number is present."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    m = _PRICE_RE.search(text.replace("\xa0", " "))
    return float(m.group(1).replace(",", ".")) if m else None


_UNIT_ALIASES = {
    "kg": ("kg", 1.0), "g": ("kg", 0.001), "gr": ("kg", 0.001),
    "l": ("l", 1.0), "ltr": ("l", 1.0), "ml": ("l", 0.001), "cl": ("l", 0.01),
    "vnt": ("vnt.", 1.0), "vnt.": ("vnt.", 1.0), "pcs": ("vnt.", 1.0),
}

_NUM = r"(\d+(?:[.,]\d+)?)"
# '2 x 100 g', '3 vnt. × 40 g', '2 ind. × 175 g'
_MULTI_RE = re.compile(_NUM + r"\s*(?:vnt\.?|ind\.?|pak\.?)?\s*[x×]\s*" + _NUM + r"\s*(kg|g|gr|ml|cl|l)\b", re.I)
_SINGLE_RE = re.compile(_NUM + r"\s*(kg|g|gr|ml|cl|ltr|l|vnt\.?)(?![a-ząčęėįšųūž])", re.I)


def parse_quantity(text):
    """Find the package size in a product name.

    Returns (amount, unit) in base units ('kg', 'l', 'vnt.') or None.
    Ranges like '0,75–1,5 kg' are ambiguous and return None.
    """
    if not text:
        return None
    t = text.replace("\xa0", " ")
    if re.search(_NUM + r"\s*[–-]\s*" + _NUM + r"\s*(kg|g|ml|l)\b", t, re.I):
        return None
    m = _MULTI_RE.search(t)
    if m:
        count = float(m.group(1).replace(",", "."))
        size = float(m.group(2).replace(",", "."))
        unit, factor = _UNIT_ALIASES[m.group(3).lower()]
        return round(count * size * factor, 6), unit
    found = _SINGLE_RE.findall(t)
    if not found:
        return None
    # The last match is usually the package size ('PILOS Sviestas 82 %, 200 g').
    num, u = found[-1]
    unit, factor = _UNIT_ALIASES[u.lower()]
    amount = float(num.replace(",", ".")) * factor
    return (round(amount, 6), unit) if amount > 0 else None


def unit_price_from_name(price, name):
    """Compute (unit_price, unit) from the package size in the name, or (None, None)."""
    q = parse_quantity(name)
    if not q or price is None:
        return None, None
    amount, unit = q
    return round(price / amount, 2), unit


_UNIT_PRICE_RE = re.compile(r"(?:1\s*(kg|l|vnt\.?)\s*[=–-]\s*" + _NUM + r")|(?:" + _NUM + r"\s*€?\s*/\s*(kg|l|vnt\.?))", re.I)


def parse_unit_price(text):
    """'1 kg = 5,98 €' or '0,72 €/kg' or '1 kg – 2,49 €' -> (5.98, 'kg'); None if absent."""
    if not text:
        return None
    m = _UNIT_PRICE_RE.search(text.replace("\xa0", " "))
    if not m:
        return None
    if m.group(1):
        unit, value = m.group(1), m.group(2)
    else:
        value, unit = m.group(3), m.group(4)
    unit = unit.lower()
    unit = "vnt." if unit.startswith("vnt") else unit
    return float(value.replace(",", ".")), unit


def normalize(text):
    """Lower-case and strip Lithuanian diacritics so 'sūris' matches 'suris'."""
    t = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in t if not unicodedata.combining(c)).lower()
