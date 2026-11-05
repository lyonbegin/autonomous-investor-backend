"""Chromium E2E: user selections update a real plotted chart, not an inert iframe."""
import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect

ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA={"status":"OK","source":"SYNTHETIC_TEST_FIXTURE","bar_count":30,"interval":"1d","currency":"USD","asof_utc":1760000000,"latest_close":102,"bars":[]}
for i in range(30):
    price=100+i%7
    DATA["bars"].append({"t":1757500000+i*86400,"o":price,"c":price+1,"h":price+2,"l":price-1,"v":5000+i})
DATA["asof_utc"]=DATA["bars"][-1]["t"];DATA["latest_close"]=DATA["bars"][-1]["c"]

def main():
    with tempfile.TemporaryDirectory() as temp:
        folder=pathlib.Path(temp)
        shutil.copy(ROOT/"admin-console"/"markets.html",folder/"index.html")
        shutil.copy(ROOT/"admin-console"/"markets-chart.js",folder/"markets-chart.js")
        shutil.copy(ROOT/"markets-preview"/"server.py",folder/"server.py")
        sock=socket.socket();sock.bind(("127.0.0.1",0));port=sock.getsockname()[1];sock.close()
        env={**os.environ,"PORT":str(port),"MARKETS_PROBE_ON_START":"0"}
        proc=subprocess.Popen([sys.executable,"server.py"],cwd=folder,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            for attempt in range(40):
                try:
                    with urlopen(f"http://127.0.0.1:{port}/health",timeout=1) as r:
                        assert json.load(r)["status"]=="ok"
                    break
                except Exception: time.sleep(.2)
            else: raise AssertionError("preview server failed healthcheck")
            with sync_playwright() as pw:
                browser=pw.chromium.launch(headless=True)
                page=browser.new_page(viewport={"width":1365,"height":850})
                errors=[]
                page.on("pageerror", lambda e: errors.append(str(e)))
                calls=[]
                def route_market(route):
                    calls.append(route.request.url)
                    route.fulfill(status=200,content_type="application/json",body=json.dumps(DATA))
                page.route("**/api/markets/ohlcv?**",route_market)
                page.goto(f"http://127.0.0.1:{port}/",wait_until="domcontentloaded")
                expect(page.locator("section.section")).to_have_count(10)
                expect(page.locator("#chart-world svg")).to_have_count(1,timeout=12000)
                expect(page.locator("#world .symbol").first.locator(".empty-price")).to_contain_text("USD")
                page.locator("#world .symbol").nth(1).click()
                expect(page.locator("#world .symbol").nth(1)).to_have_attribute("aria-pressed","true")
                expect(page.locator("#chart-world svg")).to_have_count(1)
                page.locator("#world .periods button",has_text="1Y").click()
                expect(page.locator("#chart-world svg")).to_have_count(1)
                assert any("period=1Y" in u for u in calls),calls
                page.locator("#kr .item").first.click()
                expect(page.locator("#detail")).to_have_class("detail open")
                page.locator("#close").click()
                expect(page.locator("#detail")).to_have_class("detail")
                page.locator("#find").fill("회사채")
                expect(page.locator("section.section")).to_have_count(1)
                expect(page.locator("section.section h2")).to_have_text("회사채")
                assert not errors,errors
                page.locator("#find").fill("")
                page.screenshot(path=str(folder/"markets-pass.png"),full_page=True)
                print("PASS Chromium: sections=10; chart real-data draw; click symbol; period; details; search; JS exceptions=0")
                # Provider failure must yield explicit official embed fallback and deep link.
                blocked=browser.new_page()
                blocked.route("**/api/markets/ohlcv?**",lambda route:route.fulfill(status=503,content_type="application/json",body=json.dumps({"status":"DATA_UNAVAILABLE","reason":"provider_http_429"})))
                blocked.route("**/s3.tradingview.com/**",lambda route:route.abort())
                blocked.goto(f"http://127.0.0.1:{port}/",wait_until="domcontentloaded")
                expect(blocked.locator("#chart-world a")).to_contain_text("원본 차트로 이동",timeout=12000)
                print("PASS Chromium: provider failure displays official embed attempt and usable direct link")
                browser.close()
        finally:
            proc.terminate()
            try:proc.wait(timeout=3)
            except subprocess.TimeoutExpired:proc.kill()

if __name__=="__main__":main()
