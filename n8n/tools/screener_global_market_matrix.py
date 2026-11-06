#!/usr/bin/env python3
"""Minimal, observational stock/ETF scan for each market code seen in captured
TradingView ETF global/metainfo payload. No auth, no bulk pagination, no bypass.
One symbol maximum per product/market; stop on 403/429.
"""
import asyncio, csv, datetime as dt, json, pathlib
from playwright.async_api import async_playwright

MARKETS = "america argentina australia austria bahrain bangladesh belgium bulgaria brazil canada chile china colombia croatia cyprus czech denmark egypt estonia finland france germany greece hongkong hungary iceland india indonesia ireland israel italy japan kenya kuwait latvia lithuania luxembourg malaysia mexico morocco netherlands newzealand nigeria norway pakistan peru philippines poland portugal qatar romania russia ksa serbia singapore slovakia slovenia rsa korea spain srilanka sweden switzerland taiwan thailand tunisia turkey uae uk venezuela vietnam".split()
OUT = pathlib.Path("global_market_matrix")
OUT.mkdir(exist_ok=True)
PRODUCTS = [
    ("stock", "주식", "https://kr.tradingview.com/screener/", "korea"),
    ("etf", "ETF", "https://kr.tradingview.com/etf-screener/", "america"),
]
results=[]
errors=[]
def utc(): return dt.datetime.now(dt.timezone.utc).isoformat()

async def run_product(browser, product, label, url, expected):
    ctx=await browser.new_context(locale="ko-KR",timezone_id="Asia/Seoul",
        viewport={"width":1400,"height":900})
    page=await ctx.new_page()
    baseline=[]
    def on_request(req):
        if "/scan?" in req.url and ("label-product=screener-"+product) in req.url:
            try:
                baseline.append({"url":req.url,"json":json.loads(req.post_data or "{}")})
            except Exception as exc:
                errors.append({"product":product,"stage":"baseline","error":str(exc)[:160]})
    page.on("request",on_request)
    try:
        resp=await page.goto(url,wait_until="domcontentloaded",timeout=60000)
        await page.wait_for_timeout(5500)
        if not baseline:
            errors.append({"product":product,"stage":"baseline","status":resp.status if resp else None,"error":"initial scan not seen"})
            return
        base=baseline[0]["json"]
        print("BASELINE",product,resp.status if resp else None,
              "markets",base.get("markets"),"columns",len(base.get("columns",[])),
              "initial_url",baseline[0]["url"],flush=True)
        for i,market in enumerate(MARKETS):
            endpoint=f"https://scanner.tradingview.com/{market}/scan?label-product=screener-{product}"
            req=dict(base)
            req["markets"]=[market]
            req["range"]=[0,1]
            now=utc()
            try:
                reply=await page.evaluate(r"""async ({url,payload}) => {
                    const started=performance.now();
                    try {
                        const resp=await fetch(url,{method:"POST",mode:"cors",credentials:"omit",
                            headers:{"content-type":"application/json"},body:JSON.stringify(payload)});
                        let body=null;let is_json=false;
                        try {body=await resp.json();is_json=true;} catch(e) {}
                        return {status:resp.status,elapsed_ms:Math.round(performance.now()-started),
                            is_json,totalCount:body?.totalCount??null,
                            rows:Array.isArray(body?.data)?body.data.length:null,
                            first_symbol:Array.isArray(body?.data)&&body.data.length?body.data[0]?.s:null,
                            response_keys:body&&typeof body==="object"?Object.keys(body).slice(0,20):[],
                            error:null};
                    } catch(e) {
                        return {status:null,elapsed_ms:Math.round(performance.now()-started),
                            is_json:false,error:String(e).slice(0,180)};
                    }
                }""",{"url":endpoint,"payload":req})
            except Exception as exc:
                reply={"status":None,"error":type(exc).__name__+": "+str(exc)[:180]}
            row={"product":product,"market":market,"url":endpoint,"method":"POST",
                "captured_at_utc":now,"range":[0,1],
                "request_markets":[market],"request_columns":len(req.get("columns",[])),**reply}
            results.append(row)
            print(product,market,"HTTP",reply.get("status"),"total",reply.get("totalCount"),
                  "rows",reply.get("rows"),"error",reply.get("error"),flush=True)
            if reply.get("status") in (403,429):
                errors.append({"product":product,"market":market,"stage":"stop","status":reply["status"]})
                break
            await page.wait_for_timeout(500)
    except Exception as exc:
        errors.append({"product":product,"stage":"run","error":str(exc)[:360]})
    finally:
        await ctx.close()

async def main():
    assert len(MARKETS)==71, f"expected 71 markets, found {len(MARKETS)}"
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(headless=True,args=["--no-sandbox","--disable-dev-shm-usage"])
        try:
            for product,label,url,expected in PRODUCTS:
                await run_product(browser,product,label,url,expected)
        finally:
            await browser.close()
    status={}
    for product,*_ in PRODUCTS:
        subset=[r for r in results if r["product"]==product]
        status[product]={"tested":len(subset),"http_200":sum(r.get("status")==200 for r in subset),
            "nonempty":sum(r.get("status")==200 and isinstance(r.get("totalCount"),int)
                          and r.get("totalCount")>0 for r in subset),
            "http_errors":[{"market":r["market"],"status":r["status"],"error":r.get("error")}
                for r in subset if r.get("status")!=200]}
    output={"captured_at_utc":utc(),"source":"2026-11-06 ETF global/metainfo markets",
        "market_count":len(MARKETS),"stop_on_403_or_429":True,
        "scope":"first-row-only public scan; never verifies full-history or bulk access",
        "summary":status,"errors":errors,"records":results}
    (OUT/"all_market_scan_results.json").write_text(
        json.dumps(output,ensure_ascii=False,indent=2),encoding="utf-8")
    with (OUT/"all_market_scan_results.csv").open("w",newline="",encoding="utf-8-sig") as f:
        columns=["product","market","status","totalCount","rows","first_symbol",
                 "url","method","elapsed_ms","error","captured_at_utc"]
        writer=csv.DictWriter(f,fieldnames=columns,extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    print("SUMMARY",json.dumps(status,ensure_ascii=False),flush=True)
    print("ERRORS",json.dumps(errors,ensure_ascii=False),flush=True)
    if not results:raise SystemExit("No market scan requests captured")

if __name__=="__main__":
    asyncio.run(main())
