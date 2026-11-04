"""Private content-addressed S3 transport from collector volume to WF-04 worker.

No public URLs and no automatic uploads unless --mirror-s3 is enabled.
The source catalogue SQLite and original Parquet remain untouched.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
import re
import sqlite3
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from .collector import Instrument, Store, normalize, quality, ten_year_window


SCHEMA = """
CREATE TABLE IF NOT EXISTS market_s3_mirror(
  instrument_key TEXT PRIMARY KEY,
  parquet_sha256 TEXT NOT NULL,
  object_key TEXT NOT NULL,
  mirrored_at TEXT NOT NULL
);
"""


def _json_bytes(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,
                      separators=(",",":"),allow_nan=False).encode("utf-8")


def _digest(contents):
    return hashlib.sha256(contents).hexdigest()


def s3_client_from_env():
    keys = {
        'endpoint_url':os.getenv('MARKET_POOL_S3_ENDPOINT'),
        'aws_access_key_id':os.getenv('MARKET_POOL_S3_ACCESS_KEY_ID'),
        'aws_secret_access_key':os.getenv('MARKET_POOL_S3_SECRET_ACCESS_KEY'),
        'region_name':os.getenv('MARKET_POOL_S3_REGION','auto'),
    }
    bucket=os.getenv('MARKET_POOL_S3_BUCKET')
    if not bucket or any(not x for x in keys.values()):
        raise RuntimeError('MARKET_POOL_S3_CREDENTIALS_REQUIRED')
    if not keys['endpoint_url'].startswith('https://'):
        raise ValueError('MARKET_POOL_S3_HTTPS_REQUIRED')
    import boto3
    from botocore.config import Config
    style=os.getenv('MARKET_POOL_S3_ADDRESSING_STYLE','virtual')
    if style not in ('virtual','path'):
        raise ValueError('UNSUPPORTED_S3_ADDRESS_STYLE')
    client=boto3.client('s3',config=Config(s3={'addressing_style':style},
                         retries={'max_attempts':3,'mode':'standard'}),
                         **keys)
    return client,bucket


class PrivatePoolBridge:
    def __init__(self, store, client, bucket):
        self.store=store
        self.client=client
        self.bucket=bucket
        with sqlite3.connect(store.db) as con:
            con.executescript(SCHEMA)

    def mirror_instrument(self, instrument):
        row=next((x for x in self.store.status()['instruments']
                  if x['key']==instrument.key),None)
        if row is None:
            raise ValueError('S3_LOCAL_INSTRUMENT_NOT_COLLECTED')
        path=self.store.file(instrument)
        if not path.exists():
            raise ValueError('S3_LOCAL_PARQUET_MISSING')
        content=path.read_bytes()
        if _digest(content)!=row['sha256']:
            raise ValueError('S3_LOCAL_FILE_HASH_MISMATCH')
        # Immutable object key, preserving previous 10Y snapshots if refreshed.
        key=f"daily/v1/{instrument.file_id}/{row['sha256']}.parquet"
        with sqlite3.connect(self.store.db) as con:
            old=con.execute("SELECT parquet_sha256 FROM market_s3_mirror WHERE instrument_key=?",
                            (instrument.key,)).fetchone()
        if old is not None and old[0]==row['sha256']:
            return {'status':'ALREADY_MIRRORED','key':key,
                    'sha256':row['sha256']}
        self.client.put_object(Bucket=self.bucket,Key=key,Body=content,
                               ContentType='application/octet-stream')
        with sqlite3.connect(self.store.db) as con:
            con.execute("""INSERT INTO market_s3_mirror VALUES(?,?,?,?)
              ON CONFLICT(instrument_key) DO UPDATE
              SET parquet_sha256=excluded.parquet_sha256,
                  object_key=excluded.object_key,
                  mirrored_at=excluded.mirrored_at""",
              (instrument.key,row['sha256'],key,datetime.now(timezone.utc).isoformat()))
        return {'status':'MIRRORED','key':key,'sha256':row['sha256']}

    def publish(self, asof):
        start,end=ten_year_window(asof)
        records=[]
        with sqlite3.connect(self.store.db) as con:
            con.row_factory=sqlite3.Row
            query="""SELECT i.*,m.parquet_sha256,m.object_key
              FROM instruments i JOIN market_s3_mirror m ON i.key=m.instrument_key
              WHERE i.eligible=1 AND i.start=? AND i.end_exclusive=?
                AND i.sha256=m.parquet_sha256 ORDER BY i.key"""
            for row in con.execute(query,(str(start),str(end))):
                records.append({
                    'key':row['key'],'asset_class':row['asset_class'],
                    'exchange':row['exchange'],'symbol':row['symbol'],
                    'vendor_symbol':row['vendor_symbol'],'timezone':row['timezone'],
                    'calendar':row['calendar'],'contract_type':row['contract_type'],
                    'first_date':row['first_date'],'last_date':row['last_date'],
                    'start':row['start'],'end_exclusive':row['end_exclusive'],
                    'rows':row['rows'],'coverage':row['coverage'],
                    'sha256':row['sha256'],'object_key':row['object_key'],
                })
        if not records:
            raise ValueError('NO_S3_MIRRORED_ELIGIBLE_ASOF_INSTRUMENTS')
        manifest={
            'schema_version':1,'purpose':'WF04_LOCAL_RESEARCH_INPUT_ONLY',
            'licensed_for_commercial_redistribution':False,
            'timeframe':'1d','window_start':str(start),
            'asof_end_exclusive':str(asof),
            'ready':len(records),'instruments':records,
        }
        content=_json_bytes(manifest)
        digest=_digest(content)
        object_key=f"manifests/v1/{asof}/{digest}.json"
        self.client.put_object(Bucket=self.bucket,Key=object_key,Body=content,
                               ContentType='application/json')
        pointer={'schema_version':1,'asof_end_exclusive':str(asof),
                 'manifest_sha256':digest,'manifest_key':object_key}
        self.client.put_object(Bucket=self.bucket,
                               Key=f"manifests/v1/{asof}/latest.json",
                               Body=_json_bytes(pointer),ContentType='application/json')
        return {'status':'PUBLISHED_PRIVATE_MANIFEST','ready':len(records),
                'manifest_sha256':digest,'asof_end_exclusive':str(asof)}

    def hydrate(self, asof, keys, destination):
        """Download exactly selected objects, validate hashes and 10Y OHLC."""
        keys=list(dict.fromkeys(keys))
        if not 1<=len(keys)<=100:
            raise ValueError('S3_INVALID_SELECTED_KEY_COUNT')
        pointer_key=f"manifests/v1/{asof}/latest.json"
        pointer=json.loads(self.client.get_object(Bucket=self.bucket,Key=pointer_key)['Body'].read())
        if pointer.get('asof_end_exclusive')!=str(asof):
            raise ValueError('S3_POINTER_ASOF_MISMATCH')
        manifest_bytes=self.client.get_object(Bucket=self.bucket,
                                Key=pointer['manifest_key'])['Body'].read()
        if _digest(manifest_bytes)!=pointer['manifest_sha256']:
            raise ValueError('S3_MANIFEST_HASH_MISMATCH')
        manifest=json.loads(manifest_bytes)
        start,end=ten_year_window(asof)
        if (manifest.get('schema_version')!=1 or
                manifest.get('window_start')!=str(start) or
                manifest.get('asof_end_exclusive')!=str(end)):
            raise ValueError('S3_MANIFEST_WINDOW_MISMATCH')
        by_key={r['key']:r for r in manifest['instruments']}
        if any(key not in by_key for key in keys):
            raise ValueError('S3_UNVERIFIED_INSTRUMENT')
        store=Store(destination)
        imported=[]
        for key in keys:
            row=by_key[key]
            inst=Instrument(row['asset_class'],row['exchange'],row['symbol'],
                            row['vendor_symbol'],row['timezone'],
                            row['calendar'],row['contract_type'])
            expected_key=f"daily/v1/{inst.file_id}/{row['sha256']}.parquet"
            if row['key']!=inst.key or row['object_key']!=expected_key:
                raise ValueError('S3_UNSAFE_INSTRUMENT_OBJECT_KEY')
            body=self.client.get_object(Bucket=self.bucket,Key=expected_key)['Body'].read()
            if _digest(body)!=row['sha256']:
                raise ValueError('S3_PARQUET_HASH_MISMATCH')
            raw=pd.read_parquet(io.BytesIO(body))
            df=normalize(raw,start,end)
            observed=quality(inst,df,start,end)
            if (not observed['eligible'] or observed['rows']!=row['rows']
                    or observed['first_date']!=row['first_date']
                    or observed['last_date']!=row['last_date']):
                raise ValueError('S3_PARQUET_QUALITY_MISMATCH')
            path=store.file(inst)
            path.parent.mkdir(parents=True,exist_ok=True)
            fd,tmp=tempfile.mkstemp(prefix='.hydrate-',suffix='.parquet',dir=path.parent)
            try:
                with os.fdopen(fd,'wb') as output:output.write(body)
                os.replace(tmp,path)
            finally:
                Path(tmp).unlink(missing_ok=True)
            with sqlite3.connect(store.db) as con:
                con.execute("""INSERT INTO instruments VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(key) DO UPDATE SET
                    start=excluded.start,end_exclusive=excluded.end_exclusive,
                    first_date=excluded.first_date,last_date=excluded.last_date,
                    rows=excluded.rows,coverage=excluded.coverage,eligible=excluded.eligible,
                    sha256=excluded.sha256,updated_at=excluded.updated_at""",
                    (inst.key,inst.asset_class,inst.exchange,inst.symbol,inst.vendor_symbol,
                     inst.timezone,inst.calendar,inst.contract_type,
                     str(start),str(end),observed['first_date'],observed['last_date'],
                     observed['rows'],observed['coverage_ratio'],1,'[]',
                     row['sha256'],datetime.now(timezone.utc).isoformat()))
            imported.append(inst.key)
        return {'status':'PRIVATE_S3_SNAPSHOT_HYDRATED',
                'asof_end_exclusive':str(asof),'instruments':imported,
                'local_root':str(store.root),'rechecked':len(imported)}


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--root',default=os.getenv('DAILY_POOL_ROOT','/data/market_daily_10y'))
    p.add_argument('--asof',required=True,type=date.fromisoformat)
    p.add_argument('--publish',action='store_true')
    p.add_argument('--hydrate',action='store_true')
    p.add_argument('--key',action='append')
    p.add_argument('--destination')
    args=p.parse_args(argv)
    if args.publish==args.hydrate:
        p.error('choose exactly one of --publish or --hydrate')
    client,bucket=s3_client_from_env()
    bridge=PrivatePoolBridge(Store(args.root),client,bucket)
    if args.publish:
        result=bridge.publish(args.asof)
    else:
        if not args.key or not args.destination:
            p.error('hydrate requires --key and --destination')
        result=bridge.hydrate(args.asof,args.key,args.destination)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':
    main()
