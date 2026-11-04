"""Import permissioned JPX, HKEX and KRX listed-security master snapshots.

Snapshots are inputs, not proof of 10Y price coverage. Neither price history nor
market-data redistribution permission is inferred from listing directory access.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

FIELDS = ('asset_class', 'exchange', 'symbol', 'vendor_symbol', 'timezone', 'calendar', 'contract_type')
SUPPORTED = {'jpx', 'hkex', 'krx'}
COLUMNS = {
    'jpx': {'code': ('コード', 'Code'), 'category': ('市場・商品区分', 'Market/Product Category')},
    'hkex': {'code': ('Stock Code', 'StockCode', 'Code'),
             'category': ('Category', 'Product Type'),
             'sub': ('Sub-Category', 'Sub Category', 'Sub-category', 'Security Type')},
    'krx': {'code': ('단축코드', '단축종목코드', 'shortCode', 'srtnCd'),
            'category': ('시장구분', '시장명', 'mrktCtg', 'market')},
}


def _text(value):
    if value is None or pd.isna(value):
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _table(source, kind):
    """Discover header among first 30 rows, reject unexpected Excel layouts."""
    p = Path(source)
    if p.suffix.lower() in ('.xlsx', '.xls'):
        book = pd.ExcelFile(p)
        for sheet in book.sheet_names[:8]:
            sample = pd.read_excel(book, sheet_name=sheet, header=None, nrows=31, dtype=str)
            for index, row in sample.iterrows():
                present = {_text(v).casefold() for v in row.tolist()}
                if all(any(alias.casefold() in present for alias in aliases)
                       for field, aliases in COLUMNS[kind].items() if field != 'sub'):
                    return pd.read_excel(book, sheet_name=sheet, header=int(index), dtype=str)
        raise ValueError('MISSING_EXPECTED_EXCEL_HEADERS')
    if p.suffix.lower() in ('.csv', '.txt'):
        for encoding in ('utf-8-sig', 'cp949', 'shift_jis'):
            try:
                raw = p.read_text(encoding=encoding)
                return pd.read_csv(io.StringIO(raw), dtype=str, sep=None, engine='python')
            except UnicodeError:
                continue
        raise ValueError('UNSUPPORTED_CSV_ENCODING')
    raise ValueError('UNSUPPORTED_SNAPSHOT_FORMAT')


def _column(df, kind, field):
    options = COLUMNS[kind][field]
    found = {str(c).strip().casefold(): c for c in df.columns}
    for option in options:
        if option.casefold() in found:
            return found[option.casefold()]
    if field == 'sub':
        return None
    raise ValueError(f'MISSING_{kind.upper()}_{field.upper()}_COLUMN')


def classify(kind, code, category, sub=''):
    """Conservative mappings: ambiguous products remain out of price universe."""
    cat = category.lower().replace(' ', '')
    sub = sub.lower().replace(' ', '')
    if kind == 'jpx':
        if not re.fullmatch(r'[0-9]{4}', code):
            return None, 'JPX_COMPLEX_OR_NEW_CODE'
        if ('内国株式' in category or 'foreign stocks' in cat or '国内株式' in category):
            return ('equity', 'TSE', code + '.T', 'Asia/Tokyo'), ''
        if 'etf' in cat and 'etn' not in cat:
            return ('etf', 'TSE', code + '.T', 'Asia/Tokyo'), ''
        return None, 'JPX_UNSUPPORTED_SECURITY_CATEGORY'
    if kind == 'hkex':
        if not re.fullmatch(r'[0-9]{1,5}', code):
            return None, 'HKEX_NONNUMERIC_CODE'
        value = str(int(code)).zfill(4)
        if 'warrant' in cat or 'derivative' in cat or 'debt' in cat or 'cbbc' in cat:
            return None, 'HKEX_NON_EQUITY_PRODUCT'
        if ('equity' in cat and ('ordinary' in sub or 'equity' in sub or 'share' in sub or not sub)):
            return ('equity', 'HKEX', value + '.HK', 'Asia/Hong_Kong'), ''
        if ('exchangetraded' in cat or 'etf' in cat) and 'etn' not in sub:
            return ('etf', 'HKEX', value + '.HK', 'Asia/Hong_Kong'), ''
        return None, 'HKEX_AMBIGUOUS_SECURITY_CATEGORY'
    if kind == 'krx':
        if not re.fullmatch(r'[0-9]{6}', code):
            return None, 'KRX_UNSUPPORTED_CODE'
        if 'kospi' in cat or '유가증권' in cat:
            return ('equity', 'KRX', code + '.KS', 'Asia/Seoul'), ''
        if 'kosdaq' in cat or '코스닥' in cat:
            return ('equity', 'KRX', code + '.KQ', 'Asia/Seoul'), ''
        return None, 'KRX_MARKET_OR_INSTRUMENT_UNMAPPED'
    raise ValueError('UNKNOWN_MARKET')


def parse_snapshot(source, kind):
    if kind not in SUPPORTED:
        raise ValueError('UNSUPPORTED_MARKET')
    df = _table(source, kind)
    code_col, cat_col = (_column(df, kind, x) for x in ('code', 'category'))
    sub_col = _column(df, kind, 'sub') if kind == 'hkex' else None
    accepted, quarantined = [], []
    for _, record in df.iterrows():
        code = _text(record[code_col])
        if not code:
            continue
        category = _text(record[cat_col])
        sub = _text(record[sub_col]) if sub_col else ''
        mapped, reason = classify(kind, code, category, sub)
        if mapped is None:
            quarantined.append({'market': kind, 'symbol': code, 'category': category[:100], 'reason': reason})
            continue
        asset, exchange, vendor, tz = mapped
        accepted.append(dict(zip(FIELDS, (asset, exchange, code, vendor, tz, 'weekday', 'spot'))))
    if not accepted:
        raise ValueError('NO_SUPPORTED_SECURITY_IN_SNAPSHOT')
    return accepted, quarantined


def merge_snapshots(base_csv, snapshots, output_csv, report_json, rejected_json=None):
    """Commit only on successful all-source parsing. Never destroy base on failure."""
    with Path(base_csv).open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if not set(FIELDS).issubset(reader.fieldnames or []):
            raise ValueError('BASE_UNIVERSE_SCHEMA_MISMATCH')
        base = [{c: row[c] for c in FIELDS} for row in reader]
    uniq = {(r['asset_class'], r['exchange'], r['symbol'], r['contract_type']):r for r in base}
    details, quarantine = {}, []
    for kind, file in snapshots.items():
        if kind not in SUPPORTED:
            raise ValueError('UNKNOWN_MARKET')
        rows, rejected = parse_snapshot(file, kind)
        quarantine.extend(rejected)
        added = 0
        for row in rows:
            key = (row['asset_class'], row['exchange'], row['symbol'], row['contract_type'])
            if key not in uniq:
                uniq[key] = row
                added += 1
        details[kind] = {
            'source_file_name': Path(file).name,
            'sha256': hashlib.sha256(Path(file).read_bytes()).hexdigest(),
            'accepted': len(rows), 'added': added, 'quarantined': len(rejected),
        }
    ordered = sorted(uniq.values(), key=lambda r: (r['asset_class'],r['exchange'],r['symbol']))
    output = Path(output_csv)
    output.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(prefix='.universe-', suffix='.csv', dir=output.parent)
    try:
        with os.fdopen(handle,'w',newline='',encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(ordered)
        os.replace(temp, output)
    finally:
        Path(temp).unlink(missing_ok=True)
    report = {
        'generated_at':datetime.now(timezone.utc).isoformat(),
        'listing_snapshot_only':True,
        'price_history_fetched':False,
        'vendor_mapping_price_verified':False,
        'total_universe':len(ordered),
        'base_universe':len(base),
        'sources':details,
        'quarantine_count':len(quarantine),
        'quarantine_reasons':dict(Counter(x['reason'] for x in quarantine)),
        'output_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
    }
    dest = Path(report_json)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if rejected_json:
        Path(rejected_json).write_text(json.dumps(quarantine,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--base', required=True, help='existing curated or US-expanded CSV')
    parser.add_argument('--output', required=True)
    parser.add_argument('--report', required=True)
    parser.add_argument('--rejected', required=True)
    parser.add_argument('--jpx-file', help='official JPX workbook snapshot')
    parser.add_argument('--hkex-file', help='official HKEX Full List workbook snapshot')
    parser.add_argument('--krx-file', help='licensed KRX stock master CSV/XLSX')
    args=parser.parse_args(argv)
    sources={key:getattr(args,key+'_file') for key in SUPPORTED if getattr(args,key+'_file')}
    if not sources:parser.error('provide at least one verified exchange source file')
    result=merge_snapshots(args.base,sources,args.output,args.report,args.rejected)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':
    main()
