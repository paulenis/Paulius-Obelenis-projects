"""Each chain parser against a small saved sample of the real page (October 2026).

When a store changes its site, save the new raw page from data/raw/<chain>/ as the
fixture, fix the parser until these pass again, and update the expected values.
"""

import unittest
from datetime import date
from pathlib import Path

from kainos.chains import iki, lidl, maxima, norfa, rimi
from kainos.models import RawPage

FIXTURES = Path(__file__).parent / "fixtures"
TODAY = date(2026, 10, 29)


def parse(module, filename):
    page = RawPage(filename, (FIXTURES / filename).read_text(encoding="utf-8"))
    return {p.name: p for p in module.parse([page], today=TODAY)}


class LidlTest(unittest.TestCase):
    def setUp(self):
        self.products = parse(lidl, "lidl.html")

    def test_regular_offer_with_base_price(self):
        p = self.products["PILOS Sviestas 82 %, 200 g"]
        self.assertEqual((p.price, p.unit_price, p.unit), (0.99, 4.95, "kg"))
        self.assertEqual((p.valid_from, p.valid_to), ("2026-10-29", "2026-11-01"))

    def test_lidl_plus_price_is_marked_as_card_price(self):
        p = self.products["Moliūgai Halloween"]
        self.assertEqual((p.price, p.card), (0.49, "Lidl Plus"))

    def test_ended_offer_picks_the_next_date_range(self):
        p = self.products["Šviežia kalakutų šlaunelių mėsa, 1 kg"]
        self.assertEqual((p.price, p.old_price, p.promo), (5.99, 6.99, "-14 %"))
        self.assertEqual(p.valid_from, "2026-10-31")


class MaximaTest(unittest.TestCase):
    def setUp(self):
        self.products = parse(maxima, "maxima.html")

    def test_card_price(self):
        p = self.products["Žaliosios cukinijos, 1 kg"]
        self.assertEqual((p.price, p.old_price, p.card, p.unit_price, p.unit), (1.55, 1.75, "AČIŪ", 1.55, "kg"))

    def test_x_for_y_promotion(self):
        p = self.products["GRŪDĖTA varškė, 7% rieb., 200 g"]
        self.assertEqual((p.price, p.promo, p.unit_price), (1.59, "2 už 2,79 €", 7.95))


class RimiTest(unittest.TestCase):
    def setUp(self):
        self.products = parse(rimi, "rimi.html")

    def test_card_label_price_beats_shelf_price(self):
        p = self.products["Plautos morkos, kg"]
        self.assertEqual((p.price, p.old_price, p.card, p.unit_price), (0.55, 0.72, "Mano Rimi", 0.55))

    def test_plain_discount(self):
        p = self.products["Sūris RIMI MOZZARELLA, 45% rieb., 125g"]
        self.assertEqual((p.price, p.old_price, p.card, p.unit_price), (0.79, 0.85, None, 6.32))


class NorfaTest(unittest.TestCase):
    def setUp(self):
        self.products = parse(norfa, "norfa.html")

    def test_only_current_priced_offers_are_kept(self):
        self.assertEqual(len(self.products), 1)

    def test_fields_and_unit_price_from_name(self):
        p = next(iter(self.products.values()))
        self.assertEqual((p.price, p.old_price, p.unit_price, p.unit), (1.79, 2.69, 11.55, "kg"))
        self.assertEqual((p.valid_from, p.valid_to), ("2026-10-29", "2026-11-11"))


class IkiTest(unittest.TestCase):
    def setUp(self):
        self.products = parse(iki, "iki.json")

    def test_loyalty_price_and_dates(self):
        p = self.products["Sviestas ŠEIMININKĖS, 82% rieb., 200 g"]
        self.assertEqual((p.price, p.old_price, p.card, p.unit_price, p.valid_to), (1.49, 2.99, "IKI", 7.45, "2026-11-01"))


if __name__ == "__main__":
    unittest.main()
