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
            id        INT AUTO_INCREMENT PRIMARY KEY,
            timestamp DATETIME     NOT NULL,
            website   VARCHAR(50)  NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS houses (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            scan_id     INT          NOT NULL,
            name        VARCHAR(500),
            price       VARCHAR(50),
            url         VARCHAR(1000),
            rooms       VARCHAR(50),
            surface     VARCHAR(50),
            zone        VARCHAR(200),
            description TEXT,
            FOREIGN KEY (scan_id) REFERENCES scans(id)
        )
    """)


def _val(v):
    """Convert 'N/A' to NULL for cleaner storage."""
    return None if v == "N/A" else v


def save_scan(website, offers):
    conn = _connect()
    try:
        with conn.cursor() as cur:
            _ensure_tables(cur)
            cur.execute(
                "INSERT INTO scans (timestamp, website) VALUES (%s, %s)",
                (datetime.now(), website),
            )
            scan_id = cur.lastrowid
            for offer in offers:
                cur.execute(
                    """INSERT INTO houses
                           (scan_id, name, price, url, rooms, surface, zone, description)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        scan_id,
                        _val(offer.get("name")),
                        _val(offer.get("price")),
                        _val(offer.get("url")),
                        _val(offer.get("rooms")),
                        _val(offer.get("surface")),
                        _val(offer.get("zone")),
                        _val(offer.get("description")),
                    ),
                )
        conn.commit()
        print(f"[db] scan #{scan_id} saved — {len(offers)} house(s) for '{website}'")
    finally:
        conn.close()
