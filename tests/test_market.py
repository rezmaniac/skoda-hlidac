import importlib.util
import pathlib
import unittest


MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "scraper" / "update.py"
SPEC = importlib.util.spec_from_file_location("skoda_update", MODULE_PATH)
UPDATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UPDATE)


def offer(**overrides):
    value = {
        "id": "target",
        "make": "Škoda",
        "model": "Scala",
        "trim": "Style",
        "fuel": "Benzín",
        "transmission": "Manuál",
        "powerKw": 81,
        "year": 2022,
        "mileage": 80_000,
        "price": 350_000,
    }
    value.update(overrides)
    return value


class MarketBenchmarkTests(unittest.TestCase):
    def test_median_uses_only_matching_trim_and_drivetrain(self):
        catalog = [
            offer(id=f"match-{index}", price=price, mileage=80_000 + index * 1_000)
            for index, price in enumerate([300_000, 320_000, 340_000, 360_000, 500_000])
        ]
        catalog.extend([
            offer(id="wrong-trim", trim="Ambition", price=100_000),
            offer(id="wrong-transmission", transmission="Automat", price=100_000),
        ])

        local = offer()
        self.assertEqual(UPDATE.attach_market_benchmarks([local], catalog), 1)
        self.assertEqual(local["market"]["typicalPrice"], 340_000)
        self.assertEqual(local["market"]["sampleSize"], 5)
        self.assertEqual(local["market"]["confidence"], "low")

    def test_small_sample_does_not_create_estimate(self):
        catalog = [offer(id=f"match-{index}") for index in range(4)]
        local = offer()

        self.assertEqual(UPDATE.attach_market_benchmarks([local], catalog), 0)
        self.assertIsNone(local["market"])

    def test_api_fuel_and_dsg_values_are_normalized(self):
        node = {
            "fuel": {"id": "fuel_type_2", "value": "Diesel"},
            "transmission": {"id": "transmission_5", "value": "DSG"},
        }

        self.assertEqual(UPDATE.infer_fuel(node), "Nafta")
        self.assertEqual(UPDATE.transmission_name(node), "Automat")


if __name__ == "__main__":
    unittest.main()
