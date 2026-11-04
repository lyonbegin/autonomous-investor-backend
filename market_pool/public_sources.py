"""Import curated, PRE-BUILT public daily/intraday CSVs (no web scraping).

For example: alessiostomeo/btc-cycle-data has existing Bitstamp BTCUSD
OHLCV from 2012 to 2026. The repo has no explicit license at inspection;
confirm legal data use before any public redistribution.
"""
from __future__ import annotations

import hashlib
import io
import urllib.parse
import urllib.request

import pandas as pd

from .pool import MarketPool,Instrument,intraday_to_daily

APPROVED_HOSTS=frozenset({"raw.githubusercontent.com","huggingface.co"})
MAX_BYTES=75_000_000


def import_existing_public_csv(pool:MarketPool,inst:Instrument,url:str,*,
                               timestamp_column:str|None=None,
                               rollover_hour:int=0,timeout:int=60):
    parsed=urllib.parse.urlsplit(url)
    if (parsed.scheme!="https" or parsed.hostname not in APPROVED_HOSTS
        or parsed.username or parsed.password or parsed.fragment):
        raise ValueError("PUBLIC_CSV_URL_NOT_APPROVED")
    req=urllib.request.Request(url,headers={"User-Agent":"stock-global-market-pool/1.0"})
    with urllib.request.urlopen(req,timeout=timeout) as response:
        raw=response.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:
        raise ValueError("PUBLIC_CSV_TOO_LARGE")
    digest=hashlib.sha256(raw).hexdigest()
    frame=pd.read_csv(io.BytesIO(raw))
    # BTC(Bitstamp) existing daily dataset has datetime_utc, open, high, ...
    if timestamp_column:
        daily=intraday_to_daily(frame,timezone_name=inst.timezone,
            utc_column=timestamp_column,rollover_hour=rollover_hour)
    else:
        frame.columns=[str(x).strip().lower() for x in frame.columns]
        if "date" not in frame and "datetime_utc" in frame:
            frame=frame.rename(columns={"datetime_utc":"date"})
        if "date" not in frame and "date_utc" in frame:
            frame=frame.rename(columns={"date_utc":"date"})
        daily=frame
    return {**pool.ingest(inst,daily,source="existing-public-csv",
            detail=f"url={url};payload_sha256={digest}"),
            "source_url":url,"source_sha256":digest}
