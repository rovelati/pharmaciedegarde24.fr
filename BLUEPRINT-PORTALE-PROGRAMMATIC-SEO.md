# Blueprint & Template: Creazione Portali Programmatic SEO ad Alta Autorità
*Guida completa e architettura riutilizzabile per directory locali, comparatori e servizi di pubblica utilità basati su Open Data, Astro SSG, Cloudflare Pages e PostgreSQL.*

> **Riferimento implementazione reale:** [PharmacieDeGarde24.fr](https://pharmaciedegarde24.fr)  
> **Repository GitHub:** [rovelati/pharmaciedegarde24.fr](https://github.com/rovelati/pharmaciedegarde24.fr)  
> **Data di stesura:** Novembre 2026  

---

## Indice dei Contenuti
1. [Stack Tecnologico & Scelte Architetturali](#1-stack-tecnologico--scelte-architetturali)
2. [Database & Pipeline Open Data](#2-database--pipeline-open-data)
3. [Alberatura SEO & Strategie Anti-Thin Content](#3-alberatura-seo--strategie-anti-thin-content)
4. [Mappe Interattive & Geocoding Mobile-First](#4-mappe-interattive--geocoding-mobile-first)
5. [Arricchimento Contenuti a Basso Costo (Google Places API)](#5-arricchimento-contenuti-a-basso-costo-google-places-api)
6. [Monetizzazione (AdSense) & CMP Google Consent Mode v2](#6-monetizzazione-adsense--cmp-google-consent-mode-v2)
7. [Indicizzazione Istantanea (IndexNow & Google Indexing)](#7-indicizzazione-istantanea-indexnow--google-indexing)
8. [Automazione Crontab & Regole VPS Contabo](#8-automazione-crontab--regole-vps-contabo)
9. [Authority Building (GitHub, Release & Gist)](#9-authority-building-github-release--gist)
10. [Checklist di Lancio Rapido per Nuovi Progetti](#10-checklist-di-lancio-rapido-per-nuovi-progetti)

---

## 1. Stack Tecnologico & Scelte Architetturali

| Componente | Tecnologia | Scelta / Motivazione |
| :--- | :--- | :--- |
| **Frontend Framework** | **Astro 5 (SSG Static)** | Zero-JS di default, compilazione ultra-rapida (6.000+ pagine in ~5s), TTFB istantaneo, punteggi Lighthouse 100/100. |
| **Hosting & CDN** | **Cloudflare Pages** | Hosting globale a costo zero, banda illimitata, build ed edge deployment istantaneo via `wrangler`, cache purge via API. |
| **Database** | **PostgreSQL 16 (VPS Contabo)** | Relazionale robusto su `127.0.0.1:5432`, ideale per gestire coordinate spaziali, turnazioni, query geodetiche e arricchimento progressivo. |
| **Linguaggio Scripting** | **Python 3 & Node.js 22** | Ingestione dati, normalizzazione stringhe, elaborazione orari e notifiche automatiche via crontab. |
| **Mappe** | **Leaflet + MarkerCluster** | Mappe responsive senza costi di licenza Google Maps JavaScript API, con custom pin a palloncino e raggruppamento dinamico. |
| **Stile & Design** | **CSS Moderno / Token CSS** | Mobile-first nativo, Dark & Solar mode con variabili CSS, nessun framework pesante. |

---

## 2. Database & Pipeline Open Data

### 2.1 Schema Database Minimo
Creare un database dedicato (`pharmaciedegarde`, `prezzobenza`, ecc.) con utente PostgreSQL a permessi limitati:

```sql
-- Tabella Dipartimenti / Province
CREATE TABLE departements (
  code VARCHAR(5) PRIMARY KEY,
  nom VARCHAR(100) NOT NULL,
  slug VARCHAR(120) NOT NULL UNIQUE,
  region VARCHAR(100)
);

-- Tabella Comuni
CREATE TABLE communes (
  insee_code VARCHAR(10) PRIMARY KEY,
  nom VARCHAR(255) NOT NULL,
  slug VARCHAR(255) NOT NULL,
  departement_code VARCHAR(5) NOT NULL REFERENCES departements(code),
  postal_codes TEXT[] NOT NULL DEFAULT '{}',
  lat NUMERIC(9,6),
  lon NUMERIC(9,6),
  population INT DEFAULT 0
);

-- Tabella Entità / Schede Principali
CREATE TABLE pharmacies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  finess_id VARCHAR(30) UNIQUE NOT NULL,
  nom VARCHAR(255) NOT NULL,
  slug VARCHAR(255) NOT NULL,
  adresse TEXT,
  code_postal VARCHAR(10) NOT NULL,
  ville VARCHAR(255) NOT NULL,
  departement_code VARCHAR(5) NOT NULL REFERENCES departements(code),
  lat NUMERIC(9,6),
  lon NUMERIC(9,6),
  telephone VARCHAR(30),
  is_open_24h BOOLEAN DEFAULT FALSE,
  -- Campi di arricchimento Google Places
  google_place_id VARCHAR(100),
  google_rating NUMERIC(3,2),
  google_user_ratings_total INT DEFAULT 0,
  google_reviews JSONB DEFAULT '[]'::jsonb,
  google_photos TEXT[] DEFAULT '{}',
  google_website TEXT,
  editorial_summary TEXT,
  google_opening_hours JSONB DEFAULT '[]'::jsonb,
  enriched_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tabella Turnazioni / Disponibilità Dinamica
CREATE TABLE garde_shifts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pharmacy_id UUID NOT NULL REFERENCES pharmacies(id) ON DELETE CASCADE,
  type_garde VARCHAR(20) NOT NULL, -- 'nuit', 'dimanche', '24h'
  date_debut TIMESTAMPTZ NOT NULL,
  date_fin TIMESTAMPTZ NOT NULL,
  notes TEXT
);

CREATE INDEX idx_pharma_dept ON pharmacies(departement_code);
CREATE INDEX idx_pharma_slug ON pharmacies(slug);
CREATE INDEX idx_shifts_window ON garde_shifts(date_debut, date_fin);
```

### 2.2 Trappole Tipiche degli Open Data (Lezioni Imparate)
1. **Leading Zeros nei CAP**: se il CSV o l'Excel perde lo zero iniziale (es. `6500` anziché `06500`), applicare sempre `.zfill(5)`.
2. **Identificativi Primari Alternativi**: in dataset complessi (come FINESS), l'ID ufficiale può trovarsi in colonne diverse (`finess_et` vs `finess_ej`). Usare sempre un fallback `row.get('finess_et') or row.get('finess_ej')`.
3. **Sharding dei file JSON per la build statica**: non caricare un unico JSON da 20.000 righe in memoria durante la build Astro. Esportare file JSON partizionati per dipartimento (`src/data/shards/{dept_code}.json`) e sincronizzarli in `public/data/shards/` per le chiamate AJAX della mappa.

---

## 3. Alberatura SEO & Strategie Anti-Thin Content

### 3.1 Struttura URL Gerarchica
```
/                                      -> Homepage (Ricerca istantanea + Top Metropoli)
/autour-de-moi/                        -> Tool Geolocation GPS "Vicino a Me"
/pharmacie-de-garde/                   -> Hub Nazionale (101 Dipartimenti)
/pharmacie-de-garde/[dept]/            -> Pagina Dipartimentale (Tutti i comuni del dipartimento)
/pharmacie-de-garde/[dept]/[commune]/  -> Pagina Locale Comune (Mappa + Farmacie aperte + raggio 20km)
/pharmacie/[slug]/                     -> Scheda Dettaglio Farmacia (Orari, Street View, recensioni verificate)
/mentions-legales/                     -> Pagine di conformità normativa
/politique-de-confidentialite/         -> Privacy Policy conforme GDPR/AdSense
```

### 3.2 Strategie Chiave per Evitare Penalizzazioni di "Thin Content"
1. **Live Freshness Badge (`LiveDateBadge.astro`)**:
   Mostra in cima a ogni pagina lo stato in tempo reale con data e ora locale (es. *"Situation en temps réel : dimanche 1 novembre 2026 à 22:30"*). I motori di ricerca vedono un segnale continuo di freschezza.
2. **Espansione del Raggio a 20 km**:
   Nei comuni piccoli, una pagina con 0 farmacie viene scartata da Google come soft-404. Calcolando la formula geodetica di Haversine, si includono le farmacie dei comuni confinanti entro 20 km contrassegnate con badge di prossimità (es. `à 3.2 km — Roquebrune`). La pagina è sempre ricca di contenuti utili.
3. **Fisarmonica per le attività chiuse**:
   Mostrare subito in evidenza solo le strutture aperte o di turno (`🟢 Pharmacies actuellement ouvertes et de garde`), e posizionare quelle attualmente chiuse all'interno di un `<details>` espandibile.
4. **Dati Strutturati Schema.org Multipli**:
   - `MedicalWebPage` / `LocalBusiness`
   - `BreadcrumbList` su tutti i livelli
   - `ItemList` per le directory di comune
   - `FAQPage` per occupare i box People Also Ask (PAA) di Google

---

## 4. Mappe Interattive & Geocoding Mobile-First

### Architettura del Componente Mappa (`PharmacyMap.astro`)
- **Librerie**: Leaflet 1.9 + Leaflet.markercluster 1.5.3 (via CDN o bundle statico).
- **Palloncini con Conteggio**: Icone circolari con contatore dinamico dei punti (`.pharma-cluster-balloon`).
- **Filtro di Default "Aperte Ora"**: La mappa parte filtrata solo per i punti attualmente in servizio o 24h/24. Se nessuno è aperto nell'istante esatto, fa un fallback morbido mostrando tutti i punti per non lasciare la mappa vuota.
- **Popup Ricchi**: Titolo, indirizzo, badge orario, pulsante verde per chiamata diretta `tel:` e pulsante nero per navigazione GPS su Google Maps / Waze.

---

## 5. Arricchimento Contenuti a Basso Costo (Google Places API)

### Formula Sostenibile (~3 $ al mese per 60 schede)
Non interrogare l'intera banca dati in un colpo solo. Un processo batch progressivo garantisce aggiornamenti costanti a costo zero (coperto dai 200 $ di crediti gratuiti mensili di Google Cloud):

1. **Text Search**: `https://maps.googleapis.com/maps/api/place/textsearch/json?query={nom}+{adresse}+{ville}`
2. **Place Details**: campi `name,rating,user_ratings_total,reviews,photos,formatted_phone_number,opening_hours,editorial_summary`
3. **Street View Facade**: `https://maps.googleapis.com/maps/api/streetview?size=640x360&location={lat},{lon}&key={key}`
4. **Volume**: limitato a **2 schede al giorno** via cron (`--limit 2`).

Lo script aggiorna le colonne `google_rating`, `google_reviews` (JSON) e `google_photos` su PostgreSQL, eliminando la necessità di generare testi artificiali e garantendo E-E-A-T genuino.

---

## 6. Monetizzazione (AdSense) & CMP Google Consent Mode v2

### 6.1 Implementazione Consent Mode v2 e AdSense
Nel layout principale (`Base.astro`), inserire i tag nell'ordine corretto:

```html
<!-- 1. Google AdSense Account Verification -->
<meta name="google-adsense-account" content="ca-pub-2168172914069272" />

<!-- 2. Consent Mode v2 Default (DEVE girare PRIMA di GA4 e AdSense) -->
<script is:inline>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('consent', 'default', {
    'ad_storage': 'denied',
    'ad_user_data': 'denied',
    'ad_personalization': 'denied',
    'analytics_storage': 'denied',
    'wait_for_update': 500
  });
  gtag('js', new Date());
  gtag('config', 'G-H0QJ65JZ88');
</script>

<!-- 3. Google Tag GA4 -->
<script is:inline async src="https://www.googletagmanager.com/gtag/js?id=G-H0QJ65JZ88"></script>

<!-- 4. Google AdSense & Funding Choices CMP (TCF v2.2) -->
<script
  is:inline
  async
  src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-2168172914069272"
  crossorigin="anonymous"
></script>
```

### 6.2 Prevenzione Spazi Bianchi in Dark Mode
Google AdSense carica un iframe vuoto bianco prima che gli annunci siano approvati o quando non c'è inventory. Per non rovinare la Dark Mode:

```css
/* tokens.css */
.adslot {
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent !important;
  border: none !important;
  margin: 1.5rem 0;
  overflow: hidden;
}

.adslot ins.adsbygoogle {
  background: transparent !important;
}

/* Collasso automatico se l'annuncio non viene servito */
.adslot ins.adsbygoogle[data-ad-status="unfilled"],
.adslot ins.adsbygoogle:empty {
  display: none !important;
  min-height: 0 !important;
  height: 0 !important;
  margin: 0 !important;
}
```

### 6.3 File `ads.txt`
Posizionato in `public/ads.txt`:
```
google.com, pub-2168172914069272, DIRECT, f08c47fec0942fa0
```

---

## 7. Indicizzazione Istantanea (IndexNow & Google Indexing)

### 7.1 IndexNow (Bing, Yandex, Seznam, Naver)
1. Generare una chiave hex casuale da 32 caratteri: `c8d2a6e95f144e0fb23d7a8e51b3c99a`.
2. Creare il file di verifica in `public/c8d2a6e95f144e0fb23d7a8e51b3c99a.txt` contenente la stringa della chiave.
3. Eseguire uno script Python (`scripts/notify_indexnow.py`) che invia un `POST` JSON a `https://api.indexnow.org/indexnow` con l'elenco delle URL arricchite e dei principali hub (ritorna `HTTP 202 Accepted`).

### 7.2 Google Indexing API
1. Configurare un Google Service Account autorizzato su Google Search Console.
2. Inviare le notifiche con payload `{"url": "...", "type": "URL_UPDATED"}` all'endpoint `https://indexing.googleapis.com/v3/urlNotifications:publish`.
3. Notificare giornalmente solo le 2-5 schede arricchite per non saturare la quota (200 richieste/giorno per progetto GCP).

---

## 8. Automazione Crontab & Regole VPS Contabo

### 8.1 Script di Automazione Completa (`scripts/daily-enrich-and-rebuild.sh`)
```bash
#!/bin/bash
set -euo pipefail

ROOT_DIR="/var/www/pharmaciedegarde24.fr"
LOG_DIR="/var/log/pharmaciedegarde24"
LOG_FILE="$LOG_DIR/daily.log"
LOCK_FILE="/tmp/pharmaciedegarde24-daily.lock"

mkdir -p "$LOG_DIR"
exec 200>"$LOCK_FILE"
flock -n 200 || { echo "[$(date '+%Y-%m-%d %H:%M:%S')] Processo già in corso, esco." >> "$LOG_FILE"; exit 0; }

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

cd "$ROOT_DIR"

# 1. Turni & disponibilità
log "1. Aggiornamento turni di guardia..."
/usr/bin/python3 ingest/generate_shifts.py >> "$LOG_FILE" 2>&1

# 2. Arricchimento 2 schede al giorno
log "2. Arricchimento Google Places (2 schede)..."
/usr/bin/python3 ingest/enrich_pharmacies_google.py --limit 2 >> "$LOG_FILE" 2>&1

# 3. Export JSON shards
log "3. Esportazione shards JSON..."
/usr/bin/python3 ingest/export_data.py >> "$LOG_FILE" 2>&1

# 4. Build Astro
log "4. Build Astro..."
cd "$ROOT_DIR/site"
npm run build >> "$LOG_FILE" 2>&1

# 5. Deploy Cloudflare Pages & Purge Cache
log "5. Deploy Cloudflare Pages..."
CF_TOKEN_FILE="$ROOT_DIR/.cloudflare-token"
ACCOUNT_ID="$(grep -i '^accountid:' "$CF_TOKEN_FILE" | cut -d: -f2- | tr -d ' ')"
API_KEY="$(grep -i '^api-key:' "$CF_TOKEN_FILE" | cut -d: -f2- | tr -d ' ')"
EMAIL="$(grep -i '^email:' "$CF_TOKEN_FILE" | cut -d: -f2- | tr -d ' ')"
ZONE_ID="$(grep -i '^zoneid:' "$CF_TOKEN_FILE" | cut -d: -f2- | tr -d ' ')"

CLOUDFLARE_ACCOUNT_ID="$ACCOUNT_ID" \
CLOUDFLARE_API_KEY="$API_KEY" \
CLOUDFLARE_EMAIL="$EMAIL" \
npx wrangler pages deploy dist --project-name=pharmaciedegarde24 --branch=main --commit-dirty=true >> "$LOG_FILE" 2>&1

curl -s -X POST "https://api.cloudflare.com/client/v4/zones/${ZONE_ID}/purge_cache" \
  -H "X-Auth-Email: ${EMAIL}" \
  -H "X-Auth-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  --data '{"purge_everything":true}' >> "$LOG_FILE" 2>&1 || true

# 6. Ping Motori di Ricerca
log "6. Notifica IndexNow & Google Indexing..."
cd "$ROOT_DIR"
/usr/bin/python3 scripts/notify_indexnow.py >> "$LOG_FILE" 2>&1 || true
/usr/bin/python3 scripts/notify_google_indexing.py >> "$LOG_FILE" 2>&1 || true

log "Operazione completata con successo."
```

### 8.2 Configurazione Crontab (`crontab -e`)
Pianificare all'alba in una finestra oraria libera da altri job (es. **05:25** ora locale Europe/Paris):

```cron
# PharmacieDeGarde24.fr — Daily Enrich, Rebuild & Indexing
25 5 * * * /usr/bin/flock -n /tmp/pharmaciedegarde24-daily.lock /var/www/pharmaciedegarde24.fr/scripts/daily-enrich-and-rebuild.sh >> /var/log/pharmaciedegarde24/daily.log 2>&1
```

---

## 9. Authority Building (GitHub, Release & Gist)

Per trasmettere autorità algoritmica al dominio appena acquistato:

1. **Repository Pubblico su GitHub**:
   - Creare repo con nome del dominio: `rovelati/[dominio]`.
   - Impostare la URL del sito nel campo **Website / Homepage**.
   - Aggiungere 10-15 **Topics** tematici pertinenti (es. `opendata`, `france`, `sante`, `medical-directory`, `leaflet`, ecc.).
   - Redigere un `README.md` esaustivo contenente:
     - Badge di stato, licenza e fonte Open Data ufficiale.
     - Tabelle con **deep-link verso le 20 città principali**.
     - Documentazione tecnica degli endpoint JSON aperti.
2. **GitHub Release Ufficiale**:
   - Rilasciare un tag di versione (es. `v1.0.0`) con note di rilascio ricche e link all'homepage.
3. **Public GitHub Gist (DA 96+)**:
   - Creare un Gist pubblico markdown con il sommario del dataset aperto e link alle sezioni chiave del portale.

---

## 10. Checklist di Lancio Rapido per Nuovi Progetti

- [ ] **1. Dominio & DNS**: Dominio acquistato e puntato sui NameServer di Cloudflare.
- [ ] **2. Database PostgreSQL**: DB creato con utente e password dedicate su localhost:5432.
- [ ] **3. Ingestione Open Data**: Script Python con deduplica slug, normalizzazione telefoni e gestione leading zero dei CAP (`zfill(5)`).
- [ ] **4. Partizionamento Shard JSON**: Dati esportati in `src/data/shards/` e `public/data/shards/`.
- [ ] **5. Sviluppo Astro SSG**: Pagine `/`, `/autour-de-moi/`, `/[dept]/`, `/[dept]/[commune]/` con raggio a 20 km e `LiveDateBadge`.
- [ ] **6. Mappe Leaflet**: Widget con palloncini raggruppati e filtro "Aperte ora" con fallback sicuro.
- [ ] **7. AdSense & Consent Mode v2**: Meta tag verifica, script CMP, `ads.txt` e CSS adslot trasparente anti-spazi bianchi.
- [ ] **8. IndexNow & Ping Google**: Chiave IndexNow pubblicata in `public/`, script di notifica testato con HTTP 202.
- [ ] **9. Cloudflare Pages Deploy**: Progetto creato su Cloudflare Pages e deploy automatico tramite script `deploy.sh`.
- [ ] **10. Crontab sul Server**: Job schedulato protetto da `flock` e regole documentate in `CONTABO-SERVER-RULES.md`.
- [ ] **11. Authority GitHub**: Repository pubblico, README con anchor link tematici, tag Release v1.0.0 e Gist pubblico.
