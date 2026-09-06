#!/usr/bin/env python3
"""Download offers, compare them with the previous snapshot and notify Telegram."""

from __future__ import annotations

import datetime as dt
import html
import json
import os
import pathlib
import statistics
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request


ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "latest.json"
MARKET_PATH = ROOT / "data" / "market.json"
CONFIG_PATH = ROOT / "config" / "filters.json"
GRAPHQL_URL = "https://www.skodaplus.cz/graphql"
SITE_URL = "https://www.skodaplus.cz"
PAGE_SIZE = 100
EQUIPMENT_BATCH_SIZE = 25
MARKET_CACHE_HOURS = 20
SKODA_MAKE_ID = "brand_32"

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
        fuel { id value(lang: $lang) }
        motorType { value(lang: $lang) }
        transmission { id value(lang: $lang) }
        equipmentLevel { value }
        modifiedAt
        prettyUrl
        images(limit: 1) { thumbnailUrl normalUrl bigUrl }
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


def graphql_call(query: str, variables: dict) -> dict:
    body = json.dumps({
        "query": query,
        "variables": variables,
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


def offer_filter(dealer_ids: list[str] | None = None, make_ids: list[str] | None = None) -> dict:
    car_filter = {
        "regionCountry": "CZ",
        "carsOrderBy": "FIRST_REGISTRATION_DESC",
        "skodaPlus": True,
        "oneYearCar": True,
        "usedCar": True,
        "demoCarTypes": ["EMPTY", "FOR_SALE", "ON_REQUEST"],
    }
    if dealer_ids:
        car_filter["dealers"] = dealer_ids
    if make_ids:
        car_filter["make"] = make_ids
    return car_filter


def graphql_request(car_filter: dict, after: str | None = None) -> dict:
    return graphql_call(QUERY, {
        "filter": car_filter,
        "first": PAGE_SIZE,
        "after": after,
        "lang": "CS",
    })


def fetch_all(car_filter: dict, label: str) -> list[dict]:
    nodes: list[dict] = []
    after = None
    expected_count = None
    while True:
        result = graphql_request(car_filter, after)
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
            print(f"Loaded {len(nodes)} {label} offers.")
            return nodes
        after = info.get("endCursor")
        if not after:
            raise RuntimeError("Pagination did not provide an end cursor")


def clean_equipment_names(items: list[dict]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for item in items:
        name = " ".join((item.get("name") or "").split())
        key = name.casefold()
        if not name or key in seen:
            continue
        seen.add(key)
        names.append(name)
    return sorted(names, key=str.casefold)


def fetch_equipment(nodes: list[dict], previous: dict[str, dict]) -> dict[str, list[str]]:
    equipment_by_id: dict[str, list[str]] = {}
    pending: list[dict] = []
    for node in nodes:
        car_id = node["id"].replace("Car-", "")
        old = previous.get(car_id)
        if (
            old is not None
            and isinstance(old.get("equipment"), list)
            and (old.get("sourceModifiedAt") is None or old.get("sourceModifiedAt") == node.get("modifiedAt"))
        ):
            equipment_by_id[node["id"]] = old["equipment"]
        else:
            pending.append(node)

    for start in range(0, len(pending), EQUIPMENT_BATCH_SIZE):
        batch = pending[start:start + EQUIPMENT_BATCH_SIZE]
        definitions = ", ".join(f"$car{index}: ID!" for index in range(len(batch)))
        selections = "\n".join(
            f"car{index}: car(id: $car{index}) {{ equipmentItems {{ name(lang: CS) }} }}"
            for index in range(len(batch))
        )
        query = f"query Equipment({definitions}) {{\n{selections}\n}}"
        variables = {f"car{index}": node["id"] for index, node in enumerate(batch)}
        result = graphql_call(query, variables)
        for index, node in enumerate(batch):
            detail = result.get(f"car{index}") or {}
            equipment_by_id[node["id"]] = clean_equipment_names(detail.get("equipmentItems") or [])
        print(f"Loaded equipment for {min(start + len(batch), len(pending))}/{len(pending)} offers needing refresh.")

    return equipment_by_id


def infer_fuel(node: dict) -> str:
    source_value = (node.get("fuel") or {}).get("value", "").lower()
    if "hybrid" in source_value:
        return "Hybrid"
    if "diesel" in source_value or "nafta" in source_value:
        return "Nafta"
    if "elektr" in source_value:
        return "Elektřina"
    if "cng" in source_value:
        return "CNG"
    if "benz" in source_value:
        return "Benzín"

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
    transmission = node.get("transmission") or {}
    transmission_id = transmission.get("id", "")
    value = transmission.get("value", "").lower()
    is_automatic = transmission_id in {"transmission_2", "transmission_5"} or "automat" in value or "dsg" in value
    return "Automat" if is_automatic else "Manuál"


def market_offer(node: dict) -> dict:
    registration = node.get("firstRegistration") or ""
    model = node.get("model") or {}
    return {
        "id": node["id"].replace("Car-", ""),
        "model": model.get("modelName") or "",
        "trim": (node.get("equipmentLevel") or {}).get("value") or "",
        "powerKw": int(node.get("enginePower") or 0),
        "fuel": infer_fuel(node),
        "transmission": transmission_name(node),
        "year": int(registration[:4]) if registration[:4].isdigit() else 0,
        "mileage": int(node.get("mileage") or 0),
        "price": int((node.get("price") or {}).get("value") or 0),
    }


def parse_timestamp(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def load_market_catalog(now: dt.datetime) -> tuple[list[dict], str]:
    cached = load_json(MARKET_PATH, {})
    generated_at = parse_timestamp(cached.get("generatedAt"))
    cached_offers = cached.get("offers") or []
    is_fresh = (
        cached.get("schemaVersion") == 2
        and generated_at is not None
        and now.astimezone(dt.timezone.utc) - generated_at.astimezone(dt.timezone.utc) < dt.timedelta(hours=MARKET_CACHE_HOURS)
        and len(cached_offers) >= 100
    )
    if is_fresh:
        print(f"Using cached nationwide catalog with {len(cached_offers)} offers.")
        return cached_offers, cached["generatedAt"]

    raw_market = fetch_all(offer_filter(make_ids=[SKODA_MAKE_ID]), "nationwide Škoda")
    offers = [offer for offer in (market_offer(node) for node in raw_market) if offer["price"] > 0]
    generated = now.astimezone().isoformat(timespec="seconds")
    snapshot = {
        "schemaVersion": 2,
        "generatedAt": generated,
        "source": GRAPHQL_URL,
        "make": "Škoda",
        "offers": offers,
    }
    MARKET_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKET_PATH.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Saved nationwide market catalog with {len(offers)} offers.")
    return offers, generated


def comparison_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    return " ".join(normalized.casefold().split())


def rounded_market_price(value: float) -> int:
    return int(round(value / 1000) * 1000)


def percentile(values: list[int], fraction: float) -> int:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    interpolated = ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)
    return rounded_market_price(interpolated)


def market_benchmark(offer: dict, catalog_index: dict[tuple[str, str, str, str], list[dict]]) -> dict | None:
    model_key = comparison_key(offer["model"])
    trim_key = comparison_key(offer["trim"])
    if offer["make"] != "Škoda" or not model_key or not trim_key or not offer["year"] or not offer["powerKw"]:
        return None

    candidates = []
    key = (model_key, trim_key, offer["fuel"], offer["transmission"])
    for candidate in catalog_index.get(key, []):
        if candidate["id"] == offer["id"]:
            continue
        year_gap = abs(candidate["year"] - offer["year"])
        mileage_gap = abs(candidate["mileage"] - offer["mileage"])
        power_gap = abs(candidate["powerKw"] - offer["powerKw"])
        if year_gap > 2 or mileage_gap > 30_000 or power_gap > 15:
            continue
        score = year_gap * 6 + mileage_gap / 5_000 + power_gap / 5
        candidates.append((score, candidate))

    nearest = [candidate for _, candidate in sorted(candidates, key=lambda item: item[0])[:40]]
    if len(nearest) < 5:
        return None
    prices = [candidate["price"] for candidate in nearest]
    sample_size = len(prices)
    confidence = "high" if sample_size >= 15 else "medium" if sample_size >= 8 else "low"
    return {
        "typicalPrice": rounded_market_price(statistics.median(prices)),
        "lowerQuartile": percentile(prices, 0.25),
        "upperQuartile": percentile(prices, 0.75),
        "sampleSize": sample_size,
        "confidence": confidence,
    }


def attach_market_benchmarks(offers: list[dict], catalog: list[dict]) -> int:
    catalog_index: dict[tuple[str, str, str, str], list[dict]] = {}
    for candidate in catalog:
        key = (
            comparison_key(candidate["model"]),
            comparison_key(candidate["trim"]),
            candidate["fuel"],
            candidate["transmission"],
        )
        catalog_index.setdefault(key, []).append(candidate)
    matched = 0
    for offer in offers:
        offer["market"] = market_benchmark(offer, catalog_index)
        if offer["market"] is not None:
            matched += 1
    return matched


def normalize(node: dict, dealers_by_id: dict[str, dict], previous: dict[str, dict], equipment_by_id: dict[str, list[str]], baseline: bool, now: str) -> dict:
    raw_id = node["id"]
    car_id = raw_id.replace("Car-", "")
    old = previous.get(car_id)
    price = int((node.get("price") or {}).get("value") or 0)
    old_price = int(old.get("price", price)) if old else price
    registration = node.get("firstRegistration") or ""
    model = node.get("model") or {}
    trim = (node.get("equipmentLevel") or {}).get("value") or ""
    images = node.get("images") or []
    image_path = (
        images[0].get("bigUrl")
        or images[0].get("normalUrl")
        or images[0].get("thumbnailUrl")
    ) if images else None
    pretty_url = node.get("prettyUrl") or ""
    dealer = node.get("dealer") or {}
    first_seen = old.get("firstSeen") if old else now
    dealer_config = dealers_by_id.get(dealer.get("id"), {})
    return {
        "id": car_id,
        "make": (model.get("carMake") or {}).get("name") or "",
        "model": model.get("modelName") or "",
        "trim": trim,
        "equipment": equipment_by_id.get(raw_id, []),
        "sourceModifiedAt": node.get("modifiedAt"),
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
        "city": dealer_config.get("city") or (dealer.get("address") or {}).get("city") or "",
        "area": dealer_config.get("area") or "Okolí Brna",
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
        and (filters.get("minPrice") is None or offer["price"] >= filters["minPrice"])
        and (filters.get("maxPrice") is None or offer["price"] <= filters["maxPrice"])
        and (filters.get("maxMileage") is None or offer["mileage"] <= filters["maxMileage"])
        and (filters.get("minYear") is None or offer["year"] >= filters["minYear"])
    )


def money(value: int) -> str:
    return f"{value:,}".replace(",", " ") + " Kč"


def build_message(new_offers: list[dict], discounts: list[dict], priority_cities: list[str]) -> str:
    changes = [("NOVINKA", offer) for offer in new_offers] + [("ZLEVNĚNO", offer) for offer in discounts]
    changes.sort(key=lambda item: (item[1]["city"] not in priority_cities, item[0] != "NOVINKA", item[1]["city"], item[1]["price"]))
    has_priority = any(offer["city"] in priority_cities for _, offer in changes)
    lines = ["⭐ <b>Hlídač vozů našel prioritní změnu</b>" if has_priority else "🚗 <b>Hlídač vozů našel změny</b>", ""]
    for label, offer in changes[:10]:
        title = " ".join(part for part in (offer["make"], offer["model"], offer["trim"]) if part)
        priority = "⭐ PRIORITA · " if offer["city"] in priority_cities else ""
        lines.extend([
            f"<b>{priority}{label} · {html.escape(offer['city'])}</b>",
            html.escape(title),
            f"{offer['year']} · {offer['mileage']:,} km · <b>{money(offer['price'])}</b>".replace(",", " "),
            f"<a href=\"{html.escape(offer['url'], quote=True)}\">Otevřít nabídku</a>",
            "",
        ])
    remaining = len(changes) - 10
    if remaining > 0:
        lines.append(f"…a dalších {remaining} změn na webu.")
    return "\n".join(lines).strip()


def build_report_messages(offers: list[dict], models: list[str], min_price: int, max_price: int, priority_cities: list[str]) -> list[str]:
    offers.sort(key=lambda offer: (offer["city"] not in priority_cities, offer["price"], offer["mileage"]))
    chunks = [offers[index:index + 8] for index in range(0, len(offers), 8)]
    messages = []
    for index, chunk in enumerate(chunks, start=1):
        lines = [
            f"📋 <b>Aktuální {html.escape(' / '.join(models))}</b>",
            f"{money(min_price)}–{money(max_price)} · {len(offers)} vozů · {index}/{len(chunks)}",
            "",
        ]
        for offer in chunk:
            title = " ".join(part for part in (offer["make"], offer["model"], offer["trim"]) if part)
            priority = "⭐ " if offer["city"] in priority_cities else ""
            lines.extend([
                f"<b>{priority}{html.escape(offer['city'])} · {html.escape(title)}</b>",
                f"{offer['year']} · {offer['mileage']:,} km · <b>{money(offer['price'])}</b>".replace(",", " "),
                f"<a href=\"{html.escape(offer['url'], quote=True)}\">Otevřít nabídku</a>",
                "",
            ])
        messages.append("\n".join(lines).strip())
    return messages


def report_filter_from_environment() -> tuple[list[str], int, int]:
    models = [model.strip() for model in os.environ.get("TELEGRAM_REPORT_MODELS", "").split(",") if model.strip()]
    try:
        min_price = int(os.environ.get("TELEGRAM_REPORT_MIN_PRICE", "0"))
        max_price = int(os.environ.get("TELEGRAM_REPORT_MAX_PRICE", "0"))
    except ValueError as exc:
        raise RuntimeError("Telegram report price must be a whole number") from exc
    if not models or min_price < 0 or max_price < min_price:
        raise RuntimeError("Telegram report filters are invalid")
    return models, min_price, max_price


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
        or previous_snapshot.get("schemaVersion") != 4
    )
    now_datetime = dt.datetime.now(dt.timezone.utc).astimezone()
    now = now_datetime.isoformat(timespec="seconds")
    dealer_ids = [dealer["id"] for dealer in dealers]
    dealers_by_id = {dealer["id"]: dealer for dealer in dealers}
    raw_offers = fetch_all(offer_filter(dealer_ids=dealer_ids), "local")
    equipment_by_id = fetch_equipment(raw_offers, previous_offers)
    offers = [normalize(node, dealers_by_id, previous_offers, equipment_by_id, baseline, now) for node in raw_offers]
    market_catalog, market_generated_at = load_market_catalog(now_datetime)
    benchmark_count = attach_market_benchmarks(offers, market_catalog)
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
        "schemaVersion": 4,
        "generatedAt": now,
        "demo": False,
        "source": GRAPHQL_URL,
        "summary": {
            "total": len(offers),
            "new": len(new_offers),
            "discounted": len(discounts),
            "removed": len(removed_ids),
            "benchmarked": benchmark_count,
        },
        "market": {
            "generatedAt": market_generated_at,
            "sampleSize": len(market_catalog),
            "method": "median of same model, trim, fuel and transmission; power ±15 kW, year ±2, mileage ±30,000 km",
        },
        "offers": offers,
    }
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(offers)} offers ({len(new_offers)} new, {len(discounts)} discounted, {len(removed_ids)} removed).")

    if os.environ.get("TELEGRAM_REPORT") == "1":
        report_models, report_min_price, report_max_price = report_filter_from_environment()
        report_offers = [
            offer for offer in offers
            if offer["model"] in report_models and report_min_price <= offer["price"] <= report_max_price
        ]
        report_messages = build_report_messages(report_offers, report_models, report_min_price, report_max_price, filters.get("priorityCities") or [])
        if not report_messages:
            send_telegram("📋 <b>Aktuální přehled</b>\nV zadaném filtru teď není žádný vůz.")
        else:
            for report_message in report_messages:
                send_telegram(report_message)
    elif os.environ.get("TELEGRAM_TEST") == "1":
        send_telegram("✅ <b>Hlídač vozů je propojený.</b>\nTestovací zpráva z GitHub Actions dorazila správně.")
    elif new_offers or discounts:
        send_telegram(build_message(new_offers, discounts, filters.get("priorityCities") or []))
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
