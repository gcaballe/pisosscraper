import re
import time
import random
import json
from curl_cffi import requests
from tqdm import tqdm

LISTING_URL = "https://www.habitaclia.com/comprar/viviendas/barcelona-provincia/igualada/s?maxPrice=220000"
BASE_URL = "https://www.habitaclia.com"
HEADERS = {"Accept-Language": "es-ES,es;q=0.9"}

_PROPS_RE = re.compile(r'window\.__INITIAL_PROPS__\s*=\s*JSON\.parse\(("(?:[^"\\]|\\.)*")\)')

_FLOOR_MAP = {
    "GROUND_FLOOR": 0, "FIRST": 1, "SECOND": 2, "THIRD": 3, "FOURTH": 4, "FIFTH": 5,
    "SIXTH": 6, "SEVENTH": 7, "EIGHTH": 8, "NINTH": 9, "TENTH": 10,
}

_ORIENT_MAP = {
    "NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "O",
    "NORTH_EAST": "NE", "NORTH_WEST": "NO", "SOUTH_EAST": "SE", "SOUTH_WEST": "SO",
}


def _get(session, url, referer=None):
    headers = {**HEADERS}
    if referer:
        headers["Referer"] = referer
    time.sleep(random.uniform(3, 6))
    return session.get(url, impersonate="chrome136", headers=headers)


def _page_url(page):
    """Habitaclia paginates by inserting /<page> after the trailing /s segment."""
    if page == 1:
        return LISTING_URL
    base, sep, query = LISTING_URL.partition("?")
    return f"{base}/{page}{sep}{query}"


def _extract_results(html):
    """Return (items, pagination) from the window.__INITIAL_PROPS__ JSON embedded in the page."""
    m = _PROPS_RE.search(html)
    if not m:
        return [], {}
    # The payload is a JS string literal containing JSON, so decode twice.
    data = json.loads(json.loads(m.group(1)))
    results = data.get("initialSearchResultsPage", {}).get("initialSearchContext", {}).get("results", {})
    return results.get("items", []), results.get("pagination", {})


def _parse_item(item):
    summary = item.get("summary") or {}
    prop = item.get("property") or {}
    location = summary.get("location") or {}

    amount = ((item.get("transaction") or {}).get("price") or {}).get("amount")
    price = f"{amount:,} \u20ac".replace(",", ".") if amount else "N/A"

    path = item.get("navigationUrl") or (item.get("urls") or {}).get("canonical") or ""
    url = BASE_URL + path.split("?")[0] if path else "N/A"

    rooms = prop.get("rooms")
    surface = prop.get("builtSurface")
    description = (summary.get("description") or "").strip()

    # Some publishers leave the title empty; build one from the location like the site does.
    name = summary.get("title")
    if not name:
        zone_line = location.get("displayZoneLine")
        name = f"Vivienda en venta en {zone_line}" if zone_line else "N/A"

    features = set((prop.get("features") or {}).get("has") or [])
    cert_label = (((prop.get("energyEfficiencyCertificate") or {}).get("data") or {})
                  .get("consumption") or {}).get("label")
    publisher = summary.get("publisher") or {}

    return {
        "id": str(item.get("legacyNumericId") or item.get("id") or "N/A"),
        "name": name,
        "price": price,
        "url": url,
        "rooms": f"{rooms} hab." if rooms else "N/A",
        "surface": f"{surface} m\u00b2" if surface else "N/A",
        "zone": location.get("district") or location.get("displayZoneLine") or "N/A",
        "description": description or "N/A",
        "planta": _FLOOR_MAP.get(prop.get("floor")),
        "ascensor": 1 if "ELEVATOR" in features else 0,
        "orientacion": _ORIENT_MAP.get(prop.get("orientation")),
        "trastero": 1 if "STORAGE_ROOM" in features else 0,
        "terraza": 1 if (prop.get("terrace") or {}).get("has") else 0,
        "certificado_energetico": cert_label or None,
        "inmobiliaria": publisher.get("tradeName") or publisher.get("name") or None,
    }


def scrape(limit=None):
    session = requests.Session()
    offers = []
    seen_ids = set()
    page = 1
    prev_url = None

    with tqdm(desc="Scraping listings", unit="property") as pbar:
        while True:
            url = _page_url(page)
            resp = _get(session, url, referer=prev_url)
            resp.raise_for_status()

            items, pagination = _extract_results(resp.text)
            new_items = [it for it in items if it.get("id") not in seen_ids]
            if not new_items:
                break

            for item in new_items:
                seen_ids.add(item.get("id"))
                offers.append(_parse_item(item))
                pbar.update(1)
                if limit is not None and len(offers) >= limit:
                    return offers

            total_pages = pagination.get("totalPages")
            if total_pages is not None and page >= total_pages:
                break

            prev_url = url
            page += 1

    return offers
