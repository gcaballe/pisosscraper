import re
import time
import random
from urllib.parse import urljoin
from curl_cffi import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

LISTING_URL = "https://www.yaencontre.com/venta/pisos/igualada/f--250000euros"
BASE_URL = "https://www.yaencontre.com"
HEADERS = {"Accept-Language": "es-ES,es;q=0.9"}

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
    resp = session.get(url, impersonate="safari17_0", headers=headers)
    time.sleep(random.uniform(2, 4))
    return resp


def scrape(limit=None):
    session = requests.Session()
    ids = []
    page = 1
    prev_url = None

    while True:
        url = LISTING_URL if page == 1 else f"{LISTING_URL}/pag-{page}"
        resp = _get(session, url, referer=prev_url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        seen = set()
        for a in soup.find_all("a", href=re.compile(r"/venta/piso/inmueble-")):
            m = re.search(r"/inmueble-(.+?)(?:/|$)", a["href"])
            if m and m.group(1) not in seen:
                seen.add(m.group(1))
                ids.append(m.group(1))
                if limit is not None and len(ids) >= limit:
                    break

        if not seen:
            break

        if limit is not None and len(ids) >= limit:
            break

        prev_url = url
        page += 1
        listing_path = LISTING_URL.replace(BASE_URL, "")
        if not soup.find("a", href=f"{listing_path}/pag-{page}"):
            break

    offers = []
    for property_id in tqdm(ids, desc="Scraping details", unit="property"):
        offers.append(scrape_individual(property_id))

    return offers


def scrape_individual(property_id):
    url = f"{BASE_URL}/venta/piso/inmueble-{property_id}"
    session = requests.Session()

    # Step 1: warm up through listing
    r0 = _get(session, LISTING_URL)
    r0.raise_for_status()

    # Step 2: visit one real listing item to establish session trust
    soup0 = BeautifulSoup(r0.text, "html.parser")
    first_link = soup0.find("a", href=re.compile(r"/venta/piso/inmueble-"))
    if first_link:
        warmup_url = urljoin(BASE_URL, first_link["href"])
        if warmup_url != url:
            _get(session, warmup_url, referer=LISTING_URL)

    resp = _get(session, url, referer=LISTING_URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    return _parse_detail(soup, url)


def _parse_detail(soup, url):
    m_id = re.search(r"/inmueble-(.+?)(?:/|$)", url)

    title_el = soup.select_one("h1")
    title = title_el.get_text(strip=True) if title_el else "N/A"

    price_el = soup.select_one(".heading-text-l.c-content-primary")
    price = price_el.get_text(strip=True) if price_el else "N/A"

    rooms_el = soup.select_one(".icon-room span")
    rooms_text = rooms_el.get_text(strip=True) if rooms_el else None
    rooms = f"{rooms_text} hab." if rooms_text else "N/A"

    surface_el = soup.select_one(".icon-meter span")
    surface = surface_el.get_text(strip=True) if surface_el else "N/A"

    # Zone from location section
    zone = "N/A"
    loc_el = soup.select_one(".details-location")
    if loc_el:
        for s in loc_el.stripped_strings:
            s = s.strip()
            if "," in s and s != "Ubicación":
                zone = s.split(",")[0].strip()
                break

    features = [li.get_text(" ", strip=True) for li in soup.select(".characteristics li")]

    # Planta
    planta = None
    for f in features:
        m = re.search(r"[Pp]lanta\s+(\d+)", f)
        if m:
            planta = int(m.group(1))
            break

    # Ascensor
    ascensor = 0
    for f in features:
        if re.search(r"^ascensor$", f, re.IGNORECASE):
            ascensor = 1
            break

    # Orientacion
    orientacion = None
    for f in features:
        m = re.search(r"[Oo]rientad[oa]\s+a[:\s]+(\w+)", f, re.IGNORECASE)
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
    cert_el = soup.select_one(".energy-letter[data-rating]")
    cert = None
    if cert_el:
        rating = cert_el.get("data-rating", "").upper()
        cert = rating or None

    # Inmobiliaria
    agency_el = soup.select_one(".agency-info p.name")
    inmobiliaria = agency_el.get_text(strip=True) or None if agency_el else None

    # Description
    desc_el = soup.select_one(".raw-format.description")
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


def _parse_zone(name):
    """Extract zone from 'Piso en Zone, City' → Zone"""
    m = re.search(r"\ben\s+(.+?)(?:,|$)", name)
    return m.group(1).strip() if m else "N/A"
