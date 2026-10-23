from __future__ import annotations

import hashlib
import html as html_lib
import re
import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from typing import Any
from urllib import error, parse, request


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
    "vietnam": "vietnam",
    "vn": "vietnam",
    "베트남": "vietnam",
    "futures": "futures",
    "선물": "futures",
    "bonds": "bonds",
    "bond": "bonds",
    "국채": "bonds",
    "회사채": "corporate-bonds",
    "corporate-bonds": "corporate-bonds",
    "company-bonds": "corporate-bonds",
    "indices": "indices",
    "index": "indices",
    "지수": "indices",
    "global-stocks": "global-stocks",
    "world-stocks": "global-stocks",
    "세계주식": "global-stocks",
    "etf": "etf",
    "etfs": "etf",
}

DEFAULT_COLUMNS = [
    "name",
    "description",
    "close",
    "change",
    "volume",
    "Volatility.D",
    "relative_volume_10d_calc",
    "RSI",
    "ATR",
    "ADX",
    "Recommend.All",
    "market_cap_basic",
    "market_cap_calc",
    "sector",
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

MARKET_SCANNER_PROFILES: dict[str, dict[str, Any]] = {
    "korea": {"endpoint": "korea", "filters": []},
    "america": {"endpoint": "america", "filters": []},
    "crypto": {"endpoint": "crypto", "filters": []},
    "forex": {"endpoint": "forex", "filters": []},
    "india": {"endpoint": "india", "filters": []},
    "japan": {"endpoint": "japan", "filters": []},
    "vietnam": {"endpoint": "vietnam", "filters": []},
    "futures": {"endpoint": "futures", "filters": []},
    "bonds": {"endpoint": "bonds", "filters": []},
    "corporate-bonds": {
        "endpoint": "bond",
        "markets": ["bond"],
        "columns": [
            "ticker-view",
            "exchange.tr",
            "source-logoid",
            "isin-displayed",
            "yield_to_worst",
            "close_pct",
            "close_net",
            "type",
            "typespecs",
            "fundamental_currency_code",
            "current_coupon",
            "maturity_date",
            "redemption_type.tr",
            "bond_issuer_type.tr",
            "bond_snp_rating_lt.tr",
            "bond_fitch_rating_lt.tr"
        ],
        "default_sort": "yield_to_worst",
        "allowed_sort": ["yield_to_worst", "current_coupon", "maturity_date", "bond_snp_rating_lt", "name"],
        "filters": []
    },
    "indices": {
        "endpoint": "global",
        "filters": [{"left": "type", "operation": "equal", "right": "index"}],
    },
    "global-stocks": {
        "endpoint": "global",
        "filters": [{"left": "type", "operation": "equal", "right": "stock"}],
    },
    "etf": {
        "endpoint": "america",
        "filters": [{"left": "type", "operation": "equal", "right": "fund"}],
    },
}


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
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
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
                is_video INTEGER DEFAULT 0,
                is_education INTEGER DEFAULT 0,
                is_picked INTEGER DEFAULT 0,
                is_hot INTEGER DEFAULT 0,
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

            CREATE TABLE IF NOT EXISTS script_source_attempts (
                script_id_part TEXT PRIMARY KEY,
                ok INTEGER NOT NULL DEFAULT 0,
                protected INTEGER NOT NULL DEFAULT 0,
                reason TEXT,
                fetched_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS source_details (
                source_kind TEXT NOT NULL,
                source_id TEXT NOT NULL,
                source_url TEXT NOT NULL,
                title TEXT,
                full_text TEXT NOT NULL,
                hero_images_json TEXT NOT NULL,
                content_images_json TEXT NOT NULL,
                page_hash TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                PRIMARY KEY (source_kind, source_id)
            );

            CREATE TABLE IF NOT EXISTS collector_state (
                collector_key TEXT PRIMARY KEY,
                cursor_page INTEGER NOT NULL,
                total_pages INTEGER NOT NULL,
                items_seen INTEGER NOT NULL DEFAULT 0,
                details_seen INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS market_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                market TEXT NOT NULL,
                ticker TEXT NOT NULL,
                name TEXT,
                description TEXT,
                close REAL,
                change REAL,
                volume REAL,
                exchange TEXT,
                asset_type TEXT,
                volatility_d REAL,
                relative_volume REAL,
                rsi REAL,
                atr REAL,
                adx REAL,
                recommendation REAL,
                market_cap REAL,
                sector TEXT,
                rank_index INTEGER,
                collected_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_market_snapshots_market_time
                ON market_snapshots(market, collected_at DESC);
            CREATE INDEX IF NOT EXISTS idx_market_snapshots_ticker_time
                ON market_snapshots(ticker, collected_at DESC);

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

            CREATE TABLE IF NOT EXISTS agent_universe_members (
                agent_id TEXT NOT NULL,
                ticker TEXT NOT NULL,
                rank_index INTEGER NOT NULL,
                prescreen_score REAL NOT NULL,
                rationale TEXT NOT NULL,
                snapshot_at TEXT NOT NULL,
                resolved_at TEXT NOT NULL,
                PRIMARY KEY (agent_id, ticker)
            );

            CREATE TABLE IF NOT EXISTS agent_status_history (
                event_id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                from_status TEXT,
                to_status TEXT NOT NULL,
                reason TEXT,
                metadata_json TEXT NOT NULL,
                changed_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_agent_status_history_agent
                ON agent_status_history(agent_id, changed_at DESC);
            """
        )
        migrations = [
            ("community_ideas", "is_video", "INTEGER DEFAULT 0"),
            ("community_ideas", "is_education", "INTEGER DEFAULT 0"),
            ("community_ideas", "is_picked", "INTEGER DEFAULT 0"),
            ("community_ideas", "is_hot", "INTEGER DEFAULT 0"),
            ("market_snapshots", "volatility_d", "REAL"),
            ("market_snapshots", "relative_volume", "REAL"),
            ("market_snapshots", "rsi", "REAL"),
            ("market_snapshots", "atr", "REAL"),
            ("market_snapshots", "adx", "REAL"),
            ("market_snapshots", "recommendation", "REAL"),
            ("market_snapshots", "market_cap", "REAL"),
            ("market_snapshots", "sector", "TEXT"),
            ("market_snapshots", "raw_json", "TEXT"),
            ("strategy_candidates", "source_hash", "TEXT"),
            ("strategy_candidates", "source_version", "TEXT"),
            ("strategy_candidates", "classification_version", "TEXT"),
            ("strategy_candidates", "updated_at", "TEXT"),
        ]
        for table, column, definition in migrations:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            except sqlite3.OperationalError:
                pass

        conn.execute(
            """
            INSERT OR IGNORE INTO script_source_attempts (
                script_id_part,ok,protected,reason,fetched_at
            )
            SELECT script_id_part,1,0,NULL,fetched_at
            FROM script_sources
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


def _http_text(url: str) -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Referer": "https://www.tradingview.com/",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    }
    req = request.Request(url, headers=headers, method="GET")
    with request.urlopen(req, timeout=25) as response:
        return response.read().decode("utf-8", errors="replace")


class _TradingViewDetailParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_main = False
        self.main_depth = 0
        self.in_description = False
        self.description_depth = 0
        self.in_h1 = False
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.hero_images: list[str] = []
        self.content_images: list[str] = []

    @staticmethod
    def _attr(attrs: list[tuple[str, str | None]], name: str) -> str:
        for key, value in attrs:
            if key == name and value:
                return value
        return ""

    @staticmethod
    def _is_content_image(url: str) -> bool:
        if not url:
            return False
        return (
            "s3.tradingview.com/" in url
            or "/x/" in url
        ) and "userpics/" not in url and "s3-symbol-logo." not in url

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        cls = self._attr(attrs, "class")
        element_id = self._attr(attrs, "id")
        if tag == "main" and (element_id == "tv-content" or "tv-content" in cls):
            self.in_main = True
            self.main_depth = 1
        elif self.in_main and tag == "main":
            self.main_depth += 1

        if self.in_main and tag == "h1":
            self.in_h1 = True

        if self.in_main and tag == "div":
            if self.in_description:
                self.description_depth += 1
            elif any(part.startswith("description-") for part in cls.split()):
                self.in_description = True
                self.description_depth = 1

        if self.in_description and tag == "br":
            self.text_parts.append("\n")

        if tag == "img":
            src = self._attr(attrs, "src")
            if self._is_content_image(src):
                if self.in_description:
                    if src not in self.content_images:
                        self.content_images.append(src)
                elif self.in_main and src not in self.hero_images:
                    self.hero_images.append(src)

        if self.in_description and tag == "a":
            href = self._attr(attrs, "href")
            if self._is_content_image(href) and href not in self.content_images:
                self.content_images.append(href)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1":
            self.in_h1 = False
        if self.in_description and tag == "div":
            self.description_depth -= 1
            if self.description_depth <= 0:
                self.in_description = False
                self.description_depth = 0
        if self.in_main and tag == "main":
            self.main_depth -= 1
            if self.main_depth <= 0:
                self.in_main = False
                self.main_depth = 0

    def handle_data(self, data: str) -> None:
        value = data.strip()
        if not value:
            return
        if self.in_h1:
            self.title_parts.append(value)
        if self.in_description:
            if self.text_parts and not self.text_parts[-1].endswith("\n"):
                self.text_parts.append(" ")
            self.text_parts.append(value)

    def result(self) -> dict[str, Any]:
        text = "".join(self.text_parts)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        return {
            "title": " ".join(self.title_parts).strip(),
            "full_text": text,
            "hero_images": self.hero_images,
            "content_images": self.content_images,
        }


def _detail_source(source_kind: str, source_id: str) -> tuple[str, str, str]:
    init_db()
    with _connect() as conn:
        if source_kind == "idea":
            row = conn.execute(
                "SELECT title,description,chart_url,image_url FROM community_ideas WHERE idea_id = ?",
                (source_id,),
            ).fetchone()
        elif source_kind == "script":
            row = conn.execute(
                "SELECT name AS title,description,chart_url,image_url FROM community_scripts WHERE script_id_part = ?",
                (source_id,),
            ).fetchone()
        else:
            raise ValueError(f"unsupported source kind: {source_kind}")
    if row is None:
        raise KeyError(source_id)
    item = dict(row)
    return (
        str(item.get("title") or ""),
        str(item.get("description") or ""),
        str(item.get("chart_url") or ""),
    )


def fetch_source_detail(source_kind: str, source_id: str, *, force: bool = False) -> dict[str, Any]:
    init_db()
    with _connect() as conn:
        cached = conn.execute(
            "SELECT * FROM source_details WHERE source_kind = ? AND source_id = ?",
            (source_kind, source_id),
        ).fetchone()
        if cached is not None and not force:
            item = dict(cached)
            item["hero_images"] = json.loads(item.pop("hero_images_json") or "[]")
            item["content_images"] = json.loads(item.pop("content_images_json") or "[]")
            item["from_cache"] = True
            return item

    fallback_title, fallback_text, source_url = _detail_source(source_kind, source_id)
    if not source_url:
        raise ValueError("TradingView source URL is missing")

    separator = "&" if "?" in source_url else "?"
    detail_missing = False
    try:
        html_text = _http_text(source_url + separator + "component-data-only=1")
        parser = _TradingViewDetailParser()
        parser.feed(html_text)
        parsed = parser.result()
    except error.HTTPError as exc:
        if exc.code not in {404, 410}:
            raise
        detail_missing = True
        html_text = ""
        parsed = {
            "title": fallback_title,
            "full_text": fallback_text,
            "hero_images": [],
            "content_images": [],
        }

    hero_images = list(parsed["hero_images"])
    content_images = list(parsed["content_images"])
    with _connect() as conn:
        if source_kind == "idea":
            row = conn.execute(
                "SELECT image_url FROM community_ideas WHERE idea_id = ?",
                (source_id,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT image_url FROM community_scripts WHERE script_id_part = ?",
                (source_id,),
            ).fetchone()
    if row is not None and row["image_url"] and row["image_url"] not in hero_images:
        hero_images.insert(0, str(row["image_url"]))

    title = str(parsed.get("title") or fallback_title)
    full_text = str(parsed.get("full_text") or fallback_text)
    now = utcnow()
    hash_material = html_text if html_text else json.dumps(
        {"source_url": source_url, "title": title, "full_text": full_text},
        ensure_ascii=False,
        sort_keys=True,
    )
    page_hash = hashlib.sha256(hash_material.encode("utf-8")).hexdigest()

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO source_details (
                source_kind,source_id,source_url,title,full_text,
                hero_images_json,content_images_json,page_hash,fetched_at
            ) VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(source_kind,source_id) DO UPDATE SET
                source_url=excluded.source_url,
                title=excluded.title,
                full_text=excluded.full_text,
                hero_images_json=excluded.hero_images_json,
                content_images_json=excluded.content_images_json,
                page_hash=excluded.page_hash,
                fetched_at=excluded.fetched_at
            """,
            (
                source_kind, source_id, source_url, title, full_text,
                json.dumps(hero_images, ensure_ascii=False),
                json.dumps(content_images, ensure_ascii=False),
                page_hash, now,
            ),
        )

    return {
        "source_kind": source_kind,
        "source_id": source_id,
        "source_url": source_url,
        "title": title,
        "full_text": full_text,
        "hero_images": hero_images,
        "content_images": content_images,
        "page_hash": page_hash,
        "fetched_at": now,
        "from_cache": False,
        "detail_missing": detail_missing,
    }


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
        "is_video": bool(item.get("is_video")),
        "is_education": bool(item.get("is_education")),
        "is_picked": bool(item.get("is_picked")),
        "is_hot": bool(item.get("is_hot")),
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
                created_at,comments_count,likes_count,views_count,chart_url,image_url,
                is_video,is_education,is_picked,is_hot,raw_json,collected_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
                is_video=excluded.is_video,
                is_education=excluded.is_education,
                is_picked=excluded.is_picked,
                is_hot=excluded.is_hot,
                raw_json=excluded.raw_json,
                collected_at=excluded.collected_at
            """,
            [
                (
                    x["idea_id"], x["title"], x["description"], x["author"], x["symbol"], x["exchange"],
                    x["asset_type"], x["direction"], x["interval"], x["created_at"], x["comments_count"],
                    x["likes_count"], x["views_count"], x["chart_url"], x["image_url"],
                    int(x["is_video"]), int(x["is_education"]), int(x["is_picked"]), int(x["is_hot"]),
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


def prune_market_snapshots(retention_days: int = 30) -> int:
    init_db()
    cutoff = (datetime.now(UTC) - timedelta(days=max(1, retention_days))).isoformat()
    with _connect() as conn:
        cursor = conn.execute(
            "DELETE FROM market_snapshots WHERE collected_at < ?",
            (cutoff,),
        )
        return int(cursor.rowcount or 0)


def _sqlite_real(value: Any) -> float | None:
    """Normalize scanner numerics before SQLite binding.

    TradingView can return arbitrary-size JSON integers, especially for crypto
    volume/cap fields. Python sqlite3 binds an int as SQLite INTEGER before
    column affinity is applied, so values outside signed int64 can overflow
    even when the destination column is declared REAL.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def store_market_snapshot(market: str, rows: list[dict[str, Any]], collected_at: str) -> None:
    init_db()
    bucket = collected_at[:16]
    with _connect() as conn:
        conn.executemany(
            """
            INSERT OR IGNORE INTO market_snapshots (
                snapshot_id,market,ticker,name,description,close,change,volume,exchange,asset_type,
                volatility_d,relative_volume,rsi,atr,adx,recommendation,market_cap,sector,rank_index,collected_at,raw_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            [
                (
                    hashlib.sha1(f"{market}|{x.get('ticker')}|{bucket}".encode()).hexdigest(),
                    market,
                    x.get("ticker") or "",
                    x.get("name"),
                    x.get("description"),
                    _sqlite_real(x.get("close")),
                    _sqlite_real(x.get("change")),
                    _sqlite_real(x.get("volume")),
                    x.get("exchange"),
                    x.get("type"),
                    _sqlite_real(x.get("Volatility.D")),
                    _sqlite_real(x.get("relative_volume_10d_calc")),
                    _sqlite_real(x.get("RSI")),
                    _sqlite_real(x.get("ATR")),
                    _sqlite_real(x.get("ADX")),
                    _sqlite_real(x.get("Recommend.All")),
                    _sqlite_real(x.get("market_cap_basic") if x.get("market_cap_basic") is not None else x.get("market_cap_calc")),
                    x.get("sector"),
                    idx,
                    collected_at,
                    json.dumps(x, ensure_ascii=False),
                )
                for idx, x in enumerate(rows, start=1)
                if x.get("ticker")
            ],
        )


def list_market_snapshots(market: str, limit: int = 100, latest_only: bool = True) -> list[dict[str, Any]]:
    init_db()
    market_key = MARKET_ALIASES.get(market.lower(), market.lower())
    safe_limit = min(max(limit, 1), 1000)
    with _connect() as conn:
        if latest_only:
            latest = conn.execute(
                "SELECT MAX(collected_at) AS ts FROM market_snapshots WHERE market = ?",
                (market_key,),
            ).fetchone()["ts"]
            if latest is None:
                return []
            rows = conn.execute(
                """
                SELECT market,ticker,name,description,close,change,volume,exchange,asset_type,
                       volatility_d,relative_volume,rsi,atr,adx,recommendation,market_cap,sector,rank_index,collected_at
                FROM market_snapshots
                WHERE market = ? AND collected_at = ?
                ORDER BY rank_index ASC
                LIMIT ?
                """,
                (market_key, latest, safe_limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT market,ticker,name,description,close,change,volume,exchange,asset_type,
                       volatility_d,relative_volume,rsi,atr,adx,recommendation,market_cap,sector,rank_index,collected_at
                FROM market_snapshots
                WHERE market = ?
                ORDER BY collected_at DESC, rank_index ASC
                LIMIT ?
                """,
                (market_key, safe_limit),
            ).fetchall()
    return [dict(row) for row in rows]


def collect_market(
    market: str,
    *,
    limit: int = 20,
    offset: int = 0,
    sort_by: str = "volume",
    sort_order: str = "desc",
) -> dict[str, Any]:
    market_key = MARKET_ALIASES.get(market.lower(), market.lower())
    if market_key not in MARKET_SCANNER_PROFILES:
        raise ValueError(f"unsupported market: {market}")

    safe_limit = min(max(limit, 1), 100)
    safe_offset = max(int(offset), 0)
    profile = MARKET_SCANNER_PROFILES[market_key]
    default_allowed_sort = {
        "volume", "change", "close", "name", "Volatility.D",
        "relative_volume_10d_calc", "RSI", "ATR", "ADX",
        "market_cap_basic", "market_cap_calc",
    }
    allowed_sort = set(profile.get("allowed_sort") or default_allowed_sort)
    if sort_by not in allowed_sort:
        sort_by = str(profile.get("default_sort") or "volume")
    if sort_order not in {"asc", "desc"}:
        sort_order = "desc"

    columns = list(profile.get("columns") or DEFAULT_COLUMNS)
    if "markets" in profile:
        scanner_markets = list(profile.get("markets") or [])
    else:
        scanner_markets = [] if market_key in {"futures", "bonds", "indices", "global-stocks"} else [profile["endpoint"]]

    payload = {
        "filter": list(profile.get("filters") or []),
        "options": {"lang": "ko"},
        "markets": scanner_markets,
        "columns": columns,
        "sort": {"sortBy": sort_by, "sortOrder": sort_order},
        "range": [safe_offset, safe_offset + safe_limit],
    }
    raw = _http_json(SCANNER_URL.format(market=profile["endpoint"]), method="POST", payload=payload)
    rows: list[dict[str, Any]] = []
    for item in raw.get("data", []):
        values = item.get("d", [])
        row = dict(zip(columns, values))
        row["ticker"] = item.get("s")
        if market_key == "corporate-bonds":
            ticker_view = row.get("ticker-view") if isinstance(row.get("ticker-view"), dict) else {}
            row["name"] = ticker_view.get("name") or row.get("isin-displayed") or item.get("s")
            row["description"] = ticker_view.get("description") or ""
            row["ticker_view"] = ticker_view
            row["close"] = row.get("close_pct")
            row["change"] = row.get("close_net")
            row["type"] = row.get("type") or ticker_view.get("type") or "bond"
            row["exchange"] = row.get("exchange.tr")
        rows.append(row)

    collected_at = utcnow()
    store_market_snapshot(market_key, rows, collected_at)
    prune_market_snapshots(retention_days=30)
    return {
        "source": "TradingView scanner",
        "market": market_key,
        "total_count": raw.get("totalCount"),
        "count": len(rows),
        "offset": safe_offset,
        "limit": safe_limit,
        "has_more": safe_offset + len(rows) < int(raw.get("totalCount") or 0),
        "columns": columns,
        "items": rows,
        "collected_at": collected_at,
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


def search_stored_scripts(query: str, limit: int = 50) -> list[dict[str, Any]]:
    init_db()
    needle = f"%{str(query or '').strip()}%"
    safe_limit = min(max(int(limit), 1), 200)
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT script_id_part,script_id,name,author,script_type,script_access,version,
                   likes_count,comments_count,views_count,created_at,updated_at,chart_url,image_url,
                   symbol,interval,is_picked,is_hot,description,collected_at
            FROM community_scripts
            WHERE name LIKE ? COLLATE NOCASE
               OR description LIKE ? COLLATE NOCASE
               OR symbol LIKE ? COLLATE NOCASE
            ORDER BY is_picked DESC, likes_count DESC, collected_at DESC
            LIMIT ?
            """,
            (needle, needle, needle, safe_limit),
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
            conn.execute(
                """
                INSERT INTO script_source_attempts (script_id_part,ok,protected,reason,fetched_at)
                VALUES (?,?,?,?,?)
                ON CONFLICT(script_id_part) DO UPDATE SET
                    ok=excluded.ok,
                    protected=excluded.protected,
                    reason=excluded.reason,
                    fetched_at=excluded.fetched_at
                """,
                (script_id_part, 1, 0, None, row.get("fetched_at") or utcnow()),
            )
            row["ok"] = True
            row["from_cache"] = True
            return row

    encoded_id = parse.quote(script_id_part, safe="")
    encoded_version = parse.quote(str(version), safe="")
    url = f"{PINE_FACADE_ORIGIN}/pine-facade/get/{encoded_id}/{encoded_version}?no_4xx=true"
    raw = _http_json(url)
    source = raw.get("source")
    if not isinstance(source, str):
        reason = raw.get("reason") or "No Pine source returned"
        now = utcnow()
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO script_source_attempts (script_id_part,ok,protected,reason,fetched_at)
                VALUES (?,?,?,?,?)
                ON CONFLICT(script_id_part) DO UPDATE SET
                    ok=excluded.ok,
                    protected=excluded.protected,
                    reason=excluded.reason,
                    fetched_at=excluded.fetched_at
                """,
                (script_id_part, 0, 1, reason, now),
            )
        return {
            "ok": False,
            "protected": True,
            "script_id_part": script_id_part,
            "reason": reason,
            "fetched_at": now,
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
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO script_source_attempts (script_id_part,ok,protected,reason,fetched_at)
            VALUES (?,?,?,?,?)
            ON CONFLICT(script_id_part) DO UPDATE SET
                ok=excluded.ok,
                protected=excluded.protected,
                reason=excluded.reason,
                fetched_at=excluded.fetched_at
            """,
            (script_id_part, 1, 0, None, now),
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


def script_source_completion_status() -> dict[str, Any]:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN d.source_id IS NOT NULL THEN 1 ELSE 0 END) AS detail_ready,
                SUM(CASE WHEN a.script_id_part IS NOT NULL THEN 1 ELSE 0 END) AS source_attempted,
                SUM(CASE WHEN s.script_id_part IS NOT NULL THEN 1 ELSE 0 END) AS source_ready,
                SUM(CASE WHEN a.protected = 1 THEN 1 ELSE 0 END) AS source_protected
            FROM community_scripts c
            LEFT JOIN source_details d
              ON d.source_kind = 'script' AND d.source_id = c.script_id_part
            LEFT JOIN script_source_attempts a
              ON a.script_id_part = c.script_id_part
            LEFT JOIN script_sources s
              ON s.script_id_part = c.script_id_part
            """
        ).fetchone()
    data = dict(row or {})
    for key in ("total","detail_ready","source_attempted","source_ready","source_protected"):
        data[key] = int(data.get(key) or 0)
    data["detail_missing"] = max(0, data["total"] - data["detail_ready"])
    data["source_unattempted"] = max(0, data["total"] - data["source_attempted"])
    return data


def complete_missing_script_assets(limit: int = 500) -> dict[str, Any]:
    init_db()
    safe_limit = min(max(int(limit), 1), 2000)
    before = script_source_completion_status()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT c.*
            FROM community_scripts c
            LEFT JOIN source_details d
              ON d.source_kind = 'script' AND d.source_id = c.script_id_part
            LEFT JOIN script_source_attempts a
              ON a.script_id_part = c.script_id_part
            WHERE d.source_id IS NULL OR a.script_id_part IS NULL
            ORDER BY c.collected_at DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
    items = [dict(row) for row in rows]
    detail_count = 0
    pine_count = 0
    errors: list[str] = []
    if items:
        with ThreadPoolExecutor(max_workers=16) as executor:
            results = list(executor.map(
                lambda item: _backfill_script_item(item, True, True),
                items,
            ))
        for d_count, p_count, item_errors in results:
            detail_count += d_count
            pine_count += p_count
            errors.extend(item_errors)
    after = script_source_completion_status()
    return {
        "selected": len(items),
        "details_processed": detail_count,
        "pine_sources_processed": pine_count,
        "error_count": len(errors),
        "errors": errors[:20],
        "before": before,
        "after": after,
        "at": utcnow(),
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
                candidate_id,source_kind,source_id,name,category,domain,logic,candidate_horizons,status,
                created_at,source_hash,source_version,classification_version,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(candidate_id) DO UPDATE SET
                name=excluded.name,
                category=excluded.category,
                domain=excluded.domain,
                logic=excluded.logic,
                candidate_horizons=excluded.candidate_horizons,
                status=excluded.status,
                source_hash=excluded.source_hash,
                source_version=excluded.source_version,
                classification_version=excluded.classification_version,
                updated_at=excluded.updated_at
            """,
            (
                candidate_id, "TradingViewPineStrategy", script_id_part,
                script.get("name") or candidate_id, category, CATEGORY_DOMAINS[category],
                logic, json.dumps(horizons, ensure_ascii=False), "후보", now,
                source_hash, str(script.get("version") or ""), "category-v2", now,
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


def _collector_state(key: str) -> dict[str, Any]:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM collector_state WHERE collector_key = ?",
            (key,),
        ).fetchone()
        if row is None:
            now = utcnow()
            conn.execute(
                """
                INSERT INTO collector_state (
                    collector_key,cursor_page,total_pages,items_seen,details_seen,last_error,updated_at
                ) VALUES (?,?,?,?,?,?,?)
                """,
                (key, 1, 1, 0, 0, None, now),
            )
            return {
                "collector_key": key,
                "cursor_page": 1,
                "total_pages": 1,
                "items_seen": 0,
                "details_seen": 0,
                "last_error": None,
                "updated_at": now,
            }
    return dict(row)


def list_collector_states() -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM collector_state ORDER BY collector_key"
        ).fetchall()
    return [dict(row) for row in rows]


def _backfill_idea_item(item: dict[str, Any], fetch_details: bool) -> tuple[int, int, list[str]]:
    source_id = str(item.get("idea_id") or "")
    if not source_id:
        return 0, 0, []
    if not fetch_details:
        return 0, 0, []
    try:
        fetch_source_detail("idea", source_id, force=False)
        return 1, 0, []
    except Exception as exc:
        return 0, 0, [f"idea:{source_id}:{type(exc).__name__}:{exc}"]


def _backfill_script_item(
    item: dict[str, Any],
    fetch_details: bool,
    fetch_pine: bool,
) -> tuple[int, int, list[str]]:
    source_id = str(item.get("script_id_part") or "")
    if not source_id:
        return 0, 0, []
    detail_count = 0
    pine_count = 0
    errors: list[str] = []
    if fetch_details:
        try:
            fetch_source_detail("script", source_id, force=False)
            detail_count = 1
        except Exception as exc:
            errors.append(f"script-detail:{source_id}:{type(exc).__name__}:{exc}")
    if fetch_pine:
        try:
            pine = fetch_script_source(source_id, str(item.get("version") or "last"))
            if pine.get("ok"):
                pine_count = 1
        except Exception as exc:
            errors.append(f"script-pine:{source_id}:{type(exc).__name__}:{exc}")
    return detail_count, pine_count, errors


def backfill_tradingview_source(
    kind: str,
    *,
    pages: int = 1,
    fetch_details: bool = True,
    fetch_pine: bool = True,
) -> dict[str, Any]:
    kind_key = kind.strip().lower()
    if kind_key not in {"ideas", "scripts"}:
        raise ValueError(f"unsupported backfill kind: {kind}")
    safe_pages = min(max(int(pages), 1), 25)
    state_key = f"tradingview:{kind_key}"
    state = _collector_state(state_key)
    page = max(1, int(state["cursor_page"]))
    processed_pages: list[int] = []
    item_count = 0
    detail_count = 0
    pine_count = 0
    errors: list[str] = []
    total_pages = max(1, int(state.get("total_pages") or 1))
    cycle_completed = False

    for _ in range(safe_pages):
        current_page = page
        try:
            if kind_key == "ideas":
                payload = collect_ideas(sort="recent", page=current_page, lang="ko")
                items = list(payload.get("items") or [])
                total_pages = max(1, int(payload.get("page_count") or 1))
                if fetch_details and items:
                    with ThreadPoolExecutor(max_workers=16) as executor:
                        results = list(executor.map(
                            lambda item: _backfill_idea_item(item, fetch_details),
                            items,
                        ))
                    for d_count, p_count, item_errors in results:
                        detail_count += d_count
                        pine_count += p_count
                        errors.extend(item_errors)

                item_count += len(items)
                processed_pages.append(current_page)
                if current_page >= total_pages:
                    page = 1
                    cycle_completed = True
                    break
                page = current_page + 1
            else:
                payload = collect_scripts(
                    page=current_page,
                    sort="recent_extended",
                    topic=None,
                    editors_picks=False,
                )
                items = list(payload.get("items") or [])
                has_more = bool(payload.get("has_more"))
                if items and (fetch_details or fetch_pine):
                    with ThreadPoolExecutor(max_workers=16) as executor:
                        results = list(executor.map(
                            lambda item: _backfill_script_item(item, fetch_details, fetch_pine),
                            items,
                        ))
                    for d_count, p_count, item_errors in results:
                        detail_count += d_count
                        pine_count += p_count
                        errors.extend(item_errors)

                item_count += len(items)
                processed_pages.append(current_page)
                if has_more:
                    total_pages = max(total_pages, current_page + 1)
                    page = current_page + 1
                else:
                    total_pages = current_page
                    page = 1
                    cycle_completed = True
                    break
        except Exception as exc:
            errors.append(f"page:{current_page}:{type(exc).__name__}:{exc}")
            page = current_page + 1

    now = utcnow()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO collector_state (
                collector_key,cursor_page,total_pages,items_seen,details_seen,last_error,updated_at
            ) VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(collector_key) DO UPDATE SET
                cursor_page=excluded.cursor_page,
                total_pages=excluded.total_pages,
                items_seen=collector_state.items_seen + excluded.items_seen,
                details_seen=collector_state.details_seen + excluded.details_seen,
                last_error=excluded.last_error,
                updated_at=excluded.updated_at
            """,
            (
                state_key,
                page,
                total_pages,
                item_count,
                detail_count,
                errors[-1] if errors else None,
                now,
            ),
        )

    return {
        "collector": state_key,
        "processed_pages": processed_pages,
        "next_page": page,
        "total_pages": total_pages,
        "cycle_completed": cycle_completed,
        "items_processed": item_count,
        "details_processed": detail_count,
        "pine_sources_processed": pine_count,
        "errors": errors[:20],
        "error_count": len(errors),
        "workers": 16,
        "updated_at": now,
    }


def list_stored_ideas(limit: int = 100) -> list[dict[str, Any]]:
    init_db()
    safe_limit = min(max(limit, 1), 500)
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT idea_id,title,description,author,symbol,exchange,asset_type,direction,interval,
                   created_at,comments_count,likes_count,views_count,chart_url,image_url,
                   is_video,is_education,is_picked,is_hot,collected_at
            FROM community_ideas
            ORDER BY collected_at DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def _category_for(text: str) -> str:
    haystack = text.lower()

    def matches(keyword: str) -> bool:
        word = keyword.lower()
        # Short indicator/ticker tokens must be lexical tokens.  Plain substring
        # matching made "rsi" match the "rsi" inside "version".
        if re.fullmatch(r"[a-z0-9]+", word):
            return re.search(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", haystack) is not None
        return word in haystack

    for category, words in CATEGORY_RULES:
        if any(matches(word) for word in words):
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


def candidate_build_status() -> dict[str, Any]:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total_scripts,
                SUM(CASE WHEN c.candidate_id IS NOT NULL THEN 1 ELSE 0 END) AS candidate_count,
                SUM(
                    CASE WHEN c.candidate_id IS NOT NULL
                              AND c.classification_version = 'category-v2'
                              AND COALESCE(c.source_hash,'') = COALESCE(s.source_hash,'')
                         THEN 1 ELSE 0 END
                ) AS current_count
            FROM community_scripts s0
            LEFT JOIN script_sources s ON s.script_id_part = s0.script_id_part
            LEFT JOIN strategy_candidates c
              ON c.source_kind = 'TradingViewPineStrategy'
             AND c.source_id = s0.script_id_part
            """
        ).fetchone()
    data = dict(row or {})
    total = int(data.get("total_scripts") or 0)
    candidate_count = int(data.get("candidate_count") or 0)
    current = int(data.get("current_count") or 0)
    return {
        "total_scripts": total,
        "candidate_count": candidate_count,
        "current_count": current,
        "remaining": max(0, total - current),
        "classification_version": "category-v2",
    }


def build_pending_strategy_candidates(limit: int = 500) -> dict[str, Any]:
    init_db()
    safe_limit = min(max(int(limit), 1), 5000)
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT s0.*, s.source AS pine_source, s.source_hash AS pine_source_hash
            FROM community_scripts s0
            LEFT JOIN script_sources s ON s.script_id_part = s0.script_id_part
            LEFT JOIN strategy_candidates c
              ON c.source_kind = 'TradingViewPineStrategy'
             AND c.source_id = s0.script_id_part
            WHERE c.candidate_id IS NULL
               OR COALESCE(c.classification_version,'') <> 'category-v2'
               OR COALESCE(c.source_hash,'') <> COALESCE(s.source_hash,'')
            ORDER BY s0.collected_at DESC, s0.script_id_part
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()

    now = utcnow()
    payloads: list[tuple[Any, ...]] = []
    errors: list[dict[str, str]] = []
    for raw in rows:
        try:
            script = dict(raw)
            source_id = str(script["script_id_part"])
            source_text = str(script.get("pine_source") or "")
            source_hash = str(script.get("pine_source_hash") or "")
            classification_text = " ".join([
                str(script.get("name") or ""),
                str(script.get("description") or ""),
                source_text[:20000],
            ])
            category = _category_for(classification_text)
            horizons = list(CATEGORY_HORIZONS[category])
            source_interval = _normalize_interval(str(script.get("interval") or ""))
            if source_interval and source_interval not in horizons:
                horizons.insert(0, source_interval)

            candidate_id = "TVS-" + hashlib.sha1(source_id.encode()).hexdigest()[:10].upper()
            logic = str(script.get("description") or script.get("name") or "").strip()
            if len(logic) > 800:
                logic = logic[:800]
            if source_hash:
                logic = f"{logic}\n[Pine source hash: {source_hash[:16]}]".strip()

            payloads.append(
                (
                    candidate_id,
                    "TradingViewPineStrategy",
                    source_id,
                    script.get("name") or candidate_id,
                    category,
                    CATEGORY_DOMAINS[category],
                    logic,
                    json.dumps(horizons, ensure_ascii=False),
                    "후보",
                    now,
                    source_hash or None,
                    str(script.get("version") or ""),
                    "category-v2",
                    now,
                )
            )
        except Exception as exc:
            errors.append({
                "source_id": str(raw["script_id_part"]),
                "error": f"{type(exc).__name__}: {exc}",
            })

    if payloads:
        with _connect() as conn:
            conn.executemany(
                """
                INSERT INTO strategy_candidates (
                    candidate_id,source_kind,source_id,name,category,domain,logic,candidate_horizons,status,
                    created_at,source_hash,source_version,classification_version,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(candidate_id) DO UPDATE SET
                    name=excluded.name,
                    category=excluded.category,
                    domain=excluded.domain,
                    logic=excluded.logic,
                    candidate_horizons=excluded.candidate_horizons,
                    status=excluded.status,
                    source_hash=excluded.source_hash,
                    source_version=excluded.source_version,
                    classification_version=excluded.classification_version,
                    updated_at=excluded.updated_at
                """,
                payloads,
            )

    return {
        "selected": len(rows),
        "built": len(payloads),
        "error_count": len(errors),
        "errors": errors[:30],
        "status": candidate_build_status(),
        "classification_version": "category-v2",
        "batch_mode": "bulk-read + memory-classify + executemany",
        "at": utcnow(),
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


def _scanner_market_for_agent(plan: dict[str, Any]) -> str | None:
    country = str(plan.get("country") or "").lower()
    market = str(plan.get("market") or "").lower()
    if "한국" in country or "kospi" in market or "kosdaq" in market:
        return "korea"
    if "미국" in country or "nasdaq" in market or "nyse" in market or "미국" in market:
        return "america"
    if "일본" in country or "tse" in market:
        return "japan"
    if "베트남" in country or "vn30" in market or "hose" in market or "hnx" in market:
        return "vietnam"
    if "가상자산" in country or "crypto" in country:
        return "crypto"
    if country == "fx" or "외환" in market or "글로벌" in market and "fx" in country:
        return "forex"
    return None


def _numeric(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        value = row.get(key)
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _market_cap(row: dict[str, Any]) -> float:
    basic = _numeric(row, "market_cap_basic")
    return basic if basic > 0 else _numeric(row, "market_cap_calc")


def _turnover(row: dict[str, Any]) -> float:
    return max(0.0, _numeric(row, "close")) * max(0.0, _numeric(row, "volume"))


def _universe_filter(plan: dict[str, Any], row: dict[str, Any]) -> tuple[bool, str]:
    universe = str(plan.get("universe") or "")
    market = str(plan.get("market") or "").lower()
    country = str(plan.get("country") or "").lower()
    ticker = str(row.get("ticker") or "")
    close = _numeric(row, "close")
    volume = _numeric(row, "volume")
    market_cap = _market_cap(row)
    turnover = _turnover(row)
    asset_type = str(row.get("type") or "").lower()

    # Exact ETF baskets declared by the Agent plan must stay exact.
    if "qqq" in universe.lower() or "spy" in universe.lower() or "smh" in universe.lower():
        allowed = {"QQQ", "SPY", "SMH"}
        symbol = ticker.split(":")[-1].upper()
        return (symbol in allowed, "고정 ETF 바스켓 QQQ/SPY/SMH")

    # U.S. high-liquidity large-cap universe: remove penny stocks and micro/small caps first.
    if ("미국" in country or "nasdaq" in market or "nyse" in market) and "대형주" in universe:
        if close < 5.0:
            return False, "미국 대형주 가격 하한 미달"
        if market_cap < 10_000_000_000:
            return False, "미국 대형주 시가총액 100억달러 하한 미달"
        if turnover < 50_000_000:
            return False, "미국 일 거래대금 5천만달러 하한 미달"
        return True, "미국 고유동성 대형주 조건 통과"

    # Korea large-cap/turnover universe.
    if ("한국" in country or "kospi" in market or "kosdaq" in market) and "대형주" in universe:
        if close < 1_000:
            return False, "한국 대형주 가격 하한 미달"
        if market_cap < 1_000_000_000_000:
            return False, "한국 대형주 시가총액 1조원 하한 미달"
        if turnover < 5_000_000_000:
            return False, "한국 일 거래대금 50억원 하한 미달"
        return True, "한국 거래대금 상위 대형주 조건 통과"

    # Explicit turnover/momentum universes should reject illiquid shells/penny-like names.
    if "거래대금" in universe or "모멘텀" in universe:
        if "한국" in country or "kospi" in market or "kosdaq" in market:
            if close < 1_000 or turnover < 3_000_000_000:
                return False, "한국 거래대금/가격 사전조건 미달"
        elif "미국" in country or "nasdaq" in market or "nyse" in market:
            if close < 3.0 or turnover < 25_000_000:
                return False, "미국 거래대금/가격 사전조건 미달"

    # Common minimums prevent zero-liquidity rows from becoming candidates.
    if close <= 0 or volume <= 0:
        return False, "가격 또는 거래량 없음"
    if asset_type and asset_type not in {"stock", "fund", "dr", "crypto", "forex"}:
        return False, f"지원하지 않는 자산유형 {asset_type}"
    return True, "기본 유동성 조건 통과"


def _prescreen_score(category: str, row: dict[str, Any]) -> tuple[float, str]:
    rel = _numeric(row, "relative_volume_10d_calc")
    rsi = _numeric(row, "RSI", 50.0)
    volatility = _numeric(row, "Volatility.D")
    adx = _numeric(row, "ADX")
    change = _numeric(row, "change")
    recommendation = _numeric(row, "Recommend.All")
    turnover = _turnover(row)
    market_cap = _market_cap(row)

    # Liquidity contributes only after the hard universe filter. Log-scaled turnover
    # prevents penny stocks with huge share volume from dominating the rank.
    import math
    liquidity = min(25.0, max(0.0, math.log10(max(turnover, 1.0)) - 5.0) * 4.0)
    cap_quality = min(12.0, max(0.0, math.log10(max(market_cap, 1.0)) - 8.0) * 2.0)

    if category == "평균회귀":
        score = abs(rsi - 50.0) * 1.15 + min(rel, 5.0) * 3.0 + liquidity + cap_quality
        rationale = f"RSI {rsi:.1f}, 상대거래량 {rel:.2f}, 거래대금 {turnover:,.0f}"
    elif category in {"돌파", "모멘텀"}:
        score = max(min(change, 25.0), -25.0) * 1.1 + min(rel, 6.0) * 4.5 + min(adx, 60.0) * 0.45 + liquidity
        rationale = f"등락률 {change:.2f}%, 상대거래량 {rel:.2f}, ADX {adx:.1f}, 거래대금 {turnover:,.0f}"
    elif category == "추세추종":
        score = min(adx, 60.0) * 0.85 + abs(recommendation) * 22.0 + min(rel, 5.0) * 2.5 + liquidity
        rationale = f"ADX {adx:.1f}, 기술평가 {recommendation:.2f}, 상대거래량 {rel:.2f}, 거래대금 {turnover:,.0f}"
    elif category == "변동성":
        score = min(volatility, 100.0) * 1.0 + min(rel, 5.0) * 3.0 + liquidity + cap_quality
        rationale = f"일변동성 {volatility:.2f}%, 상대거래량 {rel:.2f}, 거래대금 {turnover:,.0f}"
    else:
        score = min(rel, 5.0) * 3.0 + min(adx, 60.0) * 0.35 + liquidity + cap_quality
        rationale = f"상대거래량 {rel:.2f}, ADX {adx:.1f}, 거래대금 {turnover:,.0f}"
    return round(score, 4), rationale

def _explicit_universe_tickers(plan: dict[str, Any]) -> list[str]:
    label = str(plan.get("universe") or "")
    normalized = (
        label.replace("↔", " ")
        .replace("·", " ")
        .replace(",", " ")
        .replace("(", " ")
        .replace(")", " ")
        .replace("[", " ")
        .replace("]", " ")
    )
    tickers: list[str] = []
    for token in normalized.split():
        token = token.strip()
        if ":" not in token:
            continue
        exchange, symbol = token.split(":", 1)
        if not exchange or not symbol:
            continue
        if not exchange.replace("_", "").isalnum():
            continue
        qualified = f"{exchange.upper()}:{symbol.upper()}"
        if qualified not in tickers:
            tickers.append(qualified)
    return tickers


def resolve_agent_universe(agent_id: str, limit: int = 20) -> dict[str, Any]:
    init_db()
    safe_limit = min(max(int(limit), 1), 100)
    with _connect() as conn:
        plan_row = conn.execute(
            "SELECT * FROM agent_plans WHERE agent_id = ?",
            (agent_id,),
        ).fetchone()
        if plan_row is None:
            raise KeyError(agent_id)
        plan = dict(plan_row)
        candidate_row = conn.execute(
            "SELECT category FROM strategy_candidates WHERE candidate_id = ?",
            (plan["candidate_id"],),
        ).fetchone()
    category = str(candidate_row["category"]) if candidate_row is not None else "아이디어 기반"

    if str(plan.get("status") or "").startswith("RETIRED"):
        return {
            "agent_id": agent_id,
            "candidate_id": plan["candidate_id"],
            "resolved": False,
            "reason": f"Agent plan is retired: {plan.get('status')}",
            "items": [],
        }

    explicit_tickers = _explicit_universe_tickers(plan)
    if explicit_tickers:
        now = utcnow()
        selected = [
            {
                "ticker": ticker,
                "name": ticker,
                "exchange": ticker.split(":", 1)[0],
                "prescreen_score": 100.0,
                "rationale": "원본 전략이 명시한 고정 Universe 심볼 — Scanner 랭킹으로 대체하지 않음",
                "rsi": None,
                "adx": None,
                "relative_volume": None,
                "volatility_d": None,
                "change": None,
                "market_cap": None,
                "turnover": None,
            }
            for ticker in explicit_tickers[:safe_limit]
        ]
        with _connect() as conn:
            conn.execute("DELETE FROM agent_universe_members WHERE agent_id = ?", (agent_id,))
            conn.executemany(
                """
                INSERT INTO agent_universe_members (
                    agent_id,ticker,rank_index,prescreen_score,rationale,snapshot_at,resolved_at
                ) VALUES (?,?,?,?,?,?,?)
                """,
                [
                    (
                        agent_id,
                        x["ticker"],
                        rank_index,
                        x["prescreen_score"],
                        x["rationale"],
                        now,
                        now,
                    )
                    for rank_index, x in enumerate(selected, start=1)
                ],
            )
        return {
            "agent_id": agent_id,
            "candidate_id": plan["candidate_id"],
            "category": category,
            "fixed_horizon": plan["fixed_horizon"],
            "resolved": True,
            "method": "EXPLICIT_SOURCE_UNIVERSE",
            "snapshot_at": now,
            "count": len(selected),
            "items": selected,
        }

    scanner_market = _scanner_market_for_agent(plan)
    if scanner_market is None:
        return {
            "agent_id": agent_id,
            "resolved": False,
            "reason": "No TradingView scanner mapping for this market yet.",
            "items": [],
        }

    universe_label = str(plan.get("universe") or "")
    if "대형주" in universe_label:
        sort_by = "market_cap_basic"
    else:
        sort_by = {
            "평균회귀": "volume",
            "돌파": "relative_volume_10d_calc",
            "모멘텀": "relative_volume_10d_calc",
            "추세추종": "ADX",
            "변동성": "Volatility.D",
        }.get(category, "volume")

    market_data = collect_market(
        scanner_market,
        limit=max(100, safe_limit),
        sort_by=sort_by,
        sort_order="desc",
    )
    scored: list[dict[str, Any]] = []
    for row in market_data.get("items", []):
        ticker = str(row.get("ticker") or "")
        if not ticker:
            continue
        allowed, universe_reason = _universe_filter(plan, row)
        if not allowed:
            continue
        score, rationale = _prescreen_score(category, row)
        rationale = universe_reason + " · " + rationale
        scored.append(
            {
                "ticker": ticker,
                "name": row.get("description") or row.get("name"),
                "exchange": row.get("exchange"),
                "prescreen_score": score,
                "rationale": rationale,
                "rsi": row.get("RSI"),
                "adx": row.get("ADX"),
                "relative_volume": row.get("relative_volume_10d_calc"),
                "volatility_d": row.get("Volatility.D"),
                "change": row.get("change"),
                "market_cap": _market_cap(row),
                "turnover": _turnover(row),
            }
        )
    scored.sort(key=lambda x: float(x["prescreen_score"]), reverse=True)
    selected = scored[:safe_limit]
    now = utcnow()
    snapshot_at = str(market_data.get("collected_at") or now)

    with _connect() as conn:
        conn.execute("DELETE FROM agent_universe_members WHERE agent_id = ?", (agent_id,))
        conn.executemany(
            """
            INSERT INTO agent_universe_members (
                agent_id,ticker,rank_index,prescreen_score,rationale,snapshot_at,resolved_at
            ) VALUES (?,?,?,?,?,?,?)
            """,
            [
                (
                    agent_id,
                    x["ticker"],
                    idx,
                    x["prescreen_score"],
                    x["rationale"],
                    snapshot_at,
                    now,
                )
                for idx, x in enumerate(selected, start=1)
            ],
        )

    return {
        "agent_id": agent_id,
        "candidate_id": plan["candidate_id"],
        "category": category,
        "fixed_horizon": plan["fixed_horizon"],
        "scanner_market": scanner_market,
        "resolved": bool(selected),
        "method": "Universe hard filters (market cap/turnover/price) + TradingView quantitative pre-screen; not a backtest performance score",
        "snapshot_at": snapshot_at,
        "count": len(selected),
        "items": selected,
    }


def list_agent_universe(agent_id: str) -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT ticker,rank_index,prescreen_score,rationale,snapshot_at,resolved_at
            FROM agent_universe_members
            WHERE agent_id = ?
            ORDER BY rank_index ASC
            """,
            (agent_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_agent_plan(agent_id: str) -> dict[str, Any] | None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM agent_plans WHERE agent_id = ?",
            (agent_id,),
        ).fetchone()
    return dict(row) if row is not None else None


def set_agent_status(
    agent_id: str,
    status: str,
    *,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    init_db()
    allowed = {
        "RESEARCH",
        "PAPER_CANDIDATE",
        "PAPER",
        "LIVE_CANDIDATE",
        "LIVE",
        "REJECTED_VALIDATION",
        "RETIRED_SOURCE_CONTEXT",
        "RETIRED_DISCOVERY_REJECTED",
    }
    target = str(status or "").strip().upper()
    if target not in allowed:
        raise ValueError(f"unsupported agent status: {status}")
    now = utcnow()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM agent_plans WHERE agent_id = ?",
            (agent_id,),
        ).fetchone()
        if row is None:
            raise KeyError(agent_id)
        current = dict(row)
        from_status = str(current.get("status") or "")
        if from_status != target:
            conn.execute(
                "UPDATE agent_plans SET status = ? WHERE agent_id = ?",
                (target, agent_id),
            )
            event_id = "ASE-" + hashlib.sha1(
                f"{agent_id}|{from_status}|{target}|{now}".encode()
            ).hexdigest()[:16].upper()
            conn.execute(
                """
                INSERT INTO agent_status_history (
                    event_id,agent_id,from_status,to_status,reason,metadata_json,changed_at
                ) VALUES (?,?,?,?,?,?,?)
                """,
                (
                    event_id,
                    agent_id,
                    from_status,
                    target,
                    reason,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    now,
                ),
            )
        row = conn.execute(
            "SELECT * FROM agent_plans WHERE agent_id = ?",
            (agent_id,),
        ).fetchone()
    item = dict(row)
    item["status_changed_at"] = now if from_status != target else None
    return item


def list_agent_status_history(agent_id: str) -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM agent_plans WHERE agent_id = ?",
            (agent_id,),
        ).fetchone()
        if exists is None:
            raise KeyError(agent_id)
        rows = conn.execute(
            """
            SELECT * FROM agent_status_history
            WHERE agent_id = ?
            ORDER BY changed_at DESC
            """,
            (agent_id,),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
        out.append(item)
    return out


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
