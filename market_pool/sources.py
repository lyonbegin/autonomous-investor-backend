"""Reuse existing global archives first; incrementally repair missing daily bars."""
from __future__ import annotations
import csv
import io
import time
import urllib.error
import urllib.request
import zipfile
from datetime import date,timedelta
from pathlib import Path
import pandas as pd
from .pool import Instrument,MarketPool,intraday_to_daily

SUFFIX={
  "NASDAQ":"","NYSE":"","NSE":".NS","BSE":".BO","LSE":".L",
  "EURONEXT":".PA","XETRA":".DE","TSE":".T","HKEX":".HK",
  "SSE":".SS","SZSE":".SZ","TSX":".TO","ASX":".AX",
  "KRX":".KS","SGX":".SI","SIX":".SW"
}


def import_global_eod(pool,csv_path,*,exchange=None,asset_class="equity",timezone_name="UTC"):
    """Existing Global EOD Market Data Symbol,Date,Open,High,Low,Close,Volume.

    This importer does NOT falsely classify ETFs as equities. Set --asset
    explicitly when importing ETF CSV; a future external instrument directory
    can supply this classification at scale.
    """
    if asset_class not in ("equity","etf","index"):
        raise ValueError("GLOBAL_EOD_ASSET_CLASS_EXPLICIT")
    results=[]
    for chunk in pd.read_csv(csv_path,chunksize=150_000,low_memory=False):
        chunk.columns=[str(x).strip().lower() for x in chunk.columns]
        if not {"symbol","date","open","high","low","close"}.issubset(chunk):
            raise ValueError("GLOBAL_EOD_CSV_MISSING_COLUMNS")
        for raw,rows in chunk.groupby("symbol",sort=False):
            raw=str(raw).strip()
            if "." in raw:
                orig,local=raw.split(".",1)
                market=(exchange or orig).upper()
            else:
                market=(exchange or "").upper()
                local=raw
            if not market or market not in SUFFIX:
                raise ValueError("GLOBAL_EOD_EXCHANGE_MUST_BE_EXPLICIT")
            suffix=SUFFIX[market]
            vendor_symbol=local if local.endswith(suffix) else local+suffix
            inst=Instrument(asset_class,market,local,"yahoo",vendor_symbol,
                timezone=timezone_name,notes="Existing Global EOD CSV; verify rights")
            results.append(pool.ingest(inst,rows,source="existing-global-eod:csv",
                                      detail=str(csv_path)))
    return results


def import_intraday_csv(pool,inst,path,*,timestamp_col="timestamp",rollover_hour=0):
    src=Path(path)
    existing=pd.read_parquet(src) if src.suffix.lower()==".parquet" else pd.read_csv(src)
    daily=intraday_to_daily(existing,timezone_name=inst.timezone,
                            utc_column=timestamp_col,rollover_hour=rollover_hour)
    return pool.ingest(inst,daily,source="existing-intraday:resampled",
                detail=f"{path};tz={inst.timezone};rollover={rollover_hour}")


def yahoo_backfill(pool,instruments,*,start="2016-11-04",end=None,
                   pause=1.5,retry=2,full_refresh=False):
    """Actual yfinance 1d source; missing periods only, 7-day overlap."""
    import yfinance as yf
    maximum=pd.Timestamp(end or (date.today()+timedelta(days=1)).isoformat()).date()
    since=pd.Timestamp(start).date()
    results=[]
    for inst in instruments:
        if inst.vendor!="yahoo":
            results.append({"id":inst.id,"status":"SKIPPED_NOT_YAHOO"});continue
        if inst.asset_class=="option":
            results.append({"id":inst.id,"status":"NO_EXPIRED_OPTIONS_FROM_YAHOO"});continue
        previous=pool.read(inst)
        lower=max(since,pd.Timestamp(previous.iloc[-1]["date"]).date()-timedelta(days=7)) if (
            not full_refresh and not previous.empty) else since
        if lower>=maximum:
            results.append({"id":inst.id,"status":"UP_TO_DATE"});continue
        last_error=None
        for attempt in range(retry+1):
            try:
                hist=yf.Ticker(inst.vendor_symbol).history(
                    start=lower.isoformat(),end=maximum.isoformat(),
                    interval="1d",auto_adjust=False,actions=True)
                if hist.empty:raise ValueError("NO_YAHOO_DAILY_BARS")
                frame=hist.reset_index().rename(columns={
                    "Date":"date","Datetime":"date","Open":"open",
                    "High":"high","Low":"low","Close":"close",
                    "Adj Close":"adj_close","Volume":"volume"})
                results.append({"status":"INGESTED",**pool.ingest(inst,frame,
                     source="yfinance:1d",detail="raw OHLC and supplied adjusted close")})
                last_error=None
                break
            except Exception as exc:
                last_error=type(exc).__name__+": "+str(exc)[:150]
                if attempt<retry:time.sleep((attempt+1)*3)
        if last_error:
            results.append({"id":inst.id,"status":"FAILED","error":last_error})
        if pause:time.sleep(pause)
    return results


def import_qlib_snapshot(pool,dataset_path,*,region="us",
                         start="2016-11-04",end=None,limit=0,batch_symbols=40):
    """Import already-downloaded Qlib US/CN snapshots. Qlib values can be
    normalized/adjusted; these are NOT raw exchange-executable OHLC."""
    if region not in ("us","cn"):raise ValueError("QLIB_REGION_US_CN_ONLY")
    import qlib
    from qlib.data import D
    qlib.init(provider_uri=str(Path(dataset_path).resolve()),region=region)
    symbols=D.list_instruments(D.instruments(market="all"),
        start_time=start,end_time=end or date.today().isoformat(),as_list=True)
    if limit:symbols=symbols[:limit]
    results=[]
    for first in range(0,len(symbols),batch_symbols):
        subset=symbols[first:first+batch_symbols]
        frame=D.features(subset,["$open","$high","$low","$close","$volume"],
            start_time=start,end_time=end or date.today().isoformat(),freq="day")
        for sym in subset:
            try:
                item=frame.xs(sym,level="instrument").reset_index().rename(columns={
                    "datetime":"date","$open":"open","$high":"high","$low":"low",
                    "$close":"close","$volume":"volume"})
                if item.empty:continue
                inst=Instrument("equity",region.upper()+"_QLIB",str(sym),"qlib",
                    str(sym),notes="QLIB normalized/adjusted, NOT raw order execution prices")
                results.append(pool.ingest(inst,item,source="existing-qlib:"+region,
                    detail="Downloaded Qlib 1d archive; factor-adjusted series"))
            except (KeyError,ValueError):continue
    return results


def binance_zip_to_frame(payload):
    """Official public-data ZIP: spot klines in ms until 2024, us from 2025."""
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        names=[n for n in zf.namelist() if n.endswith(".csv") and ".." not in n]
        if len(names)!=1:raise ValueError("BINANCE_EXPECTED_ONE_CSV")
        if zf.getinfo(names[0]).file_size>80_000_000:
            raise ValueError("BINANCE_ZIP_EXPANSION_TOO_LARGE")
        rows=list(csv.reader(io.StringIO(zf.read(names[0]).decode("utf-8-sig"))))
    if rows and not rows[0][0].strip().isdigit():rows=rows[1:]
    parsed=[]
    for row in rows:
        if len(row)<6:continue
        stamp=int(row[0])
        day=pd.to_datetime(stamp,unit="us" if stamp>10**14 else "ms",utc=True)
        parsed.append({"date":day.strftime("%Y-%m-%d"),
                       "open":row[1],"high":row[2],"low":row[3],
                       "close":row[4],"volume":row[5]})
    if not parsed:raise ValueError("BINANCE_ARCHIVE_EMPTY")
    return pd.DataFrame(parsed)


def binance_monthly_backfill(pool,inst,*,begin="2017-08",until=None,pause=0.8):
    """Use EXISTING Binance 1d monthly archives for spot and USDM/COINM future."""
    if inst.vendor!="binance" or inst.asset_class not in ("crypto_spot","crypto_future"):
        raise ValueError("BINANCE_ASSET_PROVIDER_REQUIRED")
    market={"spot":"spot","um":"futures/um","cm":"futures/cm"}.get(inst.contract_type)
    if not market:raise ValueError("BINANCE_MARKET_UNKNOWN")
    end=until or (date.today().replace(day=1)-timedelta(days=1)).strftime("%Y-%m")
    results=[]
    for period in pd.period_range(begin,end,freq="M"):
        month=str(period)
        name=f"{inst.vendor_symbol}-1d-{month}.zip"
        url=(f"https://data.binance.vision/data/{market}/monthly/klines/"
             f"{inst.vendor_symbol}/1d/{name}")
        with pool._connect() as db:
            cached=db.execute("SELECT 1 FROM ingests WHERE instrument_id=? AND source=? AND detail=?",
                              (inst.id,"binance-public-monthly:1d",url)).fetchone()
        if cached:
            results.append({"month":month,"status":"CACHED"});continue
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"market-pool/1.0"})
            with urllib.request.urlopen(req,timeout=30) as resp:
                data=resp.read(85_000_000)
            if len(data)>=85_000_000:raise ValueError("BINANCE_ZIP_TOO_LARGE")
            frame=binance_zip_to_frame(data)
            results.append({"month":month,"status":"INGESTED",
                **pool.ingest(inst,frame,source="binance-public-monthly:1d",detail=url)})
        except urllib.error.HTTPError as exc:
            results.append({"month":month,"status":"MISSING" if exc.code==404 else "FAILED",
                            "http":exc.code})
        except Exception as exc:
            results.append({"month":month,"status":"FAILED","error":str(exc)[:150]})
        if pause:time.sleep(pause)
    return results
