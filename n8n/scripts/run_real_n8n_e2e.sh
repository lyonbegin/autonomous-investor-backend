#!/usr/bin/env bash
# Full n8n queue-mode integration: real Webhook -> n8n Worker -> Python API.
set -euo pipefail
COMPOSE="n8n/docker-compose.yml"
export N8N_DB_PASSWORD
N8N_DB_PASSWORD="$(openssl rand -hex 18)"
export N8N_REDIS_PASSWORD
N8N_REDIS_PASSWORD="$(openssl rand -hex 18)"
export N8N_ENCRYPTION_KEY
N8N_ENCRYPTION_KEY="$(openssl rand -hex 32)"
export CI_SCENARIO_TOKEN
CI_SCENARIO_TOKEN="$(openssl rand -hex 24)"
export ALPHA_NODE_API_KEY="$CI_SCENARIO_TOKEN"
export SCENARIO_DB_PATH="/tmp/n8n-e2e-scenarios.sqlite3"
export N8N_INTERNAL_WEBHOOK_BASE="http://127.0.0.1:5678"
mkdir -p /tmp/n8n-ci-import
python n8n/scripts/render_ci_workflows.py --output /tmp/n8n-ci-import

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 \
  > /tmp/n8n-ci-backend.log 2>&1 &
BACKEND_PID=$!
cleanup() {
  docker compose -f "$COMPOSE" logs --tail=60 n8n worker || true
  docker compose -f "$COMPOSE" down --volumes --remove-orphans || true
  kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT

echo "BOOT n8n queue mode + PostgreSQL + Redis + Worker"
docker compose -f "$COMPOSE" up -d postgres redis n8n worker
for i in $(seq 1 90); do
  if curl --silent --fail http://127.0.0.1:5678/healthz >/dev/null 2>&1 &&
     curl --silent --fail -H "Authorization: Bearer $ALPHA_NODE_API_KEY" \
       http://127.0.0.1:8000/api/v1/alpha/scenarios >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
curl --fail --silent http://127.0.0.1:5678/healthz >/dev/null
curl --fail --silent -H "Authorization: Bearer $ALPHA_NODE_API_KEY" \
  http://127.0.0.1:8000/api/v1/alpha/scenarios >/dev/null
echo "MAIN_AND_BACKEND_HEALTHY"

N8N_CONTAINER="$(docker compose -f "$COMPOSE" ps -q n8n)"
docker exec "$N8N_CONTAINER" mkdir -p /tmp/ci_workflows
docker cp /tmp/n8n-ci-import/. "$N8N_CONTAINER:/tmp/ci_workflows/"
docker exec "$N8N_CONTAINER" n8n import:workflow --separate --input=/tmp/ci_workflows
for n in $(seq -w 1 10); do
  echo "PUBLISH autonomousScenario$n"
  docker exec "$N8N_CONTAINER" n8n publish:workflow "--id=autonomousScenario$n"
done
# CLI changes take effect when n8n main process restarts.
docker compose -f "$COMPOSE" restart n8n worker
for i in $(seq 1 60); do
  if curl --silent --fail http://127.0.0.1:5678/healthz >/dev/null 2>&1; then break; fi
  sleep 2
done
curl --fail --silent http://127.0.0.1:5678/healthz >/dev/null
echo "TEN_IMPORTED_AND_PUBLISHED_N8N_WORKFLOWS"
echo "Workflow publication and webhook registration summary:"
docker compose -f "$COMPOSE" exec -T postgres psql -U n8n -d n8n -Atc \
  'SELECT id, active, "activeVersionId" FROM workflow_entity ORDER BY id;'
for i in $(seq 1 70); do
  WEBHOOKS="$(docker compose -f "$COMPOSE" exec -T postgres psql -U n8n -d n8n -Atc \
    "SELECT count(*) FROM webhook_entity WHERE \"workflowId\" LIKE 'autonomousScenario%';" | tr -d '\\r')"
  if [ "$WEBHOOKS" -ge 10 ]; then break; fi
  sleep 2
done
echo "REGISTERED_N8N_WEBHOOKS=$WEBHOOKS"
test "$WEBHOOKS" -ge 10

python n8n/scripts/verify_real_worker.py

# Verify actual n8n execution history in *its own PostgreSQL*, not only Python.
for i in $(seq 1 60); do
  SUCCESS_COUNT="$(docker compose -f "$COMPOSE" exec -T postgres psql -U n8n -d n8n -Atc \
    "SELECT count(*) FROM execution_entity WHERE status='success' AND \"workflowId\" LIKE 'autonomousScenario%';" | tr -d '\r')"
  if [ "$SUCCESS_COUNT" -ge 10 ]; then break; fi
  sleep 2
done
echo "N8N_POSTGRES_SUCCESSFUL_WORKER_EXECUTIONS=$SUCCESS_COUNT"
test "$SUCCESS_COUNT" -ge 10
docker compose -f "$COMPOSE" exec -T postgres psql -U n8n -d n8n -Atc \
  'SELECT "workflowId",status,count(*) FROM execution_entity GROUP BY "workflowId",status ORDER BY "workflowId";'
