from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
from playwright.async_api import async_playwright

app = FastAPI(title="Autonomous Investor TradingView Browser Worker", version="1.0.0")


class DetailRequest(BaseModel):
    url: HttpUrl
    wait_ms: int = 3000


class InspectRequest(BaseModel):
    url: HttpUrl = HttpUrl("https://www.tradingview.com/bond-screener/")
    wait_ms: int = 5000
    scroll_steps: int = 8


async def _browser():
    p = await async_playwright().start()
    browser = await p.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
    )
    context = await browser.new_context(
        locale="en-US",
        timezone_id="Asia/Seoul",
        viewport={"width": 1600, "height": 1200},
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
        ),
    )
    return p, browser, context


async def _close(p, browser, context):
    try:
        await context.close()
    finally:
        try:
            await browser.close()
        finally:
            await p.stop()


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "service": "autonomous-investor-tradingview-browser"}


@app.post("/v1/source/detail")
async def source_detail(req: DetailRequest) -> dict[str, Any]:
    p, browser, context = await _browser()
    try:
        page = await context.new_page()
        response = await page.goto(str(req.url), wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(max(0, min(req.wait_ms, 10000)))
        data = await page.evaluate(
            """() => {
              const root = document.querySelector('main') || document.body;
              const clean = (s) => (s || '').replace(/\u00a0/g,' ').replace(/[ \t]+\n/g,'\n').replace(/\n{3,}/g,'\n\n').trim();
              const imgs = Array.from(root.querySelectorAll('img'))
                .map(x => x.currentSrc || x.src)
                .filter(Boolean)
                .filter(x => !x.includes('userpics/') && !x.includes('s3-symbol-logo.'));
              const uniq = [...new Set(imgs)];
              return {
                title: clean((root.querySelector('h1') || document.querySelector('h1'))?.textContent || document.title),
                full_text: clean(root.innerText || ''),
                images: uniq,
                html_chars: root.innerHTML.length,
                body_chars: (root.innerText || '').length,
              };
            }"""
        )
        return {
            "ok": True,
            "url": str(req.url),
            "status": response.status if response else None,
            **data,
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"{type(exc).__name__}: {exc}") from exc
    finally:
        await _close(p, browser, context)


@app.post("/v1/inspect/network")
async def inspect_network(req: InspectRequest) -> dict[str, Any]:
    p, browser, context = await _browser()
    captured: list[dict[str, Any]] = []
    seen: set[str] = set()
    try:
        page = await context.new_page()

        def on_request(request):
            url = request.url
            if "tradingview.com" not in url:
                return
            if not any(key in url for key in ("scanner", "screener-facade", "/bond/", "/scan", "screener")):
                return
            post = request.post_data or ""
            key = f"{request.method}|{url}|{post[:800]}"
            if key in seen:
                return
            seen.add(key)
            captured.append({
                "kind": "request",
                "method": request.method,
                "url": url,
                "post_data": post[:12000],
                "headers": {
                    k: v for k, v in request.headers.items()
                    if k.lower() in {"content-type", "accept", "origin", "referer"}
                },
            })

        page.on("request", on_request)
        response = await page.goto(str(req.url), wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(max(1500, min(req.wait_ms, 10000)))

        for _ in range(max(0, min(req.scroll_steps, 30))):
            await page.mouse.wheel(0, 2400)
            await page.wait_for_timeout(700)

        dom = await page.evaluate(
            """() => ({
              title: document.title,
              rows: document.querySelectorAll('tr').length,
              buttons: Array.from(document.querySelectorAll('button')).map(x => (x.innerText || '').trim()).filter(Boolean).slice(0,120),
              links: Array.from(document.querySelectorAll('a')).map(x => ({t:(x.innerText||'').trim(), h:x.href})).filter(x=>x.t).slice(0,120)
            })"""
        )
        return {
            "ok": True,
            "url": str(req.url),
            "status": response.status if response else None,
            "captured_count": len(captured),
            "captured": captured[-200:],
            "dom": dom,
            "at": time.time(),
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"{type(exc).__name__}: {exc}") from exc
    finally:
        await _close(p, browser, context)
