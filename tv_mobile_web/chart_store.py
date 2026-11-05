"""Private research-only store for actual chart-observed five-year daily bars.

Existing TradingView chart link -> Playwright normal UI -> existing WF-02
WebSocket OHLCV parser -> 5Y/1D quality review -> atomic gzip + SQLite.
Never fabricates bars, reports partial coverage explicitly, no cron.
This is not a claim of TradingView market-data redistribution rights.
"""
from __future__ import annotations

from datetime import datetime, timezone, date
from hashlib import sha256
from pathlib import Path
import gzip
import json
import os
import re
import sqlite3
import tempfile

from .chart_observer import evaluate_history

_KEY=re.compile(r"^[A-Z0-9_]{1,30}:[A-Z0-9_.!/-]{1,65}$")
DDL="""CREATE TABLE IF NOT EXISTS chart_history (
    symbol TEXT NOT NULL,
    interval TEXT NOT NULL,
    asof_exclusive TEXT NOT NULL,
    requested_start TEXT NOT NULL,
    first_time_ms INTEGER,
    last_time_ms INTEGER,
    bar_count INTEGER NOT NULL,
    five_year_extent_covered INTEGER NOT NULL,
    interval_verified INTEGER NOT NULL,
    coverage_status TEXT NOT NULL,
    source TEXT NOT NULL,
    file_sha256 TEXT NOT NULL,
    stored_at TEXT NOT NULL,
    original_request_method TEXT NOT NULL,
    PRIMARY KEY(symbol,interval)
)"""


def _stamp():
    return datetime.now(timezone.utc).isoformat()


def _encoded(obj):
    return json.dumps(obj,ensure_ascii=False,separators=(",",":"),
                      sort_keys=True,allow_nan=False).encode("utf-8")


class ChartHistoryStore:
    def __init__(self,root):
        self.root=Path(root)
        self.root.mkdir(parents=True,exist_ok=True)
        self.files=self.root/"histories"
        self.files.mkdir(exist_ok=True)
        self.db=self.root/"chart_history.sqlite3"
        with sqlite3.connect(self.db) as conn:
            conn.execute(DDL)

    def file(self,symbol):
        if not _KEY.fullmatch(symbol):
            raise ValueError("INVALID_CHART_SYMBOL")
        return self.files/(sha256(symbol.encode()).hexdigest()+".1D.5Y.json.gz")

    def save_observation(self,result,asof):
        symbol=result.get("symbol")
        if not isinstance(symbol,str) or not _KEY.fullmatch(symbol):
            raise ValueError("INVALID_CHART_SYMBOL")
        if result.get("interval")!="1D":
            raise ValueError("STORE_ACCEPTS_DAILY_ONLY")
        # Original WebSocket bars are required, not widget data or Yahoo.
        if result.get("source")!="TRADINGVIEW_PUBLIC_CHART_NORMAL_UI_PASSIVE_WEBSOCKET":
            raise ValueError("UNVERIFIED_CHART_PROVENANCE")
        q=evaluate_history(result.get("bars") or [],interval="1D",asof=asof)
        if q["observed_count"]<20 or not q["interval_verified"]:
            raise ValueError("NO_VERIFIED_DAILY_CHART_BARS")
        payload={
            "schema_version":1,"symbol":symbol,"timeframe":"1D","years":5,
            "asof_exclusive":str(asof),
            "source":"TRADINGVIEW_PUBLIC_CHART_NORMAL_UI_PASSIVE_WEBSOCKET",
            "license_for_public_redistribution":False,
            "quality":{k:v for k,v in q.items() if k!="bars"},
            "bars":q["bars"],
        }
        raw=_encoded(payload)
        compressed=gzip.compress(raw,mtime=0)
        checksum=sha256(compressed).hexdigest()
        dest=self.file(symbol)
        fd,tmp=tempfile.mkstemp(prefix=".chart-observed-",dir=self.files)
        try:
            with os.fdopen(fd,"wb") as f:
                f.write(compressed)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp,dest)
        finally:
            Path(tmp).unlink(missing_ok=True)
        bars=q["bars"]
        with sqlite3.connect(self.db,timeout=20) as conn:
            conn.execute("""INSERT INTO chart_history VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
              ON CONFLICT(symbol,interval) DO UPDATE SET
              asof_exclusive=excluded.asof_exclusive,
              requested_start=excluded.requested_start,
              first_time_ms=excluded.first_time_ms,
              last_time_ms=excluded.last_time_ms,
              bar_count=excluded.bar_count,
              five_year_extent_covered=excluded.five_year_extent_covered,
              interval_verified=excluded.interval_verified,
              coverage_status=excluded.coverage_status,
              source=excluded.source,
              file_sha256=excluded.file_sha256,
              stored_at=excluded.stored_at,
              original_request_method=excluded.original_request_method""",
              (symbol,"1D",str(asof),q["requested_start"],
               bars[0]["time_ms"],bars[-1]["time_ms"],len(bars),
               int(q["five_year_window_covered"]),int(q["interval_verified"]),
               q["coverage_status"],payload["source"],checksum,_stamp(),
               "normal_ui_chart_websocket_observation"))
        return self.status(symbol)

    def status(self,symbol):
        if not _KEY.fullmatch(symbol):
            raise ValueError("INVALID_CHART_SYMBOL")
        with sqlite3.connect(self.db) as db:
            db.row_factory=sqlite3.Row
            row=db.execute("""SELECT * FROM chart_history
               WHERE symbol=? AND interval='1D'""",(symbol,)).fetchone()
        if row is None:
            return {"symbol":symbol,"interval":"1D","state":"NOT_COLLECTED",
                    "saved":False,"five_year_extent_covered":False,
                    "bar_count":0}
        record=dict(row)
        record["saved"]=self.file(symbol).is_file()
        if not record["saved"]:
            record["state"]="FILE_MISSING"
        elif not record["five_year_extent_covered"]:
            record["state"]="SAVED_PARTIAL_FIVE_YEAR_HISTORY"
        else:
            record["state"]="SAVED_FIVE_YEAR_DATE_EXTENT_UNAUDITED_SESSIONS"
        record["five_year_extent_covered"]=bool(record["five_year_extent_covered"])
        record["interval_verified"]=bool(record["interval_verified"])
        record["public_data_rights_verified"]=False
        return record

    def read(self,symbol,*,include_bars=True):
        state=self.status(symbol)
        if not state["saved"]:
            return {"metadata":state,"bars":[]}
        contents=self.file(symbol).read_bytes()
        if sha256(contents).hexdigest()!=state["file_sha256"]:
            raise ValueError("CHART_STORED_SHA256_MISMATCH")
        payload=json.loads(gzip.decompress(contents))
        if (payload["symbol"]!=symbol or payload["timeframe"]!="1D" or
                payload["asof_exclusive"]!=state["asof_exclusive"] or
                payload["quality"]["observed_count"]!=state["bar_count"]):
            raise ValueError("CHART_STORED_MANIFEST_MISMATCH")
        return {"metadata":state,"quality":payload["quality"],
                "bars":payload["bars"] if include_bars else []}

    def totals(self):
        with sqlite3.connect(self.db) as db:
            row=db.execute("""SELECT COUNT(*), COALESCE(SUM(bar_count),0),
                             COALESCE(SUM(five_year_extent_covered),0)
                              FROM chart_history""").fetchone()
        return {"stored_symbols":row[0],"stored_bars":row[1],
                "five_year_date_extent_records":row[2],
                "missing_sessions_audited":False,
                "manual_only":True}
