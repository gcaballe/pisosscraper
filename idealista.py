import re
import time
import random
from curl_cffi import requests
from bs4 import BeautifulSoup

LISTING_URL = "https://www.idealista.com/venta-viviendas/igualada-barcelona/con-precio-hasta_260000/"
BASE_URL = "https://www.idealista.com"
HEADERS = {
    "Accept-Language": "es-ES,es;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
}


def _get(session, url, referer=None):
    headers = {**HEADERS}
    if referer:
        headers["Referer"] = referer
    time.sleep(random.uniform(2, 4))
    return session.get(url, impersonate="safari17_0", headers=headers)


def scrape():
    session = requests.Session()
    offers = []
    current_url = LISTING_URL
    prev_url = None

    while current_url:
        resp = _get(session, current_url, referer=prev_url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for article in soup.select("article.item"):
            link = article.select_one("a.item-link")
            if not link:
                continue

            title = link.get_text(strip=True)
            url = BASE_URL + link["href"]

            price_el = article.select_one("span.item-price")
            price = _clean_price(price_el.get_text(strip=True)) if price_el else "N/A"

            details = [el.get_text(strip=True) for el in article.select(".item-detail")]
            rooms = next((d for d in details if re.match(r"\d+ hab\.", d)), "N/A")
            surface = next((d for d in details if re.match(r"\d+\s*m²", d)), "N/A")

            zone = _parse_zone(title)

            desc_el = article.select_one(".item-description")
            description = " ".join(desc_el.get_text(" ", strip=True).split()) if desc_el else "N/A"

            m_id = re.search(r"/inmueble/(\d+)/", link["href"])
            offers.append({
                "id": m_id.group(1) if m_id else "N/A",
                "name": title,
                "price": price,
                "url": url,
                "rooms": rooms,
                "surface": surface,
                "zone": zone,
                "description": description,
            })

        next_link = soup.select_one("a.icon-arrow-right-after")
        prev_url = current_url
        current_url = BASE_URL + next_link["href"] if next_link else None

    return offers


def _clean_price(text):
    # "325.000€" → "325.000 €"
    return re.sub(r"(\d)€", r"\1 €", text)


def _parse_zone(title):
    """Extract zone from 'Piso en Street, Zone, City' or 'Piso en Zone, City'."""
    parts = [p.strip() for p in title.split(",")]
    
    # "Dúplex en Centre, Igualada" → extract after "en "
    m = re.search(r"\ben\s+(.+)$", parts[0])
    return m.group(1).strip() if m else "N/A"
