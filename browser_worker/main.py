from __future__ import annotations

import asyncio
import json
import os
import time
import ipaddress
from urllib.parse import urlparse
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
from playwright.async_api import async_playwright

app = FastAPI(title="Autonomous Investor Data Browser Worker", version="2.0.0")

_PLAYWRIGHT = None
_SHARED_BROWSER = None
_BROWSER_LOCK = asyncio.Lock()


class DetailRequest(BaseModel):
    url: HttpUrl
    wait_ms: int = 3000


class InspectRequest(BaseModel):
    url: HttpUrl = HttpUrl("https://www.tradingview.com/bond-screener/")
    wait_ms: int = 5000
    scroll_steps: int = 8


class BondPageRequest(BaseModel):
    offset: int = 0
    limit: int = 100


class HttpFetchRequest(BaseModel):
    url: HttpUrl
    method: str = "GET"
    headers: dict[str, str] = {}
    json_body: Any | None = None
    body: str | None = None
    warmup_url: HttpUrl | None = None
    wait_ms: int = 0
    timeout_ms: int = 30000


def _validate_public_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="Only http/https URLs are allowed")
    host = (parsed.hostname or "").lower()
    if not host or host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise HTTPException(status_code=400, detail="Local/private hosts are not allowed")
    try:
        addr = ipaddress.ip_address(host)
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
            raise HTTPException(status_code=400, detail="Local/private IPs are not allowed")
    except ValueError:
        pass
    return value


async def _ensure_browser():
    global _PLAYWRIGHT, _SHARED_BROWSER
    if _SHARED_BROWSER is not None and _SHARED_BROWSER.is_connected():
        return _SHARED_BROWSER
    async with _BROWSER_LOCK:
        if _SHARED_BROWSER is not None and _SHARED_BROWSER.is_connected():
            return _SHARED_BROWSER
        if _PLAYWRIGHT is None:
            _PLAYWRIGHT = await async_playwright().start()
        _SHARED_BROWSER = await _PLAYWRIGHT.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        return _SHARED_BROWSER


async def _browser():
    browser = await _ensure_browser()
    context = await browser.new_context(
        locale="en-US",
        timezone_id="Asia/Seoul",
        viewport={"width": 1600, "height": 1200},
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
        ),
    )
    return None, browser, context


async def _close(p, browser, context):
    await context.close()


@app.on_event("shutdown")
async def _shutdown_browser():
    global _PLAYWRIGHT, _SHARED_BROWSER
    if _SHARED_BROWSER is not None:
        try:
            await _SHARED_BROWSER.close()
        except Exception:
            pass
        _SHARED_BROWSER = None
    if _PLAYWRIGHT is not None:
        try:
            await _PLAYWRIGHT.stop()
        except Exception:
            pass
        _PLAYWRIGHT = None


@app.get("/health")
async def health() -> dict[str, Any]:
    browser = await _ensure_browser()
    return {
        "status": "ok",
        "service": "autonomous-investor-data-browser",
        "browser_connected": bool(browser and browser.is_connected()),
        "transport": "playwright-chromium",
    }


@app.post("/v1/http/fetch")
async def http_fetch(req: HttpFetchRequest) -> dict[str, Any]:
    target = _validate_public_url(str(req.url))
    warmup = _validate_public_url(str(req.warmup_url)) if req.warmup_url else None
    method = str(req.method or "GET").upper()
    if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
        raise HTTPException(status_code=400, detail=f"Unsupported method: {method}")

    p, browser, context = await _browser()
    try:
        if warmup:
            page = await context.new_page()
            await page.goto(warmup, wait_until="domcontentloaded", timeout=max(1000, min(req.timeout_ms, 60000)))
            if req.wait_ms > 0:
                await page.wait_for_timeout(max(0, min(req.wait_ms, 10000)))

        kwargs: dict[str, Any] = {
            "method": method,
            "headers": {str(k): str(v) for k, v in (req.headers or {}).items()},
            "timeout": max(1000, min(int(req.timeout_ms), 120000)),
        }
        if req.json_body is not None:
            kwargs["data"] = req.json_body
            if not any(k.lower() == "content-type" for k in kwargs["headers"]):
                kwargs["headers"]["Content-Type"] = "application/json"
        elif req.body is not None:
            kwargs["data"] = req.body

        response = await context.request.fetch(target, **kwargs)
        text_body = await response.text()
        parsed_json: Any | None = None
        try:
            parsed_json = json.loads(text_body)
        except Exception:
            parsed_json = None

        headers = dict(response.headers)
        safe_headers = {
            k: v for k, v in headers.items()
            if k.lower() in {
                "content-type", "content-length", "etag", "last-modified",
                "retry-after", "cache-control", "x-ratelimit-limit",
                "x-ratelimit-remaining", "x-ratelimit-reset",
            }
        }
        return {
            "ok": response.ok,
            "status": response.status,
            "url": target,
            "headers": safe_headers,
            "json": parsed_json,
            "text": None if parsed_json is not None else text_body,
            "text_preview": text_body[:2000],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"{type(exc).__name__}: {exc}") from exc
    finally:
        await _close(p, browser, context)


@app.post("/v1/source/detail")
async def source_detail(req: DetailRequest) -> dict[str, Any]:
    p, browser, context = await _browser()
    try:
        page = await context.new_page()
        response = await page.goto(str(req.url), wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(max(0, min(req.wait_ms, 10000)))
        data = await page.evaluate(
            r"""() => {
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
    scanner_responses: list[dict[str, Any]] = []
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

        async def on_response(response):
            if "scanner.tradingview.com/bond/scan" not in response.url:
                return
            try:
                data = await response.json()
                scanner_responses.append({
                    "url": response.url,
                    "status": response.status,
                    "total_count": int(data.get("totalCount") or 0),
                    "count": len(data.get("data") or []),
                    "first": ((data.get("data") or [{}])[0]).get("s") if data.get("data") else None,
                    "last": ((data.get("data") or [{}])[-1]).get("s") if data.get("data") else None,
                })
            except Exception as exc:
                scanner_responses.append({"url": response.url, "status": response.status, "error": str(exc)})

        page.on("request", on_request)
        page.on("response", on_response)
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
            "scanner_responses": scanner_responses[-50:],
            "dom": dom,
            "at": time.time(),
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"{type(exc).__name__}: {exc}") from exc
    finally:
        await _close(p, browser, context)


@app.post("/v1/bond/page")
async def bond_page(req: BondPageRequest) -> dict[str, Any]:
    p, browser, context = await _browser()
    try:
        page = await context.new_page()
        template: dict[str, Any] = {}
        event = asyncio.Event()

        def on_request(request):
            if "scanner.tradingview.com/bond/scan" not in request.url:
                return
            if request.method != "POST" or not request.post_data:
                return
            try:
                template["url"] = request.url
                template["payload"] = json.loads(request.post_data)
                event.set()
            except Exception:
                return

        page.on("request", on_request)
        response = await page.goto(
            "https://www.tradingview.com/bond-screener/",
            wait_until="domcontentloaded",
            timeout=45000,
        )
        try:
            await asyncio.wait_for(event.wait(), timeout=15)
        except asyncio.TimeoutError as exc:
            raise RuntimeError("Bond Screener scan request was not observed") from exc

        offset = max(0, int(req.offset))
        limit = max(1, min(int(req.limit), 500))
        payload = dict(template["payload"])
        payload["range"] = [offset, offset + limit]

        api_response = await context.request.post(
            template["url"],
            data=payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Referer": "https://www.tradingview.com/bond-screener/",
            },
            timeout=30000,
        )
        text_body = await api_response.text()
        try:
            data = json.loads(text_body)
        except Exception:
            data = {}
        rows = list(data.get("data") or [])
        return {
            "ok": api_response.ok,
            "browser_status": response.status if response else None,
            "scanner_status": api_response.status,
            "offset": offset,
            "limit": limit,
            "total_count": int(data.get("totalCount") or 0),
            "count": len(rows),
            "has_more": offset + len(rows) < int(data.get("totalCount") or 0),
            "items": rows,
            "scanner_url": template["url"],
            "request_range": payload.get("range"),
            "error_text": None if data else text_body[:2000],
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"{type(exc).__name__}: {exc}") from exc
    finally:
        await _close(p, browser, context)
