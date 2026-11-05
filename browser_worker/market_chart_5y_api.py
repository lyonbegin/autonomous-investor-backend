"""Separate *local research* API for five-year chart observations.

Do not publicly deploy this proof-of-concept as a market-data redistributor.
No auth UI, no auto cron, no scheduled collector, no edits to existing services.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

try:
    from browser_worker.market_chart_5y import (
        MAX_PANS, TIMEFRAMES, chart_url, observe_five_year_chart,
    )
except ModuleNotFoundError:
    from market_chart_5y import MAX_PANS, TIMEFRAMES, chart_url, observe_five_year_chart


app=FastAPI(title="5-year chart observation — isolated research prototype",
            version="0.1.0")
_CAPTURE_LOCK=asyncio.Lock()


class ChartRequest(BaseModel):
    symbol: str=Field(default="NASDAQ:AAPL",max_length=96)
    interval: Literal["1D"]="1D"
    years: Literal[5]=5
    max_pans: int=Field(default=12,ge=0,le=MAX_PANS)
    # This endpoint returns an observed-only preview, not a bulk data export.
    max_return_bars: int=Field(default=3000,ge=20,le=5000)


@app.get("/health")
def health():
    return {"status":"ok","scheduled_ingestion":False,
            "permanent_data_storage":False,"public_bulk_licence":False}


@app.get("/v1/research/chart/options")
def chart_options():
    return {
        "periods":[{"value":"5Y","label":"최근 5년"}],
        "timeframes":[{"value":"1D","label":"일봉"}],
        "automatic_updates":False,
        "quality_rule":"Never mark 5Y complete unless observed bars reach the requested start and interval is verified",
        "limitations":"TradingView intraday history varies by plan, symbol and timeframe; 5Y minutes are not guaranteed",
    }


@app.post("/v1/research/chart/observe")
async def preview(payload:ChartRequest):
    try:
        chart_url(payload.symbol,payload.interval)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    if _CAPTURE_LOCK.locked():
        raise HTTPException(409,"CHART_OBSERVATION_ALREADY_RUNNING")
    async with _CAPTURE_LOCK:
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser=await p.chromium.launch(headless=True,
                    args=["--no-sandbox","--disable-dev-shm-usage"])
                try:
                    context=await browser.new_context(locale="ko-KR",
                        viewport={"width":1440,"height":900})
                    try:
                        result=await observe_five_year_chart(
                            context,symbol=payload.symbol,
                            interval=payload.interval,asof=datetime.now(timezone.utc).date(),
                            max_pans=payload.max_pans)
                    finally:
                        await context.close()
                finally:
                    await browser.close()
        except Exception as exc:
            # No internal credentials or raw captured WS frames in errors.
            raise HTTPException(502, f"CHART_OBSERVATION_FAILED:{type(exc).__name__}") from exc
    series=result.pop("bars",[])
    result["bars_returned"]=min(len(series),payload.max_return_bars)
    result["bars_truncated_in_response"]=len(series)>payload.max_return_bars
    result["bars"]=series[-payload.max_return_bars:]
    result["research_only"]=True
    result["automated_collector_enabled"]=False
    return result
