import re
import time
import random
import json
import base64
from curl_cffi import requests
from tqdm import tqdm

LISTING_URL = "https://www.yaencontre.com/venta/pisos/igualada/f--250000euros"
BASE_URL = "https://www.yaencontre.com"
HEADERS = {"Accept-Language": "es-ES,es;q=0.9"}
# DataDome rejects most curl_cffi fingerprints (403); safari18_0 currently passes.
IMPERSONATE = "safari18_0"

_STATE_RE = re.compile(r'window\.__INITIAL_STATE__\s*=\s*JSON\.parse\(atob\("([^"]+)"\)\)')

_ORIENT_MAP = {
    "sureste": "SE", "suroeste": "SO", "noreste": "NE", "noroeste": "NO",
    "sudeste": "SE", "sudoeste": "SO",
    "sur": "S", "sud": "S", "norte": "N", "nord": "N",
    "este": "E", "est": "E", "oeste": "O", "oest": "O",
}


def _get(session, url, referer=None):
    headers = {**HEADERS}
    if referer:
        headers["Referer"] = referer
    resp = session.get(url, impersonate=IMPERSONATE, headers=headers)
    time.sleep(random.uniform(2, 4))
    return resp


def _extract_state(html):
    """Decode the base64 JSON state embedded as window.__INITIAL_STATE__."""
    m = _STATE_RE.search(html)
    if not m:
        return {}
    return json.loads(base64.b64decode(m.group(1)))


def _page_url(page):
    return LISTING_URL if page == 1 else f"{LISTING_URL}/pag-{page}"


def scrape(limit=None):
    session = requests.Session()
    ids = []
    page = 1
    prev_url = None

    while True:
        url = _page_url(page)
        resp = _get(session, url, referer=prev_url)
        resp.raise_for_status()
        state = _extract_state(resp.text)

        results = state.get("results", {}).get("currentPageItems", {})
        items = results.get("byId", {})
        new_ids = []
        for key in results.get("sortedItems", []):
            item = (items.get(key) or {}).get("item") or {}
            ref = item.get("reference")
            if ref and ref not in ids and ref not in new_ids:
                new_ids.append(ref)
        if not new_ids:
            break

        ids.extend(new_ids)
        if limit is not None and len(ids) >= limit:
            ids = ids[:limit]
            break

        num_pages = state.get("pagination", {}).get("numPages")
        if num_pages is not None and page >= num_pages:
            break

        prev_url = url
        page += 1

    offers = []
    for property_id in tqdm(ids, desc="Scraping details", unit="property"):
        offers.append(_scrape_detail(session, property_id, referer=prev_url or LISTING_URL))

    return offers


def scrape_individual(property_id):
    session = requests.Session()
    # Visit the listing first so DataDome issues a session cookie before the detail request.
    r0 = _get(session, LISTING_URL)
    r0.raise_for_status()
    return _scrape_detail(session, property_id, referer=LISTING_URL)


def _scrape_detail(session, property_id, referer):
    url = f"{BASE_URL}/venta/piso/inmueble-{property_id}"
    resp = _get(session, url, referer=referer)
    resp.raise_for_status()
    item = _extract_state(resp.text).get("details", {}).get("item") or {}
    return _parse_detail(item, property_id, url)


def _parse_detail(item, property_id, url):
    price_val = item.get("price")
    price = f"{price_val:,} \u20ac".replace(",", ".") if price_val else "N/A"

    rooms = item.get("rooms")
    area = item.get("area")

    qualified = (item.get("address") or {}).get("qualifiedName") or ""
    zone = qualified.split(",")[0].strip() if qualified else "N/A"

    features = item.get("businessFeatures") or {}
    characteristics = features.get("characteristics") or []
    equipment = [e.get("label", "") for e in
                 (features.get("outstandingEquipment") or []) + (features.get("regularEquipment") or [])
                 if e.get("value")]
    all_feats = characteristics + equipment

    # Planta: "Planta 2ª" → 2, "Bajo" → 0
    planta = None
    for f in characteristics:
        m = re.search(r"[Pp]lanta\s+(\d+)", f)
        if m:
            planta = int(m.group(1))
            break
        if f.strip().lower() == "bajo":
            planta = 0
            break

    # Orientacion: "Orientado a: Sur"
    orientacion = None
    for f in characteristics:
        m = re.search(r"[Oo]rientad[oa]\s+a[:\s]+(\w+)", f)
        if m:
            orientacion = _ORIENT_MAP.get(m.group(1).lower(), m.group(1).upper())
            break

    def _has(word):
        return 1 if any(word in f.lower() for f in all_feats) else 0

    cert = ((item.get("energyCertificateRating") or {}).get("consumption") or {}).get("rating")

    description = " ".join((item.get("description") or "").split())

    return {
        "id": property_id,
        "name": item.get("title") or "N/A",
        "price": price,
        "url": url,
        "rooms": f"{rooms} hab." if rooms else "N/A",
        "surface": f"{area} m\u00b2" if area else "N/A",
        "zone": zone,
        "description": description or None,
        "planta": planta,
        "ascensor": _has("ascensor"),
        "orientacion": orientacion,
        "trastero": _has("trastero"),
        "terraza": _has("terraza"),
        "certificado_energetico": cert.upper() if cert else None,
        "inmobiliaria": (item.get("owner") or {}).get("name") or None,
    }


def _parse_zone(name):
    """Extract zone from 'Piso en Zone, City' → Zone"""
    m = re.search(r"\ben\s+(.+?)(?:,|$)", name)
    return m.group(1).strip() if m else "N/A"
