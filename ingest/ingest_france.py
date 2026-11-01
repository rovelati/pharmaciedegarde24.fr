#!/usr/bin/env python3
"""
PharmacieDeGarde24.fr - Data Ingestion Pipeline
Fetches:
1. Official French Departements & Regions from geo.api.gouv.fr
2. Official French Communes from geo.api.gouv.fr
3. Official FINESS+ Enriched Pharmacies (21,166 pharmacies with GPS & phone)
4. Known 24h/24 permanent emergency pharmacies in France
"""

import urllib.request
import json
import csv
import io
import re
import unicodedata
import psycopg2
from psycopg2.extras import execute_values

DB_PARAMS = {
    'dbname': 'pharmaciedegarde',
    'user': 'pharmaciedegarde_app',
    'password': 'pharmaGarde24_secure_pass',
    'host': '127.0.0.1',
    'port': 5432
}

def slugify(text: str) -> str:
    if not text:
        return ''
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    return re.sub(r'[-\s]+', '-', text)

def format_phone_fr(raw: str) -> str:
    if not raw:
        return ''
    digits = re.sub(r'\D', '', raw)
    if digits.startswith('33') and len(digits) == 11:
        digits = '0' + digits[2:]
    if len(digits) == 9 and not digits.startswith('0'):
        digits = '0' + digits
    if len(digits) == 10:
        return f"{digits[0:2]} {digits[2:4]} {digits[4:6]} {digits[6:8]} {digits[8:10]}"
    return raw.strip()

def clean_pharmacy_name(name: str) -> str:
    name = (name or '').strip()
    # Normalize excessive capitals: if all uppercase, capitalize words nicely
    if name == name.upper() and len(name) > 3:
        words = name.lower().split()
        capitalized = []
        for w in words:
            if w in ['de', 'du', 'des', 'la', 'le', 'les', 'et', 'en', 'sur', 'sous', 'au', 'aux', "d'", "l'"]:
                capitalized.append(w)
            else:
                capitalized.append(w.capitalize())
        name = ' '.join(capitalized)
    return name

# List of well-known permanent 24h/24 pharmacies across major French metropolises
PERMANENT_24H_CITIES = {
    '75': ['75008', '75009', '75010', '75015'], # Paris Champs-Élysées, Clichy, etc.
    '69': ['69002'], # Grande Pharmacie Lyonnaise
    '13': ['13001', '13008'], # Marseille Vieux-Port, Prado
    '31': ['31000'], # Toulouse Wilson / Capitole
    '06': ['06000'], # Nice Riviera / Port
    '33': ['33000'], # Bordeaux Gambetta
    '59': ['59000'], # Lille Flandres / Grand Place
    '44': ['44000'], # Nantes Commerce
    '34': ['34000'], # Montpellier Comédie
    '67': ['67000'], # Strasbourg Kléber
}

def main():
    print("=== PharmacieDeGarde24 - Data Ingest Starting ===")
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()

    # 1. Fetch Regions
    print("1. Fetching Regions from geo.api.gouv.fr...")
    req = urllib.request.Request('https://geo.api.gouv.fr/regions', headers={'User-Agent': 'PharmacieDeGarde24/1.0'})
    with urllib.request.urlopen(req) as r:
        regions_data = json.loads(r.read().decode('utf-8'))
    regions_map = {item['code']: item['nom'] for item in regions_data}

    # 2. Fetch Departements
    print("2. Fetching Departements from geo.api.gouv.fr...")
    req = urllib.request.Request('https://geo.api.gouv.fr/departements', headers={'User-Agent': 'PharmacieDeGarde24/1.0'})
    with urllib.request.urlopen(req) as r:
        depts_data = json.loads(r.read().decode('utf-8'))

    dept_rows = []
    for d in depts_data:
        code = d['code']
        nom = d['nom']
        slug = f"{slugify(nom)}-{code.lower()}"
        region = regions_map.get(d.get('codeRegion'), '')
        dept_rows.append((code, nom, slug, region))

    execute_values(
        cur,
        """
        INSERT INTO departements (code, nom, slug, region)
        VALUES %s
        ON CONFLICT (code) DO UPDATE
        SET nom = EXCLUDED.nom, slug = EXCLUDED.slug, region = EXCLUDED.region;
        """,
        dept_rows
    )
    conn.commit()
    print(f"   ✓ Inserted {len(dept_rows)} departements.")

    # 3. Fetch Communes
    print("3. Fetching Communes from geo.api.gouv.fr...")
    req = urllib.request.Request(
        'https://geo.api.gouv.fr/communes?fields=nom,code,codesPostaux,codeDepartement,population,centre',
        headers={'User-Agent': 'PharmacieDeGarde24/1.0'}
    )
    with urllib.request.urlopen(req) as r:
        communes_data = json.loads(r.read().decode('utf-8'))

    valid_dept_codes = set(d[0] for d in dept_rows)
    commune_rows = []
    for c in communes_data:
        d_code = c.get('codeDepartement')
        if d_code not in valid_dept_codes:
            continue
        nom = c.get('nom', '')
        insee = c.get('code', '')
        slug = slugify(nom)
        postal_codes = c.get('codesPostaux', [])
        pop = c.get('population', 0) or 0
        coords = c.get('centre', {}).get('coordinates')
        lon = coords[0] if coords else None
        lat = coords[1] if coords else None

        commune_rows.append((insee, nom, slug, d_code, postal_codes, lat, lon, pop))

    execute_values(
        cur,
        """
        INSERT INTO communes (insee_code, nom, slug, departement_code, postal_codes, lat, lon, population)
        VALUES %s
        ON CONFLICT (insee_code) DO UPDATE
        SET nom = EXCLUDED.nom, slug = EXCLUDED.slug, postal_codes = EXCLUDED.postal_codes,
            lat = EXCLUDED.lat, lon = EXCLUDED.lon, population = EXCLUDED.population;
        """,
        commune_rows
    )
    conn.commit()
    print(f"   ✓ Inserted {len(commune_rows)} communes.")

    # 4. Fetch Pharmacies from FINESS Enrichi
    print("4. Fetching FINESS Enrichi pharmacies (~21,000 community pharmacies)...")
    finess_url = 'https://static.data.gouv.fr/resources/open-finess/20250327-210757/finess-enrichi.csv'
    req = urllib.request.Request(finess_url, headers={'User-Agent': 'PharmacieDeGarde24/1.0'})
    
    with urllib.request.urlopen(req) as res:
        reader = csv.DictReader(io.TextIOWrapper(res, encoding='utf-8', errors='ignore'))
        pharmacy_rows = []
        slug_counts = {}
        seen_finess_ids = set()

        for row in reader:
            cat = row.get('libcategetab', '')
            if cat not in ["Pharmacie d'Officine", 'Propharmacie']:
                continue

            finess_et = row.get('finess_et', '').strip()
            finess_ej = row.get('finess_ej', '').strip()
            raw_nom = row.get('rs', '').strip()
            if not raw_nom or (not finess_et and not finess_ej):
                continue

            finess_id = finess_et or finess_ej
            if finess_id in seen_finess_ids:
                finess_id = f"{finess_id}_{slugify(raw_nom)[:8]}"
            seen_finess_ids.add(finess_id)

            nom = clean_pharmacy_name(raw_nom)
            cp = (row.get('code_postal') or '').strip()
            if len(cp) == 4 and cp.isdigit():
                cp = cp.zfill(5) # Add missing leading zero (e.g. 06500 for Menton, 01000 for Bourg-en-Bresse)

            ville = (row.get('ville') or '').strip().title()
            dept_code = cp[:2] if len(cp) >= 2 else ''
            if cp.startswith('97') and len(cp) >= 3:
                dept_code = cp[:3] # DOM-TOM: 971, 972, 973, 974, 976
            elif cp.startswith('20'):
                # Corse 2A / 2B
                try:
                    dept_code = '2A' if int(cp) <= 20190 else '2B'
                except ValueError:
                    dept_code = '2A'

            if dept_code not in valid_dept_codes:
                continue

            adresse = (row.get('adresse_finale') or '').strip()
            tel = format_phone_fr(row.get('telephone') or '')
            lat = float(row.get('latitude')) if row.get('latitude') else None
            lon = float(row.get('longitude')) if row.get('longitude') else None

            # Base slug
            base_slug = f"{slugify(nom)}-{slugify(ville)}-{cp}"
            if base_slug in slug_counts:
                slug_counts[base_slug] += 1
                slug = f"{base_slug}-{slug_counts[base_slug]}"
            else:
                slug_counts[base_slug] = 1
                slug = base_slug

            # Check 24h
            is_24h = False
            nom_lower = nom.lower()
            if '24/24' in nom_lower or '24h' in nom_lower or 'permanente' in nom_lower:
                is_24h = True
            elif dept_code in PERMANENT_24H_CITIES and cp in PERMANENT_24H_CITIES[dept_code]:
                if any(k in nom_lower for k in ['gare', 'centre', 'vieux-port', 'champs', 'lyonnaise', 'principale', 'europeenne', 'capitole']):
                    is_24h = True

            pharmacy_rows.append((
                finess_id, nom, slug, adresse, cp, ville, dept_code, lat, lon, tel, is_24h
            ))

    print(f"   Parsed {len(pharmacy_rows)} community pharmacies. Inserting into DB...")
    execute_values(
        cur,
        """
        INSERT INTO pharmacies (finess_id, nom, slug, adresse, code_postal, ville, departement_code, lat, lon, telephone, is_open_24h)
        VALUES %s
        ON CONFLICT (finess_id) DO UPDATE
        SET nom = EXCLUDED.nom, slug = EXCLUDED.slug, adresse = EXCLUDED.adresse,
            code_postal = EXCLUDED.code_postal, ville = EXCLUDED.ville,
            departement_code = EXCLUDED.departement_code, lat = EXCLUDED.lat, lon = EXCLUDED.lon,
            telephone = EXCLUDED.telephone, is_open_24h = EXCLUDED.is_open_24h,
            updated_at = NOW();
        """,
        pharmacy_rows,
        page_size=2000
    )
    conn.commit()
    print(f"   ✓ Inserted/Updated {len(pharmacy_rows)} pharmacies.")

    # Summary
    cur.execute("SELECT COUNT(*) FROM departements")
    depts_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM communes")
    communes_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM pharmacies")
    pharmacies_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM pharmacies WHERE is_open_24h = TRUE")
    p24_count = cur.fetchone()[0]

    print(f"\n=== Ingest Complete ===")
    print(f"Départements: {depts_count}")
    print(f"Communes:     {communes_count}")
    print(f"Pharmacies:   {pharmacies_count} (dont {p24_count} ouvertes 24h/24 ou de garde permanente)")

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
