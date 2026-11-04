"""Construct a persistent multi-market universe with source freshness and fail-safe reuse.

Network access is explicit. Never equate an exchange master with collected prices.
Existing world.csv and saved OHLC files are preserved on download errors.
"""
from __future__ import annotations
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .global_universe import merge_snapshots, parse_snapshot
from .official_listing_smoke import download_url, HKEX_URL, MAX_BYTES
from .universe_discovery import SOURCES, build_universe, fetch_text, parse_directory


def _recent(path, days):
    return path.exists() and (
        datetime.now(timezone.utc).timestamp() - path.stat().st_mtime < days * 86400)


def _atomic_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.official-')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def prepare_global_universe(root, base_csv, *, allow_network=False, us_fetch=None,
                            hkex_fetch=None, max_age_days=7, min_us=1000,
                            min_hkex=200, jpx_file=None, krx_file=None):
    """Return (world.csv, evidence). No silent false claim of global completeness.

    Source errors use previously validated cached files; lacking these raises.
    Caller may fall back to curated universe but must record incomplete coverage.
    """
    folder = Path(root) / 'universe'
    folder.mkdir(parents=True, exist_ok=True)
    us_fetch = us_fetch or fetch_text
    hkex_fetch = hkex_fetch or download_url
    us_texts = {}
    evidence = {'source_scope':'US_NASDAQ_AND_HKEX_OPTIONAL_JPX_KRX',
                'full_worldwide_universe':False,
                'source_stale':[],'source_refreshed':[],
                'price_bars_collected_by_bootstrap':0}
    for kind,url in SOURCES.items():
        cache = folder / ('official-'+kind+'.txt')
        if not _recent(cache,max_age_days) and allow_network:
            try:
                body = us_fetch(url)
                count = len(parse_directory(body,kind))
                if count < min_us:
                    raise ValueError(f'OFFICIAL_US_{kind.upper()}_TOO_SMALL_{count}')
                _atomic_bytes(cache,body.encode('utf-8'))
                evidence['source_refreshed'].append(kind)
            except Exception as exc:
                evidence.setdefault('source_errors',{})[kind]=str(exc)[:180]
        if not cache.exists():
            raise ValueError('OFFICIAL_US_SOURCE_NOT_READY_'+kind)
        body = cache.read_text(encoding='utf-8')
        if len(parse_directory(body,kind)) < min_us:
            raise ValueError('CACHED_US_SOURCE_NOT_VALID_'+kind)
        us_texts[kind] = body
        if not _recent(cache,max_age_days):
            evidence['source_stale'].append(kind)

    hkex = folder / 'official-hkex.xlsx'
    if not _recent(hkex,max_age_days) and allow_network:
        try:
            raw = hkex_fetch(HKEX_URL)
            if len(raw)>MAX_BYTES or not raw.startswith(b'PK\x03\x04'):
                raise ValueError('OFFICIAL_HKEX_NOT_XLSX')
            with tempfile.TemporaryDirectory() as temp:
                preview = Path(temp)/'hkex.xlsx'
                preview.write_bytes(raw)
                rows,_ = parse_snapshot(preview,'hkex')
                if len(rows)<min_hkex:
                    raise ValueError('OFFICIAL_HKEX_LIST_TOO_SMALL')
            _atomic_bytes(hkex,raw)
            evidence['source_refreshed'].append('hkex')
        except Exception as exc:
            evidence.setdefault('source_errors',{})['hkex']=str(exc)[:180]
    if not hkex.exists():
        raise ValueError('OFFICIAL_HKEX_SOURCE_NOT_READY')
    rows,_ = parse_snapshot(hkex,'hkex')
    if len(rows)<min_hkex:
        raise ValueError('CACHED_HKEX_SOURCE_NOT_VALID')
    if not _recent(hkex,max_age_days):
        evidence['source_stale'].append('hkex')

    us_csv=folder/'us-expanded.csv'
    us_meta=folder/'us-source-report.json'
    us_report=build_universe(base_csv,us_texts,us_csv,us_meta)
    snapshots={'hkex':hkex}
    if jpx_file:snapshots['jpx']=jpx_file
    if krx_file:snapshots['krx']=krx_file
    world=folder/'world.csv'
    result=merge_snapshots(us_csv,snapshots,world,folder/'world-report.json',
                           folder/'quarantined.json')
    evidence.update({
        'world_universe_count':result['total_universe'],
        'hkex_accepted':result['sources']['hkex']['accepted'],
        'us_universe_count':us_report['universe_count'],
        'global_universe_sha256':result['output_sha256'],
    })
    (folder/'bootstrap-status.json').write_text(
        json.dumps(evidence,indent=2,ensure_ascii=False),encoding='utf-8')
    return world,evidence
