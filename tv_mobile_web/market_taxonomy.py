"""Complete asset-domain taxonomy with evidence-driven, never-truncated venues.

Two different inventories MUST NOT be conflated:
- all ISO 3166 countries / nine TradingView symbol types are a *navigation scope*;
- exchanges and market-data feeds actually advertised on the TradingView
  public data-coverage page are a *source-derived snapshot*, not the set of
  exchange listings, licenses, or 5Y candle histories we have collected.

Manual refresh only. Preserve every source row, including uncategorized rows;
never infer 'supported' from being an ISO country. No cron, no credentials.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from bs4 import BeautifulSoup
import json
import os
import re
import tempfile

import httpx
import pycountry

DATA_COVERAGE_URL = "https://www.tradingview.com/data-coverage/"
# Nine types stated in official TradingView symbol search support material.
# Commodity exposure can appear in futures, indices, funds or spot instruments,
# but is also preserved as an independent navigation facet, not silently omitted.
TYPES = (
    ("stocks", "주식", "Stocks",
     ("보통주","우선주","DR/ADR/GDR","리츠(REITs)","SPAC","신주인수권·권리","OTC")),
    ("funds", "펀드·ETF·ETN", "Funds",
     ("ETF","ETN","ETC","뮤추얼펀드","폐쇄형펀드","채권형펀드","인덱스펀드","레버리지·인버스")),
    ("futures", "선물", "Futures",
     ("주가지수선물","금리선물","통화선물","에너지선물","금속선물","농산물선물","축산물선물","암호화폐선물","연속선물","개별만기")),
    ("forex", "외환", "Forex",
     ("메이저","마이너","이머징·이국통화","크로스환율","현물환","환율지수")),
    ("crypto", "암호화폐", "Crypto",
     ("코인","현물 거래쌍","스테이블코인","디파이(DeFi)","파생·무기한","선물","암호화폐 지수")),
    ("indices", "지수", "Indices",
     ("주식지수","산업·섹터지수","지역지수","통화지수","변동성지수","상품지수","채권지수")),
    ("bonds", "채권", "Bonds",
     ("국채","회사채","지방채","이자율·수익률","신용등급","만기별·듀레이션별","유통채권")),
    ("options", "옵션", "Options",
     ("주식옵션","ETF옵션","지수옵션","선물옵션","콜","풋","행사가","만기","그릭스","변동성")),
    ("economy", "경제 데이터", "Economy",
     ("GDP","CPI·인플레이션","정책금리","실업·고용","무역·국제수지","국채금리","인구·경제지표","기업 실적 일정")),
)
FACETS = (
    ("commodities", "원자재·현물·상품", ("에너지","금속","귀금속","농산물","축산물","현물","상품지수")),
    ("derivatives", "파생상품", ("선물","옵션","무기한·스왑","CFD","레버리지 상품")),
    ("calendars", "이벤트·캘린더", ("경제 일정","실적","IPO","배당","권리락","만기")),
)
ASSET_IDS = frozenset(row[0] for row in TYPES)
# Existing backend scanner profiles -- NOT a statement of worldwide coverage.
SCANNER_ROUTES = {
    "stocks": ("korea","america","india","japan","vietnam","global-stocks"),
    "funds": ("etf",),
    "futures": ("futures",),
    "forex": ("forex",),
    "crypto": ("crypto","crypto-coins"),
    "indices": ("indices",),
    "bonds": ("bonds","corporate-bonds"),
    "options": (),
    "economy": (),
}
ASSET_ENGLISH = {
    "stocks": ("stock", "stocks", "equities", "equity", "shares"),
    "funds": ("fund", "funds", "etf", "etn", "etc"),
    "futures": ("futures", "future"),
    "forex": ("forex", "currency", "currencies", "fx"),
    "crypto": ("crypto", "cryptocurrency", "spot", "swap", "perpetual"),
    "indices": ("indices", "index"),
    "bonds": ("bond", "bonds"),
    "options": ("options", "option"),
    "economy": ("economy", "economic"),
}
SOURCE_SCHEMA = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def countries() -> list[dict]:
    """All ISO countries displayed; unknown TradingView feed ≠ unsupported."""
    result = []
    for value in pycountry.countries:
        result.append({
            "iso2": value.alpha_2,
            "iso3": value.alpha_3,
            "name": value.name,
            "tradingview_source_status": "NOT_YET_VERIFIED",
        })
    return sorted(result, key=lambda x: (x["name"].casefold(), x["iso2"]))


def all_types() -> list[dict]:
    return [{
        "id": code, "name": ko, "source_symbol_type": english,
        "subcategories": list(subtypes),
        "scanner_routes": list(SCANNER_ROUTES[code]),
        "scanner_route_status": "LINKED" if SCANNER_ROUTES[code] else "NOT_YET_CONNECTED",
        "all_world_symbols_loaded": False,
        "five_year_daily_all_instruments_loaded": False,
    } for code, ko, english, subtypes in TYPES]


def _normalized_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def coverage_rows(html: str) -> list[dict]:
    """Lossless (at row level) public source parser.

    Do not discard a row just because its country, venue or asset names were
    not parsed. Row-index + all original visible cells allow later correction.
    Source tables can change without requiring a hardcoded list of exchanges.
    """
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.select("table")
    candidates = []
    for table in tables:
        rows = table.select("tr")
        # Only real data-coverage tables, not menus or unrelated site tables.
        if len(rows) >= 2 and any("data source" in
              _normalized_whitespace(x.get_text(" ", strip=True)).casefold()
              for x in rows[:3]):
            candidates.extend(rows)
    if not candidates:
        # Allow source to change table headings. Keep rows and report extraction
        # as partial / unverified instead of silently claiming complete coverage.
        candidates = [row for row in soup.select("table tr") if row.select("td")]
    values = []
    seen = set()
    for row in candidates:
        cells = row.find_all("td", recursive=False)
        if len(cells) < 1:
            continue
        texts = [_normalized_whitespace(x.get_text(" ", strip=True)) for x in cells]
        text = " | ".join(texts)
        if not text or text in seen:
            continue
        seen.add(text)
        primary = cells[0]
        names = [ _normalized_whitespace(x.get("alt",""))
                 for x in primary.select("img[alt]") ]
        names = [n for n in names if n]
        links = [a.get("href") for a in primary.select("a[href]")
                 if a.get("href","").startswith("/")]
        direct_assets = []
        for category, variants in ASSET_ENGLISH.items():
            # Match source labels, NOT arbitrary words like "spot" in provider
            # names; source mapping remains "inferred" pending data audit.
            for word in variants:
                if re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)",
                             texts[0], re.I):
                    direct_assets.append(category)
                    break
        values.append({
            "source_row": len(values)+1,
            "display": texts[0],
            "all_cells": texts,
            "image_alts": names,
            "relative_links": links,
            "asset_type_candidate_ids": sorted(set(direct_assets)),
            "classification_verified": False,
            "source": DATA_COVERAGE_URL,
        })
    return values


def build_catalog(source_html: str, *, retrieved_at: str | None = None) -> dict:
    records = coverage_rows(source_html)
    return {
        "schema_version": SOURCE_SCHEMA,
        "source": DATA_COVERAGE_URL,
        "snapshot_at": retrieved_at or utc_now(),
        "official_site_html_sha256": sha256(source_html.encode("utf-8")).hexdigest(),
        "raw_row_count": len(records),
        "source_row_count_confirmed_complete": False,
        "source_html_returned_nonempty": bool(source_html.strip()),
        "records": records,
    }


class MarketTaxonomyStore:
    def __init__(self, root: str | Path):
        self.root=Path(root)
        self.root.mkdir(parents=True,exist_ok=True)
        self.snapshot_path=self.root/"official_market_sources_snapshot.json"

    def read(self) -> dict:
        if not self.snapshot_path.is_file():
            return {
                "schema_version":SOURCE_SCHEMA, "source": DATA_COVERAGE_URL,
                "snapshot_at":None,"raw_row_count":0,
                "records":[],"source_row_count_confirmed_complete":False,
                "source_refresh_state":"NOT_REQUESTED",
            }
        try:
            value=json.loads(self.snapshot_path.read_text(encoding="utf-8"))
        except (OSError,ValueError) as exc:
            raise ValueError("SAVED_SOURCE_CATALOG_CORRUPTED") from exc
        if value.get("schema_version")!=SOURCE_SCHEMA:
            raise ValueError("SAVED_SOURCE_CATALOG_SCHEMA_MISMATCH")
        value["source_refresh_state"]="SOURCE_SNAPSHOT_STORED"
        return value

    def save(self, html: str):
        snapshot=build_catalog(html)
        if not snapshot["records"]:
            raise ValueError("COVERAGE_SITE_NO_PARSEABLE_RECORDS")
        fd,temp=tempfile.mkstemp(prefix=".tv-taxonomy-",dir=self.root)
        try:
            with os.fdopen(fd,"w",encoding="utf-8") as f:
                json.dump(snapshot,f,ensure_ascii=False,separators=(",",":"))
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp,self.snapshot_path)
        finally:
            Path(temp).unlink(missing_ok=True)
        return snapshot

    async def refresh(self):
        async with httpx.AsyncClient(follow_redirects=False,timeout=28.0,
                                     headers={"User-Agent":"Mozilla/5.0 (compatible; research source snapshot)"}) as client:
            response=await client.get(DATA_COVERAGE_URL)
            response.raise_for_status()
            if "html" not in response.headers.get("content-type","html"):
                raise ValueError("COVERAGE_EXPECTED_HTML")
            return self.save(response.text)


def hierarchy(snapshot:dict) -> dict:
    return {
        "source_taxonomy": "TradingView symbol search: nine canonical types",
        "country_standard": "ISO-3166-1, NOT evidence TradingView supports every country",
        "categories": all_types(),
        "additional_cross_asset_facets":[{
            "id":key,"name":name,"subcategories":list(subtypes),
            "not_distinct_tradingview_symbol_type":True
        } for key,name,subtypes in FACETS],
        "countries": countries(),
        "countries_in_iso_scope":len(list(pycountry.countries)),
        "tradingview_source_records":snapshot.get("records",[]),
        "source_row_count":snapshot.get("raw_row_count",0),
        "source_snapshot_at":snapshot.get("snapshot_at"),
        "source_refresh_state":snapshot.get("source_refresh_state","NOT_REQUESTED"),
        "all_exchanges_verified":False,
        "all_tradingview_symbols_collected":False,
        "all_5y_daily_collected":False,
        "existing_scanner_route_count":sum(len(x) for x in SCANNER_ROUTES.values()),
        "automation_cron_enabled":False,
    }
