#!/usr/bin/env python3
"""
IndexNow Ping for PharmacieDeGarde24.fr
Notifies Bing, Yandex, and Naver of:
1. Hub pages (Home, /pharmacie-de-garde/, /autour-de-moi/)
2. Priority communes with active night/Sunday shifts
3. Recently enriched pharmacy pages (enriched in the last 24h)
"""
from __future__ import annotations

import os
import sys
import json
import urllib.request
import urllib.error
import psycopg2
from psycopg2.extras import RealDictCursor

HOST = "www.pharmaciedegarde24.fr"
SITE_ORIGIN = f"https://{HOST}"
INDEXNOW_KEY = os.environ.get("INDEXNOW_KEY", "c8d2a6e95f144e0fb23d7a8e51b3c99a")
KEY_LOCATION = f"{SITE_ORIGIN}/{INDEXNOW_KEY}.txt"
INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"

DB_PARAMS = {
    'dbname': 'pharmaciedegarde',
    'user': 'pharmaciedegarde_app',
    'password': 'pharmaGarde24_secure_pass',
    'host': os.environ.get('PGHOST', '127.0.0.1'),
    'port': int(os.environ.get('PGPORT', '5432')),
}

PRIORITY_COMMUNES = [
    ("75", "paris"),
    ("13", "marseille"),
    ("69", "lyon"),
    ("31", "toulouse"),
    ("06", "nice"),
    ("44", "nantes"),
    ("34", "montpellier"),
    ("67", "strasbourg"),
    ("33", "bordeaux"),
    ("59", "lille"),
    ("35", "rennes"),
    ("83", "toulon"),
    ("51", "reims"),
    ("42", "saint-etienne"),
    ("76", "le-havre"),
    ("21", "dijon"),
    ("49", "angers"),
    ("38", "grenoble"),
    ("30", "nimes"),
    ("14", "caen"),
]

def collect_urls() -> list[str]:
    urls = [
        f"{SITE_ORIGIN}/",
        f"{SITE_ORIGIN}/pharmacie-de-garde/",
        f"{SITE_ORIGIN}/autour-de-moi/",
    ]

    for dept, commune in PRIORITY_COMMUNES:
        urls.append(f"{SITE_ORIGIN}/pharmacie-de-garde/{dept}/{commune}/")

    # Fetch pharmacies enriched in the last 24-48 hours
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT slug, departement_code, ville
            FROM pharmacies
            WHERE enriched_at >= NOW() - INTERVAL '48 hours'
            ORDER BY enriched_at DESC
            LIMIT 50;
        """)
        enriched = cur.fetchall()
        for p in enriched:
            if p.get('slug'):
                urls.append(f"{SITE_ORIGIN}/pharmacie/{p['slug']}/")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[IndexNow] DB query notice: {e}")

    # Deduplicate preserving order
    return list(dict.fromkeys(urls))

def submit_indexnow(url_list: list[str]) -> bool:
    if not url_list:
        print("[IndexNow] Aucune URL à soumettre.")
        return True

    payload = {
        "host": HOST,
        "key": INDEXNOW_KEY,
        "keyLocation": KEY_LOCATION,
        "urlList": url_list[:250]
    }

    req = urllib.request.Request(
        INDEXNOW_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "PharmacieDeGarde24-IndexNow/1.0"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            if status in (200, 202):
                print(f"[IndexNow] Succès ! {len(url_list)} URLs soumises (HTTP {status}).")
                return True
            print(f"[IndexNow] Réponse inattendue: HTTP {status}")
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')[:200]
        print(f"[IndexNow] HTTPError {e.code}: {body}")
    except Exception as e:
        print(f"[IndexNow] Erreur de requête: {e}")

    return False

def main():
    print(f"=== PharmacieDeGarde24 IndexNow Submitter ===")
    url_list = collect_urls()
    print(f"Total URLs à soumettre : {len(url_list)}")
    for u in url_list[:5]:
        print(f"  - {u}")
    if len(url_list) > 5:
        print(f"  ... et {len(url_list) - 5} autres URLs.")

    success = submit_indexnow(url_list)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
