import re
import time
import random
from curl_cffi import requests
from bs4 import BeautifulSoup

LISTING_URL = "https://www.habitaclia.com/viviendas-igualada.htm?pmax=180000&codzonas=4,2"
HEADERS = {"Accept-Language": "es-ES,es;q=0.9"}


def _get(session, url, referer=None):
    headers = {**HEADERS}
    if referer:
        headers["Referer"] = referer
    time.sleep(random.uniform(3, 6))
    return session.get(url, impersonate="chrome136", headers=headers)


def scrape():
    session = requests.Session()
    offers = []
    current_url = LISTING_URL
    prev_url = None

    while current_url:
        resp = _get(session, current_url, referer=prev_url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for card in soup.select("div.list-item-info"):
            link = card.select_one("h3.list-item-title a")
            if not link:
                continue

            name = link.get_text(strip=True)
            url = link["href"].split("?")[0]

            price_el = card.select_one("span.font-2")
            price = price_el.get_text(strip=True) if price_el else "N/A"

            loc_el = card.select_one("p.list-item-location span")
            loc_text = loc_el.get_text(strip=True) if loc_el else ""
            zone = loc_text.split(" - ", 1)[-1].strip() if " - " in loc_text else loc_text or "N/A"

            feat_el = card.select_one("p.list-item-feature")
            feat_text = feat_el.get_text(strip=True) if feat_el else ""
            m = re.match(r"(\d+)m", feat_text)
            surface = f"{m.group(1)} m\u00b2" if m else "N/A"
            m = re.search(r"(\d+)\s*habitacion", feat_text)
            rooms = f"{m.group(1)} hab." if m else "N/A"

            desc_el = card.select_one("p.list-item-description")
            description = desc_el.get_text(strip=True) if desc_el else "N/A"

            m_id = re.search(r"-i(\d+)\.htm", url)
            offers.append({
                "id": m_id.group(1) if m_id else "N/A",
                "name": name,
                "price": price,
                "url": url,
                "rooms": rooms,
                "surface": surface,
                "zone": zone,
                "description": description,
            })

        next_a = next((a for a in soup.find_all("a") if "Siguiente" in a.get_text()), None)
        prev_url = current_url
        current_url = next_a["href"] if next_a else None

    return offers
