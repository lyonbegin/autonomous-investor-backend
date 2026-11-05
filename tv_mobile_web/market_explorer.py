"""Multi-asset exploration over the EXISTING TradingView market integration.

No fabricated prices, no market data crawling triggered by this module, no cron,
and no proprietary TradingView mobile session replay. Stored-market reads use
the *existing* tradingview-service /stored route (up to 1000 per market).
Results are visibly partial until full-universe evidence exists.
"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/explore", tags=["multi-asset"])
# These market IDs are implemented in app/core/tradingview.py
# MARKET_SCANNER_PROFILES on the existing tradingview-service branch.
from .market_taxonomy import TYPES, SCANNER_ROUTES, all_types

# All 9 official TradingView symbol types. Scanner routes are a subset only.
CATEGORIES = tuple((ko, code, SCANNER_ROUTES[code]) for code,ko,_,_ in TYPES)

SUPPORTED_MARKETS = frozenset(k for _, _, names in CATEGORIES for k in names)
# Product team only verified scanner fields, not live ranking parity with TV.
RANKINGS = {
    "volume": ("volume", "desc", "거래량 상위"),
    "gainers": ("change", "desc", "상승률 상위"),
    "losers": ("change", "asc", "하락률 상위"),
    "volatility": ("Volatility.D", "desc", "일간 변동성"),
    "market_cap": ("market_cap_basic", "desc", "시가총액 상위"),
    "price": ("close", "desc", "가격 상위"),
}
SEARCHABLE_FIELDS = (
    "ticker", "symbol", "name", "description", "exchange", "sector", "isin"
)


async def _existing(path: str, params: dict[str, Any]) -> dict:
    # Kept inside call to avoid import cycle; tests monkeypatch server._tv_get.
    from .server import _tv_get
    return await _tv_get(path, params)


def _match(row: dict, q: str) -> bool:
    return any(q in str(row.get(field, "") or "").casefold()
               for field in SEARCHABLE_FIELDS)


async def stored_page(market: str, limit: int = 1000, offset: int = 0) -> dict:
    if market not in SUPPORTED_MARKETS:
        raise HTTPException(404, "UNKNOWN_MARKET")
    source = await _existing(f"/api/v1/tradingview/markets/{market}/stored", {
        "limit": limit, "offset": offset, "sort_by": "volume", "sort_order": "desc",
    })
    items = source.get("items", [])
    if not isinstance(items, list) or not all(isinstance(x, dict) for x in items):
        raise HTTPException(502, "INVALID_STORED_UNIVERSE_FORMAT")
    return {
        "items": items,
        "total_count": source.get("total_count"),
        "market": market,
        "source": "existing_tradingview_market_stored_universe",
        "scope": "one_page_of_stored_market_not_all_listings",
        "complete_universe_verified": False,
        "limit": limit,
        "offset": offset,
    }


@router.get("/catalog")
def catalog():
    return {
        "categories": [
            {"name": name, "asset_class": group, "markets": list(markets),
             "scanner_status": "LINKED" if markets else "NOT_YET_CONNECTED"}
            for name, group, markets in CATEGORIES
        ],
        "canonical_symbol_types": all_types(),
        "scanner_market_count": len(SUPPORTED_MARKETS),
        "rankings": [{"id": k, "name": v[2]} for k, v in RANKINGS.items()],
        "unlisted_venues_automatically_supported": False,
        "verified_global_full_listings": False,
        "market_data_licensing_verified": False,
        "scheduled_collection_enabled": False,
        "symbols_can_link_to_saved_5y_daily": True,
    }


@router.get("/stored/{market}")
async def market_stored(market: str,
                        limit: int = Query(100, ge=1, le=1000),
                        offset: int = Query(0, ge=0)):
    return await stored_page(market, limit, offset)


@router.get("/ranking/{market}/{ranking}")
async def market_ranking(market: str, ranking: str,
                         limit: int = Query(10, ge=1, le=100),
                         offset: int = Query(0, ge=0)):
    if market not in SUPPORTED_MARKETS:
        raise HTTPException(404, "UNKNOWN_MARKET")
    if ranking not in RANKINGS:
        raise HTTPException(404, "UNKNOWN_RANKING")
    field, direction, label = RANKINGS[ranking]
    # May raise 502 if scanner does not support sort for a particular market.
    data = await _existing(f"/api/v1/tradingview/markets/{market}", {
        "limit": limit, "offset": offset, "sort_by": field, "sort_order": direction,
    })
    items = data.get("items")
    if not isinstance(items, list):
        raise HTTPException(502, "INVALID_LIVE_RANKING_FORMAT")
    return {
        "market": market, "ranking": ranking, "label": label,
        "items": items, "sort_field": field, "sort_direction": direction,
        "source": data.get("source") or "existing_tradingview_live_scanner",
        "all_markets_exhaustive": False, "total_count": data.get("total_count"),
        "offset":offset, "limit":limit,
        "page":offset//limit+1,
    }


@router.get("/search")
async def search_markets(q: str = Query(min_length=2, max_length=90),
                         market: str | None = None,
                         limit: int = Query(50, ge=1, le=100),
                         pages_per_market: int = Query(1, ge=1, le=3)):
    """Search already-stored items, bounded pages; NOT an exhaustive global search.

    No API call to refresh or download prices. Coverage per market is explicit.
    """
    if market and market not in SUPPORTED_MARKETS:
        raise HTTPException(404, "UNKNOWN_MARKET")
    names = [market] if market else sorted(SUPPORTED_MARKETS)
    query = q.casefold().strip()
    sem = asyncio.Semaphore(3)

    async def one(name: str):
        found, scanned, exhausted, errors = [], 0, False, []
        for page in range(pages_per_market):
            try:
                async with sem:
                    data = await stored_page(name, limit=1000, offset=page*1000)
            except HTTPException as exc:
                errors.append(str(exc.detail))
                break
            rows = data["items"]
            scanned += len(rows)
            for row in rows:
                if _match(row, query):
                    found.append({"market": name, **row})
            if len(rows) < 1000:
                exhausted = True
                break
        return {"market": name, "found": found, "rows_scanned": scanned,
                "pages_retrieved": (scanned + 999)//1000,
                "all_stored_pages_examined": exhausted,
                "errors": errors}

    results = await asyncio.gather(*(one(name) for name in names))
    items = [item for result in results for item in result["found"]]
    return {
        "query": q, "items": items[:limit], "matches_in_scanned_pages": len(items),
        "limit": limit, "searched_markets": names,
        "markets": [{k: v for k, v in r.items() if k != "found"} for r in results],
        "partial_search": any(not r["all_stored_pages_examined"]
                              for r in results),
        "source": "existing_stored_market_universe",
        "prices_automatically_downloaded": False,
        "worldwide_complete": False,
    }


@router.get("/symbol")
async def symbol_details(symbol: str = Query(min_length=3, max_length=96),
                         market: str = "global-stocks"):
    """Bounded actual instrument lookup plus actual locally stored daily status."""
    if market not in SUPPORTED_MARKETS:
        raise HTTPException(404, "UNKNOWN_MARKET")
    from .server import _history_store
    sym = symbol.strip().upper()
    if ":" not in sym:
        raise HTTPException(422, "EXPECTED_EXCHANGE_PREFIXED_SYMBOL")
    # Search up to first 3k stored market instruments. Flag partial coverage.
    candidates = await search_markets(q=sym, market=market, limit=100,
                                      pages_per_market=3)
    exact = next((item for item in candidates["items"]
                  if str(item.get("ticker") or item.get("symbol") or
                         item.get("name") or "").upper() == sym), None)
    if exact is None:
        # No fabricated quote; chart may still have history already stored.
        exact = {}
    try:
        saved = _history_store().status(sym)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {
        "symbol": sym, "market": market,
        "fundamentals": exact if exact else None,
        "fundamentals_found_in_stored_scan": bool(exact),
        "scan_is_exhaustive": not candidates["partial_search"],
        "five_year_daily": saved,
        "source": "existing_market_universe_and_actual_5y_store",
        "no_synthetic_fundamentals": True,
    }
