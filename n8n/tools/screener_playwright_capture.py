#!/usr/bin/env python3
"""Playwright Chromium TradingView Stock Screener PUBLIC UI/XHR inventory.

No account, no login, no Cloudflare bypass, no cookie/header credentials recorded.
Saves redacted request/response SHAPES and at most two data rows per UI action.
Does not fetch all instruments, paginate the universe or make financial orders.
"""
import asyncio
import datetime
import json
import os
import pathlib
import re
import traceback
from collections import Counter
from urllib.parse import urlsplit, parse_qsl

from playwright.async_api import async_playwright

BASE = "https://kr.tradingview.com/screener/"
OUT = pathlib.Path(os.getenv("TV_CAPTURE_DIR", "tv_capture"))
OUT.mkdir(parents=True, exist_ok=True)
WATCH_HOSTS = ("scanner.tradingview.com","kr.tradingview.com","www.tradingview.com")
MAX_EVENTS = 650
MAX_ACTIONS = 60
SAFE_QUERY_KEYS = {"label-product", "lang", "version", "screener_key", "source", "symbol", "sort_by", "sort_order"}
records, actions, controls, errors = [], [], [], []
pending = set()
current_action = "load"
request_counter = 0

def clean_url(s):
    p = urlsplit(s)
    if p.hostname not in WATCH_HOSTS:
        return None
    parts = p.path.split("/")
    # Never record account names, user identifiers, tracking tokens or analytics payloads
    if re.search(r"username|user_id|session|auth|token|collect|captcha",p.path,re.I):
        return None
    q = {k:v[:120] for k,v in parse_qsl(p.query, keep_blank_values=True) if k in SAFE_QUERY_KEYS}
    query = "&".join(f"{k}={v}" for k,v in sorted(q.items()))
    return p.scheme + "://" + p.netloc + p.path + ("?" + query if query else "")

def shape(obj, depth=0):
    if depth >= 3:
        return type(obj).__name__
    if isinstance(obj,dict):
        return {k: shape(v,depth+1) for k,v in list(obj.items())[:80]}
    if isinstance(obj,list):
        return {"array_len":len(obj),"item":shape(obj[0],depth+1) if obj else None}
    return type(obj).__name__

def safe_request(req):
    result={"method":req.method,"url":clean_url(req.url),"resource_type":req.resource_type}
    p=urlsplit(req.url)
    if p.hostname=="scanner.tradingview.com" and req.method=="POST":
        try:
            body=json.loads(req.post_data or "{}")
            if isinstance(body,dict):
                # Only public screener selection/filter columns - never headers/cookies
                keep=("columns","filter","filter2","options","range","sort","markets",
                      "ignore_unknown_fields","symbols","query")
                result["body"]={k:body[k] for k in keep if k in body}
        except Exception:
            result["body_status"]="non_json"
    return result

def safe_response(obj,url):
    if not isinstance(obj,dict):
        return {"type":type(obj).__name__,"shape":shape(obj)}
    ret={"keys":list(obj.keys())[:80]}
    if "totalCount" in obj:
        ret["totalCount"]=obj.get("totalCount")
    if isinstance(obj.get("data"),list):
        data=obj["data"]
        ret["returned_rows"]=len(data)
        ret["first_rows"]=[]
        for row in data[:2]:
            if isinstance(row,dict):
                ret["first_rows"].append({
                    "s":row.get("s"),
                    "d":row.get("d")[:30] if isinstance(row.get("d"),list) else None
                })
        ret["d_length_counts"]=dict(Counter(len(row.get("d",[])) for row in data if isinstance(row,dict)))
    if "fields" in obj and isinstance(obj["fields"],dict):
        ret["field_count"]=len(obj["fields"])
        ret["field_names"]=list(obj["fields"].keys())[:4000]
    if "filters" in obj and isinstance(obj["filters"],dict):
        ret["filter_field_count"]=len(obj["filters"])
        ret["filter_names"]=list(obj["filters"].keys())[:4000]
    ret["schema"]=shape(obj)
    return ret

def req_event(req):
    global request_counter
    url=clean_url(req.url)
    if not url:return
    if req.resource_type not in ("xhr","fetch"):return
    if len(records)>=MAX_EVENTS:return
    request_counter+=1
    r=safe_request(req)
    r.update({"id":request_counter,"action":current_action,"started_at":datetime.datetime.now(datetime.timezone.utc).isoformat()})
    records.append(r)
    setattr(req,"_capture_index",len(records)-1)  # request Python object can be immutable: index fallback below

async def response_event(res):
    if len(records)>MAX_EVENTS:return
    req=res.request
    url=clean_url(req.url)
    if not url or req.resource_type not in ("xhr","fetch"):return
    target=next((r for r in reversed(records) if r["url"]==url and r["method"]==req.method and "status" not in r),None)
    if target is None:return
    target["status"]=res.status
    target["content_type"]=(res.headers.get("content-type") or "").split(";")[0]
    target["response_bytes"]=res.headers.get("content-length","unknown")
    if not ("json" in target["content_type"] or "scan" in url or "metainfo" in url):return
    try:
        parsed=await asyncio.wait_for(res.json(),timeout=15)
        target["response"]=safe_response(parsed,url)
    except Exception as e:
        target["parse_error"]=type(e).__name__

def record_task(coro):
    task=asyncio.create_task(coro)
    pending.add(task)
    task.add_done_callback(pending.discard)

async def snapshot(page,name):
    try:
        info=await page.evaluate("""() => ({
          title: document.title, url: location.href,
          body: (document.body?.innerText || '').slice(0,5500),
          controls: Array.from(document.querySelectorAll('button,[role="button"],input,[role="tab"],[role="menuitem"]'))
            .filter(x => { const r=x.getBoundingClientRect(); return r.width>0 && r.height>0; })
            .slice(0,300).map(x => ({
             tag:x.tagName, role:x.getAttribute('role'), text:(x.innerText||'').trim().slice(0,100),
             aria:x.getAttribute('aria-label'), title:x.getAttribute('title'), placeholder:x.getAttribute('placeholder'),
             dataName:x.getAttribute('data-name'), classes: typeof x.className==='string' ? x.className.slice(0,100):''
            }))
        })""")
        info["action"]=name
        controls.append(info)
        if len(controls)<=22:
            await page.screenshot(path=str(OUT / f"{len(controls):02d}_{re.sub('[^a-zA-Z0-9_-]','_',name)}.png"),full_page=False,timeout=12000)
    except Exception as e:
        errors.append({"stage":"snapshot","action":name,"error":str(e)[:400]})

async def action(page,name,do,wait=1.2):
    global current_action
    if len(actions)>=MAX_ACTIONS:return
    current_action=name
    before=len(records)
    started=asyncio.get_running_loop().time()
    outcome="ok"
    try:
        await do()
        await page.wait_for_timeout(int(wait*1000))
    except Exception as e:
        outcome=type(e).__name__ + ": " + str(e)[:240]
    await snapshot(page,name)
    actions.append({"action":name,"status":outcome,"events":len(records)-before,"duration_s":round(asyncio.get_running_loop().time()-started,2)})
    print("ACTION",len(actions),name,outcome,"xhr/fetch",len(records)-before,flush=True)

async def maybe_click(page,name,regex):
    rg=re.compile(regex,re.I)
    locator=page.locator('button,[role="button"],[role="tab"]').filter(has_text=rg)
    count=await locator.count()
    if count==0:return False
    for i in range(min(count,5)):
        el=locator.nth(i)
        if not await el.is_visible():continue
        await action(page,name,lambda:el.click(timeout=4500))
        return True
    return False

async def main():
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=["--no-sandbox","--disable-dev-shm-usage"])
        context=await browser.new_context(locale="ko-KR",timezone_id="Asia/Seoul",viewport={"width":1540,"height":940},device_scale_factor=1)
        page=await context.new_page()
        page.on("request",req_event)
        page.on("response",lambda res:record_task(response_event(res)))
        page.on("pageerror",lambda exc:errors.append({"stage":"javascript","message":str(exc)[:500]}))
        page.on("console",lambda m:None)
        await action(page,"00_initial_navigation",
                     lambda:page.goto(BASE,wait_until="domcontentloaded",timeout=45000),wait=8)
        status=(controls[-1].get("body") or "").lower() if controls else ""
        if any(q in status for q in ("access denied","verify you are human","just a moment","temporarily blocked")):
            print("BLOCKED/CHALLENGE: no bypass attempted",flush=True)
        else:
            # Read-only keyboard and menu discovery. Actions that would submit, save,
            # delete or trade are intentionally not performed.
            for name,keys in [
                ("01_filter_picker_shortcut","Shift+F"),
                ("02_column_picker_shortcut","Shift+C"),
                ("03_ai_shortcut","Shift+A"),
            ]:
                await action(page,name,lambda keys=keys:page.keyboard.press(keys),wait=1.1)
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(500)
            # Try common UI controls. Target only visible control text; no random click.
            patterns=[
                ("04_market_selector",r"한국|Korea|시장.*선택|Market"),
                ("05_filter_add",r"필터.*추가|필터|Filters"),
                ("06_columns",r"컬럼|열|Column|개요|Overview"),
                ("07_chart_view",r"차트|Chart"),
                ("08_heatmap_view",r"히트맵|Heatmap"),
                ("09_table_view",r"테이블|Table"),
                ("10_screen_presets",r"스크린|Screen"),
                ("11_sort",r"정렬|Sort"),
                ("12_refresh",r"새로|Refresh"),
                ("13_exchange",r"거래소|Exchange"),
                ("14_timeframe",r"시간|Timeframe"),
            ]
            for name,pattern in patterns:
                try:
                    await maybe_click(page,name,pattern)
                    await page.keyboard.press("Escape")
                    await page.wait_for_timeout(350)
                except Exception as e:
                    errors.append({"stage":name,"error":str(e)[:300]})
            # Filter panel and column set contents can be enumerated from DOM,
            # without requiring account-specific actions.
            for name,shortcut in [("15_filter_modal","Shift+F"),("16_column_modal","Shift+C")]:
                await action(page,name,lambda shortcut=shortcut:page.keyboard.press(shortcut),wait=.7)
                await page.keyboard.press("Escape")
        if pending:
            try:await asyncio.wait_for(asyncio.gather(*pending,return_exceptions=True),timeout=18)
            except Exception:pass
        await browser.close()
    common=Counter((r.get("url") or "").split("?")[0] for r in records)
    summary={"target":BASE,"created_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "loaded": bool(controls and "tradingview" in controls[0].get("title","").lower()),
        "actions":len(actions),"events":len(records),"unique_endpoints":len(common),
        "endpoints":dict(common.most_common(70)),
        "scan_events":sum("/scan" in (r.get("url") or "") for r in records),
        "metainfo_events":sum("/metainfo" in (r.get("url") or "") for r in records),
        "action_results":actions,
        "errors":errors}
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"xhr_fetch_inventory.json").write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"ui_control_inventory.json").write_text(json.dumps(controls,ensure_ascii=False,indent=2),encoding="utf-8")
    print("SUMMARY",json.dumps({"loaded":summary["loaded"],"actions":summary["actions"],
          "events":summary["events"],"scan_events":summary["scan_events"],
          "unique_endpoints":summary["unique_endpoints"],"endpoints":summary["endpoints"]},ensure_ascii=False),flush=True)
    if records:
        print("SCANS",json.dumps([{"action":r["action"],"status":r.get("status"),
                  "body":r.get("body"),"response":{k:r.get("response",{}).get(k) for k in ("totalCount","returned_rows","field_count") if r.get("response",{}).get(k) is not None}}
                 for r in records if "/scan" in (r.get("url") or "")][:12],ensure_ascii=False)[:6000],flush=True)
    print("ARTIFACT_DIR",OUT.resolve(),flush=True)

if __name__=="__main__":
    asyncio.run(main())
