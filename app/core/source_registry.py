from __future__ import annotations

import hashlib
import json
import math
import statistics
from typing import Any

DISCOVERY_SCORING_VERSION = "market-fit-v3"

from app.core.tradingview import (
    CATEGORY_MARKETS,
    _connect,
    _normalize_interval,
    _scanner_market_for_agent,
    collect_market,
    init_db,
    list_market_snapshots,
    list_market_universe,
    utcnow,
)


def init_source_registry_db() -> None:
    init_db()
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS strategy_sources (
                registry_source_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                origin_source_id TEXT NOT NULL,
                source_kind TEXT NOT NULL,
                source_name TEXT NOT NULL,
                source_version TEXT,
                source_hash TEXT,
                source_url TEXT,
                source_status TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_strategy_sources_kind_external
                ON strategy_sources(source_kind, source_id);

            CREATE TABLE IF NOT EXISTS horizon_discovery (
                discovery_id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                registry_source_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                origin_source_id TEXT NOT NULL,
                horizon TEXT NOT NULL,
                country TEXT NOT NULL,
                market TEXT NOT NULL,
                universe TEXT NOT NULL,
                scanner_market TEXT,
                fit_score REAL NOT NULL,
                market_score REAL NOT NULL,
                horizon_score REAL NOT NULL,
                source_score REAL NOT NULL,
                status TEXT NOT NULL,
                rationale TEXT NOT NULL,
                evaluated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_horizon_discovery_candidate
                ON horizon_discovery(candidate_id, fit_score DESC);

            CREATE TABLE IF NOT EXISTS agent_discovery_links (
                agent_id TEXT PRIMARY KEY,
                discovery_id TEXT NOT NULL,
                candidate_id TEXT NOT NULL,
                registry_source_id TEXT NOT NULL,
                origin_source_id TEXT NOT NULL,
                fit_score REAL NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        migrations = [
            ("horizon_discovery", "run_id", "TEXT"),
            ("horizon_discovery", "target_score", "REAL NOT NULL DEFAULT 0"),
            ("horizon_discovery", "is_current", "INTEGER NOT NULL DEFAULT 1"),
            ("horizon_discovery", "scoring_version", "TEXT"),
        ]
        for table, column, definition in migrations:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            except Exception:
                pass


def _registry_id(source_kind: str, source_id: str) -> str:
    prefix = {
        "TradingViewIdea": "TVI",
        "TradingViewPineStrategy": "TVS",
        "GitHub": "GH",
        "Paper": "PAPER",
        "AIResearch": "AI",
    }.get(source_kind, "SRC")
    return f"{prefix}:{source_id}"


def _upsert_source(
    *,
    source_kind: str,
    source_id: str,
    name: str,
    version: str | None = None,
    source_hash: str | None = None,
    source_url: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    init_source_registry_db()
    registry_source_id = _registry_id(source_kind, source_id)
    now = utcnow()
    with _connect() as conn:
        existing = conn.execute(
            "SELECT created_at FROM strategy_sources WHERE registry_source_id = ?",
            (registry_source_id,),
        ).fetchone()
        created_at = str(existing["created_at"]) if existing is not None else now
        conn.execute(
            """
            INSERT INTO strategy_sources (
                registry_source_id,source_id,origin_source_id,source_kind,source_name,
                source_version,source_hash,source_url,source_status,metadata_json,
                created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(registry_source_id) DO UPDATE SET
                source_name=excluded.source_name,
                source_version=excluded.source_version,
                source_hash=excluded.source_hash,
                source_url=excluded.source_url,
                source_status=excluded.source_status,
                metadata_json=excluded.metadata_json,
                updated_at=excluded.updated_at
            """,
            (
                registry_source_id,
                source_id,
                registry_source_id,
                source_kind,
                name or registry_source_id,
                version,
                source_hash,
                source_url,
                "ACTIVE",
                json.dumps(metadata or {}, ensure_ascii=False),
                created_at,
                now,
            ),
        )
    return {
        "registry_source_id": registry_source_id,
        "source_id": source_id,
        "origin_source_id": registry_source_id,
        "source_kind": source_kind,
        "source_name": name or registry_source_id,
        "source_version": version,
        "source_hash": source_hash,
        "source_url": source_url,
        "source_status": "ACTIVE",
        "created_at": created_at,
        "updated_at": now,
    }


def sync_tradingview_sources(limit: int = 2000) -> dict[str, Any]:
    init_source_registry_db()
    safe_limit = min(max(int(limit), 1), 10000)
    with _connect() as conn:
        ideas = conn.execute(
            """
            SELECT idea_id,title,author,symbol,exchange,asset_type,interval,chart_url,collected_at
            FROM community_ideas
            ORDER BY collected_at DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
        scripts = conn.execute(
            """
            SELECT s.script_id_part,s.name,s.author,s.version,s.interval,s.symbol,s.chart_url,s.collected_at,
                   p.source_hash,p.pine_version,p.kind
            FROM community_scripts s
            LEFT JOIN script_sources p ON p.script_id_part = s.script_id_part
            ORDER BY s.collected_at DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()

    idea_count = 0
    script_count = 0
    for row in ideas:
        item = dict(row)
        _upsert_source(
            source_kind="TradingViewIdea",
            source_id=str(item["idea_id"]),
            name=str(item.get("title") or item["idea_id"]),
            source_url=item.get("chart_url"),
            metadata={
                "author": item.get("author"),
                "symbol": item.get("symbol"),
                "exchange": item.get("exchange"),
                "asset_type": item.get("asset_type"),
                "interval": item.get("interval"),
                "collected_at": item.get("collected_at"),
            },
        )
        idea_count += 1

    for row in scripts:
        item = dict(row)
        _upsert_source(
            source_kind="TradingViewPineStrategy",
            source_id=str(item["script_id_part"]),
            name=str(item.get("name") or item["script_id_part"]),
            version=str(item.get("version") or "") or None,
            source_hash=item.get("source_hash"),
            source_url=item.get("chart_url"),
            metadata={
                "author": item.get("author"),
                "interval": item.get("interval"),
                "symbol": item.get("symbol"),
                "pine_version": item.get("pine_version"),
                "pine_kind": item.get("kind"),
                "collected_at": item.get("collected_at"),
            },
        )
        script_count += 1

    return {
        "synced": idea_count + script_count,
        "ideas": idea_count,
        "pine_strategies": script_count,
        "at": utcnow(),
    }


def list_sources(
    *,
    source_kind: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    init_source_registry_db()
    safe_limit = min(max(int(limit), 1), 2000)
    with _connect() as conn:
        if source_kind:
            rows = conn.execute(
                """
                SELECT * FROM strategy_sources
                WHERE source_kind = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (source_kind, safe_limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM strategy_sources ORDER BY updated_at DESC LIMIT ?",
                (safe_limit,),
            ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
        result.append(item)
    return result


def get_source(registry_source_id: str) -> dict[str, Any] | None:
    init_source_registry_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM strategy_sources WHERE registry_source_id = ?",
            (registry_source_id,),
        ).fetchone()
    if row is None:
        return None
    item = dict(row)
    item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
    return item


def _candidate(candidate_id: str) -> dict[str, Any]:
    init_source_registry_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM strategy_candidates WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
    if row is None:
        raise KeyError(candidate_id)
    item = dict(row)
    item["candidate_horizons"] = json.loads(item["candidate_horizons"])
    return item


def _ensure_candidate_source(candidate: dict[str, Any]) -> dict[str, Any]:
    registry_source_id = _registry_id(str(candidate["source_kind"]), str(candidate["source_id"]))
    source = get_source(registry_source_id)
    if source is not None:
        return source
    sync_tradingview_sources(limit=5000)
    source = get_source(registry_source_id)
    if source is not None:
        return source
    return _upsert_source(
        source_kind=str(candidate["source_kind"]),
        source_id=str(candidate["source_id"]),
        name=str(candidate["name"]),
        metadata={"candidate_id": candidate["candidate_id"]},
    )


def _number(row: dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        if key not in row:
            continue
        value = row.get(key)
        if value is None:
            continue
        try:
            n = float(value)
        except (TypeError, ValueError, OverflowError):
            continue
        if math.isfinite(n):
            return n
    return default


def _median(values: list[float], default: float = 0.0) -> float:
    clean = [float(x) for x in values if math.isfinite(float(x))]
    return float(statistics.median(clean)) if clean else default


def _scanner_for_target(target: dict[str, Any]) -> str | None:
    explicit = str(target.get("scanner_market") or "").strip().lower()
    return explicit or _scanner_market_for_agent(target)


def _market_rows(
    scanner_market: str,
    category: str,
    *,
    use_live: bool = True,
) -> tuple[list[dict[str, Any]], str]:
    sort_by = {
        "평균회귀": "volume",
        "돌파": "relative_volume_10d_calc",
        "모멘텀": "relative_volume_10d_calc",
        "추세추종": "ADX",
        "변동성": "Volatility.D",
        "크립토": "volume",
    }.get(category, "volume")

    # Prefer a completed whole-market TradingView scan. Horizon Discovery should
    # judge market state from the same universe that Agent Factory will use,
    # not from a transient top-60 request.
    try:
        stored_full = list_market_universe(
            scanner_market,
            limit=1000,
            offset=0,
            sort_by=sort_by,
            sort_order="desc",
        )
        rows = list(stored_full.get("items") or [])
        if rows:
            stamp = str(rows[0].get("collected_at") or utcnow())
            return rows, stamp
    except Exception:
        pass

    if use_live:
        try:
            live = collect_market(scanner_market, limit=100, sort_by=sort_by, sort_order="desc")
            return list(live.get("items") or []), str(live.get("collected_at") or utcnow())
        except Exception:
            pass

    stored = list_market_snapshots(scanner_market, limit=100, latest_only=True)
    return stored, str(stored[0].get("collected_at")) if stored else utcnow()


def _feature_values(
    rows: list[dict[str, Any]],
    *keys: str,
    min_value: float | None = None,
    max_value: float | None = None,
    reject_zero_dominant: bool = False,
) -> list[float]:
    values: list[float] = []
    for row in rows:
        value: float | None = None
        for key in keys:
            if key not in row or row.get(key) is None:
                continue
            try:
                candidate = float(row.get(key))
            except (TypeError, ValueError, OverflowError):
                continue
            if not math.isfinite(candidate):
                continue
            if min_value is not None and candidate < min_value:
                continue
            if max_value is not None and candidate > max_value:
                continue
            value = candidate
            break
        if value is not None:
            values.append(value)

    if reject_zero_dominant and values:
        zero_ratio = sum(1 for x in values if abs(x) < 1e-12) / len(values)
        if zero_ratio >= 0.80:
            return []
    return values


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _market_fit(category: str, rows: list[dict[str, Any]]) -> tuple[float, str]:
    if not rows:
        return 0.0, "시장 스냅샷 없음"

    rel_values = _feature_values(rows, "relative_volume_10d_calc", "relative_volume", min_value=0.0, max_value=100.0)
    adx_values = _feature_values(rows, "ADX", "adx", min_value=0.0, max_value=100.0, reject_zero_dominant=True)
    vol_values = _feature_values(rows, "Volatility.D", "volatility_d", min_value=0.0, max_value=200.0)
    rsi_values = _feature_values(rows, "RSI", "rsi", min_value=0.0, max_value=100.0, reject_zero_dominant=True)
    change_values = _feature_values(rows, "change", min_value=-1000.0, max_value=1000.0)
    rec_values = _feature_values(rows, "Recommend.All", "recommendation", min_value=-1.0, max_value=1.0)

    rel = _median(rel_values, 1.0)
    adx = _median(adx_values, 20.0)
    vol = _median(vol_values, 1.0)
    rsi_dev = _median([abs(x - 50.0) for x in rsi_values], 8.0)
    change = _median([abs(x) for x in change_values], 0.5)
    rec = _median([abs(x) for x in rec_values], 0.0)

    liquid_ratio = sum(
        1 for r in rows
        if _number(r, "volume") > 0 and _number(r, "close") > 0
    ) / max(len(rows), 1)

    feature_sets = {
        "relative_volume": rel_values,
        "adx": adx_values,
        "volatility": vol_values,
        "rsi": rsi_values,
        "change": change_values,
        "recommendation": rec_values,
    }
    category_features = {
        "평균회귀": ("relative_volume", "adx", "rsi", "change"),
        "돌파": ("relative_volume", "adx", "change"),
        "모멘텀": ("relative_volume", "adx", "change", "recommendation"),
        "추세추종": ("relative_volume", "adx", "change", "recommendation"),
        "변동성": ("relative_volume", "volatility", "change"),
        "크립토": ("relative_volume", "adx", "volatility", "change"),
    }.get(category, ("relative_volume", "adx", "volatility", "change"))
    feature_coverage = sum(1 for name in category_features if feature_sets[name]) / max(len(category_features), 1)

    if category == "평균회귀":
        raw_score = (
            _clamp01(rsi_dev / 25.0) * 28.0
            + _clamp01((32.0 - adx) / 22.0) * 18.0
            + _clamp01((rel - 0.7) / 1.8) * 14.0
            + _clamp01(change / 5.0) * 10.0
            + liquid_ratio * 15.0
        )
    elif category in {"돌파", "모멘텀"}:
        raw_score = (
            _clamp01((rel - 0.8) / 2.2) * 24.0
            + _clamp01((adx - 15.0) / 30.0) * 24.0
            + _clamp01(change / 7.0) * 17.0
            + _clamp01(rec) * 8.0
            + liquid_ratio * 15.0
        )
    elif category == "추세추종":
        raw_score = (
            _clamp01((adx - 15.0) / 35.0) * 28.0
            + _clamp01(rec) * 18.0
            + _clamp01((rel - 0.7) / 2.0) * 12.0
            + _clamp01(change / 8.0) * 10.0
            + liquid_ratio * 15.0
        )
    elif category == "변동성":
        raw_score = (
            _clamp01(vol / 8.0) * 28.0
            + _clamp01((rel - 0.7) / 2.0) * 15.0
            + _clamp01(change / 8.0) * 20.0
            + liquid_ratio * 15.0
        )
    elif category == "크립토":
        raw_score = (
            _clamp01(vol / 10.0) * 22.0
            + _clamp01((rel - 0.7) / 2.3) * 18.0
            + _clamp01((adx - 12.0) / 35.0) * 18.0
            + _clamp01(change / 10.0) * 12.0
            + liquid_ratio * 15.0
        )
    else:
        raw_score = (
            _clamp01((rel - 0.7) / 2.0) * 18.0
            + _clamp01((adx - 12.0) / 35.0) * 20.0
            + _clamp01(vol / 10.0) * 18.0
            + _clamp01(change / 8.0) * 12.0
            + liquid_ratio * 15.0
        )

    # Missing/placeholder indicators must not make a market look perfect.
    coverage_factor = 0.60 + 0.40 * feature_coverage
    score = round(max(0.0, min(85.0, raw_score * coverage_factor)), 2)
    rationale = (
        f"상대거래량 {rel:.2f}, ADX {adx:.1f}, 변동성 {vol:.2f}, "
        f"RSI 이격 {rsi_dev:.1f}, 절대등락 {change:.2f}, 유효유동성 {liquid_ratio:.0%}, "
        f"핵심피처 충족 {feature_coverage:.0%}"
    )
    return score, rationale


def _horizon_score(horizon: str, candidate_horizons: list[str], source_interval: str | None) -> float:
    try:
        rank = candidate_horizons.index(horizon)
    except ValueError:
        rank = len(candidate_horizons)
    score = max(58.0, 94.0 - rank * 8.0)
    if source_interval and horizon == source_interval:
        score += 6.0
    return min(100.0, score)


def _source_score(source: dict[str, Any]) -> float:
    kind = str(source.get("source_kind") or "")
    if kind == "TradingViewPineStrategy":
        return 96.0 if source.get("source_hash") else 80.0
    if kind == "TradingViewIdea":
        metadata = source.get("metadata") or {}
        return 72.0 if metadata.get("symbol") else 64.0
    return 70.0


def _source_interval(source: dict[str, Any]) -> str | None:
    metadata = source.get("metadata") or {}
    return _normalize_interval(str(metadata.get("interval") or ""))


def _source_aware_targets(
    candidate: dict[str, Any],
    source: dict[str, Any],
    *,
    max_markets: int,
) -> tuple[list[dict[str, Any]], str]:
    metadata = source.get("metadata") or {}
    text = " ".join(
        str(x or "")
        for x in [
            candidate.get("name"),
            candidate.get("logic"),
            source.get("source_name"),
            metadata.get("symbol"),
            metadata.get("exchange"),
            metadata.get("asset_type"),
        ]
    ).lower()

    # Explicit source context outranks generic category templates.  This prevents
    # a VN30 basis strategy, for example, from being sprayed across KOSPI/NASDAQ
    # merely because both are classified as mean reversion.
    if any(token in text for token in ("vn30", "vietnam", "viet nam", "베트남", "hose:", "hnx:")):
        return ([{
            "country": "베트남",
            "market": "VN30 선물 ↔ HOSE VN30",
            "universe": "HNX:VN301! ↔ HOSE:VN30 베이시스",
            "scanner_market": "vietnam",
            "target_score": 100.0,
            "target_reason": "원본 전략에 VN30/Vietnam/HNX/HOSE 시장 문맥이 명시됨",
        }], "SOURCE_SPECIFIC")

    if any(token in text for token in ("kospi", "kosdaq", "krx", "한국 주식", "korea stock")):
        market = "KOSDAQ" if "kosdaq" in text else "KOSPI"
        return ([{
            "country": "한국",
            "market": market,
            "universe": "원본 전략 명시 한국 시장",
            "scanner_market": "korea",
            "target_score": 96.0,
            "target_reason": "원본 전략에 한국/KRX/KOSPI/KOSDAQ 문맥이 명시됨",
        }], "SOURCE_SPECIFIC")

    if any(token in text for token in ("nikkei", "topix", "tse", "japan stock", "일본 주식")):
        return ([{
            "country": "일본",
            "market": "TSE",
            "universe": "원본 전략 명시 일본 시장",
            "scanner_market": "japan",
            "target_score": 96.0,
            "target_reason": "원본 전략에 일본/TSE/Nikkei/TOPIX 문맥이 명시됨",
        }], "SOURCE_SPECIFIC")

    if any(token in text for token in ("nasdaq", "nyse", "s&p 500", "sp500", "us stocks", "u.s. stocks")):
        return ([{
            "country": "미국",
            "market": "NASDAQ / NYSE",
            "universe": "원본 전략 명시 미국 시장",
            "scanner_market": "america",
            "target_score": 96.0,
            "target_reason": "원본 전략에 미국/NASDAQ/NYSE/S&P 시장 문맥이 명시됨",
        }], "SOURCE_SPECIFIC")

    crypto_tokens = (
        "bitcoin", "btc", "ethereum", "ethus", "crypto", "cryptocurrency",
        "binance:", "coinbase:", "bitstamp:", "bitfinex:", "bybit:", "okx:", "gate:",
    )
    if any(token in text for token in crypto_tokens):
        explicit_symbol = str(metadata.get("symbol") or "").strip()
        universe = explicit_symbol if ":" in explicit_symbol else "원본 전략 명시 크립토 자산군"
        return ([{
            "country": "가상자산",
            "market": "글로벌 크립토",
            "universe": universe,
            "scanner_market": "crypto",
            "target_score": 98.0 if explicit_symbol else 94.0,
            "target_reason": "원본 전략에 크립토 거래소/심볼 문맥이 명시됨",
        }], "SOURCE_SPECIFIC")

    fx_tokens = (
        "eurusd", "usdjpy", "gbpusd", "audusd", "usdchf", "usdcad",
        "forex", "foreign exchange", "fx pair",
    )
    if any(token in text for token in fx_tokens):
        return ([{
            "country": "FX",
            "market": "글로벌 외환",
            "universe": "원본 전략 명시 FX 통화쌍",
            "scanner_market": "forex",
            "target_score": 94.0,
            "target_reason": "원본 전략에 FX/통화쌍 문맥이 명시됨",
        }], "SOURCE_SPECIFIC")

    category = str(candidate.get("category") or "아이디어 기반")
    generic = CATEGORY_MARKETS.get(category, CATEGORY_MARKETS["아이디어 기반"])[:max(1, int(max_markets))]
    return ([
        {
            **target,
            "target_score": 62.0,
            "target_reason": "원본에 특정 시장이 없어 전략 카테고리 기본 시장 후보 사용",
        }
        for target in generic
    ], "CATEGORY_FALLBACK")


def discover_candidate_horizons(
    candidate_id: str,
    *,
    max_markets: int = 3,
    use_live_market: bool = True,
    market_cache: dict[tuple[str, str, bool], tuple[list[dict[str, Any]], str]] | None = None,
) -> dict[str, Any]:
    init_source_registry_db()
    candidate = _candidate(candidate_id)
    source = _ensure_candidate_source(candidate)
    category = str(candidate["category"])
    horizons = [str(x) for x in candidate["candidate_horizons"]]
    markets, match_mode = _source_aware_targets(candidate, source, max_markets=max_markets)
    source_interval = _source_interval(source)
    source_score = _source_score(source)
    evaluated_at = utcnow()
    run_id = "HDR-" + hashlib.sha1(f"{candidate_id}|{evaluated_at}".encode()).hexdigest()[:14].upper()
    evaluations: list[dict[str, Any]] = []

    for target in markets:
        scanner_market = _scanner_for_target(target)
        rows: list[dict[str, Any]] = []
        snapshot_at = evaluated_at
        if scanner_market:
            cache_key = (scanner_market, category, use_live_market)
            if market_cache is not None and cache_key in market_cache:
                rows, snapshot_at = market_cache[cache_key]
            else:
                rows, snapshot_at = _market_rows(scanner_market, category, use_live=use_live_market)
                if market_cache is not None:
                    market_cache[cache_key] = (rows, snapshot_at)
        market_score, market_rationale = _market_fit(category, rows)
        if not rows and match_mode == "SOURCE_SPECIFIC":
            market_score = 50.0
            market_rationale = "원본 시장은 명확하나 실시간 Scanner 표본이 없어 시장상태 점수는 중립값 50으로 보류"
        target_score = float(target.get("target_score") or 0.0)

        for horizon in horizons:
            horizon_score = _horizon_score(horizon, horizons, source_interval)
            fit_score = round(
                market_score * 0.45
                + horizon_score * 0.25
                + source_score * 0.10
                + target_score * 0.20,
                2,
            )
            if fit_score >= 72:
                status = "DISCOVERY_PASS"
            elif fit_score >= 58:
                status = "REVIEW"
            else:
                status = "REJECT"

            identity = "|".join([
                run_id,
                candidate_id,
                str(source["origin_source_id"]),
                horizon,
                str(target["country"]),
                str(target["market"]),
                str(target["universe"]),
            ])
            discovery_id = "HD-" + hashlib.sha1(identity.encode()).hexdigest()[:14].upper()
            rationale = (
                f"{target.get('target_reason')} · {market_rationale} · "
                f"target {target_score:.1f} · horizon {horizon_score:.1f} · "
                f"source {source_score:.1f} · snapshot {snapshot_at}"
            )
            item = {
                "discovery_id": discovery_id,
                "run_id": run_id,
                "candidate_id": candidate_id,
                "registry_source_id": source["registry_source_id"],
                "source_id": source["source_id"],
                "origin_source_id": source["origin_source_id"],
                "horizon": horizon,
                "country": target["country"],
                "market": target["market"],
                "universe": target["universe"],
                "scanner_market": scanner_market,
                "fit_score": fit_score,
                "market_score": market_score,
                "horizon_score": horizon_score,
                "source_score": source_score,
                "target_score": target_score,
                "status": status,
                "rationale": rationale,
                "evaluated_at": evaluated_at,
                "is_current": 1,
                "scoring_version": DISCOVERY_SCORING_VERSION,
            }
            evaluations.append(item)

    evaluations.sort(key=lambda x: float(x["fit_score"]), reverse=True)
    current_keys = {
        (str(x["horizon"]), str(x["country"]), str(x["market"]), str(x["universe"]))
        for x in evaluations
    }
    score_by_key = {
        (str(x["horizon"]), str(x["country"]), str(x["market"]), str(x["universe"])): float(x["fit_score"])
        for x in evaluations
    }

    with _connect() as conn:
        conn.execute(
            "UPDATE horizon_discovery SET is_current = 0 WHERE candidate_id = ? AND is_current = 1",
            (candidate_id,),
        )
        conn.executemany(
            """
            INSERT INTO horizon_discovery (
                discovery_id,run_id,candidate_id,registry_source_id,source_id,origin_source_id,
                horizon,country,market,universe,scanner_market,fit_score,market_score,
                horizon_score,source_score,target_score,status,rationale,evaluated_at,is_current,scoring_version
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            [
                (
                    x["discovery_id"], x["run_id"], x["candidate_id"], x["registry_source_id"],
                    x["source_id"], x["origin_source_id"], x["horizon"], x["country"],
                    x["market"], x["universe"], x["scanner_market"], x["fit_score"],
                    x["market_score"], x["horizon_score"], x["source_score"], x["target_score"],
                    x["status"], x["rationale"], x["evaluated_at"], 1, x["scoring_version"],
                )
                for x in evaluations
            ],
        )

        # Keep audit history but retire only pre-research plans whose source/market
        # premise is no longer present in the current source-aware discovery run.
        old_agents = conn.execute(
            """
            SELECT p.agent_id,p.fixed_horizon,p.country,p.market,p.universe,p.status
            FROM agent_plans p
            WHERE p.candidate_id = ?
            """,
            (candidate_id,),
        ).fetchall()
        for row in old_agents:
            if str(row["status"]) != "RESEARCH":
                continue
            key = (
                str(row["fixed_horizon"]),
                str(row["country"]),
                str(row["market"]),
                str(row["universe"]),
            )
            if key not in current_keys:
                conn.execute(
                    "UPDATE agent_plans SET status = 'RETIRED_SOURCE_CONTEXT' WHERE agent_id = ?",
                    (row["agent_id"],),
                )
            elif score_by_key.get(key, 0.0) < 72.0:
                conn.execute(
                    "UPDATE agent_plans SET status = 'RETIRED_DISCOVERY_REJECTED' WHERE agent_id = ?",
                    (row["agent_id"],),
                )

    return {
        "candidate_id": candidate_id,
        "run_id": run_id,
        "source": source,
        "category": category,
        "market_match_mode": match_mode,
        "engine": "Horizon Discovery prescreen v3 source-aware + data-quality guard",
        "note": "적합도는 백테스트 수익률이 아니라 원본 전략 시장문맥·고정기간·현재 시장상태의 사전 적합도입니다.",
        "count": len(evaluations),
        "items": evaluations,
        "evaluated_at": evaluated_at,
        "scoring_version": DISCOVERY_SCORING_VERSION,
    }


def discovery_queue_status() -> dict[str, Any]:
    init_source_registry_db()
    with _connect() as conn:
        total = int(conn.execute(
            "SELECT COUNT(*) FROM strategy_candidates WHERE source_kind = 'TradingViewPineStrategy'"
        ).fetchone()[0])
        discovered = int(conn.execute(
            """
            SELECT COUNT(DISTINCT d.candidate_id)
            FROM horizon_discovery d
            JOIN strategy_candidates c ON c.candidate_id = d.candidate_id
            WHERE d.is_current = 1
              AND COALESCE(d.scoring_version,'') = ?
              AND c.source_kind = 'TradingViewPineStrategy'
            """,
            (DISCOVERY_SCORING_VERSION,),
        ).fetchone()[0])
    return {
        "total_candidates": total,
        "discovered_candidates": discovered,
        "remaining": max(0, total - discovered),
        "scoring_version": DISCOVERY_SCORING_VERSION,
    }


def batch_discover_pending_candidates(
    *,
    limit: int = 100,
    max_markets: int = 3,
) -> dict[str, Any]:
    init_source_registry_db()
    safe_limit = min(max(int(limit), 1), 1000)
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT c.candidate_id, c.updated_at, MAX(d.evaluated_at) AS last_discovery
            FROM strategy_candidates c
            LEFT JOIN horizon_discovery d
              ON d.candidate_id = c.candidate_id
             AND d.is_current = 1
             AND COALESCE(d.scoring_version,'') = ?
            WHERE c.source_kind = 'TradingViewPineStrategy'
            GROUP BY c.candidate_id, c.updated_at
            HAVING last_discovery IS NULL
                OR COALESCE(c.updated_at,'') > COALESCE(last_discovery,'')
            ORDER BY COALESCE(c.updated_at,c.created_at) DESC, c.candidate_id
            LIMIT ?
            """,
            (DISCOVERY_SCORING_VERSION, safe_limit),
        ).fetchall()

    processed = 0
    combinations = 0
    market_cache: dict[tuple[str, str, bool], tuple[list[dict[str, Any]], str]] = {}
    pass_combinations = 0
    errors: list[dict[str, str]] = []
    for row in rows:
        candidate_id = str(row["candidate_id"])
        try:
            result = discover_candidate_horizons(
                candidate_id,
                max_markets=max_markets,
                use_live_market=False,
                market_cache=market_cache,
            )
            processed += 1
            combinations += int(result.get("count") or 0)
            pass_combinations += sum(
                1 for item in result.get("items") or []
                if str(item.get("status")) == "DISCOVERY_PASS"
            )
        except Exception as exc:
            errors.append({
                "candidate_id": candidate_id,
                "error": f"{type(exc).__name__}: {exc}",
            })

    return {
        "selected": len(rows),
        "processed": processed,
        "combinations": combinations,
        "discovery_pass_combinations": pass_combinations,
        "error_count": len(errors),
        "errors": errors[:30],
        "queue": discovery_queue_status(),
        "market_data_mode": "stored_latest_snapshot",
        "market_cache_keys": len(market_cache),
        "at": utcnow(),
    }


def discovery_leaderboard(
    *,
    limit: int = 100,
    min_score: float = 0.0,
) -> list[dict[str, Any]]:
    init_source_registry_db()
    safe_limit = min(max(int(limit), 1), 1000)
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT
                d.discovery_id,d.run_id,d.candidate_id,c.name,c.category,c.domain,
                d.registry_source_id,d.source_id,d.origin_source_id,
                d.horizon,d.country,d.market,d.universe,d.scanner_market,
                d.fit_score,d.market_score,d.horizon_score,d.source_score,d.target_score,
                d.status,d.rationale,d.evaluated_at
            FROM horizon_discovery d
            JOIN strategy_candidates c ON c.candidate_id = d.candidate_id
            WHERE d.is_current = 1
              AND COALESCE(d.scoring_version,'') = ?
              AND d.fit_score >= ?
            ORDER BY d.fit_score DESC, d.source_score DESC, d.evaluated_at DESC
            LIMIT ?
            """,
            (DISCOVERY_SCORING_VERSION, float(min_score), safe_limit),
        ).fetchall()
    return [dict(row) for row in rows]


def list_candidate_discovery(
    candidate_id: str,
    *,
    current_only: bool = True,
) -> list[dict[str, Any]]:
    init_source_registry_db()
    with _connect() as conn:
        if current_only:
            rows = conn.execute(
                """
                SELECT * FROM horizon_discovery
                WHERE candidate_id = ? AND is_current = 1
                  AND COALESCE(scoring_version,'') = ?
                ORDER BY fit_score DESC, market ASC, horizon ASC
                """,
                (candidate_id, DISCOVERY_SCORING_VERSION),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM horizon_discovery
                WHERE candidate_id = ?
                ORDER BY evaluated_at DESC, fit_score DESC
                """,
                (candidate_id,),
            ).fetchall()
    return [dict(row) for row in rows]


def create_agents_from_discovery(
    candidate_id: str,
    *,
    min_score: float = 72.0,
    max_agents: int = 12,
) -> dict[str, Any]:
    init_source_registry_db()
    existing = list_candidate_discovery(candidate_id)
    if not existing:
        discover_candidate_horizons(candidate_id)
        existing = list_candidate_discovery(candidate_id)

    selected = [
        x for x in existing
        if float(x["fit_score"]) >= float(min_score) and str(x["status"]) == "DISCOVERY_PASS"
    ][: min(max(int(max_agents), 1), 100)]

    created: list[dict[str, Any]] = []
    now = utcnow()
    with _connect() as conn:
        for x in selected:
            identity = "|".join([
                str(x["origin_source_id"]),
                candidate_id,
                str(x["horizon"]),
                str(x["country"]),
                str(x["market"]),
                str(x["universe"]),
            ])
            agent_id = "A-HD-" + hashlib.sha1(identity.encode()).hexdigest()[:14].upper()
            conn.execute(
                """
                INSERT OR IGNORE INTO agent_plans (
                    agent_id,candidate_id,source_id,fixed_horizon,country,market,universe,status,created_at
                ) VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    agent_id,
                    candidate_id,
                    x["source_id"],
                    x["horizon"],
                    x["country"],
                    x["market"],
                    x["universe"],
                    "RESEARCH",
                    now,
                ),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO agent_discovery_links (
                    agent_id,discovery_id,candidate_id,registry_source_id,origin_source_id,fit_score,created_at
                ) VALUES (?,?,?,?,?,?,?)
                """,
                (
                    agent_id,
                    x["discovery_id"],
                    candidate_id,
                    x["registry_source_id"],
                    x["origin_source_id"],
                    x["fit_score"],
                    now,
                ),
            )
            created.append({
                "agent_id": agent_id,
                "candidate_id": candidate_id,
                "registry_source_id": x["registry_source_id"],
                "source_id": x["source_id"],
                "origin_source_id": x["origin_source_id"],
                "origin_source_immutable": True,
                "fixed_horizon": x["horizon"],
                "fixed_horizon_immutable": True,
                "country": x["country"],
                "market": x["market"],
                "universe": x["universe"],
                "discovery_fit_score": x["fit_score"],
                "status": "RESEARCH",
            })

    return {
        "candidate_id": candidate_id,
        "min_score": float(min_score),
        "count": len(created),
        "invariant": "Agent = immutable Origin Source × immutable Fixed Horizon × Market Universe",
        "items": created,
    }
