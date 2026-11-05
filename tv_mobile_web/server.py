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
