"""Read-only 10-year daily pool contract for downstream WF-04/SCAMP.

Only verified, snapshot-aligned local Parquet files appear in the manifest.
This does not run SCAMP, scrape Yahoo, or expose a public data API.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

from .collector import Instrument, Store, ten_year_window


def instrument_from_row(row):
    return Instrument(row['asset_class'],row['exchange'],row['symbol'],
                      row['vendor_symbol'],row['timezone'],row['calendar'],
                      row['contract_type'])


def eligible_manifest(store, asof, *, verify_digest=True, only_keys=None):
    """Require the identical [asof-10 years, asof) snapshot for every output."""
    start,end=ten_year_window(asof)
    report=store.status()
    only_keys=set(only_keys) if only_keys is not None else None
    included=[]
    dropped={'NOT_ELIGIBLE':0,'WRONG_TEN_YEAR_SNAPSHOT':0,
             'MISSING_PARQUET':0,'DIGEST_MISMATCH':0}
    for row in report['instruments']:
        if only_keys is not None and row['key'] not in only_keys:
            continue
        if not row['eligible']:
            dropped['NOT_ELIGIBLE']+=1
            continue
        if row['start'] != str(start) or row['end_exclusive'] != str(end):
            dropped['WRONG_TEN_YEAR_SNAPSHOT']+=1
            continue
        inst=instrument_from_row(row)
        file=store.file(inst)
        if not file.is_file():
            dropped['MISSING_PARQUET']+=1
            continue
        if verify_digest and hashlib.sha256(file.read_bytes()).hexdigest()!=row['sha256']:
            dropped['DIGEST_MISMATCH']+=1
            continue
        included.append({
            'key':inst.key,'asset_class':inst.asset_class,
            'exchange':inst.exchange,'symbol':inst.symbol,
            'vendor_symbol':inst.vendor_symbol,
            'timezone':inst.timezone,'calendar':inst.calendar,
            'contract_type':inst.contract_type,
            'file_path':str(file),'sha256':row['sha256'],
            'rows':row['rows'],'first_date':row['first_date'],
            'last_date':row['last_date'],'coverage_ratio':row['coverage'],
            'start':row['start'],'end_exclusive':row['end_exclusive'],
        })
    return {
        'purpose':'WF04_INPUT_READY_ONLY','downloaded_new_bars':False,
        'source_licence_for_commercial_use_verified':False,
        'requires_same_volume_or_authorized_file_transport':True,
        'asof':str(asof),'timeframe':'1d',
        'window_start':str(start),'window_end_exclusive':str(end),
        'listing_catalog_stored':report['stored'],
        'scope':'SELECTED_INSTRUMENTS' if only_keys is not None else 'ALL_INSTRUMENTS',
        'ready':len(included),'excluded':dropped,
        'instruments':included,
    }


def export_pair(store, left, right, asof, path):
    """Never fill holidays or compare nonidentical underlying 10Y windows."""
    manifest=eligible_manifest(store,asof,only_keys={left,right})
    lookup={r['key']:r for r in manifest['instruments']}
    if left not in lookup or right not in lookup:
        raise ValueError('WF04_INPUT_NOT_SNAPSHOT_ELIGIBLE')
    a=instrument_from_row(lookup[left])
    b=instrument_from_row(lookup[right])
    shared,info=store.align(a,b,asof=asof)
    if shared.empty or not shared['date'].is_unique:
        raise ValueError('WF04_ALIGNED_DATES_INVALID')
    destination=Path(path)
    destination.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(prefix='.pair-',suffix='.parquet',dir=destination.parent)
    os.close(fd)
    try:
        shared.to_parquet(temp,index=False,compression='zstd')
        digest=hashlib.sha256(Path(temp).read_bytes()).hexdigest()
        os.replace(temp,destination)
    finally:
        Path(temp).unlink(missing_ok=True)
    return {'source':'LOCAL_VERIFIED_PARQUET_ONLY','left':left,'right':right,
            'path':str(destination),'sha256':digest,
            'window_start':str(ten_year_window(asof)[0]),
            'window_end_exclusive':str(asof),'timeframe':'1d',**info}


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--root',default=os.getenv('DAILY_POOL_ROOT','/data/market_daily_10y'))
    p.add_argument('--asof',required=True,help='exclusive UTC calendar end YYYY-MM-DD')
    p.add_argument('--manifest',action='store_true')
    p.add_argument('--pair',nargs=2,metavar=('LEFT_KEY','RIGHT_KEY'))
    p.add_argument('--output',required=True)
    args=p.parse_args(argv)
    if args.manifest==bool(args.pair):
        p.error('select exactly one of --manifest and --pair')
    store=Store(args.root)
    asof=date.fromisoformat(args.asof)
    if args.manifest:
        obj=eligible_manifest(store,asof)
        dest=Path(args.output)
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'ready':obj['ready'],'excluded':obj['excluded'],
                          'window_start':obj['window_start'],'window_end_exclusive':obj['window_end_exclusive']}))
    else:
        print(json.dumps(export_pair(store,*args.pair,asof,args.output),ensure_ascii=False))


if __name__=='__main__':main()
