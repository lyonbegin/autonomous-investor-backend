#!/bin/sh
set -u

WORKDIR="${RECOVERY_DIR:-/recovery}"
SRC="$WORKDIR/source.sqlite3"
SALV="$WORKDIR/salvaged.sqlite3"
FINAL="$WORKDIR/autonomous_investor.sqlite3"

echo "=== SQLITE TABLE SALVAGE START ==="
date -Iseconds
cd "$WORKDIR"

if [ ! -f "$SRC" ]; then
  echo "SOURCE_MISSING"
  sleep 3600
  exit 2
fi

rm -f "$SALV" "$FINAL" salvage_*.sql salvage_*.err salvage_integrity.txt
touch "$SALV"

TABLES="
community_ideas
community_scripts
script_sources
script_source_attempts
source_details
strategy_candidates
strategy_sources
agent_plans
agent_discovery_links
agent_status_history
agent_universe_members
horizon_discovery
collector_state
market_snapshots
market_collector_state
market_universe_current
market_universe_rows
bond_prefix_queue
corporate_bond_scan_state
corporate_bond_scan_tasks
corporate_bond_scan_rows
"

echo "SOURCE_COUNTS"
for t in $TABLES; do
  printf "%s=" "$t"
  sqlite3 "$SRC" "SELECT COUNT(*) FROM \"$t\";" 2>/dev/null || echo ERR
done

echo "SALVAGE_BEGIN"
SUCCESS=0
FAILED=0
for t in $TABLES; do
  echo "SALVAGE_TABLE $t"
  SQL="salvage_${t}.sql"
  ERR="salvage_${t}.err"
  rm -f "$SQL" "$ERR"
  if sqlite3 "$SRC" ".dump $t" > "$SQL" 2> "$ERR"; then
    if [ -s "$SQL" ]; then
      if sqlite3 "$SALV" < "$SQL" 2>> "$ERR"; then
        CNT="$(sqlite3 "$SALV" "SELECT COUNT(*) FROM \"$t\";" 2>/dev/null || echo ERR)"
        echo "SALVAGED $t=$CNT"
        SUCCESS=$((SUCCESS+1))
      else
        echo "IMPORT_FAILED $t"
        tail -n 10 "$ERR" || true
        FAILED=$((FAILED+1))
      fi
    else
      echo "EMPTY_DUMP $t"
      FAILED=$((FAILED+1))
    fi
  else
    echo "DUMP_FAILED $t"
    tail -n 10 "$ERR" || true
    FAILED=$((FAILED+1))
  fi
  rm -f "$SQL"
done

echo "SALVAGE_RESULT success=$SUCCESS failed=$FAILED"
echo "SALVAGE_INTEGRITY"
sqlite3 "$SALV" "PRAGMA integrity_check;" > salvage_integrity.txt 2>&1 || true
cat salvage_integrity.txt

echo "SALVAGE_TABLES"
sqlite3 "$SALV" ".tables" || true

echo "SALVAGE_COUNTS"
for t in $TABLES; do
  printf "%s=" "$t"
  sqlite3 "$SALV" "SELECT COUNT(*) FROM \"$t\";" 2>/dev/null || echo ERR
done

INTEGRITY="$(head -n 1 salvage_integrity.txt 2>/dev/null || true)"
CRITICAL_OK=1
for t in community_ideas community_scripts script_sources source_details strategy_candidates agent_plans horizon_discovery; do
  C="$(sqlite3 "$SALV" "SELECT COUNT(*) FROM \"$t\";" 2>/dev/null || echo ERR)"
  if [ "$C" = "ERR" ]; then CRITICAL_OK=0; fi
done

if [ "$INTEGRITY" = "ok" ] && [ "$CRITICAL_OK" = "1" ]; then
  cp "$SALV" "$FINAL"
  sync
  echo "SALVAGE_OK"
  ls -lh "$FINAL"
else
  echo "SALVAGE_NOT_OK"
fi

df -h "$WORKDIR" || true
echo "=== SQLITE TABLE SALVAGE FINISHED ==="
sleep 3600
