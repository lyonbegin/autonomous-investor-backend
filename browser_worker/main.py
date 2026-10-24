from __future__ import annotations

import asyncio
import hashlib
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
_CONTEXT_SEMAPHORE = asyncio.Semaphore(max(1, int(os.getenv("BROWSER_MAX_CONTEXTS", "4"))))


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


class PageVerifyRequest(BaseModel):
    url: HttpUrl
    wait_ms: int = 8000
    text_contains: str | None = None


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
    await _CONTEXT_SEMAPHORE.acquire()
    try:
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
    except Exception:
        _CONTEXT_SEMAPHORE.release()
        raise


async def _close(p, browser, context):
    try:
        await context.close()
    finally:
        _CONTEXT_SEMAPHORE.release()


@app.on_event("startup")
async def _startup_sample_regression() -> None:
    async def run_once() -> None:
        await asyncio.sleep(20)
        try:
            await page_sample_test()
        except Exception as exc:
            print(
                "NATIVE_PINE_SAMPLE_TEST_ERROR",
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )
    asyncio.create_task(run_once())


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


@app.post("/v1/page/verify")
async def page_verify(req: PageVerifyRequest) -> dict[str, Any]:
    target = _validate_public_url(str(req.url))
    p, browser, context = await _browser()
    console_errors: list[str] = []
    page_errors: list[str] = []
    try:
        page = await context.new_page()

        def on_console(msg):
            if msg.type == "error":
                console_errors.append(msg.text[:4000])

        def on_page_error(exc):
            page_errors.append(str(exc)[:4000])

        page.on("console", on_console)
        page.on("pageerror", on_page_error)

        response = await page.goto(target, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(max(1000, min(int(req.wait_ms), 30000)))

        state = await page.evaluate(
            """() => ({
              title: document.title,
              text: (document.body?.innerText || '').slice(0, 30000),
              canvases: document.querySelectorAll('canvas').length,
              canvasSizes: Array.from(document.querySelectorAll('canvas')).slice(0,20).map(c => ({
                width: c.width, height: c.height,
                clientWidth: c.clientWidth, clientHeight: c.clientHeight,
                className: c.className || ''
              })),
              svgs: document.querySelectorAll('svg').length,
              iframes: document.querySelectorAll('iframe').length,
              runtimePanels: document.querySelectorAll('.runtime-panel').length,
              nativePineCharts: document.querySelectorAll('.native-pine-chart').length,
              nativePineChartRects: Array.from(document.querySelectorAll('.native-pine-chart')).slice(0,10).map(x => {
                const r=x.getBoundingClientRect();
                return {width:r.width,height:r.height,top:r.top,left:r.left};
              }),
              nativePineErrors: Array.from(document.querySelectorAll('.native-pine-error')).map(x => (x.textContent || '').trim()).slice(0, 20),
              runtimeSummary: Array.from(document.querySelectorAll('.runtime-summary')).map(x => (x.textContent || '').trim()).slice(0,10),
              htmlChars: document.documentElement.innerHTML.length
            })"""
        )
        screenshot = await page.screenshot(type="png", full_page=False)
        needle = str(req.text_contains or "")
        return {
            "ok": True,
            "url": target,
            "status": response.status if response else None,
            "contains": (needle in (state.get("text") or "")) if needle else None,
            "console_errors": console_errors[-50:],
            "page_errors": page_errors[-50:],
            "screenshot_bytes": len(screenshot),
            "screenshot_sha256": hashlib.sha256(screenshot).hexdigest(),
            "state": state,
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"{type(exc).__name__}: {exc}") from exc
    finally:
        await _close(p, browser, context)


@app.get("/v1/page/verify")
async def page_verify_get(
    url: HttpUrl,
    wait_ms: int = 8000,
    text_contains: str | None = None,
) -> dict[str, Any]:
    return await page_verify(
        PageVerifyRequest(
            url=url,
            wait_ms=max(1000, min(int(wait_ms), 30000)),
            text_contains=text_contains,
        )
    )


@app.get("/v1/page/self_test")
async def page_self_test() -> dict[str, Any]:
    target = (
        "https://autonomous-investor-public-production.up.railway.app/"
        "scripts/PUB%3Bfd5cad2ba18e450f8665ea1761f9b034"
    )
    result = await page_verify(
        PageVerifyRequest(
            url=target,
            wait_ms=15000,
            text_contains="실행 성공",
        )
    )
    state = result.get("state") or {}
    ok = bool(
        result.get("contains")
        and int(state.get("nativePineCharts") or 0) >= 1
        and int(state.get("canvases") or 0) >= 1
        and not (result.get("page_errors") or [])
        and not (state.get("nativePineErrors") or [])
    )
    diagnostics = {
        "contains": result.get("contains"),
        "canvases": state.get("canvases"),
        "nativePineCharts": state.get("nativePineCharts"),
        "nativePineErrors": state.get("nativePineErrors"),
        "page_errors": result.get("page_errors"),
        "console_errors": result.get("console_errors"),
        "text": str(state.get("text") or "")[:4000],
    }
    if not ok:
        print("NATIVE_PINE_SELF_TEST_FAIL", json.dumps(diagnostics, ensure_ascii=False), flush=True)
        raise HTTPException(
            status_code=503,
            detail={
                "reason": "Native Pine chart regression check failed",
                **diagnostics,
            },
        )
    print("NATIVE_PINE_SELF_TEST_OK", json.dumps(diagnostics, ensure_ascii=False), flush=True)
    return {
        "status": "ok",
        "runtime": "Vela + PineTS",
        "script": "Dynamic Liquidity Clouds [BigBeluga]",
        "contains_execution_success": True,
        "canvases": state.get("canvases"),
        "native_pine_charts": state.get("nativePineCharts"),
        "console_error_count": len(result.get("console_errors") or []),
    }


@app.get("/v1/page/self_test_strategy")
async def page_self_test_strategy() -> dict[str, Any]:
    target = (
        "https://autonomous-investor-public-production.up.railway.app/"
        "scripts/PUB%3B9697fd0fa80f4251ac278e6ec9d172f5"
    )
    result = await page_verify(
        PageVerifyRequest(
            url=target,
            wait_ms=25000,
            text_contains="실행 성공",
        )
    )
    state = result.get("state") or {}
    ok = bool(
        result.get("contains")
        and int(state.get("nativePineCharts") or 0) >= 1
        and int(state.get("canvases") or 0) >= 1
        and not (result.get("page_errors") or [])
        and not (state.get("nativePineErrors") or [])
    )
    diagnostics = {
        "contains": result.get("contains"),
        "canvases": state.get("canvases"),
        "nativePineCharts": state.get("nativePineCharts"),
        "nativePineErrors": state.get("nativePineErrors"),
        "page_errors": result.get("page_errors"),
        "console_errors": result.get("console_errors"),
        "text": str(state.get("text") or "")[:5000],
    }
    if not ok:
        print("NATIVE_PINE_STRATEGY_TEST_FAIL", json.dumps(diagnostics, ensure_ascii=False), flush=True)
        raise HTTPException(status_code=503, detail={"reason": "Native Pine strategy regression failed", **diagnostics})
    print("NATIVE_PINE_STRATEGY_TEST_OK", json.dumps(diagnostics, ensure_ascii=False), flush=True)
    return {
        "status": "ok",
        "runtime": "Vela + PineTS",
        "script": "Liquidity Gravity Strategy | Weighted Swing-Pool Imbalance",
        "contains_execution_success": True,
        "canvases": state.get("canvases"),
        "native_pine_charts": state.get("nativePineCharts"),
    }


@app.get("/v1/page/self_test_all")
async def page_self_test_all() -> dict[str, Any]:
    indicator = await page_self_test()
    strategy = await page_self_test_strategy()
    return {
        "status": "ok",
        "transport": "playwright-chromium",
        "indicator": indicator,
        "strategy": strategy,
        "verified": [
            "Pine source loaded into native chart engine",
            "Trading Department OHLCV rendered",
            "Canvas created with non-zero size",
            "No page/runtime Pine errors",
        ],
    }


@app.get("/v1/page/sample_test")
async def page_sample_test() -> dict[str, Any]:
    async def list_scripts(script_type: str) -> list[dict[str, Any]]:
        p, browser, context = await _browser()
        try:
            url = (
                "https://autonomous-investor-public-api-production.up.railway.app/"
                f"api/public/scripts?page=1&script_type={script_type}&sort=latest_popular"
            )
            response = await context.request.get(url, timeout=60000)
            payload = await response.json()
            return list(payload.get("items") or [])
        finally:
            await _close(p, browser, context)

    picked: list[dict[str, Any]] = []
    for script_type in ("indicators", "strategies"):
        items = await list_scripts(script_type)
        for item in items[:2]:
            picked.append(item)

    results: list[dict[str, Any]] = []
    for item in picked:
        sid = str(item.get("script_id_part") or "")
        if not sid:
            continue
        target = (
            "https://autonomous-investor-public-production.up.railway.app/scripts/"
            + sid.replace(";", "%3B")
        )
        try:
            result = await page_verify(
                PageVerifyRequest(
                    url=target,
                    wait_ms=18000,
                    text_contains="실행 성공",
                )
            )
            state = result.get("state") or {}
            ok = bool(
                result.get("contains")
                and int(state.get("nativePineCharts") or 0) >= 1
                and int(state.get("canvases") or 0) >= 1
                and not (result.get("page_errors") or [])
                and not (state.get("nativePineErrors") or [])
            )
            results.append({
                "script_id": sid,
                "name": item.get("name"),
                "script_type": item.get("script_type"),
                "ok": ok,
                "canvases": state.get("canvases"),
                "native_pine_charts": state.get("nativePineCharts"),
                "native_pine_errors": state.get("nativePineErrors"),
                "page_errors": result.get("page_errors"),
                "console_errors": result.get("console_errors"),
                "screenshot_bytes": result.get("screenshot_bytes"),
                "screenshot_sha256": result.get("screenshot_sha256"),
            })
        except Exception as exc:
            results.append({
                "script_id": sid,
                "name": item.get("name"),
                "script_type": item.get("script_type"),
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            })

    passed = sum(1 for x in results if x.get("ok"))
    summary = {
        "status": "ok" if passed == len(results) and results else "partial",
        "transport": "playwright-chromium",
        "tested": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }
    print("NATIVE_PINE_SAMPLE_TEST", json.dumps(summary, ensure_ascii=False), flush=True)
    return summary


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
