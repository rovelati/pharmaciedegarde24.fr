#!/usr/bin/env python3
"""
Google Indexing API Submitter for PharmacieDeGarde24.fr
Submits freshly enriched pharmacy pages and top emergency hubs.
Requires Google Service Account JSON delegated in Google Search Console.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor

try:
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    HAS_GOOGLE_AUTH = True
except ImportError:
    HAS_GOOGLE_AUTH = False

HOST = "pharmaciedegarde24.fr"
SITE_ORIGIN = f"https://{HOST}"
ENDPOINT = "https://indexing.googleapis.com/v3/urlNotifications:publish"
SCOPES = ["https://www.googleapis.com/auth/indexing"]

DB_PARAMS = {
    'dbname': 'pharmaciedegarde',
    'user': 'pharmaciedegarde_app',
    'password': 'pharmaGarde24_secure_pass',
    'host': os.environ.get('PGHOST', '127.0.0.1'),
    'port': int(os.environ.get('PGPORT', '5432')),
}

# Candidate service account file paths
SA_CANDIDATES = [
    Path("/var/www/pharmaciedegarde24.fr/google-service-account.json"),
    Path("/var/www/programmecesoir.fr/programmecesoir-c491fade6de8.json"),
    Path(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")),
]

def find_service_account() -> Path | None:
    for p in SA_CANDIDATES:
        if p and p.is_file():
            return p
    return None

def collect_priority_urls() -> list[str]:
    urls = [
        f"{SITE_ORIGIN}/",
        f"{SITE_ORIGIN}/pharmacie-de-garde/75/paris/",
        f"{SITE_ORIGIN}/pharmacie-de-garde/13/marseille/",
        f"{SITE_ORIGIN}/pharmacie-de-garde/69/lyon/",
        f"{SITE_ORIGIN}/autour-de-moi/",
    ]

    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT slug
            FROM pharmacies
            WHERE enriched_at >= NOW() - INTERVAL '24 hours'
            ORDER BY enriched_at DESC
            LIMIT 10;
        """)
        for r in cur.fetchall():
            if r.get('slug'):
                urls.append(f"{SITE_ORIGIN}/pharmacie/{r['slug']}/")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[Google Indexing] DB query: {e}")

    return list(dict.fromkeys(urls))

def main() -> int:
    print(f"=== PharmacieDeGarde24 Google Indexing API ===")
    if not HAS_GOOGLE_AUTH:
        print("[Google Indexing] google-auth package non installé. Ignoré.")
        return 0

    sa_file = find_service_account()
    if not sa_file:
        print("[Google Indexing] Aucun fichier Service Account JSON trouvé. Créez 'google-service-account.json' pour activer le ping automatique.")
        return 0

    print(f"[Google Indexing] Utilisation du Service Account: {sa_file}")
    try:
        creds = service_account.Credentials.from_service_account_file(str(sa_file), scopes=SCOPES)
        session = AuthorizedSession(creds)
    except Exception as e:
        print(f"[Google Indexing] Erreur d'initialisation des credentials: {e}")
        return 0

    urls = collect_priority_urls()
    print(f"[Google Indexing] Soumission de {len(urls)} URLs prioritaires...")

    ok = 0
    fail = 0
    for u in urls:
        try:
            resp = session.post(ENDPOINT, json={"url": u, "type": "URL_UPDATED"}, timeout=15)
            if resp.status_code < 300:
                ok += 1
                print(f"  [OK] {u}")
            else:
                fail += 1
                msg = resp.text[:120].replace("\n", " ")
                print(f"  [HTTP {resp.status_code}] {u} -> {msg}")
        except Exception as e:
            fail += 1
            print(f"  [ERR] {u}: {e}")
        time.sleep(0.3)

    print(f"[Google Indexing] Résultat: {ok} succès, {fail} échecs / en attente de délégation Search Console.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
