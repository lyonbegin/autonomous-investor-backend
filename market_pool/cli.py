"""CLI: register global instruments, import prebuilt archives, repair missing bars."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path

import pandas as pd
from .pool import Instrument,MarketPool
from .sources import (
    yahoo_backfill,import_global_eod,import_intraday_csv,
    import_qlib_snapshot,binance_monthly_backfill)

def main(argv=None):
    cli=argparse.ArgumentParser(description="Durable global multi-asset 10y daily pool")
    cli.add_argument("--root",default=os.getenv("MARKET_POOL_DIR","./market_pool_data"))
    cli.add_argument("--format",choices=["csv","parquet"],
                     default=os.getenv("MARKET_POOL_FORMAT","csv"))
    sub=cli.add_subparsers(dest="command",required=True)
    p=sub.add_parser("register",help="Register all market asset categories")
    p.add_argument("--catalog",default=str(Path(__file__).resolve().parent/
                      "catalog"/"starter_universe.json"))
    p=sub.add_parser("import-universe",help="Load pre-existing exchange symbol directories with explicit asset class")
    p.add_argument("file",help="CSV columns: asset_class,exchange,symbol,vendor,vendor_symbol[,currency,timezone,contract_type,notes]")
    sub.add_parser("status")
    p=sub.add_parser("symbols");p.add_argument("--asset")
    p=sub.add_parser("import-eod",help="Import existing Global EOD CSV")
    p.add_argument("file");p.add_argument("--exchange");p.add_argument("--timezone",default="UTC")
    p.add_argument("--asset",choices=["equity","etf","index"],default="equity")
    p=sub.add_parser("import-symbol",help="Import an existing real OHLCV CSV for a registered instrument")
    p.add_argument("instrument_id");p.add_argument("file")
    p.add_argument("--source",default="existing-csv")
    p=sub.add_parser("import-qlib",help="Import an existing unpacked Microsoft Qlib US/CN archive")
    p.add_argument("directory");p.add_argument("--region",choices=["us","cn"],default="us")
    p.add_argument("--start",default="2016-11-04");p.add_argument("--limit",type=int,default=0)
    p=sub.add_parser("import-intraday",help="Resample minute/hour archives into local trading days")
    p.add_argument("instrument_id");p.add_argument("file")
    p.add_argument("--timestamp-col",default="timestamp")
    p.add_argument("--rollover-hour",type=int,default=0)
    p=sub.add_parser("yahoo",help="Download missing daily bars for equity ETF index FX futures etc.")
    p.add_argument("--asset");p.add_argument("--limit",type=int,default=0)
    p.add_argument("--start",default="2016-11-04");p.add_argument("--end")
    p.add_argument("--pause",type=float,default=1.5)
    p.add_argument("--full-refresh",action="store_true")
    p=sub.add_parser("binance",help="Import historical monthly crypto spot/futures ZIP archives")
    p.add_argument("instrument_id");p.add_argument("--begin",default="2017-08")
    p.add_argument("--until");p.add_argument("--pause",type=float,default=0.8)
    opts=cli.parse_args(argv)
    pool=MarketPool(opts.root,storage=opts.format)
    if opts.command=="register":
        result={"ids":pool.load_registry(opts.catalog),"coverage":pool.coverage()}
    elif opts.command=="import-universe":
        rows=pd.read_csv(opts.file,dtype=str,keep_default_na=False).to_dict("records")
        allowed={"asset_class","exchange","symbol","vendor","vendor_symbol","currency","timezone","contract_type","notes"}
        result={"registered":sum(bool(pool.register(Instrument(**{k:v for k,v in row.items() if k in allowed and v}))) for row in rows),
                "coverage":pool.coverage()}
    elif opts.command=="status":result=pool.coverage()
    elif opts.command=="symbols":result=pool.instruments(opts.asset)
    elif opts.command=="import-eod":
        result=import_global_eod(pool,opts.file,exchange=opts.exchange,
                  timezone_name=opts.timezone,asset_class=opts.asset)
    elif opts.command=="import-qlib":
        result=import_qlib_snapshot(pool,opts.directory,region=opts.region,
                                    start=opts.start,limit=opts.limit)
    else:
        entries=pool.instruments()
        index={x["instrument_id"]:Instrument(**{
          k:x[k] for k in ("asset_class","exchange","symbol","vendor",
             "vendor_symbol","currency","timezone","contract_type","notes")})
          for x in entries}
        if opts.command=="yahoo":
            selected=[x for x in index.values() if x.vendor=="yahoo"
                       and (not opts.asset or opts.asset==x.asset_class)]
            if opts.limit:selected=selected[:opts.limit]
            result=yahoo_backfill(pool,selected,start=opts.start,end=opts.end,
                   pause=opts.pause,full_refresh=opts.full_refresh)
        else:
            if opts.instrument_id not in index:raise ValueError("INSTRUMENT_NOT_REGISTERED")
            inst=index[opts.instrument_id]
            if opts.command=="import-symbol":
                result=pool.ingest(inst,pd.read_csv(opts.file),source=opts.source,
                                   detail=str(opts.file))
            elif opts.command=="import-intraday":
                result=import_intraday_csv(pool,inst,opts.file,
                   timestamp_col=opts.timestamp_col,rollover_hour=opts.rollover_hour)
            elif opts.command=="binance":
                result=binance_monthly_backfill(pool,inst,
                   begin=opts.begin,until=opts.until,pause=opts.pause)
            else:raise ValueError("UNKNOWN_COMMAND")
    print(json.dumps(result,ensure_ascii=False,indent=2,default=str))
    return result

if __name__=="__main__":main()
