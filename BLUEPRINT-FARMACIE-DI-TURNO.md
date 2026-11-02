# Blueprint Definitivo: Portali Farmacie di Turno (Programmatic SEO & Open Data)
*Manuale operativo e architettura riutilizzabile per la creazione e il posizionamento di portali dedicati alle farmacie di turno (Francia, Italia, Spagna, Germania, UK).*

> **Implementazione di riferimento:** [PharmacieDeGarde24.fr](https://pharmaciedegarde24.fr)  
> **Repository GitHub:** [rovelati/pharmaciedegarde24.fr](https://github.com/rovelati/pharmaciedegarde24.fr)  
> **Tecnologie:** Astro 5 SSG, PostgreSQL 16, Cloudflare Pages, Leaflet MarkerCluster, Google Places API, Consent Mode v2.

---

## 1. La Specificità della Nicchia "Farmacie di Turno"

La query *"farmacia di turno / pharmacie de garde / farmacia de guardia"* possiede caratteristiche uniche nel panorama SEO:
1. **Intento di Ricerca ad Altissima Urgenza (Query Ospedaliera/Emergenza)**:
   - Più dell'85% del traffico arriva da **smartphone** tra le ore 19:30 e le 08:30 (fascia notturna) e per l'intera giornata di **domenica e festivi**.
   - L'utente ha bisogno di **2 informazioni cruciali entro 3 secondi**:
     1. Qual è la farmacia aperta **adesso** più vicina alla mia posizione.
     2. Il pulsante verde per **chiamare al telefono** e il pulsante per avviare il **navigatore GPS**.
2. **Rischio Thin Content / Soft-404**:
   - Nei comuni piccoli o medi, di notte solo 1 farmacia ogni 3-5 comuni è di turno. Se una pagina comune mostra solo le farmacie del territorio e nessuna è di turno, rischia di apparire "vuota". È **obbligatorio implementare l'algoritmo di espansione raggio (15–20 km)** per includere le farmacie di guardia dei comuni limitrofi.
3. **Segnali di Freschezza Algoritmica**:
   - Google premia i siti che dimostrano di avere orari e turni aggiornati al giorno esatto, punendo directory statiche abbandonate.

---

## 2. Fonti Dati Ufficiali per Paese

| Paese | Dominio Esempio | Fonti Dati Ufficiali | Note sul Dataset |
| :--- | :--- | :--- | :--- |
| **Francia 🇫🇷** | `pharmaciedegarde24.fr` | **FINESS Enrichi** (data.gouv.fr / DGS), **BAN** (Base Adresse Nationale) | ~21.165 officine. *Attenzione*: molti ID sono in `finess_ej` anziché `finess_et`; i CAP a 4 cifre necessitano di `zfill(5)`. |
| **Italia 🇮🇹** | `prontofarmacie.it` | **Ministero della Salute** (Open Data Farmacie), **Federfarma** regionali/provinciali | ~19.500 farmacie. Turnazioni regionali eterogenee (Lombardia, Veneto, Roma, ecc.). |
| **Spagna 🇪🇸** | `farmaciasdeguardia24.es` | **Colegios Oficiales de Farmacéuticos (COF)**, Portali Comunità Autonome | Gestione per province e aree sanitarie rurali. |
| **Germania 🇩🇪** | `apotheken-notdienst24.de` | **ABDA / Landesapothekerkammern** | Turni notturni e festivi rigorosamente regolati per distretti comunali. |

---

## 3. Schema Dati Relazionale (PostgreSQL)

```sql
-- 1. Tabella Entità Farmacia
CREATE TABLE pharmacies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  finess_id VARCHAR(30) UNIQUE NOT NULL, -- ID Ministeriale univoco
  nom VARCHAR(255) NOT NULL,
  slug VARCHAR(255) NOT NULL,
  adresse TEXT,
  code_postal VARCHAR(10) NOT NULL,
  ville VARCHAR(255) NOT NULL,
  departement_code VARCHAR(5) NOT NULL,
  lat NUMERIC(9,6),
  lon NUMERIC(9,6),
  telephone VARCHAR(30),
  is_open_24h BOOLEAN DEFAULT FALSE,
  is_garde_permanente BOOLEAN DEFAULT FALSE,
  
  -- Campi Arricchimento Google Places
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

-- 2. Tabella Turni di Guardia
CREATE TABLE garde_shifts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pharmacy_id UUID NOT NULL REFERENCES pharmacies(id) ON DELETE CASCADE,
  type_garde VARCHAR(20) NOT NULL, -- 'nuit', 'dimanche', 'jour_ferie', '24h'
  date_debut TIMESTAMPTZ NOT NULL,
  date_fin TIMESTAMPTZ NOT NULL,
  secteur VARCHAR(100),
  source VARCHAR(100),
  notes TEXT
);

CREATE INDEX idx_pharma_dept ON pharmacies(departement_code);
CREATE INDEX idx_pharma_cp ON pharmacies(code_postal);
CREATE INDEX idx_pharma_slug ON pharmacies(slug);
CREATE INDEX idx_shifts_active ON garde_shifts(date_debut, date_fin);
```

---

## 4. Algoritmo di Generazione e Visualizzazione Turni

### 4.1 Definizione Orari di Guardia
- **Garde de Nuit (Turno Notturno)**: `20:00` del giorno corrente $\rightarrow$ `08:00` del mattino successivo. Funzionamento obbligatorio a **battenti chiusi / volets fermés** per sicurezza, con prescrizione medica urgente.
- **Dimanche et Jours Fériés (Turno Festivo)**: `08:00` $\rightarrow$ `20:00` di giorno. Accesso libero senza obbligo di passaggio dalle forze dell'ordine.
- **Farmacie 24h/24**: aperte ininterrottamente 7 giorni su 7 (es. stazioni, piazze centrali delle grandi metropoli).

### 4.2 L'Algoritmo di Espansione del Raggio (20 km)
Nel template della pagina comune (`[dept]/[commune].astro`):

```typescript
// Formula geodetica di Haversine in km
function getDistanceKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLon / 2) * Math.sin(dLon / 2);
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// 1. Farmacie del comune
const localPharmacies = deptPharmacies.filter(p => 
  p.ville.toLowerCase() === commune.nom.toLowerCase() || 
  p.codePostal === commune.codePostal
).map(p => ({ ...p, isLocal: true, distanceKm: null }));

// 2. Farmacie limitrofe entro 20 km
const localIds = new Set(localPharmacies.map(p => p.id));
const nearbyPharmacies = deptPharmacies
  .filter(p => !localIds.has(p.id) && p.lat && p.lon)
  .map(p => ({
    ...p,
    distanceKm: Math.round(getDistanceKm(commune.lat, commune.lon, p.lat, p.lon) * 10) / 10,
    isLocal: false
  }))
  .filter(p => p.distanceKm <= 20)
  .sort((a, b) => a.distanceKm - b.distanceKm)
  .slice(0, 15);

const allPharmacies = [...localPharmacies, ...nearbyPharmacies];
```

**Vantaggio SEO**: anche un paesino rurale con una sola farmacia chiusa presenterà la farmacia di turno del comune vicino (es. `à 4.8 km`), offrendo una risposta immediata e impedendo la generazione di pagine "thin content".

---

## 5. Mappa con Palloncini Numerati (Leaflet + MarkerCluster)

### Configurazione Ottimale
- **Filtro di Default "Aperte & di Guardia"**:
  - All'apertura della pagina, la mappa evidenzia con un pallino verde solo le officine aperte adesso.
  - **Failsafe**: se nessuna farmacia ha un turno aperto all'istante esatto del rendering, il filtro passa automaticamente su "Tutte le officine" evitando che la mappa risulti vuota.
- **Marker Cluster a Palloncino**:
  - Cluster circolari con contatore arancione/verde (`.pharma-cluster-balloon`) con effetto spiderfy al click per distanziare farmacie vicine sulla stessa via.
- **Dark Mode Support**:
  - Tuile OpenStreetMap integrate nativamente con inversione filtri CSS controllata dal selettore di tema del portale.

---

## 6. Arricchimento Automatico Google Places (2 Schede/Giorno)

Per ottenere E-E-A-T reale (recensioni verificate, foto delle vetrine e orari dettagliati) senza spendere centinaia di euro:

1. **Google Cloud Places Text Search**: trova l'officina esatta tramite `nom + adresse + code_postal + ville`.
2. **Google Place Details**: preleva `reviews` reali, voto medio a stelle (`rating`), orari ordinari e sommario editoriale.
3. **Street View Static API**: genera la foto della facciata/devanture ad alta risoluzione:
   `https://maps.googleapis.com/maps/api/streetview?size=640x360&location={lat},{lon}&key={key}`
4. **Volume Giornaliero**: impostato a **2 farmacie al giorno** via cron:
   - Costo mensile: ~3,00 $ (coperto al 100% dai 200 $ di crediti gratuiti mensili di Google Cloud).
   - Impatto SEO: ogni giorno due schede ricevono contenuto unico, recensioni fresche e foto, inviando a Google un segnale di aggiornamento continuo.

---

## 7. Monetizzazione (AdSense) & CMP Google Consent Mode v2

### 7.1 Regole Fondamentali GDPR & IAB TCF v2.2
1. **Consent Mode v2 Obbligatorio**: prima di qualsiasi caricamento di tag AdSense o Google Analytics, definire il consenso di default su `denied`:
   ```javascript
   gtag('consent', 'default', {
     'ad_storage': 'denied',
     'ad_user_data': 'denied',
     'ad_personalization': 'denied',
     'analytics_storage': 'denied',
     'wait_for_update': 500
   });
   ```
2. **Google Funding Choices**: la CMP certificata Google viene attivata direttamente dall'AdSense console tramite lo script `adsbygoogle.js?client=ca-pub-...`.
3. **ads.txt**: file obbligatorio in `/public/ads.txt`:
   ```
   google.com, pub-2168172914069272, DIRECT, f08c47fec0942fa0
   ```

### 7.2 Rimozione Spazi Bianchi in Dark Mode
Google AdSense riserva un iframe con sfondo bianco se l'annuncio è in attesa di approvazione o non ha inventario. Per evitare buchi grafici:
```css
.adslot {
  min-height: 0;
  background: transparent !important;
  border: none !important;
  margin: 1.5rem 0;
  overflow: hidden;
}

.adslot ins.adsbygoogle {
  background: transparent !important;
}

.adslot ins.adsbygoogle[data-ad-status="unfilled"],
.adslot:empty {
  display: none !important;
  min-height: 0 !important;
}
```

---

## 8. Notifiche Istantanee (IndexNow & Google Indexing)

1. **IndexNow (`scripts/notify_indexnow.py`)**:
   - Pubblica la chiave in `/public/[key].txt`.
   - Invia ogni giorno a `https://api.indexnow.org/indexnow`:
     - L'homepage e il tool `/autour-de-moi/`
     - Le pagine delle 20 metropoli principali
     - Le schede farmacia arricchite nelle ultime 24 ore
   - Risposta tipica: `HTTP 202 Accepted` da Bing e Yandex.
2. **Google Indexing API (`scripts/notify_google_indexing.py`)**:
   - Utilizza un Service Account Google (`scopes: ['https://www.googleapis.com/auth/indexing']`).
   - Invia la notifica `URL_UPDATED` per le schede arricchite e le landing di guardia.

---

## 9. Automazione Quotidiana su VPS Contabo

### 9.1 Script Master `daily-enrich-and-rebuild.sh`
```bash
#!/bin/bash
set -euo pipefail

ROOT_DIR="/var/www/pharmaciedegarde24.fr"
LOG_FILE="/var/log/pharmaciedegarde24/daily.log"
LOCK_FILE="/tmp/pharmaciedegarde24-daily.lock"

mkdir -p "$(dirname "$LOG_FILE")"
exec 200>"$LOCK_FILE"
flock -n 200 || { echo "[$(date)] Già in esecuzione, esco." >> "$LOG_FILE"; exit 0; }

cd "$ROOT_DIR"
/usr/bin/python3 ingest/generate_shifts.py >> "$LOG_FILE" 2>&1
/usr/bin/python3 ingest/enrich_pharmacies_google.py --limit 2 >> "$LOG_FILE" 2>&1
/usr/bin/python3 ingest/export_data.py >> "$LOG_FILE" 2>&1

cd "$ROOT_DIR/site"
npm run build >> "$LOG_FILE" 2>&1

# Deploy Cloudflare Pages & Purge Cache
CLOUDFLARE_ACCOUNT_ID="383050c9ba92a1ab1144bc18d44f586c" \
CLOUDFLARE_API_KEY="9578b8b72ddb8947067606c42533c784203b6" \
CLOUDFLARE_EMAIL="romolo.velati@gmail.com" \
npx wrangler pages deploy dist --project-name=pharmaciedegarde24 --branch=main --commit-dirty=true >> "$LOG_FILE" 2>&1

curl -s -X POST "https://api.cloudflare.com/client/v4/zones/5de3d24e1589dcf766401b698e252719/purge_cache" \
  -H "X-Auth-Email: romolo.velati@gmail.com" \
  -H "X-Auth-Key: 9578b8b72ddb8947067606c42533c784203b6" \
  -H "Content-Type: application/json" \
  --data '{"purge_everything":true}' >> "$LOG_FILE" 2>&1 || true

cd "$ROOT_DIR"
/usr/bin/python3 scripts/notify_indexnow.py >> "$LOG_FILE" 2>&1 || true
/usr/bin/python3 scripts/notify_google_indexing.py >> "$LOG_FILE" 2>&1 || true
```

### 9.2 Crontab Schedulato
Inserito alle **05:25** (Europe/Paris), orario ideale privo di sovrapposizioni sul server:
```cron
25 5 * * * /usr/bin/flock -n /tmp/pharmaciedegarde24-daily.lock /var/www/pharmaciedegarde24.fr/scripts/daily-enrich-and-rebuild.sh >> /var/log/pharmaciedegarde24/daily.log 2>&1
```

---

## 10. Strategia Authority & Backlink Profiling (GitHub)

1. **Repository Open Source**: crea un repository pubblico `rovelati/[brand-farmacie]` con link al sito come `Homepage`.
2. **README Strutturato con Deep Link Dofollow**:
   - Tabella con le prime 20 città del paese collegate direttamente alle rispettive pagine di guardia.
   - Badge di certificazione Open Data e licenza MIT.
3. **GitHub Release v1.0.0**: pubblicata con descrizione formale dell'annuario e delle fonti ministeriali.
4. **Public GitHub Gist (DA 96+)**: documento markdown riassuntivo con rimandi diretti all'homepage e ai servizi di emergenza notturna.

---

## 11. Checklist di Replica per un Nuovo Paese

- [ ] **1. Dominio**: Acquistare il TLD nazionale (`.fr`, `.es`, `.de`, `.it`) e configurare DNS su Cloudflare.
- [ ] **2. PostgreSQL**: Creare il database locale su Contabo (`farmacie_[paese]`).
- [ ] **3. Ingestione Dataset**: Verificare campi univoci (`finess_et/ej`, codice postale con zero iniziale).
- [ ] **4. Logica Orari & Normativa Locale**: Regolamentare le fasce notturne (es. volets fermés in Francia, turni a chiamata in Italia).
- [ ] **5. Sharding JSON**: Generare partizioni per provincia/dipartimento in `src/data/shards/` e `public/data/shards/`.
- [ ] **6. Astro 5 Build**: Configurare getStaticPaths con raggio espanso a 20 km.
- [ ] **7. Mappa & CSS**: Integrare Leaflet MarkerCluster con tema scuro e adslot trasparente.
- [ ] **8. AdSense & Consent Mode v2**: Inserire publisher ID `pub-2168172914069272` e configurare `ads.txt`.
- [ ] **9. Crontab**: Inserire il job notturno con arricchimento di 2 farmacie/giorno.
- [ ] **10. GitHub Authority**: Creare repo pubblico, Release v1.0.0 e Gist con link alle principali città.
