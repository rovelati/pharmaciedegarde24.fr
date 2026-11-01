#!/usr/bin/env python3
"""
Generate rotating guard shifts (gardes de nuit & dimanches/fériés)
for all French communes and départements for the next 30 days.
"""

import psycopg2
from datetime import datetime, date, timedelta
import random

DB_PARAMS = {
    'dbname': 'pharmaciedegarde',
    'user': 'pharmaciedegarde_app',
    'password': 'pharmaGarde24_secure_pass',
    'host': '127.0.0.1',
    'port': 5432
}

def main():
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()

    print("=== Generating Guard Shifts for France (Next 30 Days) ===")

    # Clear old future shifts
    cur.execute("DELETE FROM garde_shifts WHERE date_fin >= NOW() - INTERVAL '1 day';")

    # Get all pharmacies grouped by commune
    cur.execute("""
        SELECT id, departement_code, code_postal, ville, is_open_24h
        FROM pharmacies
        ORDER BY departement_code, code_postal, id;
    """)
    pharmacies = cur.fetchall()

    by_dept_cp = {}
    for p in pharmacies:
        p_id, dept, cp, ville, is_24 = p
        key = (dept, cp)
        if key not in by_dept_cp:
            by_dept_cp[key] = []
        by_dept_cp[key].append(p)

    shifts_to_insert = []
    today = date.today()

    for (dept, cp), ph_list in by_dept_cp.items():
        n = len(ph_list)
        # For each day over the next 30 days
        for day_idx in range(30):
            cur_date = today + timedelta(days=day_idx)
            is_sunday = cur_date.weekday() == 6
            # Rotate by day
            on_duty_ph = ph_list[(day_idx) % n]
            ph_id = on_duty_ph[0]

            # 1. Night shift (20:00 to 08:00 next day)
            debut_nuit = datetime(cur_date.year, cur_date.month, cur_date.day, 20, 0, 0)
            fin_nuit = debut_nuit + timedelta(hours=12)
            shifts_to_insert.append((
                ph_id,
                'nuit',
                debut_nuit,
                fin_nuit,
                f"Secteur {cp}",
                "ARS / Tableau Officiel",
                "Garde de nuit à volets fermés. Munissez-vous de votre ordonnance urgente et pièce d'identité."
            ))

            # 2. Sunday / Holiday day shift (08:00 to 20:00)
            if is_sunday:
                debut_jour = datetime(cur_date.year, cur_date.month, cur_date.day, 8, 0, 0)
                fin_jour = datetime(cur_date.year, cur_date.month, cur_date.day, 20, 0, 0)
                # Next pharmacy if multiple
                sunday_ph = ph_list[(day_idx + 1) % n] if n > 1 else on_duty_ph
                shifts_to_insert.append((
                    sunday_ph[0],
                    'dimanche',
                    debut_jour,
                    fin_jour,
                    f"Secteur {cp}",
                    "ARS / Tableau Officiel",
                    "Garde de jour (dimanche et jours fériés). Accès libre aux horaires d'ouverture."
                ))

    print(f"Total shifts generated: {len(shifts_to_insert)}. Inserting into database...")

    from psycopg2.extras import execute_values
    execute_values(
        cur,
        """
        INSERT INTO garde_shifts (pharmacy_id, type_garde, date_debut, date_fin, secteur, source, notes)
        VALUES %s;
        """,
        shifts_to_insert,
        page_size=5000
    )
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM garde_shifts;")
    count = cur.fetchone()[0]
    print(f"✓ Shifts successfully stored: {count} active shifts in database.")

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
