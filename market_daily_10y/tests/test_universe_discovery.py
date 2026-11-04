import csv
import json

from market_daily_10y.universe_discovery import build_universe, parse_directory

NASDAQ = """Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares
AAPL|Apple Inc|Q|N|N|100|N|N
TEST|Test|Q|Y|N|100|N|N
SPYQ|Fund|Q|N|N|100|Y|N
BRK.B|Class B|Q|N|N|100|N|N
File Creation Time: 1104202621|||||||
"""
OTHER = """ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol
IBM|IBM|N|IBM|N|100|N|IBM
ETF1|ETF|P|ETF1|Y|100|N|ETF1
BAD|Test|N|BAD|N|100|Y|BAD
File Creation Time: 1104202621|||||||
"""


def test_parse_realistic_nasdaq_directory():
    x = parse_directory(NASDAQ, "nasdaq")
    assert [r["symbol"] for r in x] == ["AAPL", "SPYQ", "BRK.B"]
    assert x[1]["asset_class"] == "etf"
    assert x[2]["reason"] == "VENDOR_SYMBOL_MAPPING_REQUIRED"


def test_parse_other_directory_and_filter_test():
    x = parse_directory(OTHER, "other")
    assert [r["symbol"] for r in x] == ["IBM", "ETF1"]
    assert [r["exchange"] for r in x] == ["NYSE", "NYSEARCA"]


def test_merge_base_and_snapshot_evidence(tmp_path):
    base = tmp_path / "base.csv"
    base.write_text(
        "asset_class,exchange,symbol,vendor_symbol,timezone,calendar,contract_type\n"
        "equity,NASDAQ,AAPL,AAPL,America/New_York,weekday,spot\n"
        "crypto_spot,GLOBAL,BTCUSD,BTC-USD,UTC,seven_day,spot\n"
    )
    out, meta = tmp_path / "expanded.csv", tmp_path / "report.json"
    report = build_universe(base, {"nasdaq": NASDAQ, "other": OTHER}, out, meta)
    records = list(csv.DictReader(out.open()))
    assert len(records) == 5
    assert sum(r["symbol"] == "AAPL" for r in records) == 1
    assert any(r["symbol"] == "BTCUSD" for r in records)
    assert report["quarantined_mapping_count"] == 1
    assert json.loads(meta.read_text())["output_sha256"] == report["output_sha256"]
