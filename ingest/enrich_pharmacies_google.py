#!/usr/bin/env python3
"""
Enrichissement des pharmacies via l'API Google Places & Street View.
Récupère les notes, avis clients, photos de devanture (Street View),
site web et horaires d'ouverture détaillés pour éliminer le thin content.
"""
import os
import sys
import time
import json
import argparse
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
import psycopg2
from psycopg2.extras import RealDictCursor, Json

DB_PARAMS = {
    'dbname': 'pharmaciedegarde',
    'user': 'pharmaciedegarde_app',
    'password': 'pharmaGarde24_secure_pass',
    'host': os.environ.get('PGHOST', '127.0.0.1'),
    'port': int(os.environ.get('PGPORT', '5432')),
}

GOOGLE_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', 'AIzaSyBoXNUB-99ohjTjpm-vzPYpylabJweQPbw')

def similar(a, b):
    return SequenceMatcher(None, (a or '').lower(), (b or '').lower()).ratio()

def search_place(nom, adresse, code_postal, ville, key):
    query = f"{nom} {adresse} {code_postal} {ville} France"
    url = f"https://maps.googleapis.com/maps/api/place/textsearch/json?query={urllib.parse.quote(query)}&language=fr&key={key}"
    req = urllib.request.Request(url, headers={'User-Agent': 'PharmacieDeGarde24/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data.get('status') == 'OK' and data.get('results'):
                return data['results'][0]
    except Exception as e:
        print(f"  [ERROR search_place] {e}")
    return None

def get_place_details(place_id, key):
    fields = "name,rating,user_ratings_total,reviews,photos,formatted_phone_number,opening_hours,website,editorial_summary"
    url = f"https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&fields={fields}&language=fr&key={key}"
    req = urllib.request.Request(url, headers={'User-Agent': 'PharmacieDeGarde24/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data.get('status') == 'OK':
                return data.get('result', {})
    except Exception as e:
        print(f"  [ERROR get_place_details] {e}")
    return {}

def check_street_view(lat, lon, key):
    meta_url = f"https://maps.googleapis.com/maps/api/streetview/metadata?location={lat},{lon}&key={key}"
    try:
        with urllib.request.urlopen(meta_url, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data.get('status') == 'OK':
                return f"https://maps.googleapis.com/maps/api/streetview?size=640x360&location={lat},{lon}&fov=80&heading=0&pitch=0&key={key}"
    except Exception:
        pass
    return None

def main():
    parser = argparse.ArgumentParser(description="Enrichissement Google Places pour PharmacieDeGarde24")
    parser.add_argument('--limit', type=int, default=30, help="Nombre max de pharmacies à enrichir")
    parser.add_argument('--dept', type=str, default=None, help="Filtrer par code département (ex: 75, 13, 69)")
    parser.add_argument('--force', action='store_true', help="Forcer la ré-interrogation même si déjà enrichi")
    parser.add_argument('--dry-run', action='store_true', help="Afficher sans sauvegarder dans la base")
    args = parser.parse_args()

    print(f"Démarrage enrichissement Google Places (limite: {args.limit}, dept: {args.dept})...")

    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    query = """
        SELECT id, nom, adresse, code_postal, ville, departement_code, lat, lon, telephone
        FROM pharmacies
        WHERE (google_place_id IS NULL OR %s)
    """
    params = [args.force]
    if args.dept:
        query += " AND departement_code = %s"
        params.append(args.dept)
    
    query += " ORDER BY id LIMIT %s"
    params.append(args.limit)

    cur.execute(query, params)
    pharmacies = cur.fetchall()
    print(f"Trouvé {len(pharmacies)} pharmacies éligibles à l'enrichissement.")

    enriched_count = 0

    for idx, p in enumerate(pharmacies, 1):
        print(f"\n[{idx}/{len(pharmacies)}] {p['nom']} ({p['ville']} - {p['departement_code']})")
        place = search_place(p['nom'], p['adresse'], p['code_postal'], p['ville'], GOOGLE_API_KEY)
        if not place:
            print("  -> Aucun résultat Google Places trouvé.")
            time.sleep(0.3)
            continue

        place_id = place.get('place_id')
        details = get_place_details(place_id, GOOGLE_API_KEY)

        rating = details.get('rating')
        reviews_count = details.get('user_ratings_total', 0)
        website = details.get('website')
        formatted_phone = details.get('formatted_phone_number')
        editorial = None
        if details.get('editorial_summary'):
            editorial = details['editorial_summary'].get('overview')

        # Clean reviews
        reviews = []
        for r in details.get('reviews', []):
            reviews.append({
                'author': r.get('author_name'),
                'rating': r.get('rating'),
                'text': r.get('text'),
                'time_description': r.get('relative_time_description'),
                'time': r.get('time')
            })

        # Photos & Street View
        photos = []
        if p['lat'] and p['lon']:
            sv_url = check_street_view(p['lat'], p['lon'], GOOGLE_API_KEY)
            if sv_url:
                photos.append(sv_url)

        # Opening hours
        opening_hours = []
        if details.get('opening_hours') and details['opening_hours'].get('weekday_text'):
            opening_hours = details['opening_hours']['weekday_text']

        print(f"  -> Match : {details.get('name')} | Note : {rating}⭐ ({reviews_count} avis) | Photos : {len(photos)}")

        if not args.dry_run:
            update_query = """
                UPDATE pharmacies
                SET google_place_id = %s,
                    google_rating = %s,
                    google_user_ratings_total = %s,
                    google_reviews = %s,
                    google_photos = %s,
                    google_website = %s,
                    editorial_summary = %s,
                    google_opening_hours = %s,
                    telephone = COALESCE(NULLIF(%s, ''), telephone),
                    enriched_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
            """
            cur.execute(update_query, [
                place_id,
                rating,
                reviews_count,
                Json(reviews),
                photos,
                website,
                editorial,
                Json(opening_hours),
                formatted_phone,
                p['id']
            ])
            conn.commit()
            enriched_count += 1

        time.sleep(0.3)

    cur.close()
    conn.close()
    print(f"\nTerminé ! {enriched_count} pharmacies enrichies avec succès.")

if __name__ == '__main__':
    main()
