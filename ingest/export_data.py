#!/usr/bin/env python3
"""
PharmacieDeGarde24.fr - Data Exporter
Exports database records to optimized JSON files for the Astro build:
1. site/src/data/departements.json
2. site/src/data/top-communes.json
3. site/src/data/shards/[dept_code].json (per-departement pharmacy + guard data)
"""

import psycopg2
import json
import os
from datetime import datetime, date

DB_PARAMS = {
    'dbname': 'pharmaciedegarde',
    'user': 'pharmaciedegarde_app',
    'password': 'pharmaGarde24_secure_pass',
    'host': '127.0.0.1',
    'port': 5432
}

DEST_DATA_DIR = os.environ.get('DEST_DATA_DIR', '/var/www/pharmaciedegarde24.fr/site/src/data')

def main():
    os.makedirs(DEST_DATA_DIR, exist_ok=True)
    shards_dir = os.path.join(DEST_DATA_DIR, 'shards')
    os.makedirs(shards_dir, exist_ok=True)

    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()

    print("=== Exporting Data for Astro Static Site ===")

    # 1. Export Departements with stats
    cur.execute("""
        SELECT d.code, d.nom, d.slug, d.region,
               COUNT(p.id) as pharmacy_count,
               COUNT(CASE WHEN p.is_open_24h THEN 1 END) as count_24h
        FROM departements d
        LEFT JOIN pharmacies p ON p.departement_code = d.code
        GROUP BY d.code, d.nom, d.slug, d.region
        ORDER BY d.code;
    """)
    dept_rows = cur.fetchall()

    departements = []
    for r in dept_rows:
        code, nom, slug, region, ph_count, p24_count = r
        departements.append({
            'code': code,
            'nom': nom,
            'slug': slug,
            'region': region or '',
            'pharmacyCount': int(ph_count),
            'count24h': int(p24_count)
        })

    with open(os.path.join(DEST_DATA_DIR, 'departements.json'), 'w', encoding='utf-8') as f:
        json.dump(departements, f, ensure_ascii=False, indent=2)
    print(f"✓ Exported {len(departements)} departements to departements.json")

    # 2. Export Top Communes (by population or pharmacy count)
    cur.execute("""
        SELECT c.insee_code, c.nom, c.slug, c.departement_code, c.postal_codes,
               c.population, c.lat, c.lon,
               d.nom as dept_nom, d.slug as dept_slug,
               COUNT(p.id) as ph_count
        FROM communes c
        JOIN departements d ON d.code = c.departement_code
        LEFT JOIN pharmacies p ON p.departement_code = c.departement_code AND (p.ville ILIKE c.nom OR p.code_postal = ANY(c.postal_codes))
        WHERE c.population >= 10000 OR c.insee_code IN ('75056', '13055', '69123', '06088', '33063', '31555')
        GROUP BY c.insee_code, c.nom, c.slug, c.departement_code, c.postal_codes, c.population, c.lat, c.lon, d.nom, d.slug
        ORDER BY c.population DESC, ph_count DESC
        LIMIT 350;
    """)
    top_rows = cur.fetchall()

    top_communes = []
    for r in top_rows:
        insee, nom, slug, dept_code, cps, pop, lat, lon, dept_nom, dept_slug, ph_count = r
        top_communes.append({
            'insee': insee,
            'nom': nom,
            'slug': slug,
            'departementCode': dept_code,
            'departementNom': dept_nom,
            'departementSlug': dept_slug,
            'postalCodes': cps or [],
            'population': int(pop or 0),
            'lat': float(lat) if lat else None,
            'lon': float(lon) if lon else None,
            'pharmacyCount': int(ph_count)
        })

    with open(os.path.join(DEST_DATA_DIR, 'top-communes.json'), 'w', encoding='utf-8') as f:
        json.dump(top_communes, f, ensure_ascii=False, indent=2)
    print(f"✓ Exported {len(top_communes)} top communes to top-communes.json")

    # 3. Export Shards by Departement
    now = datetime.now()
    cur.execute("""
        SELECT p.id, p.finess_id, p.nom, p.slug, p.adresse, p.code_postal, p.ville,
               p.departement_code, p.lat, p.lon, p.telephone, p.is_open_24h,
               p.google_rating, p.google_user_ratings_total, p.google_reviews,
               p.google_photos, p.google_website, p.editorial_summary, p.google_opening_hours,
               s.type_garde, s.date_debut, s.date_fin, s.notes
        FROM pharmacies p
        LEFT JOIN garde_shifts s ON s.pharmacy_id = p.id AND s.date_fin >= %s AND s.date_debut <= %s + INTERVAL '7 days'
        ORDER BY p.departement_code, p.ville, p.nom;
    """, (now, now))
    all_rows = cur.fetchall()

    # Group by dept
    by_dept = {}
    for r in all_rows:
        (p_id, finess, nom, slug, adresse, cp, ville, dept_code, lat, lon, tel, is_24,
         g_rating, g_reviews_cnt, g_reviews, g_photos, g_website, g_editorial, g_hours,
         g_type, g_debut, g_fin, g_notes) = r
        if dept_code not in by_dept:
            by_dept[dept_code] = {}

        if p_id not in by_dept[dept_code]:
            by_dept[dept_code][p_id] = {
                'id': str(p_id),
                'finessId': finess,
                'nom': nom,
                'slug': slug,
                'adresse': adresse,
                'codePostal': cp,
                'ville': ville,
                'departementCode': dept_code,
                'lat': float(lat) if lat else None,
                'lon': float(lon) if lon else None,
                'telephone': tel or '',
                'isOpen24h': bool(is_24),
                'googleRating': float(g_rating) if g_rating else None,
                'googleReviewsTotal': int(g_reviews_cnt or 0),
                'googleReviews': g_reviews or [],
                'googlePhotos': g_photos or [],
                'googleWebsite': g_website or '',
                'editorialSummary': g_editorial or '',
                'googleOpeningHours': g_hours or [],
                'shifts': []
            }

        if g_type and g_debut and g_fin:
            by_dept[dept_code][p_id]['shifts'].append({
                'type': g_type,
                'debut': g_debut.isoformat(),
                'fin': g_fin.isoformat(),
                'notes': g_notes or ''
            })

    # Write each shard
    for dept_code, ph_dict in by_dept.items():
        shard_file = os.path.join(shards_dir, f"{dept_code}.json")
        ph_list = list(ph_dict.values())
        with open(shard_file, 'w', encoding='utf-8') as f:
            json.dump(ph_list, f, ensure_ascii=False)

    print(f"✓ Exported {len(by_dept)} departement shards to {shards_dir}/")

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
