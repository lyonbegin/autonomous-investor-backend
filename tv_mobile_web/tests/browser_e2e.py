"""Real browser interaction scenarios; mocked source responses are TEST FIXTURES ONLY.

Screenshots are of the independently implemented web app, never represented
as a pixel comparison with the Android application.
"""
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE=os.getenv("MOBILE_LAB_BASE","http://127.0.0.1:8855")
SHOTS=Path(os.getenv("MOBILE_LAB_EVIDENCE","/tmp/mobile-app-lab-evidence"))
SHOTS.mkdir(parents=True,exist_ok=True)


def main():
    fixture={
        "market":"korea","items":[
            {"ticker":"KRX:005930","name":"Samsung Electronics",
             "description":"테스트용 스캐너 응답","close":123456.0,
             "change":1.25,"volume":2000,"exchange":"KRX"},
            {"ticker":"KRX:000660","name":"SK hynix",
             "description":"테스트용 스캐너 응답","close":234567.0,
             "change":-0.45,"volume":3000,"exchange":"KRX"}
        ],"total_count":2,"offset":0,"limit":40,
        "source":"browser-ci-fixture","complete_universe_verified":False,
        "price_history_verified":False
    }
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        page=browser.new_page(viewport={"width":390,"height":844},
                             device_scale_factor=1)
        bad=[]
        page.on("pageerror",lambda e:bad.append(str(e)))
        def route_market(route):
            route.fulfill(status=200,content_type="application/json",
                          body=json.dumps(fixture))
        page.route("**/api/markets/*",route_market)
        page.route("https://s3.tradingview.com/**",
                   lambda route:route.fulfill(status=200,content_type="text/javascript",body=""))
        page.goto(BASE,wait_until="domcontentloaded")
        page.locator("#marketContent .stocks-table tbody tr").first.wait_for()
        assert page.locator("#desktopDomains .domain-link").count()==26
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
