#!/usr/bin/env python3
"""TradingView public screener menu/navigation inventory with Playwright Chromium.

Observational UI clicks only. Captures menu options and navigable links, NOT credentials,
cookies, login tokens, user names, trading/order operations or bulk quote data.
Unverified paths remain explicit audit gaps.
"""
import asyncio, json, pathlib, datetime, re, os
from urllib.parse import urlsplit,parse_qsl
from playwright.async_api import async_playwright

ROOT="https://kr.tradingview.com"
PAGES=[
 ("주식","/screener/"),
 ("ETF","/etf-screener/"),
 ("채권","/bond-screener/"),
 ("암호화폐 코인","/crypto-coins-screener/"),
 ("CEX","/cex-screener/"),
 ("DEX","/dex-screener/"),
 ("Pine","/pine-screener/")
]
OUT=pathlib.Path("screener_menu_audit")
OUT.mkdir(exist_ok=True)
UI_SCRIPT="""() => {
 const visible=e=>{
   const r=e.getBoundingClientRect();
   return r.width>1 && r.height>1 && getComputedStyle(e).visibility!=='hidden'
 };
 const clean=t=>(t||'').replace(/\\s+/g,' ').trim().slice(0,180);
 const elements=[...document.querySelectorAll(
   'button,[role=button],[role=tab],[role=menuitem],[role=option],[role=checkbox],[role=radio],label,input,select,option,a,[aria-haspopup]')]
   .filter(visible).slice(0,2200);
 const rows=elements.map((e,i)=>({
    tag:e.tagName.toLowerCase(),role:e.getAttribute('role')||'',
    text:clean(e.innerText||e.textContent||''),
    aria:e.getAttribute('aria-label')||'',
    title:e.getAttribute('title')||'',
    placeholder:e.getAttribute('placeholder')||'',
    name:e.getAttribute('data-name')||'',
    href:e.tagName==='A' ? e.getAttribute('href') : '',
    expanded:e.getAttribute('aria-expanded')||'',
    checked:e.getAttribute('aria-checked')||'',
    selected:e.getAttribute('aria-selected')||''
 }));
 const dialogs=[...document.querySelectorAll('[role=dialog],[role=menu],[role=listbox],[data-state=open]')].filter(visible)
  .slice(0,20).map(e=>({role:e.getAttribute('role')||'',text:(e.innerText||'').trim().slice(0,15000),
    htmlTag:e.tagName,scrollHeight:e.scrollHeight,clientHeight:e.clientHeight}));
 return {title:document.title,href:location.href,
   active_text:(document.body?.innerText||'').slice(-10000),elements:rows,dialogs,
   visible_element_count:elements.length}
}"""
EVENTS=[]
def url_clean(url):
    p=urlsplit(url)
    if p.hostname not in ("scanner.tradingview.com","kr.tradingview.com"):return None
    if any(x in p.path for x in ("/collect","/list_alerts","/users","/report","/ping")):return None
    allowed={"label-product","screener_key","version","lang","source"}
    q="&".join(f"{k}={v[:60]}" for k,v in parse_qsl(p.query) if k in allowed)
    return p.scheme+"://"+p.netloc+p.path+("?"+q if q else "")
def handler(resp,page_name,action):
    u=url_clean(resp.url)
    if not u or resp.request.resource_type not in ("fetch","xhr"):return
    EVENTS.append({"page":page_name,"action":action[0],"url":u,
                  "method":resp.request.method,"status":resp.status})
async def take(page,page_name,action,records):
    try:
        snapshot=await page.evaluate(UI_SCRIPT)
        snapshot["page"]=page_name
        snapshot["action"]=action
        records.append(snapshot)
    except Exception as exc:
        records.append({"page":page_name,"action":action,"error":str(exc)[:240]})
async def click_probe(page,name,locator_spec,records,action):
    try:
        kind,value=locator_spec
        if kind=="title":
            loc=page.locator("button[title="+json.dumps(value)+"]")
        elif kind=="aria":
            loc=page.locator('[aria-label='+json.dumps(value)+']')
        elif kind=="exact":
            loc=page.get_by_role("button",name=value,exact=True)
        elif kind=="text":
            loc=page.get_by_text(value,exact=True)
        elif kind=="css":
            loc=page.locator(value)
        else: return
        count=await loc.count()
        if count==0:
            records.append({"page":name,"action":action,"status":"locator_not_found"})
            return
        clicked=False
        for i in range(min(count,6)):
            el=loc.nth(i)
            if await el.is_visible():
                await el.click(timeout=3500)
                clicked=True
                break
        if not clicked:
            records.append({"page":name,"action":action,"status":"not_visible"})
            return
        await page.wait_for_timeout(500)
        await take(page,name,action,records)
        try:await page.keyboard.press("Escape")
        except Exception:pass
        await page.wait_for_timeout(180)
    except Exception as exc:
        records.append({"page":name,"action":action,"status":"click_failed","error":str(exc)[:250]})
        try:await page.keyboard.press("Escape")
        except Exception:pass
async def main():
    records=[]; pages=[]; action=["initial"]
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=["--no-sandbox","--disable-dev-shm-usage"])
        ctx=await browser.new_context(locale="ko-KR",timezone_id="Asia/Seoul",viewport={"width":1550,"height":1050})
        for name,path in PAGES:
            page=await ctx.new_page()
            action[0]="initial"
            page.on("response",lambda resp,nam=name,act=action: handler(resp,nam,act))
            try:
                response=await page.goto(ROOT+path,wait_until="domcontentloaded",timeout=32000)
                await page.wait_for_timeout(4700)
                pages.append({"page":name,"path":path,"http":response.status if response else None,"title":await page.title()})
                await take(page,name,"initial",records)
                # Dropdowns using title, visible text and accessibility roles,
                # plus every initial top filter and every 12 column preset tab.
                probes=[
                 ("switch_screener",("exact","스탁 스크리너")),
                 ("screen_management",("text","올 스탁")),
                 ("region",("exact","KR")),
                 ("settings",("title","스크리너 세팅")),
                 ("view_selector",("exact","테이블")),
                 ("filters_add",("title","새 필터 넣기")),
                 ("filter_reset",("title","재설정 옵션")),
                 ("column_setup",("title","컬럼 셋업")),
                 ("watchlist",("exact","왓치리스트")),
                 ("index",("exact","지수")),
                 ("price",("exact","가격")),
                 ("change_pct",("exact","체인지 %")),
                 ("market_cap",("exact","시가총액")),
                 ("pe_ratio",("exact","P/E")),
                 ("eps_growth",("exact","EPS 희석 성장")),
                 ("dividend",("exact","배당 수익 %")),
                 ("sector",("exact","섹터")),
                 ("analyst",("exact","애널리스트 평점")),
                 ("performance",("exact","퍼포먼스 %")),
                 ("revenue_growth",("exact","매출 성장률")),
                 ("peg",("exact","PEG")),
                 ("roe",("exact","ROE")),
                 ("beta",("exact","베타")),
                 ("earnings_prev",("exact","최근 실적 발표날짜")),
                 ("earnings_next",("exact","다가올 실적 발표날짜")),
                 ("column_more",("css",'button:has-text("더보기")')),
                ]
                if name!="주식":probes=probes[:10] + [("filter_add_any",("title","새 필터 넣기"))]
                for a,loc in probes:
                    action[0]=a
                    await click_probe(page,name,loc,records,a)
                    if a=="filters_add":
                        # Capture scrollable options in picker; this can contain the entire field catalog.
                        try:
                            loc=page.locator('button[title="새 필터 넣기"]')
                            if await loc.count():
                                await loc.first.click(timeout=2500)
                                for step in range(0,7):
                                    await take(page,name,f"filters_add_scroll_{step}",records)
                                    await page.mouse.wheel(0,950)
                                    await page.wait_for_timeout(200)
                                await page.keyboard.press("Escape")
                        except Exception:pass
                if name=="주식":
                    for tab in ["오버뷰","성과","테크니컬즈","확장 시간","전망","평가","배당","수익성","손익 계산서","대차 대조표","현금 흐름","주당"]:
                        action[0]="preset_"+tab
                        await click_probe(page,name,("css",'button[role="tab"]:has-text('+json.dumps(tab)+')'),records,"preset_"+tab)
                    for key,title in (("refresh","리프레쉬"),("maximize","최대화"),("column_add","컬럼 셋업")):
                        action[0]=key
                        await click_probe(page,name,("title",title),records,key)
                print("PAGE",name,"snapshots",sum(1 for rec in records if rec.get("page")==name),
                       "last_url",page.url,"events",sum(1 for ev in EVENTS if ev.get("page")==name),flush=True)
            except Exception as exc:
                pages.append({"page":name,"error":str(exc)[:350]})
            finally:
                await page.close()
        await browser.close()
    (OUT/"pages.json").write_text(json.dumps(pages,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"menu_snapshots.json").write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"fetch_endpoints.json").write_text(json.dumps(EVENTS,ensure_ascii=False,indent=2),encoding="utf-8")
    print("DONE pages",len(pages),"snapshots",len(records),"events",len(EVENTS),flush=True)
    for sn in records:
        if sn.get("page")=="주식" and sn.get("action") in ("switch_screener","screen_management","region","settings","view_selector","filters_add","filter_reset","column_setup","price","sector","column_more"):
            visible=[x.get("text") or x.get("aria") or x.get("title") for x in sn.get("elements",[]) if x.get("role") in ("option","menuitem","radio","checkbox")]
            print("MENU",sn["action"],"options",len(visible),"examples",json.dumps(visible[:25],ensure_ascii=False),flush=True)
if __name__=="__main__":asyncio.run(main())
