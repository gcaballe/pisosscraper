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
venv\Scripts\python run.py <portal> [--db] [--limit N]
```

**Portales disponibles:** `habitaclia`, `fotocasa`, `idealista`, `yaencontre`

| Argumento | Descripción |
|---|---|
| `<portal>` | Portal a scrapear (obligatorio) |
| `--db` | Guarda los resultados en MariaDB (requiere `.env` con credenciales) |
| `--limit N` | Detiene la extracción tras obtener N resultados. Útil para pruebas rápidas. |

```bash
# Obtener sólo los 5 primeros resultados de habitaclia
venv\Scripts\python run.py habitaclia --limit 5
```

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

### Guardar en base de datos

Luego ejecuta con `--db`:

```bash
venv\Scripts\python run.py idealista --db
```

### Ver en el navegador

```bash
venv\Scripts\python web.py
# abre http://127.0.0.1:5000
```

- `/` lista los scans con su conteo real de houses y un enlace `compare ↔ previous`
  que abre directamente la comparación con el scan anterior no vacío del mismo portal.
- `/houses` lista houses con filtros: texto libre, website, scan,
  zona, habitaciones, inmobiliaria, ascensor/terraza/trastero + paginación.
- `/house/<id>` muestra el detalle y el historial del mismo piso
  en distintos scans (agrupado por `external_id`, o por `url` si no hay).
- `/compare` compara dos scans del mismo portal. Se elige primero el portal
  (pestañas) y luego los dos scans por fecha; por defecto muestra el último scan
  frente al anterior, y los enlaces `◀ previous week` / `next week ▶` desplazan
  ambos a la vez. Los scans vacíos (0 houses) no se ofrecen. Resultado: lista
  ordenada por diferencia de precio con estados `NEW`, `REMOVED`,
  `PRICE DIFF ±X€` o sin cambios, más gráfico circular con el resumen.
  Las URLs antiguas (`/compare?old_id=24&new_id=28`) siguen funcionando.

## Técnica por portal

Todos los scrapers usan `curl_cffi` con impersonación de Chrome para evadir la detección de bots por TLS fingerprint. Cada scraper devuelve una lista de dicts con `id`, `name`, `price`, `url` y, opcionalmente, `rooms`, `surface`, `zone` y `description`.

| Portal | Método |
|---|---|
| **Habitaclia** | GET SSR. Desde el rediseño de 2026 el portal usa la misma plataforma que Fotocasa: la página de listado embebe un JSON en `window.__INITIAL_PROPS__` (`initialSearchResultsPage.initialSearchContext.results`) con 29 ofertas por página (título, precio, habitaciones, superficie, barrio, descripción, URL, planta, ascensor, orientación, trastero, terraza, certificado energético e inmobiliaria). Se extrae todo del listado sin acceder a fichas de detalle. Paginación mediante `/s/N?maxPrice=...` hasta `pagination.totalPages`. Se usa `legacyNumericId` como `id` para mantener la continuidad con los scans antiguos. |
| **Fotocasa** | GET SSR. La página de listado embebe un JSON inline (`initialSearch.result.realEstates`) con las 30 primeras ofertas incluyendo URL y precio. Se accede a la ficha de detalle para obtener el nombre (`h1`) y confirmar el precio (texto con regex `\d+\.\d{3} €`). |
| **Idealista** | GET SSR con impersonación `safari17_2_ios` (DataDome rechaza con 403 el resto de huellas TLS, incluida la antigua `safari17_0`). La página de listado contiene los datos en `article.item`; se recogen las URLs (`a.item-link`) y se accede a cada ficha de detalle para extraer título (`h1`), precio (`span.info-data-price`), características (`.details-property_features li`: habitaciones, superficie, planta, ascensor, orientación, trastero, terraza), zona (`#headerMap li` → "Distrito X"), certificado energético (`span.icon-energy-c-<letra>`), inmobiliaria (`.about-advertiser-name`) y descripción (`div.adCommentsLanguage`). Paginación mediante `a.icon-arrow-right-after`. |
| **Yaencontre** | GET SSR con impersonación `safari18_0` (DataDome rechaza con 403 la mayoría de huellas TLS, incluida la antigua `safari17_0`). Tanto el listado como la ficha embeben el estado de la app en `window.__INITIAL_STATE__` (JSON en base64). Del listado se obtienen las referencias (`results.currentPageItems`) y la paginación (`pagination.numPages`, `/pag-N`); de cada ficha (`details.item`) se extraen título, precio, habitaciones, superficie, zona, descripción completa, planta, ascensor, orientación, trastero, terraza (`businessFeatures`), certificado energético (`energyCertificateRating`) e inmobiliaria (`owner.name`). Se reutiliza la misma sesión para conservar la cookie `datadome`. |

