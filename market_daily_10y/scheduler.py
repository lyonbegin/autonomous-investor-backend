"""Persistent fair collection queue for large multi-exchange 10-year daily pools.

The queue is independent of array offsets: a newly inserted listing cannot
change which existing symbol is awaiting download. Failed/short-history
instruments are retried with cooldown; refresh work has its own quota.
"""
from __future__ import annotations
import json
import math
import sqlite3
from datetime import date, datetime, timedelta, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS collection_queue (
    instrument_key TEXT PRIMARY KEY,
    asset_class TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    last_attempt TEXT,
    last_success TEXT,
    next_due TEXT NOT NULL,
    failure_count INTEGER NOT NULL DEFAULT 0,
    last_result TEXT NOT NULL DEFAULT 'PENDING',
    last_error TEXT,
    bar_count INTEGER NOT NULL DEFAULT 0,
    eligible INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_collection_queue_due ON collection_queue(next_due);
"""


class CollectionQueue:
    def __init__(self, store):
        self.store = store
        self.db = store.db
        with sqlite3.connect(self.db, timeout=30) as conn:
            conn.executescript(SCHEMA)

    def seed(self, instruments, asof):
        """Upsert listing membership; never clear historical queue or price rows."""
        today = str(asof)
        with sqlite3.connect(self.db, timeout=30) as conn:
            # Existing price data stays usable after migrating from cursor.json.
            old = {r[0]: r for r in conn.execute(
                "SELECT key, asset_class, rows, eligible, end_exclusive, updated_at FROM instruments")}
            for inst in instruments:
                prev = old.get(inst.key)
                last_success = prev[4] if prev else None
                due = (str(date.fromisoformat(last_success) + timedelta(days=7))
                       if last_success else today)
                conn.execute("""
                    INSERT INTO collection_queue
                      (instrument_key,asset_class,first_seen,last_seen,last_success,
                       next_due,last_result,bar_count,eligible)
                    VALUES (?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(instrument_key) DO UPDATE
                      SET asset_class=excluded.asset_class,
                          last_seen=excluded.last_seen
                """, (inst.key,inst.asset_class,today,today,last_success,due,
                      'IMPORTED' if prev else 'PENDING',
                      int(prev[2]) if prev else 0,int(prev[3]) if prev else 0))

    def choose(self, instruments, asof, limit, refresh_fraction=0.25):
        if limit < 1 or not 0 <= refresh_fraction <= 1:
            raise ValueError('INVALID_COLLECTION_BUDGET')
        lookup = {inst.key: inst for inst in instruments}
        today = str(asof)
        with sqlite3.connect(self.db, timeout=30) as con:
            # Priority: oldest overdue refresh; never-attempted in stable
            # listing discovery order; then due recovery retries.
            due = con.execute("""
                SELECT instrument_key, last_success, last_attempt, first_seen,
                       next_due, failure_count, eligible
                FROM collection_queue WHERE next_due<=?
                ORDER BY next_due, first_seen, instrument_key
            """, (today,)).fetchall()
        refresh = [r for r in due if r[0] in lookup and r[1]]
        initial = [r for r in due if r[0] in lookup and not r[2]]
        retry = [r for r in due if r[0] in lookup and r[2] and not r[1]]
        # Refresh backlog gets reserved capacity without starving discoveries.
        refreshed = min(len(refresh), int(math.ceil(limit * refresh_fraction)))
        ordered = refresh[:refreshed] + initial[:max(0,limit-refreshed)]
        chosen = {r[0] for r in ordered}
        for group in (retry, refresh, initial):
            for row in group:
                if len(ordered) >= limit:
                    break
                if row[0] not in chosen:
                    ordered.append(row)
                    chosen.add(row[0])
        return [lookup[row[0]] for row in ordered]

    def record(self, inst, asof, result):
        success = result.get('status') == 'COLLECTED'
        eligible = bool(result.get('eligible', False)) if success else False
        with sqlite3.connect(self.db,timeout=30) as conn:
            old = conn.execute(
                "SELECT failure_count FROM collection_queue WHERE instrument_key=?",
                (inst.key,)).fetchone()
            if old is None:
                raise ValueError('QUEUE_ENTRY_MISSING')
            count = 0 if success else min(old[0]+1,20)
            # Successful but short history: recheck occasionally; never pretend
            # that a newly-listed stock has a complete 10-year lookback.
            days = (7 if eligible else 30) if success else min(30,2**min(count,5))
            next_due = str(asof + timedelta(days=days))
            conn.execute("""
                UPDATE collection_queue
                   SET last_attempt=?, last_success=CASE WHEN ? THEN ? ELSE last_success END,
                       next_due=?, failure_count=?, last_result=?, last_error=?,
                       bar_count=CASE WHEN ? THEN ? ELSE bar_count END,
                       eligible=CASE WHEN ? THEN ? ELSE eligible END
                 WHERE instrument_key=?
            """, (str(asof),int(success),str(asof),next_due,count,
                  'COLLECTED_ELIGIBLE' if eligible else
                    'COLLECTED_INELIGIBLE' if success else 'FAILED',
                  None if success else str(result.get('reason','UNKNOWN_ERROR'))[:300],
                  int(success),int(result.get('rows',0)),
                  int(success),int(eligible),inst.key))
        return next_due

    def report(self, asof, batch_limit=100, refresh_days=7):
        with sqlite3.connect(self.db,timeout=30) as conn:
            counts = dict(conn.execute("""
                SELECT last_result, COUNT(*) FROM collection_queue GROUP BY last_result
            """).fetchall())
            total = conn.execute("SELECT COUNT(*) FROM collection_queue").fetchone()[0]
            pending = conn.execute("""
                SELECT COUNT(*) FROM collection_queue WHERE last_attempt IS NULL
            """).fetchone()[0]
            due = conn.execute("""
                SELECT COUNT(*) FROM collection_queue WHERE next_due <= ?
            """,(str(asof),)).fetchone()[0]
            # A stored bar file can be 10Y-eligible yet its latest snapshot is
            # too stale for SCAMP comparisons. Report this separately.
            eligible_recent = conn.execute("""
                SELECT COUNT(*) FROM collection_queue q
                JOIN instruments i ON i.key=q.instrument_key
                WHERE i.eligible=1 AND i.end_exclusive>=?
            """,(str(asof-timedelta(days=refresh_days)),)).fetchone()[0]
            historical_eligible = conn.execute(
                "SELECT COUNT(*) FROM instruments WHERE eligible=1").fetchone()[0]
        return {
            'asof_exclusive':str(asof), 'listing_candidates':total,
            'never_attempted':pending,'due_now':due,
            'result_counts':counts,
            'historical_eligible_rows':historical_eligible,
            'recent_eligible_rows':eligible_recent,
            'batch_limit':batch_limit,
            'minimum_daily_capacity_for_7d_refresh':math.ceil(total/refresh_days),
            'estimated_first_pass_days_at_full_new_capacity':math.ceil(total/batch_limit) if batch_limit else None,
            'capacity_below_7d_full_refresh':batch_limit*refresh_days<total,
            'worldwide_coverage_verified':False,
        }
