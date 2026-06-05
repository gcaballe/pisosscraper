import re
import time
import random
from urllib.parse import urljoin
from curl_cffi import requests
from bs4 import BeautifulSoup

LISTING_URL = "https://www.yaencontre.com/venta/pisos/igualada/f--200000euros"
HEADERS = {"Accept-Language": "es-ES,es;q=0.9"}


def _get(session, url, referer=None):
    headers = {**HEADERS}
    if referer:
        headers["Referer"] = referer
    time.sleep(random.uniform(2, 4))
    return session.get(url, impersonate="chrome136", headers=headers)


def scrape():
    session = requests.Session()
    offers = []
    page = 1
    prev_url = None

    while True:
        url = LISTING_URL if page == 1 else f"{LISTING_URL}/pag-{page}"
        resp = _get(session, url, referer=prev_url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        items = _parse_page(soup)
        if not items:
            break

        offers.extend(items)
        prev_url = url
        page += 1

        next_href = f"/venta/pisos/igualada/f--250000euros/pag-{page}"
        if not soup.find("a", href=next_href):
            break

    return offers


def _parse_page(soup):
    results = []
    seen = set()

    for a in soup.find_all("a", href=re.compile(r"/venta/piso/inmueble-")):
        h3 = a.find_parent("h3")
        if not h3:
            continue
        href = a["href"]
        url = urljoin(LISTING_URL, href)
        if url in seen:
            continue
        seen.add(url)

        name = a.get_text(strip=True)
        zone = _parse_zone(name)

        # Walk up from h3 to the card container
        card = h3
        for _ in range(5):
            parent = card.parent
            if parent is None or parent.name in ("body", "html"):
                break
            card = parent
            if card.name in ("article", "li"):
                break
            if card.name == "div" and card.get("class"):
                cls = " ".join(card["class"])
                if any(k in cls for k in ("item", "card", "property", "listing", "result")):
                    break

        text = card.get_text(" ", strip=True)

        # First price amount, excluding €/m²
        price_m = re.search(r"([\d.]+(?:,\d+)?)\s*€(?!\s*/)", text)
        price = f"{price_m.group(1)} €" if price_m else "N/A"

        m_rooms = re.search(r"(\d+)\s*hab\b", text)
        rooms = f"{m_rooms.group(1)} hab." if m_rooms else "N/A"

        # Integer m² only (excludes decimal €/m² values)
        m_surface = re.search(r"\b(\d+)\s*m²", text)
        surface = f"{m_surface.group(1)} m²" if m_surface else "N/A"

        desc = "N/A"
        for p in card.find_all("p"):
            t = p.get_text(strip=True)
            if len(t) > 30:
                desc = t
                break

        m_id = re.search(r"/inmueble-(\d+)", href)
        results.append({
            "id": m_id.group(1) if m_id else "N/A",
            "name": name,
            "price": price,
            "url": url,
            "rooms": rooms,
            "surface": surface,
            "zone": zone,
            "description": desc,
        })

    return results


def _parse_zone(name):
    """Extract zone from 'Piso en Zone, City' → Zone"""
    m = re.search(r"\ben\s+(.+?)(?:,|$)", name)
    return m.group(1).strip() if m else "N/A"
