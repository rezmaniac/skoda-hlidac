import importlib.util
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scraper" / "equipment_value.py"
SPEC = importlib.util.spec_from_file_location("equipment_value", MODULE_PATH)
VALUE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALUE)
CATALOG = json.loads((ROOT / "config" / "scala-equipment-catalog.json").read_text(encoding="utf-8"))


def offer(**overrides):
    value = {
        "make": "Škoda",
        "model": "Scala",
        "trim": "Selection",
        "year": 2024,
        "equipment": [],
    }
    value.update(overrides)
    return value


class EquipmentValueTests(unittest.TestCase):
    def test_values_packages_paint_wheels_and_spare_without_double_counting(self):
        node = {
            "manufactureYear": 2024,
            "paintType": "METALLIC",
            "color": {"value": "červená"},
            "note": "Exteriér plus, Interiér plus, Rezervní kolo, Bezpečnostní šrouby kol",
        }
        result = VALUE.estimate_equipment_value(node, offer(equipment=["ALU kola"]), CATALOG)
        self.assertEqual(result["catalogPrice"], 67_600)
        self.assertEqual({item["id"] for item in result["items"]}, {
            "exterior-plus", "interior-plus", "spare-wheel", "wheel-bolts", "paint", "wheel-fallback"
        })

    def test_city_premium_supersedes_city_plus(self):
        node = {"manufactureYear": 2024, "note": "City plus, City premium"}
        result = VALUE.estimate_equipment_value(node, offer(trim="Top Selection"), CATALOG)
        self.assertEqual(result["catalogPrice"], 40_000)
        self.assertEqual([item["id"] for item in result["items"]], ["city-premium"])

    def test_ignores_older_or_other_models(self):
        self.assertIsNone(VALUE.estimate_equipment_value({}, offer(year=2023), CATALOG))
        self.assertIsNone(VALUE.estimate_equipment_value(
            {"manufactureYear": 2024}, offer(model="Kamiq"), CATALOG
        ))

    def test_ignores_special_editions_missing_from_reference_price_list(self):
        self.assertIsNone(VALUE.estimate_equipment_value(
            {"manufactureYear": 2025, "note": "Akční model 130 let, metalíza"},
            offer(year=2025),
            CATALOG,
        ))


if __name__ == "__main__":
    unittest.main()
