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

- `/` lista los scans con su conteo real de houses.
- `/houses` lista houses con filtros: texto libre, website, scan,
  zona, habitaciones, inmobiliaria, ascensor/terraza/trastero + paginación.
- `/house/<id>` muestra el detalle y el historial del mismo piso
  en distintos scans (agrupado por `external_id`, o por `url` si no hay).
- `/compare?old_id=24&new_id=28` compara dos scans del mismo website:
  lista ordenada por diferencia de precio con estados `NEW`, `REMOVED`,
  `PRICE DIFF ±X€` o sin cambios, más gráfico circular con el resumen.

## Técnica por portal

Todos los scrapers usan `curl_cffi` con impersonación de Chrome para evadir la detección de bots por TLS fingerprint. Cada scraper devuelve una lista de dicts con `id`, `name`, `price`, `url` y, opcionalmente, `rooms`, `surface`, `zone` y `description`.

| Portal | Método |
|---|---|
| **Habitaclia** | GET SSR. Se parsea la página de listado con BeautifulSoup para obtener las URLs (`h3 a[href*='/comprar-']`), luego se accede a cada ficha de detalle para extraer nombre (`h1`) y precio (`span.font-2` con regex de formato miles). Protegido por Imperva. |
| **Fotocasa** | GET SSR. La página de listado embebe un JSON inline (`initialSearch.result.realEstates`) con las 30 primeras ofertas incluyendo URL y precio. Se accede a la ficha de detalle para obtener el nombre (`h1`) y confirmar el precio (texto con regex `\d+\.\d{3} €`). |
| **Idealista** | GET SSR con impersonación `safari17_0` (necesaria para evadir Cloudflare). La página de listado contiene los datos en `article.item`. Se extraen directamente del listado sin acceder a fichas de detalle: precio (`span.item-price`), habitaciones y superficie (`span.item-detail`), zona (parseada del título del enlace) y descripción (`.item-description`). |
| **Yaencontre** | GET SSR. Se detectan los enlaces `a[href*='/venta/piso/inmueble-']` y se sube el árbol DOM hasta el contenedor de la tarjeta para extraer precio, habitaciones, superficie y descripción mediante regex sobre el texto plano. Paginación mediante `/pag-N`. |

