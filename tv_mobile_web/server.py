"""Independent TradingView-style mobile-web study, backed by existing market APIs.

Research UI, not a TradingView product or authorized data redistribution service.
No cron, no login gate, no collection on app startup, no synthetic price values.
Does not alter the n8n editor, existing TradingView services, or Railway volumes.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
ORIGIN = os.getenv("TV_BACKEND_ORIGIN", "https://autonomous-investor-tradingview-production.up.railway.app").rstrip("/")
if urlsplit(ORIGIN).scheme != "https":
    raise RuntimeError("TV_BACKEND_ORIGIN_MUST_USE_HTTPS")

# Every market here is already modeled by app/core/tradingview.py in the
# original project's tradingview-service branch. Scanner pages may be incomplete.
MARKETS = [
    ("korea","한국 주식","주식","KR"),("america","미국 주식","주식","US"),
    ("japan","일본 주식","주식","JP"),("india","인도 주식","주식","IN"),
    ("vietnam","베트남 주식","주식","VN"),("global-stocks","세계 주식","주식","🌐"),
    ("crypto-coins","암호화폐 코인","암호화폐","₿"),("crypto","암호화폐 거래쌍","암호화폐","◇"),
    ("forex","외환","외환","⇄"),("futures","선물","선물","↗"),
    ("bonds","채권","채권","▤"),("corporate-bonds","회사채","채권","▤"),
    ("indices","지수","지수","▥"),("etf","ETF","ETF","◈"),
]
MARKET_LOOKUP = {item[0]: {"id":item[0],"name":item[1],"group":item[2],"icon":item[3]} for item in MARKETS}

# The 26 groups and original id ranges are from the user-supplied APK
# feature-audit source. A route to a feature group is not a claim of working
# parity with the Android app.
FUNCTION_GROUPS = [
    ("공통/탐색",1,14,"탭 · 검색 · 공통 내비게이션"),
    ("마켓/탐색",15,28,"시장 카테고리 · 화면 탐색"),
    ("마켓/종목",29,35,"종목 카드 · 거래소"),
    ("마켓/부가",36,41,"뉴스 · 경제 일정"),
    ("마켓/랭킹",42,51,"상승 · 하락 · 거래량 순위"),
    ("종목 검색",52,59,"검색 · 필터"),
    ("종목 상세",60,70,"시세 · 재무 · 차트"),
    ("차트",71,120,"시간봉 · 레이아웃 · 범위"),
    ("지표·분석",121,127,"기술적 지표 · 템플릿"),
    ("그리기 도구",128,141,"라인 · 객체 트리"),
    ("리플레이",142,153,"바 재생 · 단계 이동"),
    ("관심목록",154,173,"목록 · 편집 · 정렬"),
    ("알림",174,189,"조건 · 기록 · 푸시"),
    ("뉴스",190,200,"피드 · 상세"),
    ("경제 캘린더",201,211,"국가 · 일정 · 중요도"),
    ("아이디어",212,229,"게시물 · 댓글 · 반응"),
    ("커뮤니티/마인드",230,240,"작성 · 소셜 피드"),
    ("커뮤니티/사용자",241,249,"사용자 · 팔로우"),
    ("거래/브로커",250,265,"주문 · 연결 · 기록"),
    ("계정/인증",266,277,"로그인 · 가입 · 2FA"),
    ("계정/프로필",278,289,"프로필 · 계정"),
    ("설정",290,304,"테마 · 알림 · 언어"),
    ("구독/과금",305,316,"플랜 · 결제"),
    ("Android 위젯",317,325,"홈 위젯 · 구성"),
    ("공유·미디어",326,332,"이미지 · 링크"),
    ("통신/시스템",333,339,"딥링크 · 온보딩 · 오류"),
]

app = FastAPI(title="Independent Android-to-Mobile-Web Function Parity Lab", version="0.1.0")
app.mount("/assets", StaticFiles(directory=WEB), name="assets")


@app.get("/")
async def app_home():
    return FileResponse(WEB / "index.html")


@app.get("/health")
async def health():
    return {"status":"ok","branch_isolated":True,
            "collector_enabled":False,"cron_enabled":False,
            "admin_token_required":False,"synthetic_market_data":False}


@app.get("/api/app/catalog")
async def catalog():
    return {
        "app":"TradingView Android functional-reference mobile web study",
        "reference_version":"1.20.80.0.1002385",
        "markets": list(MARKET_LOOKUP.values()),
        "function_groups":[{"name":name,"start":a,"end":b,"count":b-a+1,"detail":detail,
                            "audit_status":"APK_STATIC_EVIDENCE_ONLY"}
                           for name,a,b,detail in FUNCTION_GROUPS],
        "function_candidate_count":339,
        "function_count_is_final":False,
        "android_runtime_verified":False,
        "tradingview_product":False,
        "implementation_parity_verified":False,
        "charts_are_external_widget":True,
    }


async def _tv_get(path: str, params: dict) -> dict:
    """No arbitrary URL inputs; only allowlisted upstream paths."""
    if not path.startswith("/api/v1/tradingview/"):
        raise HTTPException(400, "UNEXPECTED_UPSTREAM_PATH")
    try:
        async with httpx.AsyncClient(timeout=24, follow_redirects=False) as client:
            response = await client.get(f"{ORIGIN}{path}",params=params,
                                        headers={"Accept":"application/json"})
        response.raise_for_status()
        value=response.json()
        if not isinstance(value,dict):
            raise ValueError("UPSTREAM_NOT_OBJECT")
        return value
    except (httpx.HTTPError,ValueError) as exc:
        raise HTTPException(502,{
            "code":"MARKET_SOURCE_UNAVAILABLE",
            "upstream_status":getattr(getattr(exc,"response",None),"status_code",None),
            "source":"existing tradingview-service",
        }) from exc


@app.get("/api/markets/{market}")
async def market_rows(
    market: str,
    limit: int=Query(40,ge=1,le=100),
    offset: int=Query(0,ge=0),
    order: str=Query("volume",pattern="^(volume|change|close|name|market_cap_basic)$"),
    direction: str=Query("desc",pattern="^(asc|desc)$"),
):
    if market not in MARKET_LOOKUP:
        raise HTTPException(404, "UNSUPPORTED_MARKET")
    # No write, backfill or scheduled ingestion occurs on this GET.
    value=await _tv_get(f"/api/v1/tradingview/markets/{market}",
                      {"limit":limit,"offset":offset,
                       "sort_by":order,"sort_order":direction})
    items=value.get("items",[])
    if not isinstance(items,list):
        raise HTTPException(502,"INVALID_UPSTREAM_MARKET_SCHEMA")
    return {
        "market":market,"source":value.get("source","existing tradingview-service"),
        "items":items,"total_count":value.get("total_count"),
        "offset":offset,"limit":limit,
        "collected_at":value.get("collected_at"),
        "complete_universe_verified":False,
        "price_history_verified":False,
    }


@app.get("/api/ideas")
async def ideas(sort:str=Query("trending",pattern="^(trending|recent)$"),
                page:int=Query(1,ge=1,le=100)):
    result=await _tv_get("/api/v1/tradingview/ideas/live",
                        {"sort":sort,"page":page,"lang":"ko"})
    return {"source":"existing tradingview-service","data":result,
            "site_like_or_comment_actions_live":False}


@app.get("/api/features")
async def feature_ranges():
    return {
        "total_candidates":339,
        "all_runtime_verified":False,
        "feature_ranges":[{"name":x[0],"ids":f"TV-{x[1]:03d} ~ TV-{x[2]:03d}",
                           "count":x[2]-x[1]+1,"audit":"NOT_WEB_PARITY_VERIFIED"}
                          for x in FUNCTION_GROUPS],
    }


# Real TradingView chart WebSocket OHLCV research ingestion.
# This feature belongs ONLY to the isolated mobile-web branch/service.
# Every collection starts with the user's explicit POST; GET never fetches data.
import asyncio
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Literal

from .chart_store import ChartHistoryStore
from .chart_observer import chart_url, observe_five_year_chart

_chart_job = {"state":"idle"}
_chart_task = None


def _history_store():
    return ChartHistoryStore(os.getenv("TV_CHART_DATA_ROOT","/data/tv-chart-5y"))


class CollectDaily(BaseModel):
    symbol: str
    years: Literal[5] = 5
    interval: Literal["1D"] = "1D"


@app.get("/api/chart/options")
def chart_history_options():
    return {
        "periods":[{"value":5,"label":"최근 5년"}],
        "intervals":[{"value":"1D","label":"일봉"}],
        "requested_from":"existing TradingView /chart link",
        "transport":"existing WF02 browser WebSocket OHLCV decoder",
        "never_auto_collect":True,
        "storage":"private gzip JSON plus SQLite, observed bars only",
        "end_to_end_live_verified":False,
    }


@app.get("/api/chart/status")
def chart_history_status(symbol:str):
    try:
        return _history_store().status(symbol.upper())
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc


@app.get("/api/chart/history")
def chart_history_read(symbol:str):
    try:
        result=_history_store().read(symbol.upper(),include_bars=True)
    except ValueError as exc:
        raise HTTPException(409,str(exc)) from exc
    if not result["metadata"]["saved"]:
        raise HTTPException(404,"FIVE_YEAR_CHART_HISTORY_NOT_COLLECTED")
    return JSONResponse(result,headers={"Cache-Control":"private, no-store"})


@app.get("/api/chart/totals")
def chart_history_totals():
    return _history_store().totals()


@app.get("/api/chart/jobs/current")
def chart_capture_current():
    return dict(_chart_job)


async def _capture_5y_daily(job_id,symbol,asof):
    global _chart_job
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser=await p.chromium.launch(
                headless=True,args=["--no-sandbox","--disable-dev-shm-usage"])
            try:
                context=await browser.new_context(
                    viewport={"width":1440,"height":900},
                    locale="ko-KR",
                )
                try:
                    capture=await observe_five_year_chart(
                        context,symbol=symbol,interval="1D",
                        asof=asof,max_pans=24,load_wait_ms=1100)
                finally:
                    await context.close()
            finally:
                await browser.close()
        if job_id!=_chart_job.get("id"):
            return
        count=capture.get("observed_count",0)
        if count<20 or not capture.get("interval_verified"):
            _chart_job.update({
                "state":"failed","reason":"CHART_DAILY_BARS_NOT_VERIFIED",
                "observed_count":count,
                "websocket_connections":capture.get("ws_connections",0),
                "http_status":capture.get("http_status"),
                "outbound_chart_method_counts":capture.get("outbound_chart_method_counts",{}),
                "finished_at":datetime.now(timezone.utc).isoformat(),
            })
            return
        saved=_history_store().save_observation(capture,asof)
        _chart_job.update({
            "state":"completed" if saved["five_year_extent_covered"]
                    else "saved_partial",
            "storage":saved,"observed_count":count,
            "websocket_connections":capture.get("ws_connections",0),
            "history_request_observed":capture.get("history_request_observed",False),
            "ui_pan_attempts":capture.get("ui_pan_attempts",0),
            "initial_bar_count":capture.get("initial_bar_count",0),
            "range_5y_ui_clicked":capture.get("range_5y_ui_clicked",False),
            "native_range_bridge_available":capture.get("native_range_bridge_available",False),
            "native_range_api_called":capture.get("native_range_api_called",False),
            "range_control_candidates":capture.get("range_control_candidates",[]),
            "range_interaction_errors":capture.get("range_interaction_errors",[]),
            "outbound_chart_method_counts":capture.get("outbound_chart_method_counts",{}),
            "finished_at":datetime.now(timezone.utc).isoformat(),
        })
    except Exception as exc:
        # Browser or provider error is not translated into empty/fake candles.
        _chart_job.update({
            "state":"failed",
            "reason":f"{type(exc).__name__}: {str(exc)[:250]}",
            "finished_at":datetime.now(timezone.utc).isoformat(),
        })


@app.post("/api/chart/collect",status_code=202)
async def collect_chart_5y_daily(payload:CollectDaily):
    global _chart_job,_chart_task
    symbol=payload.symbol.strip().upper()
    try:
        target=chart_url(symbol,"1D")
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    if _chart_task is not None and not _chart_task.done():
        raise HTTPException(409,"ALREADY_COLLECTING_ANOTHER_CHART")
    if _chart_job.get("state")=="running":
        raise HTTPException(409,"ALREADY_COLLECTING_ANOTHER_CHART")
    now=datetime.now(timezone.utc)
    _chart_job={
        "id":str(uuid4()),"state":"running","symbol":symbol,
        "years":5,"interval":"1D",
        "source_chart_url":target,
        "started_at":now.isoformat(),
        "asof_exclusive":now.date().isoformat(),
        "automatic":False,"status_warning":"Date extent != audited exchange sessions",
    }
    _chart_task=asyncio.create_task(
        _capture_5y_daily(_chart_job["id"],symbol,now.date()))
    return JSONResponse(_chart_job,status_code=202,headers={"Cache-Control":"no-store"})


# Independent multi-asset discovery. All price rows come from the existing
# TradingView scanner/stored-universe integration, never generated in browser.
from .market_explorer import router as market_explorer_router
app.include_router(market_explorer_router)


# Full global taxonomy is a separate data contract from the 14 scanner routes.
# Loading this catalog does NOT download candles or trigger a schedule.
from .market_taxonomy import MarketTaxonomyStore, hierarchy, ASSET_IDS

_taxonomy_refresh_lock = asyncio.Lock()
_last_manual_taxonomy_attempt = None


def _taxonomy_store():
    return MarketTaxonomyStore(os.getenv("TV_MARKET_TAXONOMY_ROOT", "/data/tv-market-taxonomy"))


@app.get("/api/taxonomy")
def full_market_taxonomy():
    return hierarchy(_taxonomy_store().read())


@app.get("/api/taxonomy/source-status")
def full_market_source_status():
    data=_taxonomy_store().read()
    return {
        "source": data["source"],
        "snapshot_at": data.get("snapshot_at"),
        "records_preserved": data.get("raw_row_count",0),
        "refresh_status": data.get("source_refresh_state","NOT_REQUESTED"),
        "all_exchanges_covered": False,
        "all_countries_with_live_quotes": False,
        "all_instruments_stored": False,
        "manual_only": True,
        "no_token_input": True,
    }


@app.post("/api/taxonomy/refresh")
async def manual_refresh_source_taxonomy():
    """Refresh source metadata on explicit click only, NEVER on GET or cron.

    Prevent multiple users from pounding a public source without reintroducing
    any login, API key, admin token or other test-only gate.
    """
    global _last_manual_taxonomy_attempt
    from time import monotonic
    if _taxonomy_refresh_lock.locked():
        raise HTTPException(409, "MARKET_SOURCE_REFRESH_ALREADY_RUNNING")
    if (_last_manual_taxonomy_attempt is not None and
            monotonic()-_last_manual_taxonomy_attempt<120):
        raise HTTPException(429, "MARKET_SOURCE_REFRESH_COOLDOWN_120_SECONDS")
    async with _taxonomy_refresh_lock:
        _last_manual_taxonomy_attempt=monotonic()
        try:
            snapshot=await _taxonomy_store().refresh()
        except (httpx.HTTPError, ValueError, OSError) as exc:
            raise HTTPException(502, {
                "code": "PUBLIC_DATA_COVERAGE_SNAPSHOT_FAILED",
                "reason": type(exc).__name__,
                "unchanged_old_snapshot": True,
            }) from exc
        return {
            "source": snapshot["source"],
            "snapshot_at": snapshot["snapshot_at"],
            "records_preserved": snapshot["raw_row_count"],
            "source_row_count_confirmed_complete": False,
            "all_market_symbols_collected": False,
            "all_5y_daily_downloaded": False,
            "no_cron": True,
        }


# Additional market menus/categories are dynamically discovered from public
# /markets/ page links, never limited to a hardcoded depth or 14 scanner pages.
from .market_page_graph import WorldMarketPageGraph

_market_graph_refresh_lock=asyncio.Lock()
_market_graph_last_attempt=None


def _market_graph():
    return WorldMarketPageGraph(os.getenv("TV_MARKET_TAXONOMY_ROOT","/data/tv-market-taxonomy"))


@app.get("/api/taxonomy/pages")
def market_navigation_pages(limit:int=Query(500,ge=1,le=5000),
                            offset:int=Query(0,ge=0),
                            q:str=Query("",max_length=90)):
    return _market_graph().get(limit=limit,offset=offset,query=q)


@app.get("/api/taxonomy/pages/status")
def market_navigation_state():
    return _market_graph().status()


@app.post("/api/taxonomy/pages/refresh")
async def manual_market_navigation_refresh(pages:int=Query(12,ge=1,le=50)):
    global _market_graph_last_attempt
    from time import monotonic
    if _market_graph_refresh_lock.locked():
        raise HTTPException(409,"MARKET_HIERARCHY_REFRESH_ALREADY_RUNNING")
    if (_market_graph_last_attempt is not None and
            monotonic()-_market_graph_last_attempt<40):
        raise HTTPException(429,"MARKET_HIERARCHY_COOLDOWN_40_SECONDS")
    async with _market_graph_refresh_lock:
        _market_graph_last_attempt=monotonic()
        return await _market_graph().manual_step(pages=pages)


@app.post("/api/taxonomy/pages/retry-failed")
def manual_market_navigation_retry_failed():
    return {"rescheduled_failed_pages":_market_graph().requeue_failed(),
            "automatically_run":False}
