# pisosscraper
Scraper de pisos en venta para Igualada (y alrededores).

## Instalación

Requiere Python 3.10+.

```bash
git clone https://github.com/tu-usuario/pisosscraper.git
cd pisosscraper
python -m venv venv
venv\Scripts\pip install -r requirements.txt
```

## Uso

```bash
venv\Scripts\python run.py <portal>
```

**Portales disponibles:** `habitaclia`, `fotocasa`, `idealista`

**Salida:**
```
Name:  Pis en venda a Ponent - Set Camins
Price: 250.000 €
URL:   https://www.fotocasa.es/ca/comprar/vivenda/igualada/...

Name:  Piso en Rambla de Sant Isidre, Centre, Igualada
Price: 325.000 €
Rooms: 4 hab.
Surface: 125 m²
Zone:  Centre
Desc:  En la Rambla de Igualada, dond
URL:   https://www.idealista.com/inmueble/109584182/
```

Devuelve las 3 primeras ofertas de cada portal.

## Técnica por portal

Todos los scrapers usan `curl_cffi` con impersonación de Chrome para evadir la detección de bots por TLS fingerprint. Cada scraper devuelve una lista de dicts con `name`, `price`, `url` y, opcionalmente, `rooms`, `surface`, `zone` y `description`.

| Portal | Método |
|---|---|
| **Habitaclia** | GET SSR. Se parsea la página de listado con BeautifulSoup para obtener las URLs (`h3 a[href*='/comprar-']`), luego se accede a cada ficha de detalle para extraer nombre (`h1`) y precio (`span.font-2` con regex de formato miles). Protegido por Imperva. |
| **Fotocasa** | GET SSR. La página de listado embebe un JSON inline (`initialSearch.result.realEstates`) con las 30 primeras ofertas incluyendo URL y precio. Se accede a la ficha de detalle para obtener el nombre (`h1`) y confirmar el precio (texto con regex `\d+\.\d{3} €`). |
| **Idealista** | GET SSR con impersonación `safari17_0` (necesaria para evadir Cloudflare). La página de listado contiene los datos en `article.item`. Se extraen directamente del listado sin acceder a fichas de detalle: precio (`span.item-price`), habitaciones y superficie (`span.item-detail`), zona (parseada del título del enlace) y descripción (`.item-description`). |

