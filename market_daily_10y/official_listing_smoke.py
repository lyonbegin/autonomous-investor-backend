"""Explicit read-only smoke of HKEX official public securities master.

Never distributes the workbook or assumes a price-data licence. Strict URL and
size limits prevent unexpected HTML/error pages from silently becoming a master.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen
from .global_universe import FIELDS, parse_snapshot

HKEX_URL = 'https://www.hkex.com.hk/eng/services/trading/securities/securitieslists/ListOfSecurities.xlsx'
MAX_BYTES = 12_000_000


def probe_hkex(download, one_ticker=None, universe_output=None):
    payload = download(HKEX_URL)
    if len(payload) > MAX_BYTES or not payload.startswith(b'PK\x03\x04'):
        raise ValueError('HKEX_OFFICIAL_SNAPSHOT_NOT_VALID_XLSX')
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'hkex.xlsx'
        path.write_bytes(payload)
        accepted, rejected = parse_snapshot(path, 'hkex')
    if one_ticker or universe_output:
        if not (one_ticker and universe_output):
            raise ValueError('BOTH_TICKER_AND_OUTPUT_REQUIRED')
        matches = [r for r in accepted if r['symbol'] == one_ticker and r['exchange'] == 'HKEX']
        if len(matches) != 1:
            raise ValueError('SELECTED_HKEX_STOCK_NOT_UNIQUE_OR_MISSING')
        dest = Path(universe_output)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open('w',newline='',encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(matches)
    by_asset = {}
    for row in accepted:
        by_asset[row['asset_class']] = by_asset.get(row['asset_class'], 0) + 1
    return {'source_url':HKEX_URL,'source_sha256':hashlib.sha256(payload).hexdigest(),
            'listed_candidates':len(accepted),'quarantined':len(rejected),
            'asset_counts':by_asset,'price_history_collected':False}


def download_url(url):
    if url != HKEX_URL:
        raise ValueError('UNAPPROVED_SOURCE_URL')
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; Independent10YResearch/1.0)'})
    with urlopen(req, timeout=45) as resp:
        if resp.status != 200:
            raise ValueError('OFFICIAL_SOURCE_HTTP_ERROR')
        return resp.read(MAX_BYTES + 1)


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--allow-network', action='store_true')
    parser.add_argument('--one-ticker', help='exact HKEX source stock code, e.g. 0700')
    parser.add_argument('--universe-output')
    args=parser.parse_args(argv)
    if not args.allow_network:
        parser.error('--allow-network required to test remote source')
    result=probe_hkex(download_url,one_ticker=args.one_ticker,universe_output=args.universe_output)
    print(json.dumps(result,ensure_ascii=False))
    if result['listed_candidates'] < 200:
        raise ValueError('HKEX_LIST_TOO_SMALL_TO_TRUST')


if __name__=='__main__':
    main()
