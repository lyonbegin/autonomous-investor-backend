"""Global multi-asset DAILY price pool, independent of TradingView strategy runs.

Durable root MUST be on a persistent volume or object storage mount. No claim
that a symbol has history until accepted rows are on disk and cataloged.
"""
from __future__ import annotations
import hashlib
import json
import os
import sqlite3
import tempfile
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ASSET_CLASSES = frozenset({"equity","etf","index","future","option","fx",
    "crypto_spot","crypto_future","commodity","bond","rate"})
BARS = ("date","open","high","low","close","adj_close","volume")


@dataclass(frozen=True)
class Instrument:
    asset_class: str
    exchange: str
    symbol: str
    vendor: str
    vendor_symbol: str
    currency: str = ""
    timezone: str = "UTC"
    contract_type: str = "spot"
    notes: str = ""

    def __post_init__(self):
        if self.asset_class not in ASSET_CLASSES:
            raise ValueError("UNKNOWN_ASSET_CLASS")
        for part in (self.exchange,self.symbol,self.vendor,self.vendor_symbol):
            if not isinstance(part,str) or not 1<=len(part)<=110 or any(c in part for c in "\r\n\0"):
                raise ValueError("INVALID_INSTRUMENT_ID")

    @property
    def id(self):
        return ":".join((self.asset_class,self.exchange,self.symbol,self.contract_type))

    @property
    def key(self):
        return hashlib.sha256(self.id.encode()).hexdigest()[:24]


class MarketPool:
    def __init__(self,root,*,storage="csv"):
        if storage not in ("csv","parquet"):
            raise ValueError("STORAGE_MUST_BE_CSV_OR_PARQUET")
        self.root=Path(root).expanduser().resolve()
        self.root.mkdir(parents=True,exist_ok=True)
        self.storage=storage
        self.catalog=self.root/"catalog.sqlite3"
        self._schema()

    def _connect(self):
        db=sqlite3.connect(self.catalog,timeout=30)
        db.row_factory=sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA busy_timeout=30000")
        return db

    def _schema(self):
        with closing(self._connect()) as db:
            db.executescript("""
              CREATE TABLE IF NOT EXISTS instruments(
                instrument_id TEXT PRIMARY KEY,asset_class TEXT NOT NULL,
                exchange TEXT NOT NULL,symbol TEXT NOT NULL,vendor TEXT NOT NULL,
                vendor_symbol TEXT NOT NULL,currency TEXT NOT NULL,
                timezone TEXT NOT NULL,contract_type TEXT NOT NULL,
                notes TEXT NOT NULL,rows INTEGER NOT NULL DEFAULT 0,
                first_date TEXT,last_date TEXT,file_sha256 TEXT,last_source TEXT,
                updated_at TEXT);
              CREATE INDEX IF NOT EXISTS ix_pool_asset ON instruments(asset_class,exchange);
              CREATE TABLE IF NOT EXISTS ingests(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instrument_id TEXT NOT NULL,source TEXT NOT NULL,
                input_rows INTEGER NOT NULL,accepted_rows INTEGER NOT NULL,
                rejected_rows INTEGER NOT NULL,timestamp TEXT NOT NULL,
                detail TEXT NOT NULL);
            """)
            db.commit()

    def register(self,inst):
        with closing(self._connect()) as db:
            db.execute("""INSERT INTO instruments(instrument_id,asset_class,exchange,
              symbol,vendor,vendor_symbol,currency,timezone,contract_type,notes)
              VALUES(?,?,?,?,?,?,?,?,?,?)
              ON CONFLICT(instrument_id) DO UPDATE SET vendor=excluded.vendor,
              vendor_symbol=excluded.vendor_symbol,currency=excluded.currency,
              timezone=excluded.timezone,notes=excluded.notes""",
              (inst.id,inst.asset_class,inst.exchange,inst.symbol,inst.vendor,
               inst.vendor_symbol,inst.currency,inst.timezone,inst.contract_type,
               inst.notes))
            db.commit()
        return inst.id

    def load_registry(self,path):
        rows=json.loads(Path(path).read_text(encoding="utf8"))
        return [self.register(Instrument(**item)) for item in rows]

    def instruments(self,asset_class=None):
        with closing(self._connect()) as db:
            if asset_class:
                return [dict(r) for r in db.execute(
                    "SELECT * FROM instruments WHERE asset_class=? ORDER BY exchange,symbol",
                    (asset_class,))]
            return [dict(r) for r in db.execute(
                "SELECT * FROM instruments ORDER BY asset_class,exchange,symbol")]

    def _path(self,inst):
        extension="parquet" if self.storage=="parquet" else "csv.gz"
        return self.root/"daily"/inst.asset_class/inst.key/("bars."+extension)

    @staticmethod
    def clean(frame):
        if not isinstance(frame,pd.DataFrame) or frame.empty:
            raise ValueError("EMPTY_MARKET_DATA")
        x=frame.copy()
        x.columns=[str(c).strip().lower().replace(" ","_") for c in x.columns]
        if not {"date","open","high","low","close"}.issubset(x.columns):
            raise ValueError("REQUIRED_OHLC_FIELDS_MISSING")
        x["date"]=pd.to_datetime(x["date"],errors="coerce",utc=True).dt.strftime("%Y-%m-%d")
        for name in BARS[1:]:
            if name not in x:x[name]=float("nan")
            x[name]=pd.to_numeric(x[name],errors="coerce")
        size=len(x)
        x=x.dropna(subset=["date","open","high","low","close"])
        valid=((x[["open","high","low","close"]]>0).all(axis=1)
           & (x["high"]>=x[["open","low","close"]].max(axis=1))
           & (x["low"]<=x[["open","high","close"]].min(axis=1))
           & (~(x["volume"].notna()&(x["volume"]<0))))
        x=x.loc[valid,list(BARS)].sort_values("date").drop_duplicates("date",keep="last")
        if x.empty:raise ValueError("NO_VALID_OHLC_ROWS")
        return x.reset_index(drop=True),size-len(x)

    def read(self,inst):
        path=self._path(inst)
        if not path.exists():return pd.DataFrame(columns=list(BARS))
        if self.storage=="parquet":return pd.read_parquet(path)
        return pd.read_csv(path,dtype={"date":"str"})

    def ingest(self,inst,frame,*,source,detail=""):
        if not isinstance(source,str) or not 1<=len(source)<=128:
            raise ValueError("SOURCE_LABEL_REQUIRED")
        fresh,rejected=self.clean(frame)
        self.register(inst)
        old=self.read(inst)
        merged,_=self.clean(pd.concat([old,fresh],ignore_index=True))
        path=self._path(inst)
        path.parent.mkdir(parents=True,exist_ok=True)
        fd,name=tempfile.mkstemp(prefix=".ingest_",dir=path.parent)
        os.close(fd)
        tmp=Path(name)
        try:
            if self.storage=="parquet":
                merged.to_parquet(tmp,index=False,compression="zstd")
            else:
                merged.to_csv(tmp,index=False,compression="gzip")
            digest=hashlib.sha256(tmp.read_bytes()).hexdigest()
            os.replace(tmp,path)
        finally:
            tmp.unlink(missing_ok=True)
        ts=datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as db:
            db.execute("""UPDATE instruments SET rows=?,first_date=?,last_date=?,
                file_sha256=?,last_source=?,updated_at=? WHERE instrument_id=?""",
                (len(merged),merged.iloc[0]["date"],merged.iloc[-1]["date"],
                 digest,source,ts,inst.id))
            db.execute("""INSERT INTO ingests(instrument_id,source,input_rows,
                accepted_rows,rejected_rows,timestamp,detail)
                VALUES(?,?,?,?,?,?,?)""",
                (inst.id,source,len(frame),len(fresh),rejected,ts,detail))
            db.commit()
        return {"instrument_id":inst.id,"received":len(frame),"accepted":len(fresh),
            "rejected":rejected,"total_rows":len(merged),"first_date":merged.iloc[0]["date"],
            "last_date":merged.iloc[-1]["date"],"file_sha256":digest}

    def coverage(self):
        items=self.instruments()
        return {"registered":len(items),
                "populated":sum(i["rows"]>0 for i in items),
                "total_stored_rows":sum(i["rows"] for i in items),
                "by_asset":{c:{"registered":sum(i["asset_class"]==c for i in items),
                               "populated":sum(i["asset_class"]==c and i["rows"]>0 for i in items)}
                            for c in sorted({i["asset_class"] for i in items})},
                "root":str(self.root),"storage":self.storage}


def intraday_to_daily(frame,*,timezone_name,utc_column="timestamp",rollover_hour=0):
    if not 0<=rollover_hour<=23:raise ValueError("INVALID_SESSION_ROLLOVER_HOUR")
    if utc_column not in frame:raise ValueError("TIMESTAMP_MISSING")
    ts=pd.to_datetime(frame[utc_column],utc=True,errors="coerce")
    local=ts.dt.tz_convert(timezone_name)
    day=(local+pd.Timedelta(hours=24-rollover_hour)
         if rollover_hour else local).dt.strftime("%Y-%m-%d")
    x=frame.copy()
    x["date"]=day
    x["_timestamp"]=ts
    for f in ("open","high","low","close","volume"):
        x[f]=pd.to_numeric(x.get(f),errors="coerce")
    x=x.dropna(subset=["_timestamp","open","high","low","close"]).sort_values("_timestamp")
    daily=x.groupby("date",sort=True).agg(
         open=("open","first"),high=("high","max"),
         low=("low","min"),close=("close","last"),volume=("volume","sum"))
    if not x["volume"].notna().any():daily["volume"]=float("nan")
    return daily.reset_index()
