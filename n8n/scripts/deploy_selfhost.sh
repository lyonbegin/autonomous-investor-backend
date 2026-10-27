#!/usr/bin/env bash
# Non-Railway self-host deployment. Run on YOUR VPS with Docker Compose installed.
# Uses only server-local n8n/.env. Never prints database or auth secrets.
set -euo pipefail

cd "$(dirname "$0")/../.."
test -f n8n/.env || { echo >&2 "BLOCKED: n8n/.env is absent. Copy n8n/.env.example, replace all placeholders securely."; exit 20; }
command -v docker >/dev/null || { echo >&2 "BLOCKED: Docker missing"; exit 21; }
command -v openssl >/dev/null || { echo >&2 "BLOCKED: OpenSSL missing"; exit 22; }

set -a
# shellcheck disable=SC1091
. n8n/.env
set +a

for key in N8N_DB_PASSWORD N8N_REDIS_PASSWORD N8N_ENCRYPTION_KEY ALPHA_NODE_API_KEY INVESTMENT_DOMAIN INVESTMENT_ADMIN_USER INVESTMENT_ADMIN_PASSWORD_HASH; do
  value="$(printenv "$key" 2>/dev/null || true)"
  if [[ "$value" == "" || "$value" == *REPLACE* ]]; then
    echo >&2 "BLOCKED: configure $key in private n8n/.env"
    exit 23
  fi
done
if [[ "$INVESTMENT_DOMAIN" == "invest.example.com" || "$INVESTMENT_DOMAIN" == :* || "$INVESTMENT_DOMAIN" == "localhost" ]]; then
  echo >&2 "BLOCKED: real DNS name required; local HTTP test is CI-only"
  exit 24
fi
if [[ ${#N8N_DB_PASSWORD} -lt 20 || ${#N8N_REDIS_PASSWORD} -lt 20 || ${#N8N_ENCRYPTION_KEY} -lt 32 || ${#ALPHA_NODE_API_KEY} -lt 20 ]]; then
  echo >&2 "BLOCKED: secrets too short; 20+ chars for DB/API and 32+ for encryption key"
  exit 25
fi
# Docker Compose .env interpolation uses shell exports above and does not need shell expansion of bcrypt '$' contents.
if [[ "$INVESTMENT_ADMIN_PASSWORD_HASH" != \$2* ]]; then
  echo >&2 "BLOCKED: use a bcrypt hash from 'caddy hash-password', not a plaintext login password"
  exit 26
fi

compose() {
  docker compose -f n8n/docker-compose.yml -f n8n/docker-compose.backend.yml -f n8n/docker-compose.production.yml "$@"
}
echo "Validating private production configuration..."
compose config --quiet
echo "Starting Caddy (HTTPS), real React assets, FastAPI, n8n, Redis, PostgreSQL and Worker..."
compose up -d --build

healthy=0
for i in $(seq 1 80); do
  if curl --silent --fail --max-time 3 -H "Authorization: Bearer $ALPHA_NODE_API_KEY"      http://127.0.0.1:8000/api/v1/ops/overview >/dev/null 2>&1; then
    healthy=1
    break
  fi
  sleep 3
done
test "$healthy" = 1 || { echo >&2 "FAILED: FastAPI operations health check. Inspect 'docker compose logs invest-backend'."; exit 27; }

echo "PRODUCTION_BACKEND_API_HEALTHY"
echo "Caddy public domain: https://$INVESTMENT_DOMAIN/"
echo "n8n UI: SSH tunnel only (ssh -L 5678:127.0.0.1:5678 your-vps)"
echo "To verify public domain login protection: curl -I https://$INVESTMENT_DOMAIN/ (expected HTTP 401)"
echo "No broker live orders were enabled."
