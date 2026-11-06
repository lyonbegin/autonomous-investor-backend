#!/usr/bin/env python3
"""Capture PUBLIC TradingView stock/ETF/bond screener UI and Fetch/XHR evidence.

No login, no paywall bypass, no stored cookies/headers, no orders or bulk pagination.
Results are observational. Missing/blocked features remain explicit.
"""
import asyncio
import datetime as dt
import json
import os
import pathlib
import re
from collections import Counter
from urllib.parse import urlsplit, parse_qsl, urlencode
from playwright.async_api import async_playwright

PAGES = [
    ("주식", "https://kr.tradingview.com/screener/"),
    ("ETF", "https://kr.tradingview.com/etf-screener/"),
    ("채권", "https://kr.tradingview.com/bond-screener/"),
]
OUT = pathlib.Path(os.environ.get("TV_AUDIT_DIR", "screener_three_network_json"))
OUT.mkdir(parents=True, exist_ok=True)
HOSTS = {"scanner.tradingview.com", "kr.tradingview.com"}
QUERY_KEYS = {"lang", "label-product", "screener_key", "source", "version"}
DENY = re.compile(r"cookie|pass(word)?|csrf|token|secret|auth|session|user.?id|email|api.?key|account", re.I)
MAX_BODY = 1000000
MAX_RESPONSE_BODY = 6000000
MAX_EVENTS = 1500
events, snapshots, actions, pages, errors, inflight = [], [], [], [], [], set()
request_ids = {}
active = {"page": None, "action": None}

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def safe_url(url):
    p = urlsplit(url)
    if p.hostname not in HOSTS or DENY.search(p.path):
        return None
    if any(x in p.path for x in ("/collect", "/analytics", "/report", "/ping")):
        return None
    params = [(k,v[:140]) for k,v in parse_qsl(p.query, keep_blank_values=True) if k in QUERY_KEYS]
    return p.scheme + "://" + p.netloc + p.path + (("?" + urlencode(params)) if params else "")

def clean_payload(x, depth=0):
    if depth > 30:
        return "[max-depth]"
    if isinstance(x, dict):
        return {str(k): clean_payload(v, depth+1) for k,v in x.items() if not DENY.search(str(k))}
    if isinstance(x, list):
        return [clean_payload(v, depth+1) for v in x[:10000]]
    if isinstance(x, str):
        return x[:2000]
    if x is None or isinstance(x, (bool,int,float)):
        return x
    return str(type(x).__name__)

def response_shape(value, depth=0):
    if depth >= 5:
        return type(value).__name__
    if isinstance(value,dict):
        return {str(k):response_shape(v,depth+1) for k,v in list(value.items())[:250]}
    if isinstance(value,list):
        return {"type":"array","count":len(value),
                "first_item":response_shape(value[0],depth+1) if value else None}
    return type(value).__name__

def response_summary(value):
    o = {"shape":response_shape(value)}
    if isinstance(value,dict):
        o["top_level_keys"] = list(value.keys())[:250]
        if "totalCount" in value: o["totalCount"] = value["totalCount"]
        if isinstance(value.get("data"),list):
            o["returned_rows"] = len(value["data"])
            example = value["data"][0] if value["data"] else None
            if isinstance(example,dict):
                o["row_keys"] = list(example.keys())
                if isinstance(example.get("d"),list):
                    o["row_column_count"] = len(example["d"])
                    o["first_column_shapes"] = [response_shape(v) for v in example["d"][:12]]
        if isinstance(value.get("fields"),dict):
            o["field_count"] = len(value["fields"])
            o["field_names"] = list(value["fields"].keys())[:1000]
        if isinstance(value.get("fields"),list):
            o["field_count"] = len(value["fields"])
            o["field_labels"] = [
                {k:v for k,v in x.items() if k in ("n","t","r")}
                for x in value["fields"][:100] if isinstance(x,dict)
            ]
        if "/enum" not in str(value):
            pass
    return o

def request_hook(req):
    if len(events) >= MAX_EVENTS or req.resource_type not in ("xhr","fetch"):
        return
    url = safe_url(req.url)
    if url is None:
        return
    event = {"id":len(events)+1,"page":active["page"],"action":active["action"],
             "started_utc":now(),"url":url,"method":req.method,
             "resource_type":req.resource_type,"status":None}
    if req.method in ("POST","PUT","PATCH") and urlsplit(req.url).hostname == "scanner.tradingview.com":
        try:
            body = json.loads(req.post_data or "null")
            if len(json.dumps(body,ensure_ascii=False)) <= MAX_BODY:
                event["request_json"] = clean_payload(body)
                event["request_json_complete"] = True
            else:
                event["request_error"] = "body_exceeds_safe_capture_limit"
                event["request_json_complete"] = False
        except Exception as exc:
            event["request_error"] = "non_json_" + type(exc).__name__
            event["request_json_complete"] = False
    events.append(event)
    request_ids[id(req)] = event

async def response_hook(resp):
    req = resp.request
    ev = request_ids.get(id(req))
    if ev is None:
        return
    ev["status"] = resp.status
    ev["response_content_type"] = resp.headers.get("content-type","").split(";")[0]
    if "json" not in ev["response_content_type"] and not any(t in ev["url"] for t in ("/scan", "/metainfo", "/enum/")):
        return
    try:
        payload = await asyncio.wait_for(resp.json(), timeout=15)
        ev["response_structure"] = response_summary(payload)
        # Public screener responses only: save complete sanitized response JSON if within cap.
        # Offers, watchlists and any account-specific endpoints are never persisted.
        path = urlsplit(ev["url"]).path
        if urlsplit(ev["url"]).hostname == "scanner.tradingview.com" and (
            path.endswith("/scan") or path.endswith("/metainfo") or path == "/enum/ordered"):
            encoded = json.dumps(payload, ensure_ascii=False, separators=(",",":"))
            ev["response_json_bytes"] = len(encoded.encode("utf-8"))
            if len(encoded.encode("utf-8")) <= MAX_RESPONSE_BODY:
                ev["response_json"] = clean_payload(payload)
                ev["response_json_complete"] = True
            else:
                ev["response_json_complete"] = False
                ev["response_json_omission_reason"] = "response_exceeds_6MB_limit"
    except Exception as exc:
        ev["response_error"] = type(exc).__name__

def spawn(coro):
    task = asyncio.create_task(coro)
    inflight.add(task)
    task.add_done_callback(inflight.discard)

UI_JS = r"""() => {
 const visible = e => {
   let r=e.getBoundingClientRect();
   return r.width>1 && r.height>1 && getComputedStyle(e).visibility!=='hidden';
 };
 const labels = [...document.querySelectorAll('button,[role=tab],[role=option],[role=checkbox],[role=menuitem],[role=dialog],a,input')]
   .filter(visible).slice(0,1100)
   .map(e=>({
     tag:e.tagName.toLowerCase(),
     role:e.getAttribute('role')||'', text:(e.innerText||e.textContent||'').replace(/\s+/g,' ').trim().slice(0,180),
     qa:e.getAttribute('data-qa-id')||'', title:e.getAttribute('title')||'',
     aria:e.getAttribute('aria-label')||'', selected:e.getAttribute('aria-selected')||'',
     href:e.tagName==='A'?e.getAttribute('href'):''
   }));
 return {url:location.href,title:document.title,visible_controls:labels,
    visible_dialog_text:[...document.querySelectorAll('[role=dialog],[role=listbox],[role=menu]')]
     .filter(visible).map(e=>(e.innerText||'').slice(0,13000)).slice(0,8),
    body_start:(document.body?.innerText||'').slice(0,700)};
}"""

async def snapshot(page, page_name, action):
    try:
        x=await page.evaluate(UI_JS)
        snapshots.append({"page":page_name,"action":action,"at_utc":now(),**x})
    except Exception as exc:
        errors.append({"page":page_name,"action":action,"stage":"snapshot","error":str(exc)[:220]})

async def probe(page,name,label,operation,wait_ms=330):
    active.update(page=name, action=label)
    before = len(events)
    outcome = "ok"
    try:
        await operation()
        await page.wait_for_timeout(wait_ms)
        await snapshot(page,name,label)
    except Exception as exc:
        outcome = type(exc).__name__+": "+str(exc)[:240]
        errors.append({"page":name,"action":label,"stage":"click","error":outcome})
    actions.append({"page":name,"action":label,"result":outcome,
                    "new_xhr_fetch":len(events)-before})
    return outcome == "ok"

async def click_first(page, locator):
    n=await locator.count()
    for i in range(min(n,7)):
        if await locator.nth(i).is_visible():
            await locator.nth(i).click(timeout=3500)
            return
    raise RuntimeError("element missing or invisible")

async def reset_popup(page):
    try: await page.keyboard.press("Escape")
    except Exception: pass
    await page.wait_for_timeout(100)

async def run_page(browser,name,url):
    context=await browser.new_context(locale="ko-KR",timezone_id="Asia/Seoul",
                   viewport={"width":1680,"height":1030},device_scale_factor=1)
    page=await context.new_page()
    page.on("request", request_hook)
    page.on("response", lambda r: spawn(response_hook(r)))
    page.on("pageerror", lambda exc: errors.append({"page":name,"stage":"js","error":str(exc)[:250]}))
    active.update(page=name,action="initial")
    try:
        resp = await page.goto(url,wait_until="domcontentloaded",timeout=55000)
        await page.wait_for_timeout(4500)
        pages.append({"page":name,"url":url,"status":resp.status if resp else None,
                      "title":await page.title()})
        await snapshot(page,name,"initial")
        await page.screenshot(path=str(OUT/(name+"_initial.png")),timeout=12000)
        body=(await page.locator("body").inner_text())[:2000].lower()
        if any(t in body for t in ("just a moment","access denied","verify you are human")):
            raise RuntimeError("challenge_or_access_denied")
        if "스크리너" not in body.lower() and "screener" not in body.lower():
            errors.append({"page":name,"stage":"load","error":"unexpected_page_text"})

        # Every visible existing filter pill, not just a hand-picked first set.
        pill_selector = 'button[data-name^="screener-filter-pill-"]'
        pill_count=min(await page.locator(pill_selector).count(),35)
        pill_labels=await page.locator(pill_selector).all_inner_texts()
        for i in range(pill_count):
            label=(pill_labels[i] if i<len(pill_labels) else str(i)).replace("\n"," ").strip()[:85]
            await probe(page,name,f"pill_{i:02d}_{label}",
                        lambda i=i: click_first(page,page.locator(pill_selector).nth(i)))
            # Snapshot options before Escape. A popup can request enum/metainfo.
            await reset_popup(page)

        # Every visible column preset (some change the scan columns and rerun POST /scan).
        tabs=page.locator('button[role="tab"]')
        tab_count=min(await tabs.count(),25)
        tab_labels=await tabs.all_inner_texts()
        for i in range(tab_count):
            tab=(tab_labels[i] if i<len(tab_labels) else str(i)).strip()[:80]
            await probe(page,name,f"column_tab_{i:02d}_{tab}",
                        lambda i=i:click_first(page,page.locator('button[role="tab"]').nth(i)),
                        wait_ms=550)
            await reset_popup(page)

        # Read-only dropdowns, menus and control panels
        for action,selector in [
            ("screener_switch",'[data-qa-id="screener-pills-switcher"]'),
            ("screen_title",'[data-qa-id="screen-title"]'),
            ("watchlist",'button:has-text("왓치리스트")'),
            ("settings",'button[data-qa-id="screener-topbar-settings"]'),
            ("view_selector",'button:has-text("테이블")'),
            ("add_filter",'button[data-qa-id="screener-add-new-filter"]'),
            ("column_setup",'button[data-qa-id="screener-add-column-button"]'),
            ("tabs_more",'button:has-text("더보기")'),
            ("refresh",'button[data-qa-id="screener-refresh-button"]'),
        ]:
            success=await probe(page,name,action,
                      lambda selector=selector:click_first(page,page.locator(selector)))
            if success and action in ("add_filter","column_setup"):
                # Scroll the filter/column catalog to see beyond the first viewport.
                for step in range(4):
                    await page.mouse.wheel(0,740)
                    await page.wait_for_timeout(180)
                    await snapshot(page,name,f"{action}_scroll_{step}")
            await reset_popup(page)

        # Make one local, non-trading filter choice to capture an actual changed /scan.
        if pill_count:
            chosen=await probe(page,name,"apply_first_filter_open",
                              lambda:click_first(page,page.locator(pill_selector).first))
            if chosen:
                opt=page.locator('[role="option"]:visible,[role="checkbox"]:visible')
                if await opt.count():
                    await probe(page,name,"apply_first_filter_option",
                                lambda:click_first(page,opt),wait_ms=950)
            await reset_popup(page)

        print("PAGE",name,"status",pages[-1]["status"],
              "actions",sum(a["page"]==name for a in actions),
              "events",sum(a["page"]==name for a in events),flush=True)
    except Exception as exc:
        errors.append({"page":name,"stage":"page","error":type(exc).__name__+": "+str(exc)[:350]})
        print("ERROR",name,str(exc)[:240],flush=True)
    finally:
        if inflight:
            try:await asyncio.wait_for(asyncio.gather(*inflight,return_exceptions=True),timeout=20)
            except Exception:pass
        await context.close()

async def main():
    async with async_playwright() as playwright:
        browser=await playwright.chromium.launch(headless=True,
                  args=["--no-sandbox","--disable-dev-shm-usage"])
        for name,url in PAGES:
            await run_page(browser,name,url)
        await browser.close()
    summary={"captured_at_utc":now(),"pages":pages,
             "events":len(events),"actions":len(actions),"errors":errors,
             "by_page":{name:{
               "events":sum(e["page"]==name for e in events),
               "actions":sum(a["page"]==name for a in actions),
               "successful_actions":sum(a["page"]==name and a["result"]=="ok" for a in actions),
               "response_structures":sum(e["page"]==name and "response_structure" in e for e in events),
               "full_response_json":sum(e["page"]==name and e.get("response_json_complete") is True for e in events),
               "with_request_json":sum(e["page"]==name and "request_json" in e for e in events)
             } for name,_ in PAGES},
             "endpoints":dict(Counter(e["method"]+" "+e["url"] for e in events))}
    for filename,payload in [
        ("summary.json",summary),("requests_responses.json",events),
        ("menu_snapshots.json",snapshots),("action_results.json",actions)]:
        (OUT/filename).write_text(json.dumps(payload,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    print("SUMMARY",json.dumps(summary["by_page"],ensure_ascii=False),flush=True)
    print("ARTIFACT",str(OUT.resolve()),flush=True)
    if not pages or not any(p["status"]==200 for p in pages):
        raise SystemExit("No screener returned HTTP 200; evidence saved with errors.")

if __name__=="__main__":
    asyncio.run(main())
