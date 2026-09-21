"""Simple read-only web viewer for scans + houses. Run: venv\\Scripts\\python web.py"""
import argparse
import re

import pymysql.cursors
from flask import Flask, g, render_template_string, request, url_for

import db

app = Flask(__name__)

PER_PAGE_DEFAULT = 50

BASE_CSS = """
body{font-family:system-ui,sans-serif;max-width:1100px;margin:20px auto;padding:0 16px;color:#222}
nav a{margin-right:12px}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{border:1px solid #ddd;padding:6px 8px;text-align:left;vertical-align:top}
th{background:#f4f4f4}
form.filters{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}
form.filters input,form.filters select{padding:4px 6px}
.muted{color:#666;font-size:13px}
.badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px;font-weight:bold}
.b-new{background:#dcfce7;color:#166534}
.b-removed{background:#fee2e2;color:#991b1b}
.b-changed{background:#fef3c7;color:#92400e}
.pie{width:180px;height:180px;border-radius:50%;margin:10px 0}
.legend{font-size:14px;line-height:1.8}
.dot{display:inline-block;width:12px;height:12px;border-radius:50%;margin-right:6px}
.diff-up{color:#166534}.diff-down{color:#991b1b}
"""

SCANS_TPL = """
<!doctype html><html><head><meta charset="utf-8"><title>Scans</title>
<style>{{css}}</style></head><body>
<nav><a href="{{url_for('scans')}}">Scans</a><a href="{{url_for('houses')}}">Houses</a><a href="{{url_for('compare')}}">Compare</a></nav>
<h1>Scans ({{scans|length}})</h1>
<table><tr><th>ID</th><th>Date</th><th>Website</th><th>Houses</th><th></th></tr>
{% for s in scans %}
<tr><td>{{s.id}}</td><td>{{s.timestamp}}</td><td>{{s.website}}</td>
<td>{{s.real_count}}</td>
<td><a href="{{url_for('houses')}}?scan_id={{s.id}}">view</a></td></tr>
{% endfor %}</table>
<p class="muted">Total houses: {{total}}</p>
</body></html>
"""

HOUSES_TPL = """
<!doctype html><html><head><meta charset="utf-8"><title>Houses</title>
<style>{{css}}</style></head><body>
<nav><a href="{{url_for('scans')}}">Scans</a><a href="{{url_for('houses')}}">Houses</a><a href="{{url_for('compare')}}">Compare</a></nav>
<h1>Houses</h1>
<form class="filters" method="get">
<input name="q" placeholder="search name/zone/desc/id/url" value="{{f.q}}">
<select name="website"><option value="">all websites</option>
{% for w in websites %}<option value="{{w}}" {% if f.website==w %}selected{% endif %}>{{w}}</option>{% endfor %}</select>
<select name="scan_id"><option value="">all scans</option>
{% for s in scans %}<option value="{{s.id}}" {% if f.scan_id==s.id|string %}selected{% endif %}>#{{s.id}} {{s.website}} {{s.timestamp}}</option>{% endfor %}</select>
<input name="zone" placeholder="zone contains" value="{{f.zone}}">
<select name="rooms"><option value="">all rooms</option>
{% for r in rooms %}<option {% if f.rooms==r %}selected{% endif %}>{{r}}</option>{% endfor %}</select>
<input name="inmobiliaria" placeholder="inmobiliaria" value="{{f.inmobiliaria}}">
<select name="ascensor"><option value="">ascensor?</option><option value="1" {% if f.ascensor=='1' %}selected{% endif %}>yes</option><option value="0" {% if f.ascensor=='0' %}selected{% endif %}>no</option></select>
<select name="terraza"><option value="">terraza?</option><option value="1" {% if f.terraza=='1' %}selected{% endif %}>yes</option><option value="0" {% if f.terraza=='0' %}selected{% endif %}>no</option></select>
<select name="trastero"><option value="">trastero?</option><option value="1" {% if f.trastero=='1' %}selected{% endif %}>yes</option><option value="0" {% if f.trastero=='0' %}selected{% endif %}>no</option></select>
<button type="submit">Filter</button>
<a href="{{url_for('houses')}}">clear</a>
</form>
<p class="muted">{{total}} result(s) — page {{page}} of {{pages}}</p>
<table><tr><th>ID</th><th>Name</th><th>Price</th><th>Rooms</th><th>Surface</th><th>Zone</th><th>Website / Scan</th><th>Ext. ID</th></tr>
{% for h in rows %}
<tr><td><a href="{{url_for('house_detail', hid=h.id)}}">{{h.id}}</a></td>
<td><a href="{{url_for('house_detail', hid=h.id)}}">{{h.name or '—'}}</a><br><span class="muted">{{h.inmobiliaria or ''}}</span></td>
<td>{{h.price or '—'}}</td><td>{{h.rooms or '—'}}</td><td>{{h.surface or '—'}}</td>
<td>{{h.zone or '—'}}</td><td>{{h.website}} #{{h.scan_id}}<br><span class="muted">{{h.timestamp}}</span></td>
<td>{{h.external_id or '—'}}</td></tr>
{% endfor %}</table>
<p>{% if page>1 %}<a href="{{prev_url}}">← prev</a>{% endif %}
{% if page<pages %}<a href="{{next_url}}">next →</a>{% endif %}</p>
</body></html>
"""

DETAIL_TPL = """
<!doctype html><html><head><meta charset="utf-8"><title>House {{h.id}}</title>
<style>{{css}}</style></head><body>
<nav><a href="{{url_for('scans')}}">Scans</a><a href="{{url_for('houses')}}">Houses</a><a href="{{url_for('compare')}}">Compare</a></nav>
<h1>{{h.name or 'House #%d' % h.id}}</h1>
<p><b>{{h.price or '—'}}</b> · {{h.rooms or '—'}} · {{h.surface or '—'}} · {{h.zone or '—'}}</p>
<p class="muted">Seen in {{h.website}} scan #{{h.scan_id}} ({{h.timestamp}}) · ext_id={{h.external_id or '—'}}</p>
{% if h.url %}<p><a href="{{h.url}}" target="_blank">original listing ↗</a></p>{% endif %}
<table>
<tr><th>field</th><th>value</th></tr>
<tr><td>description</td><td>{{h.description or '—'}}</td></tr>
<tr><td>inmobiliaria</td><td>{{h.inmobiliaria or '—'}}</td></tr>
<tr><td>planta</td><td>{{h.planta if h.planta is not none else '—'}}</td></tr>
<tr><td>ascensor</td><td>{{h.ascensor if h.ascensor is not none else '—'}}</td></tr>
<tr><td>orientacion</td><td>{{h.orientacion or '—'}}</td></tr>
<tr><td>trastero</td><td>{{h.trastero if h.trastero is not none else '—'}}</td></tr>
<tr><td>terraza</td><td>{{h.terraza if h.terraza is not none else '—'}}</td></tr>
<tr><td>certificado_energetico</td><td>{{h.certificado_energetico or '—'}}</td></tr>
<tr><td>url</td><td style="word-break:break-all">{{h.url or '—'}}</td></tr>
</table>
<h2>History across scans ({{history|length}})</h2>
<p class="muted">Matched by {% if h.external_id %}external_id={{h.external_id}}{% else %}url{% endif %}</p>
<table><tr><th>Row</th><th>Scan</th><th>Date</th><th>Price</th><th>Name</th></tr>
{% for r in history %}
<tr {% if r.id==h.id %}style="background:#ffe"{% endif %}>
<td><a href="{{url_for('house_detail', hid=r.id)}}">{{r.id}}</a></td>
<td>#{{r.scan_id}} ({{r.website}})</td><td>{{r.timestamp}}</td>
<td>{{r.price or '—'}}</td><td>{{r.name or '—'}}</td></tr>
{% endfor %}</table>
</body></html>
"""


def get_conn():
    if "conn" not in g:
        conn = db._connect()
        g.conn = conn
    return g.conn


@app.teardown_appcontext
def close_conn(_exc=None):
    conn = g.pop("conn", None)
    if conn is not None:
        conn.close()


def qdict(cur, sql, args=()):
    cur.execute(sql, args)
    return cur.fetchall()


@app.route("/")
def scans():
    conn = get_conn()
    with conn.cursor(pymysql.cursors.DictCursor) as cur:
        scan_rows = qdict(cur, "SELECT id, timestamp, website, house_count FROM scans ORDER BY id DESC")
        for s in scan_rows:
            cur.execute("SELECT COUNT(*) AS c FROM houses WHERE scan_id=%s", (s["id"],))
            s["real_count"] = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM houses")
        total = cur.fetchone()["c"]
    return render_template_string(SCANS_TPL, css=BASE_CSS, scans=scan_rows, total=total)


def _house_filters(args):
    where, params = [], []
    f = {
        "q": args.get("q", "").strip(),
        "website": args.get("website", "").strip(),
        "scan_id": args.get("scan_id", "").strip(),
        "zone": args.get("zone", "").strip(),
        "rooms": args.get("rooms", "").strip(),
        "inmobiliaria": args.get("inmobiliaria", "").strip(),
        "ascensor": args.get("ascensor", "").strip(),
        "terraza": args.get("terraza", "").strip(),
        "trastero": args.get("trastero", "").strip(),
    }
    if f["website"]:
        where.append("s.website = %s")
        params.append(f["website"])
    if f["scan_id"] and f["scan_id"].isdigit():
        where.append("h.scan_id = %s")
        params.append(int(f["scan_id"]))
    if f["zone"]:
        where.append("h.zone LIKE %s")
        params.append(f"%{f['zone']}%")
    if f["rooms"]:
        where.append("h.rooms = %s")
        params.append(f["rooms"])
    if f["inmobiliaria"]:
        where.append("h.inmobiliaria LIKE %s")
        params.append(f"%{f['inmobiliaria']}%")
    for col in ("ascensor", "terraza", "trastero"):
        if f[col] in ("0", "1"):
            where.append(f"h.{col} = %s")
            params.append(int(f[col]))
    if f["q"]:
        like = f"%{f['q']}%"
        where.append("(h.name LIKE %s OR h.zone LIKE %s OR h.description LIKE %s"
                     " OR h.external_id LIKE %s OR h.url LIKE %s OR h.inmobiliaria LIKE %s)")
        params.extend([like] * 6)
    return f, where, params


def _page_url(page, args):
    d = dict(args)
    d["page"] = page
    qs = "&".join(f"{k}={v}" for k, v in d.items() if v != "")
    return url_for("houses") + ("?" + qs if qs else "")


@app.route("/houses")
def houses():
    page = max(int(request.args.get("page", 1) or 1), 1)
    per_page = min(int(request.args.get("per_page", PER_PAGE_DEFAULT) or PER_PAGE_DEFAULT), 200)
    f, where, params = _house_filters(request.args)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    conn = get_conn()
    with conn.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute(f"SELECT COUNT(*) AS c FROM houses h JOIN scans s ON h.scan_id=s.id {where_sql}", params)
        total = cur.fetchone()["c"]
        pages = max((total + per_page - 1) // per_page, 1)
        page = min(page, pages)
        cur.execute(
            "SELECT h.*, s.website, s.timestamp FROM houses h "
            f"JOIN scans s ON h.scan_id=s.id {where_sql} "
            "ORDER BY h.id DESC LIMIT %s OFFSET %s",
            (*params, per_page, (page - 1) * per_page),
        )
        rows = cur.fetchall()
        websites = [r["website"] for r in qdict(cur, "SELECT DISTINCT website FROM scans ORDER BY 1")]
        scan_rows = qdict(cur, "SELECT id, website, timestamp FROM scans ORDER BY id DESC")
        rooms = [r["rooms"] for r in qdict(cur, "SELECT DISTINCT rooms FROM houses WHERE rooms IS NOT NULL ORDER BY 1")]
    args = {k: request.args.get(k, "") for k in
            ("q", "website", "scan_id", "zone", "rooms", "inmobiliaria", "ascensor", "terraza", "trastero", "per_page")}
    return render_template_string(
        HOUSES_TPL, css=BASE_CSS, rows=rows, total=total, page=page, pages=pages,
        f=f, websites=websites, scans=scan_rows, rooms=rooms,
        prev_url=_page_url(page - 1, args), next_url=_page_url(page + 1, args),
    )


@app.route("/house/<int:hid>")
def house_detail(hid):
    conn = get_conn()
    with conn.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute("SELECT h.*, s.website, s.timestamp FROM houses h "
                    "JOIN scans s ON h.scan_id=s.id WHERE h.id=%s", (hid,))
        h = cur.fetchone()
        if h is None:
            return "Not found", 404
        if h.get("external_id"):
            cur.execute("SELECT h.id, h.scan_id, h.name, h.price, s.website, s.timestamp "
                        "FROM houses h JOIN scans s ON h.scan_id=s.id "
                        "WHERE h.external_id=%s ORDER BY s.timestamp", (h["external_id"],))
        else:
            cur.execute("SELECT h.id, h.scan_id, h.name, h.price, s.website, s.timestamp "
                        "FROM houses h JOIN scans s ON h.scan_id=s.id "
                        "WHERE h.url=%s ORDER BY s.timestamp", (h["url"],))
        history = cur.fetchall()
    return render_template_string(DETAIL_TPL, css=BASE_CSS, h=h, history=history)


COMPARE_TPL = """
<!doctype html><html><head><meta charset="utf-8"><title>Scan comparator</title>
<style>{{css}}</style></head><body>
<nav><a href="{{url_for('scans')}}">Scans</a><a href="{{url_for('houses')}}">Houses</a><a href="{{url_for('compare')}}">Compare</a></nav>
<h1>Scan comparator</h1>
<form class="filters" method="get">
<select name="old_id">{% for s in scans %}<option value="{{s.id}}" {% if old_id==s.id %}selected{% endif %}>{{s.website}} #{{s.id}} {{s.timestamp}} ({{s.n}})</option>{% endfor %}</select>
<span>→</span>
<select name="new_id">{% for s in scans %}<option value="{{s.id}}" {% if new_id==s.id %}selected{% endif %}>{{s.website}} #{{s.id}} {{s.timestamp}} ({{s.n}})</option>{% endfor %}</select>
<select name="show">
<option value="all" {% if show=='all' %}selected{% endif %}>all</option>
<option value="changed" {% if show=='changed' %}selected{% endif %}>price changed</option>
<option value="new" {% if show=='new' %}selected{% endif %}>NEW only</option>
<option value="removed" {% if show=='removed' %}selected{% endif %}>REMOVED only</option>
<option value="same" {% if show=='same' %}selected{% endif %}>unchanged only</option>
</select>
<button type="submit">Compare</button>
</form>
{% if error %}<p><b>{{error}}</b></p></body></html>
{% elif not rows is none %}
<h2>{{old.website}} #{{old.id}} ({{old.timestamp}}) → #{{new.id}} ({{new.timestamp}})</h2>
<div class="pie" style="background:{{pie_style}}"></div>
<div class="legend">
<span class="dot" style="background:#22c55e"></span>NEW: {{stats.new}}<br>
<span class="dot" style="background:#ef4444"></span>REMOVED: {{stats.removed}}<br>
<span class="dot" style="background:#f59e0b"></span>PRICE DIFF: {{stats.changed}}<br>
<span class="dot" style="background:#d1d5db"></span>unchanged: {{stats.same}}<br>
<span class="muted">total unique: {{stats.total}}</span>
</div>
<p class="muted">{{rows|length}} row(s) shown</p>
<table><tr><th>Status</th><th>Name</th><th>Old price</th><th>New price</th><th>Diff</th><th>Ext. ID</th></tr>
{% for r in rows %}
<tr><td>{% if r.status=='NEW' %}<span class="badge b-new">NEW</span>{% elif r.status=='REMOVED' %}<span class="badge b-removed">REMOVED</span>{% elif r.status %}<span class="badge b-changed">{{r.status}}</span>{% else %}—{% endif %}</td>
<td>{% if r.link_id %}<a href="{{url_for('house_detail', hid=r.link_id)}}">{{r.name}}</a>{% else %}{{r.name}}{% endif %}<br><span class="muted">{{r.zone or ''}}</span></td>
<td>{{r.old_price or '—'}}</td><td>{{r.new_price or '—'}}</td>
<td class="{% if r.diff and r.diff>0 %}diff-up{% elif r.diff and r.diff<0 %}diff-down{% endif %}">{{r.diff_str or '—'}}</td>
<td>{{r.key}}</td></tr>
{% endfor %}</table>
{% endif %}
</body></html>
"""


def _price_num(s):
    if not s:
        return None
    digits = re.sub(r"[^0-9]", "", s)
    return int(digits) if digits else None


def _fmt_diff(d):
    if d is None:
        return ""
    sign = "+" if d > 0 else ""
    return f"{sign}{d:,}".replace(",", ".") + "€"


def _row_key(r):
    ext = (r.get("external_id") or "").strip()
    if ext:
        return ext
    return (r.get("url") or f"id:{r['id']}").strip()


@app.route("/compare")
def compare():
    conn = get_conn()
    with conn.cursor(pymysql.cursors.DictCursor) as cur:
        scans = qdict(cur, "SELECT s.id, s.website, s.timestamp, COUNT(h.id) AS n "
                            "FROM scans s LEFT JOIN houses h ON h.scan_id=s.id "
                            "GROUP BY s.id ORDER BY s.id DESC")
    if not scans:
        return render_template_string(COMPARE_TPL, css=BASE_CSS, scans=[], rows=None, error="No scans yet.")
    try:
        old_id = int(request.args.get("old_id", scans[-1]["id"]))
        new_id = int(request.args.get("new_id", scans[0]["id"]))
    except (TypeError, ValueError):
        return render_template_string(COMPARE_TPL, css=BASE_CSS, scans=scans, rows=None,
                                      error="Invalid scan ids.", old_id=None, new_id=None, show="all")
    show = request.args.get("show", "all")
    meta = {s["id"]: s for s in scans}
    if old_id not in meta or new_id not in meta:
        return render_template_string(COMPARE_TPL, css=BASE_CSS, scans=scans, rows=None,
                                      error="Unknown scan id.", old_id=old_id, new_id=new_id, show=show)
    old, new = meta[old_id], meta[new_id]
    if old["website"] != new["website"]:
        return render_template_string(COMPARE_TPL, css=BASE_CSS, scans=scans, rows=None,
                                      error=f"Pick two scans of the same website (old={old['website']}, new={new['website']}).",
                                      old_id=old_id, new_id=new_id, show=show)
    conn = get_conn()
    with conn.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute("SELECT id, name, price, url, external_id, zone FROM houses WHERE scan_id=%s", (old_id,))
        old_rows = cur.fetchall()
        cur.execute("SELECT id, name, price, url, external_id, zone FROM houses WHERE scan_id=%s", (new_id,))
        new_rows = cur.fetchall()
    om = {_row_key(r): r for r in old_rows}
    nm = {_row_key(r): r for r in new_rows}
    rows, stats = [], {"new": 0, "removed": 0, "changed": 0, "same": 0}
    for key in om.keys() | nm.keys():
        o, n = om.get(key), nm.get(key)
        on, nn = _price_num(o["price"]) if o else None, _price_num(n["price"]) if n else None
        if o is None:
            rows.append({"key": key, "name": n["name"], "zone": n["zone"], "old_price": None,
                         "new_price": n["price"], "diff": None, "diff_str": "",
                         "status": "NEW", "link_id": n["id"]})
            stats["new"] += 1
        elif n is None:
            rows.append({"key": key, "name": o["name"], "zone": o["zone"], "old_price": o["price"],
                         "new_price": None, "diff": None, "diff_str": "",
                         "status": "REMOVED", "link_id": o["id"]})
            stats["removed"] += 1
        elif on is not None and nn is not None and on != nn:
            d = nn - on
            rows.append({"key": key, "name": n["name"] or o["name"], "zone": n["zone"] or o["zone"],
                         "old_price": o["price"], "new_price": n["price"], "diff": d,
                         "diff_str": f"PRICE DIFF {_fmt_diff(d)}", "status": f"PRICE DIFF {_fmt_diff(d)}",
                         "link_id": n["id"]})
            stats["changed"] += 1
        else:
            rows.append({"key": key, "name": (n["name"] or o["name"]), "zone": n["zone"] or o["zone"],
                         "old_price": o["price"], "new_price": n["price"], "diff": 0,
                         "diff_str": "", "status": "", "link_id": n["id"]})
            stats["same"] += 1
    stats["total"] = len(rows)
    # biggest absolute price move first, then NEW, REMOVED, unchanged last
    rows.sort(key=lambda r: (r["status"] in ("NEW", "REMOVED", ""),
                             -abs(r["diff"] or 0), r["name"] or ""))
    if show == "changed":
        rows = [r for r in rows if r["status"].startswith("PRICE DIFF")]
    elif show == "new":
        rows = [r for r in rows if r["status"] == "NEW"]
    elif show == "removed":
        rows = [r for r in rows if r["status"] == "REMOVED"]
    elif show == "same":
        rows = [r for r in rows if not r["status"]]
    total = max(stats["total"], 1)
    pn, pr, pc, ps = (stats["new"] / total * 100, stats["removed"] / total * 100,
                      stats["changed"] / total * 100, stats["same"] / total * 100)
    pie_style = (f"conic-gradient(#22c55e 0% {pn:.1f}%, #ef4444 {pn:.1f}% {pn+pr:.1f}%, "
                 f"#f59e0b {pn+pr:.1f}% {pn+pr+pc:.1f}%, #d1d5db {pn+pr+pc:.1f}% 100%)")
    return render_template_string(COMPARE_TPL, css=BASE_CSS, scans=scans, rows=rows,
                                  old_id=old_id, new_id=new_id, show=show,
                                  old=old, new=new, stats=stats, pie_style=pie_style, error=None)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=5000)
    a = p.parse_args()
    app.run(host="127.0.0.1", port=a.port, debug=True)
