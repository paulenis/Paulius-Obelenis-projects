"""One module per chain. Each exposes NAME, LABEL, MIN_COUNT, fetch(client) and parse(pages, today)."""

from . import iki, lidl, maxima, norfa, rimi

ALL = [lidl, maxima, iki, rimi, norfa]
BY_NAME = {m.NAME: m for m in ALL}
