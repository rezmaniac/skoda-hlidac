#!/usr/bin/env python3
"""Download offers, compare them with the previous snapshot and notify Telegram."""

from __future__ import annotations

import datetime as dt
import html
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "latest.json"
CONFIG_PATH = ROOT / "config" / "filters.json"
GRAPHQL_URL = "https://www.skodaplus.cz/graphql"
SITE_URL = "https://www.skodaplus.cz"
PAGE_SIZE = 100

QUERY = """
query Cars($filter: CarFilterInput, $first: Int, $after: String, $lang: Lang!) {
  carsCount(filter: $filter)
  cars(first: $first, after: $after, filter: $filter) {
    edges {
      node {
        id
        model { modelName carMake { name } }
        modelType
        mileage
        firstRegistration
        dealer { id name address { city } }
        price { value exclusiveOfVat }
        enginePower
        engineCapacity
        motorType { value(lang: $lang) }
        transmission { id }
        equipmentLevel { value }
        prettyUrl
        images(limit: 1) { thumbnailUrl }
      }
    }
    pageInfo { endCursor hasNextPage }
  }
}
"""

COLORS = ["#276b63", "#355b82", "#7b5148", "#707d75", "#9a3942", "#b8b2a8"]


def load_json(path: pathlib.Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return fallback


def graphql_request(dealer_ids: list[str], after: str | None = None) -> dict:
    car_filter = {
        "dealers": dealer_ids,
        "regionCountry": "CZ",
        "carsOrderBy": "FIRST_REGISTRATION_DESC",
        "skodaPlus": True,
        "oneYearCar": True,
        "usedCar": True,
        "demoCarTypes": ["EMPTY", "FOR_SALE", "ON_REQUEST"],
    }
    body = json.dumps({
        "query": QUERY,
        "variables": {
            "filter": car_filter,
            "first": PAGE_SIZE,
            "after": after,
            "lang": "CS",
        },
    }).encode("utf-8")
    request = urllib.request.Request(
        GRAPHQL_URL,
        data=body,
        headers={
            "content-type": "application/json",
            "accept": "application/json",
            "user-agent": "SkodaHlidac/1.0 (+GitHub Actions; daily public-offer check)",
        },
        method="POST",
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                payload = json.load(response)
            if payload.get("errors"):
                raise RuntimeError(f"GraphQL error: {payload['errors'][0].get('message', 'unknown')}")
            return payload["data"]
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == 2:
                raise RuntimeError(f"Škoda Plus request failed: {exc}") from exc
            time.sleep(2 ** attempt)
    raise RuntimeError("Škoda Plus request failed")


def fetch_all(dealer_ids: list[str]) -> list[dict]:
    nodes: list[dict] = []
    after = None
    expected_count = None
    while True:
        result = graphql_request(dealer_ids, after)
        page = result["cars"]
        expected_count = int(result["carsCount"])
        nodes.extend(edge["node"] for edge in page.get("edges", []))
        info = page.get("pageInfo") or {}
        if not info.get("hasNextPage"):
            unique = {node["id"]: node for node in nodes}
            if len(unique) != len(nodes):
                raise RuntimeError(f"Pagination returned {len(nodes) - len(unique)} duplicate offers")
            if len(nodes) != expected_count:
                raise RuntimeError(f"Expected {expected_count} offers, downloaded {len(nodes)}")
            return nodes
        after = info.get("endCursor")
        if not after:
            raise RuntimeError("Pagination did not provide an end cursor")


def infer_fuel(node: dict) -> str:
    text = f"{node.get('modelType', '')} {(node.get('motorType') or {}).get('value', '')}".lower()
    if any(value in text for value in ("electric", "elektro", "kwh", "iv 80", "iv 60")):
        return "Elektřina"
    if "phev" in text or "hybrid" in text or "i-v" in text:
        return "Hybrid"
    if "tdi" in text or "diesel" in text:
        return "Nafta"
    if "cng" in text:
        return "CNG"
    return "Benzín"


def transmission_name(node: dict) -> str:
    transmission_id = (node.get("transmission") or {}).get("id", "")
    return "Automat" if transmission_id == "transmission_2" else "Manuál"


def normalize(node: dict, dealer_cities: dict[str, str], previous: dict[str, dict], baseline: bool, now: str) -> dict:
    raw_id = node["id"]
    car_id = raw_id.replace("Car-", "")
    old = previous.get(car_id)
    price = int((node.get("price") or {}).get("value") or 0)
    old_price = int(old.get("price", price)) if old else price
    registration = node.get("firstRegistration") or ""
    model = node.get("model") or {}
    trim = (node.get("equipmentLevel") or {}).get("value") or ""
    images = node.get("images") or []
    image_path = images[0].get("thumbnailUrl") if images else None
    pretty_url = node.get("prettyUrl") or ""
    dealer = node.get("dealer") or {}
    first_seen = old.get("firstSeen") if old else now
    return {
        "id": car_id,
        "make": (model.get("carMake") or {}).get("name") or "",
        "model": model.get("modelName") or "",
        "trim": trim,
        "engine": node.get("modelType") or "",
        "powerKw": int(node.get("enginePower") or 0),
        "fuel": infer_fuel(node),
        "transmission": transmission_name(node),
        "year": int(registration[:4]) if registration[:4].isdigit() else 0,
        "mileage": int(node.get("mileage") or 0),
        "price": price,
        "previousPrice": old_price,
        "dealer": dealer.get("name") or "",
        "dealerId": dealer.get("id") or "",
        "city": dealer_cities.get(dealer.get("id"), (dealer.get("address") or {}).get("city") or ""),
        "firstSeen": first_seen,
        "isNew": bool(old is None and not baseline),
        "color": COLORS[sum(ord(char) for char in car_id) % len(COLORS)],
        "imageUrl": f"{SITE_URL}{image_path}" if image_path else None,
        "url": f"{SITE_URL}/Car/{car_id}/{pretty_url}",
    }


def matches_notification_filter(offer: dict, filters: dict) -> bool:
    models = filters.get("models") or []
    excluded_models = filters.get("excludeModels") or []
    fuels = filters.get("fuels") or []
    return (
        (not models or offer["model"] in models)
        and offer["model"] not in excluded_models
        and (not fuels or offer["fuel"] in fuels)
        and (filters.get("maxPrice") is None or offer["price"] <= filters["maxPrice"])
        and (filters.get("maxMileage") is None or offer["mileage"] <= filters["maxMileage"])
        and (filters.get("minYear") is None or offer["year"] >= filters["minYear"])
    )


def money(value: int) -> str:
    return f"{value:,}".replace(",", " ") + " Kč"


def build_message(new_offers: list[dict], discounts: list[dict]) -> str:
    lines = ["🚗 <b>Hlídač vozů našel změny</b>", ""]
    changes = [("NOVINKA", offer) for offer in new_offers] + [("ZLEVNĚNO", offer) for offer in discounts]
    for label, offer in changes[:10]:
        title = " ".join(part for part in (offer["make"], offer["model"], offer["trim"]) if part)
        lines.extend([
            f"<b>{label} · {html.escape(offer['city'])}</b>",
            html.escape(title),
            f"{offer['year']} · {offer['mileage']:,} km · <b>{money(offer['price'])}</b>".replace(",", " "),
            f"<a href=\"{html.escape(offer['url'], quote=True)}\">Otevřít nabídku</a>",
            "",
        ])
    remaining = len(changes) - 10
    if remaining > 0:
        lines.append(f"…a dalších {remaining} změn na webu.")
    return "\n".join(lines).strip()


def send_telegram(message: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram secrets are not configured; notification skipped.")
        return False
    body = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=body,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)
    if not result.get("ok"):
        raise RuntimeError("Telegram rejected the notification")
    print("Telegram notification sent.")
    return True


def main() -> int:
    config = load_json(CONFIG_PATH, {})
    dealers = config.get("dealers") or []
    if not dealers:
        raise RuntimeError("No dealers configured")
    previous_snapshot = load_json(DATA_PATH, {})
    previous_offers = {offer["id"]: offer for offer in previous_snapshot.get("offers", [])}
    baseline = (
        not previous_offers
        or bool(previous_snapshot.get("demo"))
        or previous_snapshot.get("schemaVersion") != 2
    )
    now = dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")
    dealer_ids = [dealer["id"] for dealer in dealers]
    dealer_cities = {dealer["id"]: dealer["city"] for dealer in dealers}
    raw_offers = fetch_all(dealer_ids)
    offers = [normalize(node, dealer_cities, previous_offers, baseline, now) for node in raw_offers]
    offers.sort(key=lambda offer: (offer["city"], offer["dealer"], offer["model"], offer["price"]))
    current_ids = {offer["id"] for offer in offers}
    removed_ids = sorted(set(previous_offers) - current_ids) if not baseline else []
    filters = config.get("notifications") or {}
    new_offers = [offer for offer in offers if offer["isNew"] and matches_notification_filter(offer, filters)]
    discounts = [
        offer for offer in offers
        if offer["previousPrice"] > offer["price"] and matches_notification_filter(offer, filters)
    ]
    snapshot = {
        "schemaVersion": 2,
        "generatedAt": now,
        "demo": False,
        "source": GRAPHQL_URL,
        "summary": {
            "total": len(offers),
            "new": len(new_offers),
            "discounted": len(discounts),
            "removed": len(removed_ids),
        },
        "offers": offers,
    }
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(offers)} offers ({len(new_offers)} new, {len(discounts)} discounted, {len(removed_ids)} removed).")

    if os.environ.get("TELEGRAM_TEST") == "1":
        send_telegram("✅ <b>Hlídač vozů je propojený.</b>\nTestovací zpráva z GitHub Actions dorazila správně.")
    elif new_offers or discounts:
        send_telegram(build_message(new_offers, discounts))
    elif not baseline:
        print("No relevant changes; no Telegram message needed.")
    else:
        print("Baseline created; no Telegram message sent.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
