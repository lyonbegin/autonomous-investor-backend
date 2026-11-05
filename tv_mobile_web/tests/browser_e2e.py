"""Real browser interaction scenarios; mocked source responses are TEST FIXTURES ONLY.

Screenshots are of the independently implemented web app, never represented
as a pixel comparison with the Android application.
"""
import json
import os
from urllib.parse import urlparse,parse_qs
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE=os.getenv("MOBILE_LAB_BASE","http://127.0.0.1:8855")
SHOTS=Path(os.getenv("MOBILE_LAB_EVIDENCE","/tmp/mobile-app-lab-evidence"))
SHOTS.mkdir(parents=True,exist_ok=True)


def main():
    # Test-only stubs generate exactly the requested 10 records,
    # and verify frontend never asks for the entire market catalog.
    first_symbols=["KRX:005930","KRX:000660"]+[
        f"KRX:T{i:06d}" for i in range(8)]
    api_calls=[]
    def page_from(route):
        args=parse_qs(urlparse(route.request.url).query)
        return int(args.get("page",[1])[0]),args
    def respond(route,body):
        route.fulfill(status=200,content_type="application/json",
                      body=json.dumps(body))
    def route_market(route):
        args=parse_qs(urlparse(route.request.url).query)
        offset=int(args.get("offset",[0])[0])
        limit=int(args.get("limit",[10])[0])
        api_calls.append(("market",offset,limit))
        assert limit==10,("Market request must be 10 rows",limit)
        symbols=first_symbols if offset==0 else [
            f"KRX:T{i:06d}" for i in range(offset,offset+10)]
        items=[{
            "ticker":sym,"description":"테스트용 스캐너 응답",
            "close":123456.0 if index==0 and offset==0 else 10000.0+offset+index,
            "change":1.25,"volume":2000,"exchange":"KRX"
        } for index,sym in enumerate(symbols)]
        respond(route,{"market":"korea","items":items,"total_count":2500,
                       "offset":offset,"limit":limit,"source":"browser-ci-fixture",
                       "complete_universe_verified":False,"price_history_verified":False})
    def route_countries(route):
        page,args=page_from(route)
        api_calls.append(("countries",page,10))
        assert "limit" not in args or args["limit"]==["10"]
        items=[{"iso2":f"Z{n%10}","iso3":"TST","name":f"Country {n:03d}"}
               for n in range((page-1)*10,min(249,page*10))]
        respond(route,{"items":items,"page":page,"page_size":10,"total_count":249,
                       "total_pages":25,"all_iso_country_count":249})
    def route_sources(route):
        page,args=page_from(route)
        limit=int(args.get("limit",[10])[0])
        api_calls.append(("sources",page,limit))
        assert limit==10
        items=[{"source_row":n+1,"display":f"Original Feed {n+1:03d}",
                "all_cells":[f"Original Feed {n+1:03d}","Costs"],
                "asset_type_candidate_ids":[]}
               for n in range((page-1)*10,min(417,page*10))]
        respond(route,{"items":items,"page":page,"page_size":10,
                       "total_matches":417,"total_source_rows":417,
                       "total_pages":42,"has_more":page<42,
                       "unclassified_row_count":417})
    def route_pages(route):
        page,args=page_from(route)
        limit=int(args.get("limit",[10])[0])
        api_calls.append(("pages",page,limit))
        assert limit==10
        items=[{"path":f"/markets/sample-{n+1:04d}/","label":f"Market {n+1:04d}",
                "status":"fetched"} for n in
               range((page-1)*10,min(2500,page*10))]
        respond(route,{"items":items,"page":page,"page_size":10,
                       "total_count":2500,"total_pages":250,"has_more":page<250,
                       "summary":{"fetched_pages":500,"pending_pages":2000,
                                  "failed_pages":0,"source_edges":1500}})

    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        page=browser.new_page(viewport={"width":390,"height":844},
                             device_scale_factor=1)
        bad=[]
        page.on("pageerror",lambda e:bad.append(str(e)))
        page.route("**/api/markets/*",route_market)
        page.route("**/api/taxonomy/countries?*",route_countries)
        page.route("**/api/taxonomy/sources?*",route_sources)
        page.route("**/api/taxonomy/pages?*",route_pages)
        page.route("https://s3.tradingview.com/**",
                   lambda route:route.fulfill(status=200,content_type="text/javascript",body=""))
        page.goto(BASE,wait_until="domcontentloaded")
        page.locator("#marketContent .stocks-table tbody tr").first.wait_for()
        assert page.locator("#desktopDomains .domain-link").count()==26
        try:
            page.locator("#worldAssetTabs .world-asset").first.wait_for(timeout=10000)
        except Exception:
            print("WORLD_MARKET_UI_DEBUG",{
                "panel": page.locator("#fullGlobalMarketCatalog").inner_text()[:1600],
                "catalog_response": page.request.get(BASE+"/api/taxonomy").status,
                "js_function": page.evaluate("typeof window.loadGlobalMarketsPanel"),
                "page_errors": bad,
            },flush=True)
            raise
        assert page.locator("#worldAssetTabs .world-asset").count()==9
        page.locator("#worldCountryList .world-country").first.wait_for()
        assert page.locator("#worldCountryList .world-country").count()==10
        page.locator("#worldFeedList .world-feed").first.wait_for(timeout=10000)
        page.locator("#worldGraphList .world-graph-node").first.wait_for(timeout=10000)
        assert page.locator("#worldFeedList .world-feed").count()==10
        assert page.locator("#worldGraphList .world-graph-node").count()==10
        # Country, provider and menu lists MUST NOT download all entries on load.
        assert all(n==10 for _,_,n in api_calls)
        # Pages 2, 3, 4 and direct page 234 are backed by independent HTTP calls.
        for number in (2,3,4):
            page.locator('#worldSourcesPanel [data-world-page="'+str(number)+'"]').first.click()
            page.wait_for_function("(n) => document.querySelector('#worldSourcesPanel .world-page-status')?.textContent?.startsWith(n+' /')",arg=str(number))
            assert page.locator("#worldFeedList .world-feed").count()==10
        assert ("sources",4,10) in api_calls
        page.locator('#worldPagesPanel .world-page-number').fill("234")
        page.locator('#worldPagesPanel button[type=submit]').click()
        page.wait_for_function("() => document.querySelector('#worldPagesPanel .world-page-status')?.textContent?.startsWith('234 /')")
        assert ("pages",234,10) in api_calls
        assert page.locator("#worldGraphList .world-graph-node").count()==10
        page.locator('#worldCountriesPanel [data-world-page="2"]').first.click()
        page.wait_for_function("() => document.querySelector('#worldCountriesPanel .world-page-status')?.textContent?.startsWith('2 /')")
        assert ("countries",2,10) in api_calls
        # Scanner supports a direct jump to page 234 without earlier requests.
        page.locator('#marketJumpForm input[name="page"]').fill("234")
        page.locator('#marketJumpForm button[type=submit]').click()
        page.wait_for_function("() => document.querySelector('#marketPager .world-page-status')?.textContent?.startsWith('234/')")
        assert ("market",2330,10) in api_calls
        assert page.locator("#marketContent .stocks-table tbody tr").count()==10
        page.locator('#marketPager [data-scanner-page="1"]').click()
        page.wait_for_function("() => document.querySelector('#marketPager .world-page-status')?.textContent?.startsWith('1/')")
        assert page.locator("#marketContent .stocks-table tbody tr").count()==10
        assert page.locator("[data-world-asset=options]").count()==1
        assert page.locator("[data-world-asset=economy]").count()==1
        assert page.locator("#fullGlobalMarketCatalog #worldFeedList").count()==1
        assert page.locator("#mobileNav .bottom-tab").count()==5
        assert "KRX:005930" in page.locator("#marketContent").inner_text()
        assert "123,456" in page.locator("#marketContent").inner_text()
        assert page.locator(".disclaimer").count()>=1
        page.screenshot(path=str(SHOTS/"01-mobile-market.png"),full_page=True)
        page.locator('[data-symbol="KRX:005930"]').first.click()
        assert page.locator("#chartSymbolInput").input_value()=="KRX:005930"
        assert page.locator("#chartTimeframe").input_value()=="1D"
        assert page.locator("#chartRange").input_value()=="60M"
        assert "우리 서버의 5년 일봉 저장 완료" in page.locator(".disclaimer").inner_text()
        page.screenshot(path=str(SHOTS/"02-mobile-chart.png"),full_page=True)
        page.locator("#chartWatch").click()
        page.locator('[data-nav="watchlist"]').last.click()
        assert "KRX:005930" in page.locator("#view").inner_text()
        page.locator("#newList").click()
        page.locator("#newListName").fill("국내 연구")
        page.locator('[data-modal-action="0"]').click()
        assert "국내 연구" in page.locator("#view").inner_text()
        page.screenshot(path=str(SHOTS/"03-mobile-watchlist.png"),full_page=True)
        page.locator("#alertsButton").click()
        page.locator("#newAlert").click()
        page.locator("#alertPrice").fill("125000")
        page.locator('[data-modal-action="0"]').click()
        assert "초안" in page.locator("#view").inner_text()
        page.locator('[data-nav="menu"]').last.click()
        assert "전체 339개 기능 원장" in page.locator("#view").inner_text()
        page.locator('[data-page="features"]').first.click()
        assert page.locator(".audit-group").count()==26
        assert "339" in page.locator(".audit-header").inner_text()
        page.locator("#auditDetail .choice-row").first.wait_for()
        assert page.locator("#auditDetail .choice-row").count()==10
        assert "TV-001" in page.locator("#auditDetail").inner_text()
        page.locator('#auditJump input[name="page"]').fill("34")
        page.locator('#auditJump button[type=submit]').click()
        assert page.locator("#auditDetail .choice-row").count()==9
        assert "TV-339" in page.locator("#auditDetail").inner_text()
        page.screenshot(path=str(SHOTS/"04-mobile-feature-audit.png"),full_page=True)
        page.locator("#globalSearchButton").click()
        page.locator("#searchTerm").fill("NASDAQ:AAPL")
        page.locator("#searchDirectChart").click()
        assert page.locator("#chartSymbolInput").input_value()=="NASDAQ:AAPL"
        page.locator("#accountButton").click()
        assert "계정" in page.locator("#view").inner_text()
        page.locator('[data-nav="menu"]').last.click()
        page.locator('[data-page="settings"]').first.click()
        page.locator("#themeSelect").select_option("dark")
        assert page.locator("html").get_attribute("data-theme")=="dark"
        page.screenshot(path=str(SHOTS/"05-mobile-dark-settings.png"),full_page=True)
        page.set_viewport_size({"width":1440,"height":900})
        page.locator('[data-nav="markets"]').first.click()
        page.locator("#marketContent .stocks-table tbody tr").first.wait_for()
        assert page.locator(".desktop-nav").is_visible()
        page.screenshot(path=str(SHOTS/"06-desktop-market.png"),full_page=True)
        assert bad==[],bad
        print("MOBILE_APP_PARITY_LAB_BROWSER_TESTS_PASSED")
        print("Explicit CI market fixtures used; not actual upstream data.")
        print("No Android pixel parity / 339 function completion claimed.")
        browser.close()

if __name__=="__main__":
    main()
