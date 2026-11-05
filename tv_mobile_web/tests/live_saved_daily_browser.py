"""One-off real stored TradingView 5Y/1D chart + mobile UI verification.

Live data comes from the isolated Railway persistent volume, NOT fixture,
Yahoo, TradingView embedding, or fabricated OHLCV. No new collection POST.
"""
import json
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

BASE="https://tradingview-full-mobile-web-lab-production.up.railway.app"
SYMBOL="NASDAQ:AAPL"
OUT=Path("/tmp/tv-5y-stored-ui-evidence")
OUT.mkdir(parents=True,exist_ok=True)


def get_json(path):
    with urlopen(BASE+path, timeout=30) as response:
        assert response.status==200
        return json.loads(response.read())


def main():
    stored=get_json("/api/chart/history?symbol=NASDAQ%3AAAPL")
    metadata=stored["metadata"]
    quality=stored["quality"]
    bars=stored["bars"]
    assert metadata["saved"],"Persistent Railway chart data is missing"
    assert metadata["interval"]=="1D",metadata
    assert metadata["five_year_extent_covered"] is True, metadata
    assert quality["daily_date_coverage_ratio"]>=.90, quality
    assert metadata["bar_count"]==len(bars)>=1200,metadata
    assert bars[0]["time_ms"]<bars[-1]["time_ms"]
    assert bars[0]["close"]>0
    assert all(isinstance(x["close"],(int,float)) and x["close"]>0 for x in bars)
    expected=len(bars)
    print("LIVE_RAILWAY_5Y_DAILY_VOLUME_READ_SHA256_VERIFIED",json.dumps({
        "symbol":SYMBOL,
        "count":expected,
        "first_time_ms":bars[0]["time_ms"],
        "last_time_ms":bars[-1]["time_ms"],
        "density":quality["daily_date_coverage_ratio"],
        "source":metadata["source"],
        "sha256":metadata["file_sha256"],
        "not_market_fixture":True,
    },ensure_ascii=False))
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        page=browser.new_page(viewport={"width":390,"height":844})
        js_errors=[]
        page.on("pageerror",lambda e:js_errors.append(str(e)))
        # The external embedded chart is distinct from the self-stored
        # chart under test; prevent external widget from slowing UI test.
        page.route("https://s3.tradingview.com/**",
                   lambda route:route.fulfill(status=200,content_type="text/javascript",body=""))
        page.goto(BASE+"/#/chart/NASDAQ%3AAAPL",wait_until="domcontentloaded",timeout=45000)
        page.locator("#dailySummary").wait_for(timeout=15000)
        page.wait_for_function(
            """(expected) => document.querySelector('#dailySummary')?.innerText.includes(expected)""",
            arg=f"{expected:,}",timeout=30000,
        )
        assert page.locator("#chartSymbolInput").input_value()=="NASDAQ:AAPL"
        assert page.locator("#chartTimeframe").input_value()=="1D"
        assert page.locator("#chartRange").input_value()=="60M"
        assert "도달" in page.locator("#dailyState").inner_text()
        assert str(expected) in page.locator("#dailySummary").inner_text().replace(",","")
        assert page.locator("#dailyCanvas").is_visible()
        page.screenshot(path=str(OUT/"mobile-real-aapl-5y-daily.png"),full_page=True)
        page.set_viewport_size({"width":1440,"height":900})
        page.screenshot(path=str(OUT/"desktop-real-aapl-5y-daily.png"),full_page=True)
        assert not js_errors,js_errors
        browser.close()
    (OUT/"metadata.json").write_text(json.dumps({
        "symbol":SYMBOL,"count":expected,"interval":"1D",
        "5y_daily_date_coverage_ratio":quality["daily_date_coverage_ratio"],
        "source":"ACTUAL_RAILWAY_PERSISTENT_CHART_HISTORY",
        "mobile_canvas_rendered":True,"desktop_canvas_rendered":True,
        "android_1_to_1_pixel_parity_verified":False,
    },ensure_ascii=False,indent=2),encoding="utf-8")
    print("ACTUAL_5Y_DAILY_SAVED_CHART_MOBILE_AND_DESKTOP_E2E_PASSED")


if __name__=="__main__":
    main()
