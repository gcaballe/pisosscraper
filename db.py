import os
from datetime import datetime
import pymysql
from dotenv import load_dotenv

load_dotenv()


def _connect():
    return pymysql.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", 3306)),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        charset="utf8mb4",
    )


def _ensure_tables(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scans (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            timestamp   DATETIME     NOT NULL,
            website     VARCHAR(50)  NOT NULL,
            house_count INT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS houses (
            id                    INT AUTO_INCREMENT PRIMARY KEY,
            scan_id               INT          NOT NULL,
            name                  VARCHAR(500),
            price                 VARCHAR(50),
            url                   VARCHAR(1000),
            rooms                 VARCHAR(50),
            surface               VARCHAR(50),
            zone                  VARCHAR(200),
            description           TEXT,
            external_id           VARCHAR(100),
            planta                TINYINT,
            ascensor              TINYINT(1),
            orientacion           VARCHAR(10),
            trastero              TINYINT(1),
            terraza               TINYINT(1),
            certificado_energetico VARCHAR(5),
            inmobiliaria          VARCHAR(200),
            FOREIGN KEY (scan_id) REFERENCES scans(id)
        )
    """)
    # Add columns to pre-existing tables that predate this schema
    for col, definition in [
        ("external_id",            "VARCHAR(100)"),
        ("planta",                 "TINYINT"),
        ("ascensor",               "TINYINT(1)"),
        ("orientacion",            "VARCHAR(10)"),
        ("trastero",               "TINYINT(1)"),
        ("terraza",                "TINYINT(1)"),
        ("certificado_energetico", "VARCHAR(5)"),
        ("inmobiliaria",           "VARCHAR(200)"),
    ]:
        cursor.execute(
            f"ALTER TABLE houses ADD COLUMN IF NOT EXISTS {col} {definition}"
        )


def _val(v):
    """Convert 'N/A' to NULL for cleaner storage."""
    return None if v == "N/A" else v


def save_scan(website, offers):
    conn = _connect()
    try:
        with conn.cursor() as cur:
            _ensure_tables(cur)
            cur.execute(
                "INSERT INTO scans (timestamp, website, house_count) VALUES (%s, %s, %s)",
                (datetime.now(), website, len(offers)),
            )
            scan_id = cur.lastrowid
            for offer in offers:
                cur.execute(
                    """INSERT INTO houses
                           (scan_id, name, price, url, rooms, surface, zone, description,
                            external_id, planta, ascensor, orientacion,
                            trastero, terraza, certificado_energetico, inmobiliaria)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                               %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        scan_id,
                        _val(offer.get("name")),
                        _val(offer.get("price")),
                        _val(offer.get("url")),
                        _val(offer.get("rooms")),
                        _val(offer.get("surface")),
                        _val(offer.get("zone")),
                        _val(offer.get("description")),
                        _val(offer.get("id")),
                        offer.get("planta"),
                        offer.get("ascensor"),
                        offer.get("orientacion"),
                        offer.get("trastero"),
                        offer.get("terraza"),
                        offer.get("certificado_energetico"),
                        offer.get("inmobiliaria"),
                    ),
                )
        conn.commit()
        print(f"[db] scan #{scan_id} saved — {len(offers)} house(s) for '{website}'")
    finally:
        conn.close()
