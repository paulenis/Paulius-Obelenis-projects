import tempfile
import unittest
from pathlib import Path

from kainos import storage, validation
from kainos.models import Product, normalize, parse_price, parse_quantity, parse_unit_price, unit_price_from_name


class ParsingTest(unittest.TestCase):
    def test_price(self):
        self.assertEqual(parse_price("1,49 €"), 1.49)
        self.assertEqual(parse_price("0.72 € už kg"), 0.72)
        self.assertIsNone(parse_price("nėra"))

    def test_quantity(self):
        self.assertEqual(parse_quantity("PILOS Sviestas 82 %, 200 g"), (0.2, "kg"))
        self.assertEqual(parse_quantity("Vanduo AKVILĖ, 1,5 l"), (1.5, "l"))
        self.assertEqual(parse_quantity("COMBINO makaronai, 2 x 100 g"), (0.2, "kg"))
        self.assertEqual(parse_quantity("VILVI sūrelis, 3 vnt. × 40 g"), (0.12, "kg"))
        self.assertEqual(parse_quantity("Tualetinis popierius, 24 vnt."), (24.0, "vnt."))
        self.assertIsNone(parse_quantity("PURINA ONE ėdalas, 0,75–1,5 kg"))
        self.assertIsNone(parse_quantity("Mandarinai"))

    def test_unit_price(self):
        self.assertEqual(unit_price_from_name(1.99, "Kepti vištienos kukuliai, 800 g"), (2.49, "kg"))
        self.assertEqual(parse_unit_price("1 kg = 5,98 €"), (5.98, "kg"))
        self.assertEqual(parse_unit_price("0,33 €/l"), (0.33, "l"))
        self.assertEqual(parse_unit_price("1 kg – 2,49 €"), (2.49, "kg"))

    def test_normalize(self):
        self.assertEqual(normalize("Sūris ŽEMAITIJOS"), "suris zemaitijos")


def product(i, price=1.0):
    return Product(chain="test", source_id=str(i), name=f"Prekė {i}", price=price)


class ValidationTest(unittest.TestCase):
    def test_good_data_passes(self):
        self.assertEqual(validation.check([product(i) for i in range(60)], min_count=50), [])

    def test_too_few_products(self):
        self.assertTrue(validation.check([product(1)], min_count=50))

    def test_big_drop_from_previous_run(self):
        self.assertTrue(validation.check([product(i) for i in range(60)], min_count=50, previous_count=500))

    def test_missing_prices(self):
        items = [product(i) for i in range(50)] + [product(i, price=0) for i in range(50, 60)]
        self.assertTrue(validation.check(items, min_count=10))


class ListSyncTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = storage.connect(Path(self.tmp.name) / "test.db")

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_last_write_wins(self):
        storage.merge_list_items(self.conn, [{"id": "a", "name": "Pienas", "qty": 1, "updated_at": 100}])
        storage.merge_list_items(self.conn, [{"id": "a", "name": "Pienas", "qty": 3, "updated_at": 300}])
        storage.merge_list_items(self.conn, [{"id": "a", "name": "Pienas", "qty": 2, "updated_at": 200}])  # older, ignored
        (item,) = storage.list_items(self.conn)
        self.assertEqual(item["qty"], 3)


class SearchTest(unittest.TestCase):
    def test_search_uses_only_last_good_run_and_ignores_diacritics(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = storage.connect(Path(tmp) / "test.db")
            old = storage.start_run(conn, "test", "2026-10-20", "x")
            storage.save_products(conn, old, [Product("test", "1", "Sūris senas", 5.0)])
            storage.finish_run(conn, old, "ok", "2026-10-20", 1)
            new = storage.start_run(conn, "test", "2026-10-29", "x")
            storage.save_products(conn, new, [Product("test", "2", "Sūris GOUDA", 4.0, unit_price=8.0, unit="kg")])
            storage.finish_run(conn, new, "ok", "2026-10-29", 1)
            rejected = storage.start_run(conn, "test", "2026-10-30", "x")
            storage.finish_run(conn, rejected, "rejected", "2026-10-30", 0, "per mažai prekių")
            results = storage.search(conn, "suris")
            self.assertEqual([r["name"] for r in results], ["Sūris GOUDA"])
            conn.close()


class FakeChain:
    """Stands in for a chain module; `behaviour` decides what fetch/parse return."""
    NAME, LABEL, MIN_COUNT = "fake", "Fake", 3

    def __init__(self, behaviour):
        self.behaviour = behaviour

    def fetch(self, client):
        if self.behaviour == "crash":
            raise RuntimeError("svetainė pasikeitė")
        return []

    def parse(self, pages, today=None):
        return [] if self.behaviour == "empty" else [product(i) for i in range(5)]


class CollectResilienceTest(unittest.TestCase):
    def test_broken_site_keeps_last_good_data(self):
        from kainos import collect
        with tempfile.TemporaryDirectory() as tmp:
            conn = storage.connect(Path(tmp) / "test.db")
            raw = Path(tmp) / "raw"
            original = collect.RAW_DIR
            collect.RAW_DIR = raw
            try:
                quiet = lambda *_: None
                self.assertEqual(collect.collect_chain(conn, FakeChain("ok"), client=object(), log=quiet), "ok")
                self.assertEqual(collect.collect_chain(conn, FakeChain("empty"), client=object(), log=quiet), "rejected")
                self.assertEqual(collect.collect_chain(conn, FakeChain("crash"), client=object(), log=quiet), "failed")
            finally:
                collect.RAW_DIR = original
            self.assertEqual(len(storage.search(conn, "preke")), 5)  # still the first, good run
            self.assertEqual(storage.last_run(conn, "fake")["status"], "failed")
            conn.close()


if __name__ == "__main__":
    unittest.main()
