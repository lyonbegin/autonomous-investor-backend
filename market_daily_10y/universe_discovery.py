"""Expand the research universe from Nasdaq Trader's official US symbol directories.

Does not claim global coverage. Fetch is explicit, not performed by the
collector on every strategy request. Source records and snapshot metadata
are preserved, and unknown ticker mappings are quarantined.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

SOURCES = {
    "nasdaq": "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
    "other": "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
}
FIELDS = ("asset_class", "exchange", "symbol", "vendor_symbol", "timezone",
          "calendar", "contract_type")
OTHER_EXCHANGES = {
    "N": "NYSE", "A": "NYSEAMERICAN", "P": "NYSEARCA",
    "Z": "CBOE", "V": "IEX",
}


def parse_directory(text, kind):
    """Parse pipe-delimited listings and ignore the file-creation footer."""
    if kind not in SOURCES:
        raise ValueError("UNKNOWN_DIRECTORY")
    entries = []
    for row in csv.DictReader(io.StringIO(text.lstrip("\ufeff")), delimiter="|"):
        symbol = (row.get("Symbol") if kind == "nasdaq"
                  else row.get("ACT Symbol")) or ""
        symbol = symbol.strip()
        if not symbol or symbol.startswith("File Creation Time"):
            continue
        if row.get("Test Issue", "").strip().upper() == "Y":
            continue
        if row.get("NextShares", "").strip().upper() == "Y":
            continue
        if kind == "nasdaq":
            exchange = "NASDAQ"
            is_etf = row.get("ETF", "").strip().upper() == "Y"
        else:
            exchange = OTHER_EXCHANGES.get(row.get("Exchange", "").strip())
            is_etf = row.get("ETF", "").strip().upper() == "Y"
            if exchange is None:
                continue
        # Warrant/unit/preferred and class ticker conventions vary between
        # vendors. Never guess nontrivial mappings.
        if not all(ch.isalnum() or ch in ".-" for ch in symbol):
            continue
        if "." in symbol or "-" in symbol or len(symbol) > 8:
            entries.append({"exchange": exchange, "symbol": symbol,
                            "reason": "VENDOR_SYMBOL_MAPPING_REQUIRED"})
            continue
        entries.append(dict(zip(FIELDS, (
            "etf" if is_etf else "equity",
            exchange, symbol, symbol, "America/New_York",
            "weekday", "spot",
        ))))
    return entries


def fetch_text(url, timeout=30):
    req = Request(url, headers={"User-Agent": "market-daily-10y-universe/1.0"})
    with urlopen(req, timeout=timeout) as response:
        payload = response.read(12_000_001)
    if len(payload) > 12_000_000:
        raise ValueError("DIRECTORY_TOO_LARGE")
    return payload.decode("utf-8-sig")


def build_universe(base_csv, directory_texts, output_csv, metadata_json):
    base = list(csv.DictReader(Path(base_csv).open(encoding="utf-8", newline="")))
    for row in base:
        for field in FIELDS:
            if field not in row:
                raise ValueError("BASE_COLUMNS_MISSING")
    accepted = {(r["asset_class"], r["exchange"], r["symbol"],
                 r["contract_type"]): {k: r[k] for k in FIELDS} for r in base}
    quarantined = []
    per_source = {}
    for kind, text in directory_texts.items():
        parsed = parse_directory(text, kind)
        per_source[kind] = {"bytes": len(text.encode()), "sha256":
                            hashlib.sha256(text.encode()).hexdigest(),
                            "parsed": len(parsed)}
        for row in parsed:
            if "reason" in row:
                quarantined.append(row)
                continue
            key = (row["asset_class"], row["exchange"], row["symbol"],
                   row["contract_type"])
            accepted.setdefault(key, row)
    output = Path(output_csv)
    output.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(accepted.values(), key=lambda r: (
        r["asset_class"], r["exchange"], r["symbol"]))
    temp = output.with_suffix(output.suffix + ".tmp")
    with temp.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(ordered)
    os.replace(temp, output)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "US_LISTED_NASDAQ_AND_OTHER_EXCHANGES_PLUS_EXISTING_BASE",
        "listing_not_price_coverage": True,
        "sources": per_source,
        "universe_count": len(ordered),
        "quarantined_mapping_count": len(quarantined),
        "quarantined_examples": quarantined[:100],
        "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }
    meta = Path(metadata_json)
    meta.parent.mkdir(parents=True, exist_ok=True)
    meta.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base", default=str(Path(__file__).with_name("universe.csv")))
    p.add_argument("--output", required=True)
    p.add_argument("--metadata", required=True)
    p.add_argument("--nasdaq-file", help="offline source fixture or snapshot")
    p.add_argument("--other-file", help="offline source fixture or snapshot")
    p.add_argument("--allow-network", action="store_true",
                   help="explicitly permit downloading both official directories")
    args = p.parse_args()
    if args.allow_network:
        files = {key: fetch_text(url) for key, url in SOURCES.items()}
    elif args.nasdaq_file and args.other_file:
        files = {
            "nasdaq": Path(args.nasdaq_file).read_text(encoding="utf-8-sig"),
            "other": Path(args.other_file).read_text(encoding="utf-8-sig"),
        }
    else:
        p.error("supply BOTH source snapshots or --allow-network")
    print(json.dumps(build_universe(args.base, files, args.output, args.metadata),
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
