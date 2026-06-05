import re
import time
import random
from curl_cffi import requests
from bs4 import BeautifulSoup

LISTING_URL = "https://www.idealista.com/venta-viviendas/igualada-barcelona/con-precio-hasta_180000/"
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


def scrape_individual(property_id):
    url = f"{BASE_URL}/inmueble/{property_id}/"
    session = requests.Session()
    # Warm up session through listing page to avoid bot challenge
    _get(session, LISTING_URL)
    resp = _get(session, url, referer=LISTING_URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    return _parse_detail(soup, url)


def _parse_detail(soup, url):
    m_id = re.search(r"/inmueble/(\d+)/", url)

    title_el = soup.select_one("h1")
    title = title_el.get_text(strip=True) if title_el else "N/A"

    price_el = soup.select_one("span.info-data-price")
    price = _clean_price(price_el.get_text(strip=True)) if price_el else "N/A"

    features = [li.get_text(" ", strip=True) for li in soup.select(".details-property_features li")]
    features_text = " | ".join(features)

    m_rooms = re.search(r"(\d+)\s*habitaci[oó]n", features_text, re.IGNORECASE)
    rooms = f"{m_rooms.group(1)} hab." if m_rooms else "N/A"

    m_surface = re.search(r"(\d+)\s*m²", features_text)
    surface = f"{m_surface.group(1)} m²" if m_surface else "N/A"

    zone = _parse_zone(title)

    # Planta
    planta = None
    for f in features:
        m = re.search(r"(\d+)[ªaáo°]\s*planta", f, re.IGNORECASE)
        if m:
            planta = m.group(1)
            break

    # Ascensor
    ascensor = None
    for f in features:
        if re.search(r"con\s+ascensor", f, re.IGNORECASE):
            ascensor = 1
            break
        if re.search(r"sin\s+ascensor", f, re.IGNORECASE):
            ascensor = 0
            break

    # Orientación → compass code
    _ORIENT_MAP = {
        "sureste": "SE", "suroeste": "SO", "noreste": "NE", "noroeste": "NO",
        "sudeste": "SE", "sudoeste": "SO",
        "sur": "S", "sud": "S", "norte": "N", "nord": "N",
        "este": "E", "est": "E", "oeste": "O", "oest": "O",
    }
    orientacion = None
    for f in features:
        m = re.search(r"orientaci[oó]n\s+(\w+)", f, re.IGNORECASE)
        if m:
            orientacion = _ORIENT_MAP.get(m.group(1).lower(), m.group(1).upper())
            break

    # Trastero / Terraza
    trastero = 0
    for f in features:
        if re.search(r"trastero", f, re.IGNORECASE):
            trastero = 1
            break

    terraza = 0
    for f in features:
        if re.search(r"terraza", f, re.IGNORECASE):
            terraza = 1
            break

    # Certificado energético
    cert_el = soup.find("span", class_=re.compile(r"icon-energy-"))
    cert = None
    if cert_el:
        m = re.search(r"icon-energy-([a-zA-Z])", " ".join(cert_el.get("class", [])))
        if m:
            cert = m.group(1).upper()

    # Inmobiliaria
    adv_el = soup.select_one("p.advertiser-name")
    inmobiliaria = None
    if adv_el:
        raw = adv_el.get_text(strip=True)
        inmobiliaria = re.sub(r"\s*\.\s*$", "", raw).strip() or None

    # Description
    desc_el = soup.select_one("div.adCommentsLanguage")
    description = " ".join(desc_el.get_text(" ", strip=True).split()) if desc_el else None

    return {
        "id": m_id.group(1) if m_id else "N/A",
        "name": title,
        "price": price,
        "url": url,
        "rooms": rooms,
        "surface": surface,
        "zone": zone,
        "description": description,
        "planta": planta,
        "ascensor": ascensor,
        "orientacion": orientacion,
        "trastero": trastero,
        "terraza": terraza,
        "certificado_energetico": cert,
        "inmobiliaria": inmobiliaria,
    }



def _clean_price(text):
    # "325.000€" → "325.000 €"
    return re.sub(r"(\d)€", r"\1 €", text)


def _parse_zone(title):
    """Extract zone from 'Piso en Street, Zone, City' or 'Piso en Zone, City'."""
    parts = [p.strip() for p in title.split(",")]
    
    # "Dúplex en Centre, Igualada" → extract after "en "
    m = re.search(r"\ben\s+(.+)$", parts[0])
    return m.group(1).strip() if m else "N/A"
