#!/usr/bin/env bash
# Full n8n queue-mode integration: real Webhook -> n8n Worker -> Python API.
set -euo pipefail
COMPOSE="n8n/docker-compose.yml"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-codex-n8n-e2e-$$}"
if [ -n "$(docker compose -f "$COMPOSE" ps -a -q)" ]; then
  echo "Refusing to reuse an existing Compose project; existing containers and volumes are preserved" >&2
  exit 1
fi
python - <<'PY'
import socket
for port in (8000,8001,5678):
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        try: listener.bind(('0.0.0.0',port))
        except OSError: raise SystemExit(f'Port {port} is occupied; refusing to touch the existing service')
PY
if [ -n "${N8N_E2E_STATE_DIR:-}" ] && [ -e "$N8N_E2E_STATE_DIR" ]; then
  echo "Refusing to overwrite an existing review state directory" >&2
  exit 1
fi
export N8N_DB_PASSWORD
N8N_DB_PASSWORD="$(openssl rand -hex 18)"
export N8N_REDIS_PASSWORD
N8N_REDIS_PASSWORD="$(openssl rand -hex 18)"
export N8N_ENCRYPTION_KEY
N8N_ENCRYPTION_KEY="$(openssl rand -hex 32)"
export CI_SCENARIO_TOKEN
CI_SCENARIO_TOKEN="$(openssl rand -hex 24)"
export ALPHA_NODE_API_KEY="$CI_SCENARIO_TOKEN"
E2E_RUN_DIR="${N8N_E2E_STATE_DIR:-$(mktemp -d /tmp/investor-n8n-e2e.XXXXXX)}"
mkdir -p "$E2E_RUN_DIR"
export SCENARIO_DB_PATH="$E2E_RUN_DIR/scenarios.sqlite3"
export STRATEGY_OPERATIONS_DB_PATH="$E2E_RUN_DIR/operations.sqlite3"
export ALPHA_TRADINGVIEW_BASE="http://127.0.0.1:8001"
export N8N_INTERNAL_WEBHOOK_BASE="http://127.0.0.1:5678"
REVIEW_STATE_DIR="${N8N_E2E_STATE_DIR:-}"
if [ -n "$REVIEW_STATE_DIR" ]; then
  mkdir -p "$REVIEW_STATE_DIR"
  chmod 700 "$REVIEW_STATE_DIR"
  export REVIEW_STATE_DIR
  python - <<'PY'
import json, os
from pathlib import Path
p=Path(os.environ['REVIEW_STATE_DIR'])/'credentials.json'
if p.exists():
    raise SystemExit('Refusing to replace existing review credentials; use a fresh isolated directory')
names=['N8N_DB_PASSWORD','N8N_REDIS_PASSWORD','N8N_ENCRYPTION_KEY','CI_SCENARIO_TOKEN','ALPHA_NODE_API_KEY']
fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
with os.fdopen(fd,'w') as f: json.dump({n:os.environ[n] for n in names},f)
PY
fi
mkdir -p "$E2E_RUN_DIR/import" "$E2E_RUN_DIR/import-ops"
python n8n/scripts/render_ci_workflows.py --output "$E2E_RUN_DIR/import"
python n8n/scripts/render_ci_workflows.py --source n8n/workflows/operations --expected 3 --output "$E2E_RUN_DIR/import-ops"
python n8n/scripts/mock_tradingview_service.py > "$E2E_RUN_DIR/fixture.log" 2>&1 &
FIXTURE_PID=$!

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 \
  > "$E2E_RUN_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
if [ -n "$REVIEW_STATE_DIR" ]; then
  export BACKEND_PID FIXTURE_PID
  python - <<'PY'
import json,os
from pathlib import Path
p=Path(os.environ['REVIEW_STATE_DIR'])/'processes.json'
p.write_text(json.dumps({n:int(os.environ[n]) for n in ['BACKEND_PID','FIXTURE_PID']}))
PY
fi
VERIFIED=0
cleanup() {
  if [ "${N8N_E2E_RETAIN:-0}" = "1" ] && { [ "$VERIFIED" = "1" ] || [ "${N8N_E2E_RETAIN_ON_FAILURE:-0}" = "1" ]; }; then
    echo "LOCAL_REVIEW_STACK_RETAINED verified=$VERIFIED"
    return
  fi
  docker compose -f "$COMPOSE" logs --tail=60 postgres redis n8n worker || true
  docker compose -f "$COMPOSE" down --volumes --remove-orphans || true
  kill "$BACKEND_PID" "$FIXTURE_PID" 2>/dev/null || true
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
docker cp "$E2E_RUN_DIR/import/." "$N8N_CONTAINER:/tmp/ci_workflows/"
docker exec "$N8N_CONTAINER" n8n import:workflow --separate --input=/tmp/ci_workflows
docker exec "$N8N_CONTAINER" mkdir -p /tmp/ci_ops
docker cp "$E2E_RUN_DIR/import-ops/." "$N8N_CONTAINER:/tmp/ci_ops/"
docker exec "$N8N_CONTAINER" n8n import:workflow --separate --input=/tmp/ci_ops
for n in $(seq -w 1 10); do
  echo "PUBLISH autonomousScenario$n"
  docker exec "$N8N_CONTAINER" n8n publish:workflow "--id=autonomousScenario$n"
done
for workflow in aiOperationF01 aiOperationF03 aiOperationF05; do
  echo "PUBLISH $workflow"
  docker exec "$N8N_CONTAINER" n8n publish:workflow "--id=$workflow"
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
    "SELECT count(*) FROM webhook_entity WHERE \"workflowId\" LIKE 'autonomousScenario%' OR \"workflowId\" LIKE 'aiOperationF0%';" | tr -d '\\r')"
  if [ "$WEBHOOKS" -ge 13 ]; then break; fi
  sleep 2
done
echo "REGISTERED_N8N_WEBHOOKS=$WEBHOOKS"
test "$WEBHOOKS" -ge 13

# Main health and published rows do not establish that the queue worker is ready.
for i in $(seq 1 60); do
  if docker compose -f "$COMPOSE" exec -T worker node -e \
    "fetch('http://127.0.0.1:5678/healthz/readiness').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
docker compose -f "$COMPOSE" exec -T worker node -e \
  "fetch('http://127.0.0.1:5678/healthz/readiness').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
echo "QUEUE_WORKER_READINESS_CONFIRMED"

python n8n/scripts/verify_real_worker.py
python n8n/scripts/verify_operational_flows.py
OPERATIONS_COUNT="$(docker compose -f "$COMPOSE" exec -T postgres psql -U n8n -d n8n -Atc \
  "SELECT count(*) FROM execution_entity WHERE status='success' AND \"workflowId\" IN ('aiOperationF01','aiOperationF03','aiOperationF05');" | tr -d '\r')"
echo "N8N_POSTGRES_SUCCESSFUL_OPERATIONS=$OPERATIONS_COUNT"
test "$OPERATIONS_COUNT" -ge 3

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
VERIFIED=1
