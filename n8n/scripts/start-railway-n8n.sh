#!/bin/sh
set -eu
echo "n8n startup: verifying existing workflow DB"
# First deployment imports 13 workflows. Subsequent releases preserve operator edits.
n8n export:workflow --all --output=/tmp/ai-existing-workflows.json >/dev/null 2>&1 || echo '[]' >/tmp/ai-existing-workflows.json
if node -e "const fs=require('fs');let w=JSON.parse(fs.readFileSync('/tmp/ai-existing-workflows.json'));process.exit(Array.isArray(w)&&w.some(x=>x.id==='aiOperationF01')?0:1)"; then
  echo "n8n: F01 already installed; preserving existing workflows/credentials."
else
  echo "n8n: first run - preparing 13 workflows and credential"
  node /home/node/prepare-railway-import.mjs
  n8n import:credentials --input=/tmp/ai-n8n-credentials.json
  rm -f /tmp/ai-n8n-credentials.json
  n8n import:workflow --separate --input=/tmp/ai-n8n-railway-workflows
  for n in $(seq -w 1 10); do n8n publish:workflow "--id=autonomousScenario$n"; done
  for flow in aiOperationF01 aiOperationF03 aiOperationF05; do n8n publish:workflow "--id=$flow"; done
  echo "n8n: 13 workflows imported/published with shared encrypted HTTP Header Auth."
fi
exec n8n start
