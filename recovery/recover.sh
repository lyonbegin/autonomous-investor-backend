#!/bin/sh
set -u

SOURCE_URL="${SOURCE_URL:-http://tradingview-recovery-source.railway.internal:8080/autonomous_investor.sqlite3}"
WORKDIR="${RECOVERY_DIR:-/recovery}"
SRC="$WORKDIR/source.sqlite3"
REC="$WORKDIR/recovered.sqlite3"
FINAL="$WORKDIR/autonomous_investor.sqlite3"

echo "=== SQLITE RECOVERY START ==="
date -Iseconds
df -h "$WORKDIR" || true
mkdir -p "$WORKDIR"
cd "$WORKDIR"

rm -f "$SRC" "$REC" "$FINAL" recovered_integrity.txt source_integrity.txt

echo "FETCH_SOURCE $SOURCE_URL"
i=0
until wget -O "$SRC" "$SOURCE_URL"; do
  i=$((i+1))
  if [ "$i" -ge 20 ]; then
    echo "SOURCE_FETCH_FAILED"
    sleep 3600
    exit 2
  fi
  echo "retry source fetch $i"
  sleep 3
done

echo "SOURCE_FILE"
ls -lh "$SRC"

echo "SOURCE_INTEGRITY"
sqlite3 "$SRC" "PRAGMA integrity_check;" > source_integrity.txt 2>&1 || true
head -n 50 source_integrity.txt || true

echo "RECOVER_BEGIN"
set +e
sqlite3 "$SRC" ".recover" | sqlite3 "$REC"
PIPE_STATUS=$?
set -e
echo "RECOVER_PIPE_STATUS=$PIPE_STATUS"
ls -lh "$REC" || true

echo "RECOVERED_INTEGRITY"
sqlite3 "$REC" "PRAGMA integrity_check;" > recovered_integrity.txt 2>&1 || true
cat recovered_integrity.txt || true

echo "TABLE_COUNTS"
for t in community_ideas community_scripts script_sources script_source_attempts source_details strategy_candidates agent_plans market_snapshots market_universe_current market_collector_state corporate_bond_prefix_queue horizon_discovery agent_discovery_links; do
  printf "%s=" "$t"
  sqlite3 "$REC" "SELECT COUNT(*) FROM \"$t\";" 2>/dev/null || echo ERR
done

FIRST_LINE="$(head -n 1 recovered_integrity.txt 2>/dev/null || true)"
if [ "$FIRST_LINE" = "ok" ]; then
  cp "$REC" "$FINAL"
  sync
  echo "RECOVERY_OK"
  ls -lh "$FINAL"
else
  echo "RECOVERY_NOT_OK"
fi

df -h "$WORKDIR" || true
echo "=== SQLITE RECOVERY FINISHED ==="
sleep 3600
