import re
import time
import random
import json
from curl_cffi import requests
from bs4 import BeautifulSoup

LISTING_URL = "https://www.fotocasa.es/ca/comprar/pisos/igualada/totes-les-zones/l?maxPrice=200000"
BASE_URL = "https://www.fotocasa.es"
HEADERS = {"Accept-Language": "ca-ES,ca;q=0.9,es;q=0.8"}


def _get(session, url, referer=None):
    headers = {**HEADERS}
    if referer:
        headers["Referer"] = referer
    time.sleep(random.uniform(2, 4))
    return session.get(url, impersonate="chrome136", headers=headers)


def scrape():
    session = requests.Session()
    resp = _get(session, LISTING_URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    partial_offers = _extract_items(soup)

    # Fetch detail pages only for the name (h1)
    offers = []
    for item in partial_offers:
        resp = _get(session, item["url"], referer=LISTING_URL)
        resp.raise_for_status()
        detail = BeautifulSoup(resp.text, "html.parser")
        h1 = detail.find("h1")
        item["name"] = h1.get_text(strip=True) if h1 else "N/A"
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
