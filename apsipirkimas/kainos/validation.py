"""Checks a collection result before it may replace the last good data."""

MIN_SHARE_OF_PREVIOUS = 0.5   # at least half as many products as last good run
MIN_PRICED_SHARE = 0.9        # nearly every product has a sensible price
MIN_PRICE, MAX_PRICE = 0.01, 2000.0


def check(products, min_count, previous_count=None):
    """Return a list of problems (Lithuanian, shown in the app); empty means OK."""
    problems = []
    count = len(products)
    if count < min_count:
        problems.append(f"per mažai prekių: {count} (tikėtasi bent {min_count})")
    if previous_count and count < previous_count * MIN_SHARE_OF_PREVIOUS:
        problems.append(f"prekių sumažėjo nuo {previous_count} iki {count}")
    if count:
        good = sum(1 for p in products
                   if p.name and p.price is not None and MIN_PRICE <= p.price <= MAX_PRICE)
        if good / count < MIN_PRICED_SHARE:
            problems.append(f"tik {good} iš {count} prekių turi tinkamą pavadinimą ir kainą")
        absurd = [p for p in products if p.unit_price is not None and p.unit_price > 5000]
        if len(absurd) > count * 0.05:
            problems.append(f"{len(absurd)} prekių kaina už vienetą neįtikėtina")
    return problems
