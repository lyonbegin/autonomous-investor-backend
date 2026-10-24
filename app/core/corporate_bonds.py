from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import threading
import time
from datetime import UTC, datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from urllib import error

from app.core.tradingview import (
    DB_PATH,
    MARKET_SCANNER_PROFILES,
    SCANNER_URL,
    _connect,
    _http_json,
    _market_cycle_id,
    init_db,
    utcnow,
)


MARKET = "corporate-bonds"
BOND_URL = SCANNER_URL.format(market="bond") + "?label-product=popup-screener-bond"
BOND_COLUMNS = list(MARKET_SCANNER_PROFILES[MARKET]["columns"])
COLUMN_INDEX = {name: idx for idx, name in enumerate(BOND_COLUMNS)}
CORPORATE_FILTER = {"left": "typespecs", "operation": "has", "right": "corporate"}

# TradingView throttles anonymous Bond Screener requests aggressively. All bond
# worker threads share this limiter so concurrency cannot turn into a burst.
_QUERY_LOCK = threading.Lock()
_NEXT_QUERY_AT = 0.0
_QUERY_INTERVAL_SECONDS = 0.08
_MAX_QUERY_RETRIES = 12

# Four disjoint areas cover the current public corporate-bond universe.
# Each phase has a numeric primary key so the 10-row anonymous cap can be
# traversed with keyset pagination rather than offset pagination.
PHASES: list[dict[str, Any]] = [
    {
        "phase": "yield",
        "filters": [{"left": "yield_to_worst", "operation": "nempty", "right": None}],
        "field": "yield_to_worst",
        "tie_fields": ["maturity_date", "current_coupon", "close_pct", "close_net"],
    },
    {
        "phase": "yield_empty_maturity",
        "filters": [
            {"left": "yield_to_worst", "operation": "empty", "right": None},
            {"left": "maturity_date", "operation": "nempty", "right": None},
        ],
        "field": "maturity_date",
        "tie_fields": ["current_coupon", "close_pct", "close_net"],
    },
    {
        "phase": "yield_maturity_empty_coupon",
        "filters": [
            {"left": "yield_to_worst", "operation": "empty", "right": None},
            {"left": "maturity_date", "operation": "empty", "right": None},
            {"left": "current_coupon", "operation": "nempty", "right": None},
        ],
        "field": "current_coupon",
        "tie_fields": ["close_pct", "close_net"],
    },
    {
        "phase": "yield_maturity_coupon_empty_price",
        "filters": [
            {"left": "yield_to_worst", "operation": "empty", "right": None},
            {"left": "maturity_date", "operation": "empty", "right": None},
            {"left": "current_coupon", "operation": "empty", "right": None},
            {"left": "close_pct", "operation": "nempty", "right": None},
        ],
        "field": "close_pct",
        "tie_fields": ["close_net"],
    },
    {
        "phase": "final_close_net",
        "filters": [
            {"left": "yield_to_worst", "operation": "empty", "right": None},
            {"left": "maturity_date", "operation": "empty", "right": None},
            {"left": "current_coupon", "operation": "empty", "right": None},
            {"left": "close_pct", "operation": "empty", "right": None},
            {"left": "close_net", "operation": "nempty", "right": None},
        ],
        "field": "close_net",
        "tie_fields": [],
    },
]


def init_corporate_bond_db() -> None:
    init_db()
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS corporate_bond_scan_state (
                market TEXT PRIMARY KEY,
                scan_id TEXT NOT NULL,
                source_total INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                last_error TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS corporate_bond_scan_tasks (
                scan_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                phase TEXT NOT NULL,
                primary_field TEXT NOT NULL,
                low_value REAL NOT NULL,
                high_value REAL NOT NULL,
                cursor_value REAL,
                filters_json TEXT NOT NULL,
                tie_fields_json TEXT NOT NULL,
                estimated_count INTEGER NOT NULL DEFAULT 0,
                pages_done INTEGER NOT NULL DEFAULT 0,
                rows_seen INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                last_error TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (scan_id, task_id)
            );
            CREATE INDEX IF NOT EXISTS idx_corporate_bond_tasks_status
                ON corporate_bond_scan_tasks(scan_id, status, phase);

            CREATE TABLE IF NOT EXISTS corporate_bond_scan_rows (
                scan_id TEXT NOT NULL,
                ticker TEXT NOT NULL,
                raw_json TEXT NOT NULL,
                collected_at TEXT NOT NULL,
                PRIMARY KEY (scan_id, ticker)
            );
            CREATE INDEX IF NOT EXISTS idx_corporate_bond_rows_scan
                ON corporate_bond_scan_rows(scan_id);
            """
        )


def _normalize_row(item: dict[str, Any]) -> dict[str, Any]:
    values = item.get("d") or []
    row = dict(zip(BOND_COLUMNS, values))
    row["ticker"] = str(item.get("s") or "")
    ticker_view = row.get("ticker-view") if isinstance(row.get("ticker-view"), dict) else {}
    row["name"] = ticker_view.get("name") or row.get("isin-displayed") or row["ticker"]
    row["description"] = ticker_view.get("description") or ""
    row["ticker_view"] = ticker_view
    row["close"] = row.get("close_pct")
    row["change"] = row.get("close_net")
    row["type"] = row.get("type") or ticker_view.get("type") or "bond"
    row["exchange"] = row.get("exchange.tr")
    return row


def _wait_for_query_slot() -> None:
    global _NEXT_QUERY_AT
    with _QUERY_LOCK:
        now = time.monotonic()
        wait_for = max(0.0, _NEXT_QUERY_AT - now)
        if wait_for > 0:
            time.sleep(wait_for)
        _NEXT_QUERY_AT = time.monotonic() + _QUERY_INTERVAL_SECONDS


def _query(
    filters: list[dict[str, Any]],
    *,
    sort_by: str,
    sort_order: str = "asc",
) -> dict[str, Any]:
    payload = {
        "filter": [CORPORATE_FILTER, *filters],
        "options": {"lang": "ko"},
        "markets": ["bond"],
        "columns": BOND_COLUMNS,
        "sort": {"sortBy": sort_by, "sortOrder": sort_order},
        "range": [0, 10],
    }

    last_error: Exception | None = None
    for attempt in range(_MAX_QUERY_RETRIES):
        _wait_for_query_slot()
        try:
            raw = _http_json(BOND_URL, method="POST", payload=payload)
            return {
                "total_count": int(raw.get("totalCount") or 0),
                "items": [_normalize_row(x) for x in (raw.get("data") or []) if isinstance(x, dict)],
            }
        except error.HTTPError as exc:
            last_error = exc
            if exc.code != 429:
                raise
            retry_after = 0.0
            try:
                retry_after = float(exc.headers.get("Retry-After") or 0)
            except (TypeError, ValueError):
                retry_after = 0.0
            delay = max(retry_after, min(90.0, 2.0 * (2 ** attempt)))
            time.sleep(delay)
        except Exception as exc:
            last_error = exc
            if attempt >= _MAX_QUERY_RETRIES - 1:
                raise
            time.sleep(min(10.0, 0.75 * (attempt + 1)))

    if last_error is not None:
        raise last_error
    raise RuntimeError("TradingView bond query failed without an exception")


def _numeric_value(row: dict[str, Any], field: str) -> float | None:
    value = row.get(field)
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _bounds(filters: list[dict[str, Any]], field: str) -> tuple[float, float, int] | None:
    asc = _query(filters, sort_by=field, sort_order="asc")
    total = int(asc["total_count"])
    if total <= 0 or not asc["items"]:
        return None
    lo = _numeric_value(asc["items"][0], field)
    desc = _query(filters, sort_by=field, sort_order="desc")
    hi = _numeric_value(desc["items"][0], field) if desc["items"] else None
    if lo is None or hi is None:
        return None
    return (min(lo, hi), max(lo, hi), total)


def _partition_bounds(lo: float, hi: float, estimated_count: int, target_rows: int = 500) -> list[tuple[float, float]]:
    if estimated_count <= 0:
        return []
    count = max(1, min(512, math.ceil(estimated_count / max(target_rows, 10))))
    if count == 1 or hi <= lo:
        return [(lo, hi)]
    step = (hi - lo) / count
    ranges: list[tuple[float, float]] = []
    for i in range(count):
        left = lo + step * i
        right = hi if i == count - 1 else lo + step * (i + 1)
        ranges.append((left, right))
    return ranges


def _task_filters(task: dict[str, Any], cursor: float | None = None) -> list[dict[str, Any]]:
    filters = json.loads(str(task["filters_json"]))
    filters.append({
        "left": str(task["primary_field"]),
        "operation": "in_range",
        "right": [float(task["low_value"]), float(task["high_value"])],
    })
    if cursor is not None:
        filters.append({
            "left": str(task["primary_field"]),
            "operation": "greater",
            "right": float(cursor),
        })
    return filters


def _store_rows(scan_id: str, rows: list[dict[str, Any]]) -> int:
    clean = {str(row.get("ticker") or ""): row for row in rows if row.get("ticker")}
    if not clean:
        return 0
    now = utcnow()
    conn = sqlite3.connect(DB_PATH, timeout=60, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout = 60000")
        conn.execute("PRAGMA journal_mode=MEMORY")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA synchronous=OFF")
        before = int(conn.execute(
            "SELECT COUNT(*) AS c FROM corporate_bond_scan_rows WHERE scan_id=?",
            (scan_id,),
        ).fetchone()["c"])
        conn.execute("BEGIN IMMEDIATE")
        conn.executemany(
            """
            INSERT INTO corporate_bond_scan_rows (scan_id,ticker,raw_json,collected_at)
            VALUES (?,?,?,?)
            ON CONFLICT(scan_id,ticker) DO UPDATE SET
                raw_json=excluded.raw_json,
                collected_at=excluded.collected_at
            """,
            [
                (scan_id, ticker, json.dumps(row, ensure_ascii=False), now)
                for ticker, row in clean.items()
            ],
        )
        conn.execute("COMMIT")
        after = int(conn.execute(
            "SELECT COUNT(*) AS c FROM corporate_bond_scan_rows WHERE scan_id=?",
            (scan_id,),
        ).fetchone()["c"])
        return max(0, after - before)
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        conn.close()


def _collect_exclusion_group(
    filters: list[dict[str, Any]],
    *,
    sort_by: str,
    max_rounds: int = 10000,
) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for _ in range(max_rounds):
        local = list(filters)
        if seen:
            local.append({
                "left": "symbol-fullname",
                "operation": "not_in_range",
                "right": list(seen.keys()),
            })
        result = _query(local, sort_by=sort_by, sort_order="asc")
        rows = result["items"]
        new_count = 0
        for row in rows:
            ticker = str(row.get("ticker") or "")
            if ticker and ticker not in seen:
                seen[ticker] = row
                new_count += 1
        if len(seen) >= int(result["total_count"]) + len(seen) - new_count:
            # The total returned after exclusion is the remaining count.
            if int(result["total_count"]) <= len(rows):
                break
        if not rows or new_count == 0:
            break
    return list(seen.values())


def _collect_group(
    filters: list[dict[str, Any]],
    tie_fields: list[str],
    *,
    depth: int = 0,
) -> list[dict[str, Any]]:
    sort_by = tie_fields[0] if tie_fields else "name"
    first = _query(filters, sort_by=sort_by, sort_order="asc")
    total = int(first["total_count"])
    if total <= 10:
        return list(first["items"])
    if not tie_fields:
        return _collect_exclusion_group(filters, sort_by="name")

    field = tie_fields[0]
    rest = tie_fields[1:]
    collected: dict[str, dict[str, Any]] = {}

    nonempty_filters = [
        *filters,
        {"left": field, "operation": "nempty", "right": None},
    ]
    cursor: float | None = None
    safety = 0
    while safety < 100000:
        safety += 1
        page_filters = list(nonempty_filters)
        if cursor is not None:
            page_filters.append({"left": field, "operation": "greater", "right": cursor})
        page = _query(page_filters, sort_by=field, sort_order="asc")
        rows = page["items"]
        if not rows:
            break
        for row in rows:
            ticker = str(row.get("ticker") or "")
            if ticker:
                collected[ticker] = row
        last_value = _numeric_value(rows[-1], field)
        if last_value is None:
            break
        equal_filters = [
            *nonempty_filters,
            {"left": field, "operation": "equal", "right": last_value},
        ]
        equal_rows = _collect_group(equal_filters, rest, depth=depth + 1)
        for row in equal_rows:
            ticker = str(row.get("ticker") or "")
            if ticker:
                collected[ticker] = row
        if cursor is not None and last_value <= cursor:
            break
        cursor = last_value

    empty_rows = _collect_group(
        [*filters, {"left": field, "operation": "empty", "right": None}],
        rest,
        depth=depth + 1,
    )
    for row in empty_rows:
        ticker = str(row.get("ticker") or "")
        if ticker:
            collected[ticker] = row
    return list(collected.values())


def _init_scan(force_new: bool = False) -> dict[str, Any]:
    init_corporate_bond_db()
    now = utcnow()
    with _connect() as conn:
        state = conn.execute(
            "SELECT * FROM corporate_bond_scan_state WHERE market=?",
            (MARKET,),
        ).fetchone()
    if state is not None and not force_new:
        status = str(state["status"])
        if status == "COLLECTING":
            return dict(state)
        if status == "COMPLETE" and state["completed_at"]:
            try:
                completed_at = datetime.fromisoformat(str(state["completed_at"]))
                if completed_at.tzinfo is None:
                    completed_at = completed_at.replace(tzinfo=UTC)
                if datetime.now(UTC) - completed_at < timedelta(hours=24):
                    return dict(state)
            except (TypeError, ValueError):
                pass

    source = _query([], sort_by="yield_to_worst", sort_order="asc")
    source_total = int(source["total_count"])
    scan_id = "CB-" + hashlib.sha1(f"{now}|{source_total}".encode()).hexdigest()[:16].upper()

    tasks: list[tuple[Any, ...]] = []
    for phase in PHASES:
        bounds = _bounds(list(phase["filters"]), str(phase["field"]))
        if bounds is None:
            continue
        lo, hi, estimated = bounds
        ranges = _partition_bounds(lo, hi, estimated)
        for index, (left, right) in enumerate(ranges):
            task_id = f"{phase['phase']}:{index:04d}"
            tasks.append((
                scan_id,
                task_id,
                str(phase["phase"]),
                str(phase["field"]),
                left,
                right,
                None,
                json.dumps(phase["filters"], ensure_ascii=False),
                json.dumps(phase["tie_fields"], ensure_ascii=False),
                max(1, math.ceil(estimated / max(len(ranges), 1))),
                0,
                0,
                "PENDING",
                None,
                now,
            ))

    # Defensive catch-all. Currently zero rows, but if TradingView later creates
    # a bond with all numeric pagination keys empty, retain it instead of losing it.
    all_empty_filters = [
        {"left": "yield_to_worst", "operation": "empty", "right": None},
        {"left": "maturity_date", "operation": "empty", "right": None},
        {"left": "current_coupon", "operation": "empty", "right": None},
        {"left": "close_pct", "operation": "empty", "right": None},
        {"left": "close_net", "operation": "empty", "right": None},
    ]
    all_empty = _query(all_empty_filters, sort_by="name", sort_order="asc")
    if int(all_empty["total_count"]) > 0:
        # Synthetic numeric bounds are not useful here; one special task uses
        # exclusion pagination and is handled separately by the worker.
        tasks.append((
            scan_id, "all-empty", "all_empty", "__all_empty__", 0.0, 0.0, None,
            json.dumps(all_empty_filters, ensure_ascii=False),
            json.dumps([], ensure_ascii=False),
            int(all_empty["total_count"]), 0, 0, "PENDING", None, now,
        ))

    with _connect() as conn:
        if force_new:
            conn.execute("DELETE FROM corporate_bond_scan_tasks WHERE status <> 'COMPLETE'")
        conn.execute(
            """
            INSERT INTO corporate_bond_scan_state (
                market,scan_id,source_total,status,started_at,completed_at,last_error,updated_at
            ) VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(market) DO UPDATE SET
                scan_id=excluded.scan_id,
                source_total=excluded.source_total,
                status=excluded.status,
                started_at=excluded.started_at,
                completed_at=NULL,
                last_error=NULL,
                updated_at=excluded.updated_at
            """,
            (MARKET, scan_id, source_total, "COLLECTING", now, None, None, now),
        )
        conn.executemany(
            """
            INSERT OR REPLACE INTO corporate_bond_scan_tasks (
                scan_id,task_id,phase,primary_field,low_value,high_value,cursor_value,
                filters_json,tie_fields_json,estimated_count,pages_done,rows_seen,
                status,last_error,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            tasks,
        )
    return {
        "market": MARKET,
        "scan_id": scan_id,
        "source_total": source_total,
        "status": "COLLECTING",
        "started_at": now,
        "completed_at": None,
        "last_error": None,
        "updated_at": now,
    }


def _process_task(task: dict[str, Any], max_pages: int) -> dict[str, Any]:
    scan_id = str(task["scan_id"])
    task_id = str(task["task_id"])
    field = str(task["primary_field"])
    tie_fields = json.loads(str(task["tie_fields_json"]))
    cursor = float(task["cursor_value"]) if task["cursor_value"] is not None else None
    pages_done = int(task["pages_done"] or 0)
    rows_seen = int(task["rows_seen"] or 0)

    if field == "__all_empty__":
        filters = json.loads(str(task["filters_json"]))
        rows = _collect_exclusion_group(filters, sort_by="name")
        added = _store_rows(scan_id, rows)
        with _connect() as conn:
            conn.execute(
                """
                UPDATE corporate_bond_scan_tasks
                SET status='COMPLETE',pages_done=pages_done+1,
                    rows_seen=rows_seen+?,last_error=NULL,updated_at=?
                WHERE scan_id=? AND task_id=?
                """,
                (added, utcnow(), scan_id, task_id),
            )
        return {"task_id": task_id, "complete": True, "added": added}

    added_total = 0
    local_pages = 0
    try:
        while local_pages < max_pages:
            filters = _task_filters(task, cursor)
            page = _query(filters, sort_by=field, sort_order="asc")
            rows = page["items"]
            if not rows:
                with _connect() as conn:
                    conn.execute(
                        """
                        UPDATE corporate_bond_scan_tasks
                        SET status='COMPLETE',cursor_value=?,pages_done=?,
                            rows_seen=?,last_error=NULL,updated_at=?
                        WHERE scan_id=? AND task_id=?
                        """,
                        (cursor, pages_done + local_pages, rows_seen + added_total,
                         utcnow(), scan_id, task_id),
                    )
                return {"task_id": task_id, "complete": True, "added": added_total}

            last_value = _numeric_value(rows[-1], field)
            if last_value is None:
                raise RuntimeError(f"{field} unexpectedly null inside numeric task")

            # Always collect the entire equality group at the page boundary.
            equal_filters = [
                *json.loads(str(task["filters_json"])),
                {
                    "left": field,
                    "operation": "in_range",
                    "right": [float(task["low_value"]), float(task["high_value"])],
                },
                {"left": field, "operation": "equal", "right": last_value},
            ]
            equal_rows = _collect_group(equal_filters, tie_fields)
            batch = [*rows, *equal_rows]
            added_total += _store_rows(scan_id, batch)
            local_pages += 1

            if cursor is not None and last_value <= cursor:
                raise RuntimeError(f"non-advancing keyset cursor: {cursor} -> {last_value}")
            cursor = last_value

            with _connect() as conn:
                conn.execute(
                    """
                    UPDATE corporate_bond_scan_tasks
                    SET status='RUNNING',cursor_value=?,pages_done=?,
                        rows_seen=?,last_error=NULL,updated_at=?
                    WHERE scan_id=? AND task_id=?
                    """,
                    (cursor, pages_done + local_pages, rows_seen + added_total,
                     utcnow(), scan_id, task_id),
                )

        return {"task_id": task_id, "complete": False, "added": added_total}
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        with _connect() as conn:
            conn.execute(
                """
                UPDATE corporate_bond_scan_tasks
                SET status='ERROR',last_error=?,updated_at=?
                WHERE scan_id=? AND task_id=?
                """,
                (message, utcnow(), scan_id, task_id),
            )
        return {"task_id": task_id, "complete": False, "added": added_total, "error": message}


def _finalize_if_complete(scan_id: str) -> bool:
    init_corporate_bond_db()
    conn=sqlite3.connect(DB_PATH,timeout=180,isolation_level=None)
    conn.row_factory=sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout=180000")
        conn.execute("PRAGMA journal_mode=MEMORY")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA synchronous=OFF")
        remaining=int(conn.execute(
            "SELECT COUNT(*) FROM corporate_bond_scan_tasks WHERE scan_id=? AND status<>'COMPLETE'",
            (scan_id,),
        ).fetchone()[0])
        if remaining:
            return False
        rows=conn.execute(
            "SELECT ticker,raw_json,collected_at FROM corporate_bond_scan_rows WHERE scan_id=? ORDER BY ticker",
            (scan_id,),
        ).fetchall()
        if not rows:
            return False

        completed=utcnow()
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM market_universe_rows WHERE market=? AND scan_id=?",(MARKET,scan_id))
        conn.executemany(
            """
            INSERT INTO market_universe_rows (
                market,scan_id,rank_index,ticker,name,description,exchange,asset_type,
                raw_json,collected_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            [
                (
                    MARKET,scan_id,rank,row["ticker"],
                    (raw:=json.loads(str(row["raw_json"]))).get("name"),
                    raw.get("description"),raw.get("exchange"),raw.get("type"),
                    row["raw_json"],row["collected_at"],
                )
                for rank,row in enumerate(rows,start=1)
            ],
        )
        conn.execute(
            "DELETE FROM market_universe_rows WHERE market=? AND scan_id<>?",
            (MARKET,scan_id),
        )
        conn.execute("DELETE FROM market_universe_current WHERE market=?",(MARKET,))
        new_scan_id=_market_cycle_id(MARKET)
        state=conn.execute("SELECT market FROM market_collector_state WHERE market=?",(MARKET,)).fetchone()
        if state is None:
            conn.execute(
                """
                INSERT INTO market_collector_state (
                    market,cursor_offset,total_count,scan_id,cycle_started_at,last_completed_at,
                    last_error,updated_at,completed_scan_id
                ) VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (MARKET,0,len(rows),new_scan_id,completed,completed,None,completed,scan_id),
            )
        else:
            conn.execute(
                """
                UPDATE market_collector_state
                SET cursor_offset=0,total_count=?,scan_id=?,completed_scan_id=?,
                    cycle_started_at=?,last_completed_at=?,last_error=NULL,updated_at=?
                WHERE market=?
                """,
                (len(rows),new_scan_id,scan_id,completed,completed,completed,MARKET),
            )
        conn.execute(
            """
            UPDATE corporate_bond_scan_state
            SET status='COMPLETE',completed_at=?,last_error=NULL,updated_at=?
            WHERE market=?
            """,
            (completed,completed,MARKET),
        )
        conn.execute("COMMIT")
        return True
    except Exception:
        try: conn.execute("ROLLBACK")
        except Exception: pass
        raise
    finally:
        conn.close()


def _rebalance_stale_long_tasks(scan_id: str, *, min_pages: int = 15, parts: int = 32) -> int:
    """Split a stale long-running numeric task at its current cursor.

    Previously collected rows stay in corporate_bond_scan_rows and are keyed by
    ticker, so overlap at the cursor boundary is harmless while gaps are not.
    """
    stale_before = (datetime.now(UTC) - timedelta(seconds=30)).isoformat()
    now = utcnow()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM corporate_bond_scan_tasks
            WHERE scan_id=?
              AND pages_done>=?
              AND primary_field<>'__all_empty__'
              AND cursor_value IS NOT NULL
              AND (
                    status IN ('PENDING','ERROR')
                    OR (status='RUNNING' AND updated_at<?)
                  )
            ORDER BY pages_done DESC
            LIMIT 8
            """,
            (scan_id, min_pages, stale_before),
        ).fetchall()

    split_count = 0
    for raw in rows:
        task = dict(raw)
        cursor = float(task["cursor_value"])
        high = float(task["high_value"])
        if not math.isfinite(cursor) or not math.isfinite(high) or high <= cursor:
            continue
        count = max(2, min(int(parts), 64))
        step = (high - cursor) / count
        if step <= 0:
            continue

        children: list[tuple[Any, ...]] = []
        for i in range(count):
            low = cursor if i == 0 else cursor + step * i
            right = high if i == count - 1 else cursor + step * (i + 1)
            task_id = f"{task['task_id']}:R{i:02d}"
            children.append((
                scan_id,
                task_id,
                str(task["phase"]),
                str(task["primary_field"]),
                low,
                right,
                None,
                str(task["filters_json"]),
                str(task["tie_fields_json"]),
                max(10, int(task["estimated_count"] or 0) // count),
                0,
                0,
                "PENDING",
                None,
                now,
            ))

        with _connect() as conn:
            conn.execute(
                """
                UPDATE corporate_bond_scan_tasks
                SET status='COMPLETE',
                    last_error='REBALANCED_FROM_CURSOR',
                    updated_at=?
                WHERE scan_id=? AND task_id=?
                """,
                (now, scan_id, task["task_id"]),
            )
            conn.executemany(
                """
                INSERT OR IGNORE INTO corporate_bond_scan_tasks (
                    scan_id,task_id,phase,primary_field,low_value,high_value,cursor_value,
                    filters_json,tie_fields_json,estimated_count,pages_done,rows_seen,
                    status,last_error,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                children,
            )
        split_count += 1
    return split_count


def corporate_bond_backfill(
    *,
    max_tasks: int = 64,
    pages_per_task: int = 60,
    force_new: bool = False,
) -> dict[str, Any]:
    state = _init_scan(force_new=force_new)
    scan_id = str(state["scan_id"])
    rebalanced_tasks = _rebalance_stale_long_tasks(scan_id)
    safe_tasks = min(max(int(max_tasks), 1), 128)
    safe_pages = min(max(int(pages_per_task), 1), 500)
    worker_limit = min(8, safe_tasks)

    stale_before=(datetime.now(UTC)-timedelta(seconds=30)).isoformat()
    with _connect() as conn:
        # Recover interrupted workers, but never let overlapping cron/manual
        # invocations process the same live task.
        conn.execute(
            """
            UPDATE corporate_bond_scan_tasks
            SET status='PENDING',last_error='STALE_WORKER_RECOVERED',updated_at=?
            WHERE scan_id=? AND status='RUNNING' AND updated_at<?
            """,
            (utcnow(),scan_id,stale_before),
        )
        tasks = conn.execute(
            """
            SELECT * FROM corporate_bond_scan_tasks
            WHERE scan_id=? AND status IN ('PENDING','ERROR')
            ORDER BY CASE status WHEN 'ERROR' THEN 0 ELSE 1 END,
                     estimated_count DESC, task_id ASC
            LIMIT ?
            """,
            (scan_id, worker_limit),
        ).fetchall()
        conn.executemany(
            """
            UPDATE corporate_bond_scan_tasks
            SET status='RUNNING',last_error=NULL,updated_at=?
            WHERE scan_id=? AND task_id=?
            """,
            [(utcnow(), scan_id, row["task_id"]) for row in tasks],
        )

    results: list[dict[str, Any]] = []
    if tasks:
        with ThreadPoolExecutor(max_workers=min(worker_limit, len(tasks))) as executor:
            futures = [
                executor.submit(_process_task, dict(task), safe_pages)
                for task in tasks
            ]
            for future in as_completed(futures):
                results.append(future.result())

    complete = _finalize_if_complete(scan_id)
    return {
        "market": MARKET,
        "scan_id": scan_id,
        "source_total": int(state.get("source_total") or 0),
        "rebalanced_tasks": rebalanced_tasks,
        "selected_tasks": len(tasks),
        "workers": min(worker_limit, max(1, len(tasks))),
        "pages_per_task": safe_pages,
        "tasks_completed_this_run": sum(1 for x in results if x.get("complete")),
        "rows_added_this_run": sum(int(x.get("added") or 0) for x in results),
        "errors": [x for x in results if x.get("error")],
        "cycle_completed": complete,
        "state": corporate_bond_status(),
        "at": utcnow(),
    }


def corporate_bond_status() -> dict[str, Any]:
    init_corporate_bond_db()
    with _connect() as conn:
        state = conn.execute(
            "SELECT * FROM corporate_bond_scan_state WHERE market=?",
            (MARKET,),
        ).fetchone()
        if state is None:
            return {
                "market": MARKET,
                "status": "NOT_STARTED",
                "scan_id": None,
                "source_total": 0,
                "stored_count": 0,
                "tasks_total": 0,
                "tasks_complete": 0,
                "tasks_error": 0,
            }
        item = dict(state)
        scan_id = str(item["scan_id"])
        counts = conn.execute(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN status='COMPLETE' THEN 1 ELSE 0 END) AS complete,
                   SUM(CASE WHEN status='ERROR' THEN 1 ELSE 0 END) AS errors,
                   SUM(pages_done) AS pages_done
            FROM corporate_bond_scan_tasks
            WHERE scan_id=?
            """,
            (scan_id,),
        ).fetchone()
        stored = int(conn.execute(
            "SELECT COUNT(*) AS c FROM corporate_bond_scan_rows WHERE scan_id=?",
            (scan_id,),
        ).fetchone()["c"])
        error_rows = conn.execute(
            """
            SELECT last_error,COUNT(*) AS count
            FROM corporate_bond_scan_tasks
            WHERE scan_id=? AND status='ERROR'
            GROUP BY last_error
            ORDER BY count DESC
            LIMIT 20
            """,
            (scan_id,),
        ).fetchall()
        open_rows = conn.execute(
            """
            SELECT task_id,phase,primary_field,low_value,high_value,cursor_value,
                   estimated_count,pages_done,rows_seen,status,last_error,updated_at
            FROM corporate_bond_scan_tasks
            WHERE scan_id=? AND status<>'COMPLETE'
            ORDER BY estimated_count DESC,task_id ASC
            LIMIT 20
            """,
            (scan_id,),
        ).fetchall()
        open_tasks = [dict(row) for row in open_rows]
        error_summary = [
            {"error": str(row["last_error"] or ""), "count": int(row["count"] or 0)}
            for row in error_rows
        ]
        item.update({
            "stored_count": stored,
            "tasks_total": int(counts["total"] or 0),
            "tasks_complete": int(counts["complete"] or 0),
            "tasks_error": int(counts["errors"] or 0),
            "error_summary": error_summary,
            "open_tasks": open_tasks,
            "pages_done": int(counts["pages_done"] or 0),
            "progress": round(
                stored / max(int(item.get("source_total") or 0), 1) * 100,
                2,
            ),
        })
        return item
