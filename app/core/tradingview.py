from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import UTC, datetime
from typing import Any
from urllib import parse, request


IDEAS_URL = "https://www.tradingview.com/api/v1/ideas/"
SCANNER_URL = "https://scanner.tradingview.com/{market}/scan"
SCRIPTS_ORIGIN = "https://www.tradingview.com"
PINE_FACADE_ORIGIN = "https://pine-facade.tradingview.com"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/154 Safari/537.36"

DB_PATH = os.getenv("AUTONOMOUS_DB_PATH", "/tmp/autonomous_investor.sqlite3")

MARKET_ALIASES: dict[str, str] = {
    "korea": "korea",
    "한국": "korea",
    "한국주식": "korea",
    "america": "america",
    "us": "america",
    "미국": "america",
    "세계주식": "america",
    "crypto": "crypto",
    "크립토": "crypto",
    "forex": "forex",
    "fx": "forex",
    "외환": "forex",
    "india": "india",
    "japan": "japan",
    "일본": "japan",
    "uk": "uk",
    "europe": "europe",
    "hongkong": "hongkong",
    "singapore": "singapore",
    "australia": "australia",
    "canada": "canada",
}

DEFAULT_COLUMNS = [
    "name",
    "description",
    "close",
    "change",
    "volume",
    "exchange",
    "type",
]

DIRECTION = {0: "중립", 1: "롱", 2: "숏"}

CATEGORY_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("평균회귀", ("rsi", "mean reversion", "mean-reversion", "평균회귀", "과매수", "과매도", "vwap")),
    ("돌파", ("breakout", "break out", "돌파", "donchian", "opening range", "resistance", "support")),
    ("변동성", ("bollinger", "squeeze", "volatility", "변동성", "atr")),
    ("페어 / 차익", ("pairs", "pair trade", "spread", "z-score", "arbitrage", "차익", "스프레드")),
    ("모멘텀", ("momentum", "macd", "모멘텀", "relative strength")),
    ("추세추종", ("supertrend", "trend", "추세", "ema", "moving average", "adx")),
    ("크립토", ("crypto", "bitcoin", "btc", "ethereum", "eth", "grid")),
]

CATEGORY_HORIZONS: dict[str, list[str]] = {
    "평균회귀": ["10m", "30m", "1h"],
    "돌파": ["10m", "30m", "1h"],
    "변동성": ["30m", "1h", "1d"],
    "페어 / 차익": ["1h", "4h", "1d"],
    "모멘텀": ["30m", "1h", "4h"],
    "추세추종": ["1h", "4h", "1d"],
    "크립토": ["10m", "1h", "4h"],
    "아이디어 기반": ["30m", "1h", "4h"],
}

CATEGORY_DOMAINS: dict[str, str] = {
    "평균회귀": "시장 중립",
    "돌파": "주식 성장 / CTA",
    "변동성": "변동성",
    "페어 / 차익": "상대가치",
    "모멘텀": "주식 성장",
    "추세추종": "CTA / 선물",
    "크립토": "크립토 현물 / 선물",
    "아이디어 기반": "시장 연구",
}

CATEGORY_MARKETS: dict[str, list[dict[str, str]]] = {
    "평균회귀": [
        {"country": "미국", "market": "NASDAQ / NYSE", "universe": "고유동성 대형주"},
        {"country": "한국", "market": "KOSPI", "universe": "거래대금 상위 대형주"},
        {"country": "ETF", "market": "미국", "universe": "QQQ · SPY · SMH"},
    ],
    "돌파": [
        {"country": "한국", "market": "KOSDAQ", "universe": "거래대금 상위 모멘텀주"},
        {"country": "미국", "market": "NASDAQ", "universe": "중대형 성장주"},
        {"country": "선물", "market": "CME", "universe": "ES · NQ"},
    ],
    "변동성": [
        {"country": "미국", "market": "NASDAQ / NYSE", "universe": "고변동성 성장주"},
        {"country": "ETF", "market": "미국", "universe": "SPY · QQQ · IWM"},
    ],
    "페어 / 차익": [
        {"country": "한국", "market": "KOSPI", "universe": "동일업종 대형주 페어"},
        {"country": "미국", "market": "NASDAQ / NYSE", "universe": "동일섹터 고유동성 페어"},
    ],
    "모멘텀": [
        {"country": "미국", "market": "NASDAQ", "universe": "상대강도 상위 성장주"},
        {"country": "한국", "market": "KOSDAQ", "universe": "거래대금·모멘텀 상위"},
        {"country": "일본", "market": "TSE Prime", "universe": "대형 모멘텀주"},
    ],
    "추세추종": [
        {"country": "미국 선물", "market": "CME", "universe": "ES · NQ · GC · CL"},
        {"country": "FX", "market": "글로벌", "universe": "EURUSD · USDJPY"},
        {"country": "한국", "market": "KOSPI200 선물", "universe": "KOSPI200"},
    ],
    "크립토": [
        {"country": "가상자산", "market": "글로벌", "universe": "BTC · ETH 현물"},
        {"country": "가상자산", "market": "글로벌 선물", "universe": "BTC · ETH 선물"},
    ],
    "아이디어 기반": [
        {"country": "미국", "market": "NASDAQ / NYSE", "universe": "고유동성 종목"},
        {"country": "한국", "market": "KOSPI / KOSDAQ", "universe": "거래대금 상위 종목"},
    ],
}


def utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS community_ideas (
                idea_id TEXT PRIMARY KEY,
                title TEXT,
                description TEXT,
                author TEXT,
                symbol TEXT,
                exchange TEXT,
                asset_type TEXT,
                direction TEXT,
                interval TEXT,
                created_at TEXT,
                comments_count INTEGER,
                likes_count INTEGER,
                views_count INTEGER,
                chart_url TEXT,
                image_url TEXT,
                raw_json TEXT NOT NULL,
                collected_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS community_scripts (
                script_id_part TEXT PRIMARY KEY,
                script_id TEXT,
                name TEXT,
                author TEXT,
                script_type TEXT,
                script_access INTEGER,
                version TEXT,
                likes_count INTEGER,
                comments_count INTEGER,
                views_count INTEGER,
                created_at TEXT,
                updated_at TEXT,
                chart_url TEXT,
                image_url TEXT,
                symbol TEXT,
                interval TEXT,
                is_picked INTEGER,
                is_hot INTEGER,
                description TEXT,
                raw_json TEXT NOT NULL,
                collected_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS script_sources (
                script_id_part TEXT PRIMARY KEY,
                version TEXT,
                script_name TEXT,
                kind TEXT,
                pine_version INTEGER,
                source_hash TEXT,
                source TEXT NOT NULL,
                fetched_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS strategy_candidates (
                candidate_id TEXT PRIMARY KEY,
                source_kind TEXT NOT NULL,
                source_id TEXT NOT NULL,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                domain TEXT NOT NULL,
                logic TEXT NOT NULL,
                candidate_horizons TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS agent_plans (
                agent_id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                fixed_horizon TEXT NOT NULL,
                country TEXT NOT NULL,
                market TEXT NOT NULL,
                universe TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )


def _http_json(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> Any:
    body = None
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json,text/plain,*/*",
        "Referer": "https://www.tradingview.com/",
    }
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = request.Request(url, data=body, headers=headers, method=method)
    with request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _absolute_url(value: Any) -> str | None:
    if not value or not isinstance(value, str):
        return None
    if value.startswith("http://") or value.startswith("https://"):
        return value
    if value.startswith("/"):
        return "https://www.tradingview.com" + value
    return value


def normalize_idea(item: dict[str, Any]) -> dict[str, Any]:
    symbol = item.get("symbol") if isinstance(item.get("symbol"), dict) else {}
    user = item.get("user") if isinstance(item.get("user"), dict) else {}
    image = item.get("image") if isinstance(item.get("image"), dict) else {}

    idea_id = str(item.get("id") or item.get("name") or "")
    if not idea_id:
        idea_id = hashlib.sha1(json.dumps(item, sort_keys=True, default=str).encode()).hexdigest()[:20]

    direction_raw = symbol.get("direction")
    try:
        direction_key = int(direction_raw) if direction_raw is not None else 0
    except (TypeError, ValueError):
        direction_key = 0

    return {
        "idea_id": idea_id,
        "title": item.get("name") or item.get("title") or "",
        "description": item.get("description") or "",
        "author": user.get("username") or item.get("author") or "",
        "symbol": symbol.get("name") or item.get("symbol_name") or "",
        "exchange": symbol.get("exchange") or "",
        "asset_type": symbol.get("type") or "",
        "direction": DIRECTION.get(direction_key, str(direction_raw or "중립")),
        "interval": str(symbol.get("interval") or item.get("interval") or ""),
        "created_at": str(item.get("created_at") or item.get("published_at") or ""),
        "comments_count": int(item.get("comments_count") or 0),
        "likes_count": int(item.get("likes_count") or item.get("boosts_count") or 0),
        "views_count": int(item.get("views_count") or 0),
        "chart_url": _absolute_url(item.get("chart_url") or item.get("url")),
        "image_url": _absolute_url(image.get("big") or image.get("middle") or item.get("image_url")),
        "raw_json": item,
    }


def store_ideas(items: list[dict[str, Any]]) -> None:
    init_db()
    now = utcnow()
    with _connect() as conn:
        conn.executemany(
            """
            INSERT INTO community_ideas (
                idea_id,title,description,author,symbol,exchange,asset_type,direction,interval,
                created_at,comments_count,likes_count,views_count,chart_url,image_url,raw_json,collected_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(idea_id) DO UPDATE SET
                title=excluded.title,
                description=excluded.description,
                author=excluded.author,
                symbol=excluded.symbol,
                exchange=excluded.exchange,
                asset_type=excluded.asset_type,
                direction=excluded.direction,
                interval=excluded.interval,
                comments_count=excluded.comments_count,
                likes_count=excluded.likes_count,
                views_count=excluded.views_count,
                chart_url=excluded.chart_url,
                image_url=excluded.image_url,
                raw_json=excluded.raw_json,
                collected_at=excluded.collected_at
            """,
            [
                (
                    x["idea_id"], x["title"], x["description"], x["author"], x["symbol"], x["exchange"],
                    x["asset_type"], x["direction"], x["interval"], x["created_at"], x["comments_count"],
                    x["likes_count"], x["views_count"], x["chart_url"], x["image_url"],
                    json.dumps(x["raw_json"], ensure_ascii=False), now,
                )
                for x in items
            ],
        )


def collect_ideas(sort: str = "trending", page: int = 1, lang: str = "ko") -> dict[str, Any]:
    allowed_sorts = {
        "trending", "recent", "latest_popular", "week_popular",
        "suggested", "recent_extended", "picked_time",
    }
    if sort not in allowed_sorts:
        raise ValueError(f"unsupported sort: {sort}")
    params = parse.urlencode({"lang": lang, "sort": sort, "page": max(1, page)})
    raw = _http_json(f"{IDEAS_URL}?{params}")
    rows = [normalize_idea(x) for x in raw.get("results", []) if isinstance(x, dict)]
    store_ideas(rows)
    return {
        "source": "TradingView public ideas API",
        "sort": sort,
        "page": page,
        "count": len(rows),
        "total_count": raw.get("count"),
        "page_count": raw.get("page_count"),
        "items": [{k: v for k, v in row.items() if k != "raw_json"} for row in rows],
        "collected_at": utcnow(),
    }


def collect_market(
    market: str,
    *,
    limit: int = 20,
    sort_by: str = "volume",
    sort_order: str = "desc",
) -> dict[str, Any]:
    market_key = MARKET_ALIASES.get(market.lower(), market.lower())
    if market_key not in set(MARKET_ALIASES.values()):
        raise ValueError(f"unsupported market: {market}")

    safe_limit = min(max(limit, 1), 100)
    if sort_by not in {"volume", "change", "close", "name"}:
        sort_by = "volume"
    if sort_order not in {"asc", "desc"}:
        sort_order = "desc"

    payload = {
        "filter": [],
        "options": {"lang": "ko"},
        "markets": [market_key],
        "columns": DEFAULT_COLUMNS,
        "sort": {"sortBy": sort_by, "sortOrder": sort_order},
        "range": [0, safe_limit],
    }
    raw = _http_json(SCANNER_URL.format(market=market_key), method="POST", payload=payload)
    rows: list[dict[str, Any]] = []
    for item in raw.get("data", []):
        values = item.get("d", [])
        row = dict(zip(DEFAULT_COLUMNS, values))
        row["ticker"] = item.get("s")
        rows.append(row)

    return {
        "source": "TradingView scanner",
        "market": market_key,
        "total_count": raw.get("totalCount"),
        "count": len(rows),
        "columns": DEFAULT_COLUMNS,
        "items": rows,
        "collected_at": utcnow(),
    }



def normalize_script(item: dict[str, Any]) -> dict[str, Any]:
    user = item.get("user") if isinstance(item.get("user"), dict) else {}
    image = item.get("image") if isinstance(item.get("image"), dict) else {}
    symbol = item.get("symbol") if isinstance(item.get("symbol"), dict) else {}
    script_id_part = str(item.get("script_id_part") or "")
    return {
        "script_id_part": script_id_part,
        "script_id": str(item.get("id") or ""),
        "name": item.get("name") or "",
        "author": user.get("username") or "",
        "script_type": item.get("script_type") or "",
        "script_access": int(item.get("script_access") or 0),
        "version": str(item.get("version") or ""),
        "likes_count": int(item.get("likes_count") or 0),
        "comments_count": int(item.get("comments_count") or 0),
        "views_count": int(item.get("views_count") or 0),
        "created_at": str(item.get("created_at") or ""),
        "updated_at": str(item.get("updated_at") or ""),
        "chart_url": _absolute_url(item.get("chart_url")),
        "image_url": _absolute_url(image.get("big") or item.get("image_url")),
        "symbol": symbol.get("name") or "",
        "interval": str(symbol.get("interval") or ""),
        "is_picked": bool(item.get("is_picked")),
        "is_hot": bool(item.get("is_hot")),
        "description": item.get("description") or "",
        "raw_json": item,
    }


def store_scripts(items: list[dict[str, Any]]) -> None:
    init_db()
    now = utcnow()
    rows = [x for x in items if x.get("script_id_part")]
    with _connect() as conn:
        conn.executemany(
            """
            INSERT INTO community_scripts (
                script_id_part,script_id,name,author,script_type,script_access,version,
                likes_count,comments_count,views_count,created_at,updated_at,chart_url,image_url,
                symbol,interval,is_picked,is_hot,description,raw_json,collected_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(script_id_part) DO UPDATE SET
                script_id=excluded.script_id,
                name=excluded.name,
                author=excluded.author,
                script_type=excluded.script_type,
                script_access=excluded.script_access,
                version=excluded.version,
                likes_count=excluded.likes_count,
                comments_count=excluded.comments_count,
                views_count=excluded.views_count,
                updated_at=excluded.updated_at,
                chart_url=excluded.chart_url,
                image_url=excluded.image_url,
                symbol=excluded.symbol,
                interval=excluded.interval,
                is_picked=excluded.is_picked,
                is_hot=excluded.is_hot,
                description=excluded.description,
                raw_json=excluded.raw_json,
                collected_at=excluded.collected_at
            """,
            [
                (
                    x["script_id_part"], x["script_id"], x["name"], x["author"], x["script_type"],
                    x["script_access"], x["version"], x["likes_count"], x["comments_count"],
                    x["views_count"], x["created_at"], x["updated_at"], x["chart_url"], x["image_url"],
                    x["symbol"], x["interval"], int(x["is_picked"]), int(x["is_hot"]),
                    x["description"], json.dumps(x["raw_json"], ensure_ascii=False), now,
                )
                for x in rows
            ],
        )


def collect_scripts(
    *,
    page: int = 1,
    sort: str = "latest_popular",
    topic: str | None = None,
    editors_picks: bool = False,
) -> dict[str, Any]:
    if sort not in {"latest_popular", "recent_extended"}:
        raise ValueError(f"unsupported script sort: {sort}")
    segment = "editors-picks" if editors_picks else (topic or "").strip().lower()
    if segment:
        segment = "-".join(
            part for part in "".join(ch if ch.isalnum() else "-" for ch in segment).split("-") if part
        )
    parts = ["scripts"]
    if segment:
        parts.append(segment)
    if page > 1:
        parts.append(f"page-{page}")
    path = "/" + "/".join(parts) + "/"
    query = parse.urlencode({
        "component-data-only": "1",
        "script_type": "strategies",
        "script_access": "open",
        "sort": sort,
    })
    raw = _http_json(f"{SCRIPTS_ORIGIN}{path}?{query}")
    feed = (((raw.get("data") or {}).get("ideas") or {}).get("data") or {})
    raw_items = feed.get("items") or []
    rows = [
        normalize_script(x)
        for x in raw_items
        if isinstance(x, dict) and int(x.get("script_access") or 0) == 1
    ]
    store_scripts(rows)
    return {
        "source": "TradingView Community Scripts",
        "script_type": "strategies",
        "script_access": "open",
        "sort": sort,
        "topic": topic,
        "editors_picks": editors_picks,
        "page": page,
        "total_count": feed.get("total"),
        "has_more": bool(feed.get("next")),
        "count": len(rows),
        "items": [{k: v for k, v in x.items() if k != "raw_json"} for x in rows],
        "collected_at": utcnow(),
    }


def list_stored_scripts(limit: int = 200) -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT script_id_part,script_id,name,author,script_type,script_access,version,
                   likes_count,comments_count,views_count,created_at,updated_at,chart_url,image_url,
                   symbol,interval,is_picked,is_hot,description,collected_at
            FROM community_scripts
            ORDER BY is_picked DESC, likes_count DESC, collected_at DESC
            LIMIT ?
            """,
            (min(max(limit, 1), 1000),),
        ).fetchall()
    return [dict(row) for row in rows]


def fetch_script_source(script_id_part: str, version: str = "last") -> dict[str, Any]:
    init_db()
    with _connect() as conn:
        cached = conn.execute(
            "SELECT * FROM script_sources WHERE script_id_part = ?",
            (script_id_part,),
        ).fetchone()
        if cached is not None and version in {"last", str(cached["version"])}:
            row = dict(cached)
            row["ok"] = True
            row["from_cache"] = True
            return row

    encoded_id = parse.quote(script_id_part, safe="")
    encoded_version = parse.quote(str(version), safe="")
    url = f"{PINE_FACADE_ORIGIN}/pine-facade/get/{encoded_id}/{encoded_version}?no_4xx=true"
    raw = _http_json(url)
    source = raw.get("source")
    if not isinstance(source, str):
        return {
            "ok": False,
            "protected": True,
            "script_id_part": script_id_part,
            "reason": raw.get("reason") or "No Pine source returned",
        }

    pine_version = None
    for line in source.splitlines()[:10]:
        stripped = line.strip().replace(" ", "")
        if stripped.startswith("//@version="):
            try:
                pine_version = int(stripped.split("=", 1)[1])
            except ValueError:
                pine_version = None
            break

    kind = ((raw.get("extra") or {}).get("kind") if isinstance(raw.get("extra"), dict) else None)
    resolved_version = str(raw.get("version") or raw.get("lastVersionMaj") or version)
    script_name = raw.get("scriptName") or ""
    source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
    now = utcnow()

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO script_sources (
                script_id_part,version,script_name,kind,pine_version,source_hash,source,fetched_at
            ) VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(script_id_part) DO UPDATE SET
                version=excluded.version,
                script_name=excluded.script_name,
                kind=excluded.kind,
                pine_version=excluded.pine_version,
                source_hash=excluded.source_hash,
                source=excluded.source,
                fetched_at=excluded.fetched_at
            """,
            (
                script_id_part, resolved_version, script_name, kind, pine_version,
                source_hash, source, now,
            ),
        )
    return {
        "ok": True,
        "from_cache": False,
        "script_id_part": script_id_part,
        "version": resolved_version,
        "script_name": script_name,
        "kind": kind,
        "pine_version": pine_version,
        "source_hash": source_hash,
        "source": source,
        "source_chars": len(source),
        "fetched_at": now,
    }


def create_candidate_from_script(script_id_part: str, fetch_source: bool = True) -> dict[str, Any]:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM community_scripts WHERE script_id_part = ?",
            (script_id_part,),
        ).fetchone()
    if row is None:
        raise KeyError(script_id_part)
    script = dict(row)

    source_text = ""
    source_hash = None
    if fetch_source:
        try:
            source_result = fetch_script_source(script_id_part, script.get("version") or "last")
            if source_result.get("ok"):
                source_text = source_result.get("source") or ""
                source_hash = source_result.get("source_hash")
        except Exception:
            source_text = ""

    classification_text = " ".join([
        script.get("name") or "",
        script.get("description") or "",
        source_text[:20000],
    ])
    category = _category_for(classification_text)
    horizons = list(CATEGORY_HORIZONS[category])
    source_interval = _normalize_interval(script.get("interval") or "")
    if source_interval and source_interval not in horizons:
        horizons.insert(0, source_interval)

    candidate_id = "TVS-" + hashlib.sha1(script_id_part.encode()).hexdigest()[:10].upper()
    logic = (script.get("description") or script.get("name") or "").strip()
    if len(logic) > 800:
        logic = logic[:800]
    if source_hash:
        logic = f"{logic}\n[Pine source hash: {source_hash[:16]}]".strip()

    now = utcnow()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO strategy_candidates (
                candidate_id,source_kind,source_id,name,category,domain,logic,candidate_horizons,status,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(candidate_id) DO UPDATE SET
                name=excluded.name,
                category=excluded.category,
                domain=excluded.domain,
                logic=excluded.logic,
                candidate_horizons=excluded.candidate_horizons,
                status=excluded.status
            """,
            (
                candidate_id, "TradingViewPineStrategy", script_id_part,
                script.get("name") or candidate_id, category, CATEGORY_DOMAINS[category],
                logic, json.dumps(horizons, ensure_ascii=False), "후보", now,
            ),
        )

    return {
        "candidate_id": candidate_id,
        "source_kind": "TradingViewPineStrategy",
        "source_id": script_id_part,
        "source_version": script.get("version"),
        "source_hash": source_hash,
        "name": script.get("name") or candidate_id,
        "author": script.get("author"),
        "category": category,
        "domain": CATEGORY_DOMAINS[category],
        "logic": logic,
        "candidate_horizons": horizons,
        "status": "후보",
        "origin_source_immutable": True,
        "created_at": now,
    }


def list_stored_ideas(limit: int = 100) -> list[dict[str, Any]]:
    init_db()
    safe_limit = min(max(limit, 1), 500)
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT idea_id,title,description,author,symbol,exchange,asset_type,direction,interval,
                   created_at,comments_count,likes_count,views_count,chart_url,image_url,collected_at
            FROM community_ideas
            ORDER BY collected_at DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def _category_for(text: str) -> str:
    haystack = text.lower()
    for category, words in CATEGORY_RULES:
        if any(word in haystack for word in words):
            return category
    return "아이디어 기반"


def _normalize_interval(interval: str) -> str | None:
    value = (interval or "").strip().lower()
    mapping = {
        "1": "1m", "3": "3m", "5": "5m", "10": "10m", "15": "15m", "30": "30m",
        "45": "45m", "60": "1h", "120": "2h", "180": "3h", "240": "4h",
        "1d": "1d", "d": "1d", "1w": "1w", "w": "1w",
    }
    return mapping.get(value, value or None)


def create_candidate_from_idea(idea_id: str) -> dict[str, Any]:
    init_db()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM community_ideas WHERE idea_id = ?", (idea_id,)).fetchone()
        if row is None:
            raise KeyError(idea_id)
        idea = dict(row)

        text = " ".join([idea.get("title") or "", idea.get("description") or ""])
        category = _category_for(text)
        horizons = list(CATEGORY_HORIZONS[category])
        source_interval = _normalize_interval(idea.get("interval") or "")
        if source_interval and source_interval not in horizons:
            horizons.insert(0, source_interval)

        candidate_id = "TVI-" + hashlib.sha1(idea_id.encode()).hexdigest()[:10].upper()
        logic = (idea.get("description") or idea.get("title") or "").strip()
        if len(logic) > 500:
            logic = logic[:500]

        now = utcnow()
        conn.execute(
            """
            INSERT INTO strategy_candidates (
                candidate_id,source_kind,source_id,name,category,domain,logic,candidate_horizons,status,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(candidate_id) DO UPDATE SET
                name=excluded.name,
                category=excluded.category,
                domain=excluded.domain,
                logic=excluded.logic,
                candidate_horizons=excluded.candidate_horizons,
                status=excluded.status
            """,
            (
                candidate_id, "TradingViewIdea", idea_id, idea.get("title") or candidate_id, category,
                CATEGORY_DOMAINS[category], logic, json.dumps(horizons, ensure_ascii=False), "후보", now,
            ),
        )

    return {
        "candidate_id": candidate_id,
        "source_kind": "TradingViewIdea",
        "source_id": idea_id,
        "name": idea.get("title") or candidate_id,
        "category": category,
        "domain": CATEGORY_DOMAINS[category],
        "logic": logic,
        "candidate_horizons": horizons,
        "status": "후보",
        "created_at": now,
    }


def list_candidates(limit: int = 100) -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM strategy_candidates ORDER BY created_at DESC LIMIT ?",
            (min(max(limit, 1), 500),),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["candidate_horizons"] = json.loads(item["candidate_horizons"])
        result.append(item)
    return result


def create_agent_plans(candidate_id: str, max_markets: int = 3) -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM strategy_candidates WHERE candidate_id = ?", (candidate_id,)).fetchone()
        if row is None:
            raise KeyError(candidate_id)
        candidate = dict(row)
        horizons = json.loads(candidate["candidate_horizons"])
        markets = CATEGORY_MARKETS.get(candidate["category"], CATEGORY_MARKETS["아이디어 기반"])[:max_markets]

        created: list[dict[str, Any]] = []
        for market_index, target in enumerate(markets, start=1):
            for horizon in horizons:
                identity = "|".join([
                    candidate["source_id"],
                    candidate_id,
                    horizon,
                    target["country"],
                    target["market"],
                    target["universe"],
                ])
                agent_id = "A-TV-" + hashlib.sha1(identity.encode()).hexdigest()[:12].upper()
                now = utcnow()
                conn.execute(
                    """
                    INSERT OR IGNORE INTO agent_plans (
                        agent_id,candidate_id,source_id,fixed_horizon,country,market,universe,status,created_at
                    ) VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        agent_id, candidate_id, candidate["source_id"], horizon, target["country"],
                        target["market"], target["universe"], "RESEARCH", now,
                    ),
                )
                created.append({
                    "agent_id": agent_id,
                    "candidate_id": candidate_id,
                    "source_id": candidate["source_id"],
                    "origin_source_immutable": True,
                    "fixed_horizon": horizon,
                    "fixed_horizon_immutable": True,
                    "country": target["country"],
                    "market": target["market"],
                    "universe": target["universe"],
                    "status": "RESEARCH",
                })
    return created


def list_agent_plans(candidate_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        if candidate_id:
            rows = conn.execute(
                "SELECT * FROM agent_plans WHERE candidate_id = ? ORDER BY created_at DESC LIMIT ?",
                (candidate_id, min(max(limit, 1), 1000)),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM agent_plans ORDER BY created_at DESC LIMIT ?",
                (min(max(limit, 1), 1000),),
            ).fetchall()
    return [dict(row) for row in rows]
