import re
import time
import random
import json
from curl_cffi import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

LISTING_URL = "https://www.fotocasa.es/ca/comprar/pisos/igualada/totes-les-zones/l" # ?maxPrice=200000
BASE_URL = "https://www.fotocasa.es"
HEADERS = {"Accept-Language": "ca-ES,ca;q=0.9,es;q=0.8"}


def _get(session, url, referer=None):
    headers = {**HEADERS}
    if referer:
        headers["Referer"] = referer
    time.sleep(random.uniform(2, 4))
    return session.get(url, impersonate="chrome136", headers=headers)


def _page_url(page):
    """Fotocasa paginates by inserting /<page> after the trailing /l segment."""
    if page == 1:
        return LISTING_URL
    base, sep, query = LISTING_URL.partition("?")
    return f"{base}/{page}{sep}{query}"


def scrape(limit=None):
    session = requests.Session()
    partial_offers = []
    seen_ids = set()
    page = 1
    prev_url = None

    while True:
        url = _page_url(page)
        resp = _get(session, url, referer=prev_url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        items = _extract_items(soup)
        new_items = [it for it in items if it["id"] not in seen_ids]
        if not new_items:
            # Empty page (or fotocasa repeating the last page past the end) means we're done.
            break

        seen_ids.update(it["id"] for it in new_items)
        partial_offers.extend(new_items)

        if limit is not None and len(partial_offers) >= limit:
            break

        prev_url = url
        page += 1

    if limit is not None:
        partial_offers = partial_offers[:limit]

    # Fetch detail pages only for the name (h1) and extended fields
    offers = []
    for item in tqdm(partial_offers, desc="Scraping details", unit="property"):
        resp = _get(session, item["url"], referer=LISTING_URL)
        resp.raise_for_status()
        detail = BeautifulSoup(resp.text, "html.parser")
        h1 = detail.find("h1")
        item["name"] = h1.get_text(strip=True) if h1 else "N/A"
        item.update(_parse_detail_json(detail))
        offers.append(item)

    return offers


def _extract_items(soup):
    """Extract all listing data from the initialSearch JSON embedded in the page."""
    for s_tag in soup.find_all("script"):
        txt = s_tag.string or ""
        if "__IMAGES_TO_PRELOAD__" not in txt or "initialSearch" not in txt:
            continue
        try:
            data = json.loads(txt)
            items = data["initialSearch"]["result"]["realEstates"]
            result = []
            for item in items:
                path = (item.get("detail") or {}).get("ca-ES")
                if not path or not path.startswith("/"):
                    continue
                url = BASE_URL + path.split("?")[0]
                features = {f["key"]: f["value"] for f in item.get("features", [])}
                rooms_val = features.get("rooms")
                surface_val = features.get("surface")
                _id_m = re.search(r"(\d+)\.htm", path or "")
                item_id = str(item["id"]) if item.get("id") else (_id_m.group(1) if _id_m else "N/A")
                result.append({
                    "id": item_id,
                    "url": url,
                    "price": item.get("price") or "N/A",
                    "zone": item.get("location") or "N/A",
                    "description": item.get("description") or "N/A",
                    "rooms": f"{rooms_val} hab." if rooms_val else "N/A",
                    "surface": f"{surface_val} m\u00b2" if surface_val else "N/A",
                })
            if result:
                return result
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
    return []


_ORIENT_MAP = {
    # Spanish
    "sur": "S", "norte": "N", "este": "E", "oeste": "O",
    "sureste": "SE", "sudeste": "SE", "suroeste": "SO", "sudoeste": "SO",
    "noreste": "NE", "nordeste": "NE", "noroeste": "NO", "nordoeste": "NO",
    # Catalan
    "sud": "S", "nord": "N", "est": "E", "oest": "O",
    "sud-est": "SE", "sud-oest": "SO", "nord-est": "NE", "nord-oest": "NO",
    # Catalan without hyphen
    "sudest": "SE", "sudoest": "SO", "nordest": "NE", "nordoest": "NO",
}


def _parse_detail_json(soup):
    """Extract extended fields (planta, ascensor, etc.) from the detail page JSON."""
    for tag in soup.find_all("script"):
        txt = tag.string or ""
        if "featuresList" not in txt or "clientName" not in txt:
            continue
        try:
            raw = json.loads(txt)
        except (json.JSONDecodeError, ValueError):
            continue

        # The real-estate object may be the root or nested under a key
        re_obj = None
        if isinstance(raw, dict):
            if "featuresList" in raw:
                re_obj = raw
            else:
                for v in raw.values():
                    if isinstance(v, dict) and "featuresList" in v:
                        re_obj = v
                        break
        if re_obj is None:
            continue

        features_map = {f["label"]: f["value"] for f in re_obj.get("featuresList", []) if isinstance(f, dict)}
        extras = [e.lower() for e in re_obj.get("extras", [])]

        # planta: "3ª planta" → 3
        floor_str = str(features_map.get("floor", ""))
        planta_m = re.search(r"(\d+)", floor_str)
        planta = int(planta_m.group(1)) if planta_m else None

        # orientacion: try JSON featuresList first, then HTML element fallback
        orient_raw = str(features_map.get("orientation", "")).lower().strip()
        orientacion = _ORIENT_MAP.get(orient_raw)
        if orientacion is None:
            el = soup.find(id="feature-value-orientació") or soup.find(id="feature-value-orientacion")
            if el:
                orientacion = _ORIENT_MAP.get(el.get_text(strip=True).lower())

        # ascensor: featuresList label="elevator", value="YES"
        ascensor = 1 if str(features_map.get("elevator", "")).upper() == "YES" else 0

        # trastero / terraza from extras
        trastero = 1 if any("traster" in e for e in extras) else 0
        terraza  = 1 if any("terras" in e for e in extras) else 0

        # energy certificate
        cert = re_obj.get("energyCertificate") or None
        certificado = cert if cert and cert != "0" else None

        inmobiliaria = re_obj.get("clientName") or None

        return {
            "planta": planta,
            "ascensor": ascensor,
            "orientacion": orientacion,
            "trastero": trastero,
            "terraza": terraza,
            "certificado_energetico": certificado,
            "inmobiliaria": inmobiliaria,
        }
    return {}
