"""Self-authored synthetic inputs in a dedicated local review database only."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def seed(directory: Path) -> None:
    database = Path(os.environ["AUTONOMOUS_DB_PATH"]).resolve()
    if os.environ.get("INVESTOR_LOCAL_REVIEW") != "1" or database.parent != directory.resolve():
        raise RuntimeError("review seeding is restricted to its dedicated local database")
    from app.core import tradingview as source
    from app.core.source_registry import init_source_registry_db, sync_tradingview_sources
    from app.core.quant_lab import init_db as quant_init
    from app.core.macro_data import init_macro_db

    source.init_db()
    init_source_registry_db()
    quant_init()
    init_macro_db()
    at = source.utcnow()
    idea = source.normalize_idea({
        "id": "LOCAL-REVIEW-IDEA", "name": "SYNTHETIC · 이동평균 전략 검증 자료",
        "description": "기존 수집·전략·에이전트 화면의 연결을 확인하기 위한 자체 작성 테스트 자료입니다. 실제 투자 아이디어가 아닙니다.",
        "user": {"username": "Local review fixture"}, "created_at": at,
        "symbol": {"name": "SYNTHETIC", "exchange": "TEST", "type": "stock", "interval": "1D"},
        "url": "https://example.invalid/local-review/idea",
    })
    source.store_ideas([idea])
    pine = "//@version=6\nstrategy('SYNTHETIC review only')\nfast = ta.sma(close, 3)\nslow = ta.sma(close, 5)\nif ta.crossover(fast, slow)\n    strategy.entry('long', strategy.long)\nif ta.crossunder(fast, slow)\n    strategy.close('long')\n"
    scripts = [source.normalize_script({
        "script_id_part": "LOCAL-REVIEW-PINE", "id": "LOCAL-REVIEW-PINE",
        "name": "SYNTHETIC · 이동평균 교차 테스트", "user": {"username": "Local review fixture"},
        "script_type": "strategy", "script_access": 1, "version": "1", "created_at": at,
        "description": "자체 작성한 검증용 Pine입니다. 시장 성과나 검증된 투자 전략을 의미하지 않습니다.",
        "chart_url": "https://example.invalid/local-review/pine", "symbol": {"name": "SYNTHETIC", "interval": "1D"},
    })]
    source.store_scripts(scripts)
    with source._connect() as connection:
        connection.execute("INSERT OR REPLACE INTO script_sources VALUES (?,?,?,?,?,?,?,?)",
                           ("LOCAL-REVIEW-PINE", "1", scripts[0]["name"], "strategy", 6,
                            hashlib.sha256(pine.encode()).hexdigest(), pine, at))
        for kind, identifier, title in [("idea", idea["idea_id"], idea["title"]),
                                        ("script", "LOCAL-REVIEW-PINE", scripts[0]["name"])]:
            text = "SYNTHETIC 로컬 통합 검증을 위한 자체 작성 자료. 운영 데이터가 아니며 실거래를 실행하지 않습니다."
            connection.execute("INSERT OR REPLACE INTO source_details VALUES (?,?,?,?,?,?,?,?,?)",
                               (kind, identifier, "https://example.invalid/local-review/" + kind,
                                title, text, json.dumps([]), json.dumps([]), hashlib.sha256(text.encode()).hexdigest(), at))
    candidate = source.create_candidate_from_script("LOCAL-REVIEW-PINE", fetch_source=True)
    source.create_agent_plans(candidate["candidate_id"], max_markets=1)
    sync_tradingview_sources()
    for market in ["korea", "america", "crypto-coins", "futures", "forex", "bonds", "corporate-bonds", "etf", "indices"]:
        source._store_market_universe_page(market, [{"ticker": "TEST:SYNTHETIC", "name": "SYNTHETIC",
            "description": "합성 시장 연결 검증", "exchange": "TEST", "type": "test", "close": 100,
            "change": 0, "volume": 1000, "market_cap_basic": 100000}],
            scan_id="local-review-only", base_rank=0, collected_at=at)
        source._market_state(market)
        with source._connect() as connection:
            connection.execute("UPDATE market_collector_state SET completed_scan_id=?,total_count=1,last_completed_at=? WHERE market=?",
                               ("local-review-only", at, market))
