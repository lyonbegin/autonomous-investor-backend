"""Unmocked production preview browser check against actual Railway + Yahoo."""
import os
from playwright.sync_api import sync_playwright, expect
BASE=os.environ["MARKETS_LIVE_URL"].rstrip("/")
def run():
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page(viewport={"width":1365,"height":900})
        errors=[]
        page.on("pageerror",lambda e:errors.append(str(e)))
        response=page.goto(BASE,wait_until="domcontentloaded",timeout=30000)
        assert response and response.status==200, response
        expect(page.locator("section.section")).to_have_count(10,timeout=20000)
        # The app must receive real live-provider response, not a fixture.
        api=page.request.get(BASE+"/api/markets/ohlcv?symbol=NASDAQ%3AMSFT&period=1M",timeout=20000)
        body=api.json()
        assert api.status==200 and body.get("status")=="OK",body
        assert body.get("source")=="Yahoo Finance chart API"
        assert body.get("bar_count",0)>=3
        expect(page.locator("#chart-world svg")).to_have_count(1,timeout=25000)
        expect(page.locator("#chart-world .small")).to_contain_text("Yahoo Finance")
        page.locator("#world .periods button",has_text="1Y").click()
        expect(page.locator("#chart-world svg")).to_have_count(1,timeout=25000)
        page.locator("#find").fill("한국 주식")
        expect(page.locator("section.section")).to_have_count(1)
        assert not errors,errors
        print("PASS LIVE Railway Chromium: HTTP200, real market API",body["bar_count"],"bars, SVG chart, 1Y switch, market search; errors=0",flush=True)
        browser.close()
if __name__=="__main__":run()
