"""Recognize and value factory extras for facelift Škoda Scala offers."""

from __future__ import annotations

import datetime as dt
import html
import re
import unicodedata


def searchable(value: str | None) -> str:
    value = html.unescape(re.sub(r"<[^>]+>", " ", value or ""))
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^a-zA-Z0-9]+", " ", value).casefold().split())


def has_alias(haystack: str, aliases: list[str]) -> bool:
    return any(searchable(alias) in haystack for alias in aliases)


def rounded_thousand(value: float) -> int:
    return int(round(value / 1000) * 1000)


def add_catalog_items(items: list[dict], catalog_items: list[dict], trim: str, note_text: str, equipment_text: str) -> None:
    for entry in catalog_items:
        price = (entry.get("prices") or {}).get(trim)
        if not price:
            continue
        aliases = entry.get("aliases") or []
        found_in_note = has_alias(note_text, aliases)
        found_in_equipment = has_alias(equipment_text, aliases)
        if not found_in_note and not found_in_equipment:
            continue
        items.append({
            "id": entry["id"],
            "label": entry["label"],
            "catalogPrice": int(price),
            "resaleShare": float(entry.get("resaleShare", 0.3)),
            "confidence": "high" if found_in_note else "medium",
        })


def remove_superseded(items: list[dict], catalog: dict) -> list[dict]:
    entries = (catalog.get("packages") or []) + (catalog.get("standalone") or [])
    superseded = {
        item_id
        for item in items
        for entry in entries
        if entry.get("id") == item["id"]
        for item_id in entry.get("supersedes", [])
    }
    return [item for item in items if item["id"] not in superseded]


def paint_item(node: dict, catalog: dict) -> dict | None:
    paint_type = node.get("paintType") or ""
    paint = (catalog.get("paint") or {}).get(paint_type)
    if not paint:
        return None
    color_name = (node.get("color") or {}).get("value") or ""
    override = (paint.get("overrides") or {}).get(searchable(color_name), {})
    price = int(override.get("price", paint.get("defaultPrice", 0)))
    if price <= 0:
        return None
    return {
        "id": "paint",
        "label": override.get("label") or f"{paint['defaultLabel']} ({color_name})",
        "catalogPrice": price,
        "resaleShare": float(paint.get("resaleShare", 0.15)),
        "confidence": "medium",
    }


def wheel_item(catalog: dict, trim: str, note_text: str, equipment_text: str) -> dict | None:
    for wheel in catalog.get("wheels") or []:
        price = (wheel.get("prices") or {}).get(trim)
        if price and has_alias(note_text, wheel.get("aliases") or []):
            return {
                "id": f"wheel-{wheel['id']}",
                "label": wheel["label"],
                "catalogPrice": int(price),
                "resaleShare": float(wheel.get("resaleShare", 0.3)),
                "confidence": "high",
            }
    fallback = catalog.get("wheelFallback") or {}
    if trim == fallback.get("trim") and has_alias(equipment_text, [fallback.get("equipmentAlias", "")]):
        return {
            "id": "wheel-fallback",
            "label": fallback["label"],
            "catalogPrice": int(fallback["price"]),
            "resaleShare": float(fallback.get("resaleShare", 0.3)),
            "confidence": "low",
        }
    return None


def estimate_equipment_value(node: dict, offer: dict, catalog: dict) -> dict | None:
    year = int(node.get("manufactureYear") or offer.get("year") or 0)
    if offer.get("make") != catalog.get("make") or offer.get("model") != catalog.get("model"):
        return None
    if year < int(catalog.get("appliesFromYear", 9999)):
        return None
    trim = offer.get("trim") or ""
    note_text = searchable(node.get("note"))
    if "130 let" in note_text or searchable(trim) == "drive":
        # The March 2024 reference list does not define these later bundles.
        return None
    equipment_text = searchable(" | ".join(offer.get("equipment") or []))
    items: list[dict] = []
    add_catalog_items(items, catalog.get("packages") or [], trim, note_text, "")
    add_catalog_items(items, catalog.get("standalone") or [], trim, note_text, equipment_text)
    items = remove_superseded(items, catalog)
    paint = paint_item(node, catalog)
    if paint:
        items.append(paint)
    wheels = wheel_item(catalog, trim, note_text, equipment_text)
    if wheels:
        items.append(wheels)
    if not items:
        return None

    catalog_total = sum(item["catalogPrice"] for item in items)
    age = max(0, dt.date.today().year - year)
    age_modifier = 1.25 if age == 0 else 1.12 if age == 1 else 1.0 if age == 2 else max(0.65, 1 - (age - 2) * 0.12)
    used_total = rounded_thousand(sum(item["catalogPrice"] * item["resaleShare"] * age_modifier for item in items))
    confidence_values = {item["confidence"] for item in items}
    confidence = "low" if "low" in confidence_values else "medium"
    source = catalog.get("source") or {}
    return {
        "catalogPrice": catalog_total,
        "estimatedUsedContribution": used_total,
        "referenceYear": 2024,
        "vehicleModelYear": year,
        "confidence": confidence,
        "items": [{key: value for key, value in item.items() if key != "resaleShare"} for item in items],
        "sourceTitle": source.get("title"),
        "sourceUrl": source.get("url"),
        "priceBasis": catalog.get("priceBasis"),
        "method": "Katalogová cena rozpoznaných příplatků; zůstatková hodnota je orientační koeficient podle typu výbavy a stáří.",
    }
