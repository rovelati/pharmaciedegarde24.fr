#!/bin/bash
# daily-enrich-and-rebuild.sh — PharmacieDeGarde24.fr
# Eseguito ogni giorno via crontab sul server Contabo VPS
set -euo pipefail

ROOT_DIR="/var/www/pharmaciedegarde24.fr"
LOG_DIR="/var/log/pharmaciedegarde24"
LOG_FILE="$LOG_DIR/daily.log"
LOCK_FILE="/tmp/pharmaciedegarde24-daily.lock"

export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"

mkdir -p "$LOG_DIR"
exec 200>"$LOCK_FILE"
flock -n 200 || { echo "[$(date '+%Y-%m-%d %H:%M:%S')] Un'altra istanza è già in esecuzione, esco." >> "$LOG_FILE"; exit 0; }

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

log "============================================================"
log "Démarrage Daily Enrichment & Rebuild PharmacieDeGarde24.fr..."

cd "$ROOT_DIR"

# 1. Mise à jour des tours de garde (fenêtre glissante de 7 jours)
log "1. Génération des tours de garde (shifts)..."
/usr/bin/python3 ingest/generate_shifts.py >> "$LOG_FILE" 2>&1

# 2. Enrichissement Google Places (2 pharmacies par jour)
log "2. Enrichissement de 2 pharmacies via Google Places & Street View..."
/usr/bin/python3 ingest/enrich_pharmacies_google.py --limit 2 >> "$LOG_FILE" 2>&1

# 3. Export des données pour le build statique Astro
log "3. Export des données vers src/data et public/data..."
/usr/bin/python3 ingest/export_data.py >> "$LOG_FILE" 2>&1

# 4. Build du site Astro
log "4. Build SSG Astro..."
cd "$ROOT_DIR/site"
if [ ! -d "node_modules" ]; then
  npm install --legacy-peer-deps >> "$LOG_FILE" 2>&1
fi
npm run build >> "$LOG_FILE" 2>&1

# 5. Déploiement sur Cloudflare Pages
log "5. Déploiement Cloudflare Pages..."
CF_TOKEN_FILE="$ROOT_DIR/.cloudflare-token"
if [ -f "$CF_TOKEN_FILE" ]; then
  ACCOUNT_ID="$(grep -i '^accountid:' "$CF_TOKEN_FILE" | head -1 | cut -d: -f2- | tr -d ' ')"
  API_KEY="$(grep -i '^api-key:' "$CF_TOKEN_FILE" | head -1 | cut -d: -f2- | tr -d ' ')"
  EMAIL="$(grep -i '^email:' "$CF_TOKEN_FILE" | head -1 | cut -d: -f2- | tr -d ' ')"
  ZONE_ID="$(grep -i '^zoneid:' "$CF_TOKEN_FILE" | head -1 | cut -d: -f2- | tr -d ' ')"

  CLOUDFLARE_ACCOUNT_ID="$ACCOUNT_ID" \
  CLOUDFLARE_API_KEY="$API_KEY" \
  CLOUDFLARE_EMAIL="$EMAIL" \
  npx wrangler pages deploy dist --project-name=pharmaciedegarde24 --branch=main --commit-dirty=true >> "$LOG_FILE" 2>&1

  log "6. Purge du cache Cloudflare..."
  curl -s -X POST "https://api.cloudflare.com/client/v4/zones/${ZONE_ID}/purge_cache" \
    -H "X-Auth-Email: ${EMAIL}" \
    -H "X-Auth-Key: ${API_KEY}" \
    -H "Content-Type: application/json" \
    --data '{"purge_everything":true}' >> "$LOG_FILE" 2>&1 || true
fi

# 7. Ping IndexNow (Bing / Yandex / Naver)
log "7. Ping IndexNow des pharmacies enrichies et des hubs..."
cd "$ROOT_DIR"
/usr/bin/python3 scripts/notify_indexnow.py >> "$LOG_FILE" 2>&1 || true

# 8. Ping Google Indexing API
log "8. Ping Google Indexing API..."
/usr/bin/python3 scripts/notify_google_indexing.py >> "$LOG_FILE" 2>&1 || true

log "Cycle quotidien terminé avec succès !"
log "============================================================"
