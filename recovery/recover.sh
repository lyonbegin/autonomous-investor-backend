#!/bin/sh
set -u

SOURCE_URL="${SOURCE_URL:-http://tradingview-recovery-source2.railway.internal:8080/autonomous_investor.sqlite3}"
WORKDIR="${RECOVERY_DIR:-/recovery}"
SRC="$WORKDIR/source.sqlite3"
REC="$WORKDIR/recovered.sqlite3"
FINAL="$WORKDIR/autonomous_investor.sqlite3"
EXPECTED_MIN=900000000

echo "=== SQLITE RECOVERY START ==="
date -Iseconds
df -h "$WORKDIR" || true
mkdir -p "$WORKDIR"
cd "$WORKDIR"

SRC_SIZE=0
if [ -f "$SRC" ]; then SRC_SIZE="$(stat -c %s "$SRC" 2>/dev/null || echo 0)"; fi
if [ "$SRC_SIZE" -lt "$EXPECTED_MIN" ]; then
  echo "FETCH_SOURCE $SOURCE_URL"
  rm -f "$SRC"
  i=0
  until wget -4 -q -O "$SRC" "$SOURCE_URL"; do
    i=$((i+1))
    if [ "$i" -ge 20 ]; then
      echo "SOURCE_FETCH_FAILED"
      sleep 3600
      exit 2
    fi
    sleep 3
  done
else
  echo "SOURCE_REUSE size=$SRC_SIZE"
fi

ls -lh "$SRC"
rm -f "$REC" "$FINAL" recovered_integrity.txt recover_source.err recover_import.err



echo "SOURCE_SCHEMA_PROBE"
sqlite3 "$SRC" "SELECT type,name,tbl_name,rootpage FROM sqlite_master ORDER BY type,name;" 2>&1 | head -n 200 || true
echo "SOURCE_TABLE_PROBE"
for t in community_ideas community_scripts script_sources script_source_attempts source_details strategy_candidates agent_plans horizon_discovery agent_discovery_links market_snapshots market_universe_current market_collector_state corporate_bond_prefix_queue; do
  printf "%s=" "$t"
  sqlite3 "$SRC" "SELECT COUNT(*) FROM \"$t\";" 2>&1 | head -n 3 || true
done

echo "RECOVER_IGNORE_FREELIST_BEGIN"
set +e
sqlite3 "$SRC" ".recover --ignore-freelist" 2>recover_source.err | sqlite3 "$REC" 2>recover_import.err
PIPE_STATUS=$?
set -e
echo "RECOVER_PIPE_STATUS=$PIPE_STATUS"
echo "RECOVER_SOURCE_ERRORS"
tail -n 30 recover_source.err 2>/dev/null || true
echo "RECOVER_IMPORT_ERRORS"
tail -n 30 recover_import.err 2>/dev/null || true
echo "RECOVER_FILE"
ls -lh "$REC" || true

echo "RECOVERED_INTEGRITY"
sqlite3 "$REC" "PRAGMA integrity_check;" > recovered_integrity.txt 2>&1 || true
head -n 50 recovered_integrity.txt || true

echo "TABLES"
sqlite3 "$REC" ".tables" || true
echo "SCHEMA_OBJECT_COUNT"
SCHEMA_COUNT="$(sqlite3 "$REC" "SELECT COUNT(*) FROM sqlite_master;" 2>/dev/null || echo 0)"
echo "$SCHEMA_COUNT"

echo "TABLE_COUNTS"
for t in community_ideas community_scripts script_sources script_source_attempts source_details strategy_candidates agent_plans market_snapshots market_universe_current market_collector_state corporate_bond_prefix_queue horizon_discovery agent_discovery_links lost_and_found; do
  printf "%s=" "$t"
  sqlite3 "$REC" "SELECT COUNT(*) FROM \"$t\";" 2>/dev/null || echo ERR
done

FIRST_LINE="$(head -n 1 recovered_integrity.txt 2>/dev/null || true)"
if [ "$FIRST_LINE" = "ok" ] && [ "${SCHEMA_COUNT:-0}" -gt 0 ]; then
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
