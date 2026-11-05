"""Provider contract: true bars from external response; no made-up market prices."""
import importlib.util
import io
import json
import pathlib
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

PATH=pathlib.Path(__file__).resolve().parents[1] / "markets-preview" / "server.py"
spec=importlib.util.spec_from_file_location("market_preview_server",PATH)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class Response:
    def __init__(self,data):
        self.data=json.dumps(data).encode("utf-8")
    def __enter__(self): return self
    def __exit__(self,*a): return False
    def read(self,n):return self.data

class MarketAPITest(unittest.TestCase):
    def setUp(self): module.CACHE.clear()
    def test_provider_maps_real_ohlc_and_asof(self):
        data={"chart":{"result":[{"timestamp":[100,200,300],"meta":{"currency":"USD","exchangeTimezoneName":"America/New_York"},"indicators":{"quote":[{"open":[10,11,12],"high":[13,14,15],"low":[9,10,11],"close":[12,13,14],"volume":[100,200,300]}]}}]}}
        with patch.object(module.urllib.request,"urlopen",return_value=Response(data)) as request:
            code,result=module.get_chart("NASDAQ:MSFT","1M")
        self.assertEqual(code,200)
        self.assertEqual(result["status"],"OK")
        self.assertEqual(result["bar_count"],3)
        self.assertEqual(result["latest_close"],14)
        self.assertEqual(result["asof_utc"],300)
        self.assertFalse(result["quote_realtime_verified"])
        self.assertEqual(result["bars"][1]["h"],14)
        self.assertIn("MSFT",request.call_args.args[0].full_url)
        with patch.object(module.urllib.request,"urlopen") as no_fetch:
            code,again=module.get_chart("NASDAQ:MSFT","1M")
        no_fetch.assert_not_called()
        self.assertEqual(again["cache"],"HIT")
    def test_rejects_unknown_symbol_before_network(self):
        with patch.object(module.urllib.request,"urlopen") as fetch:
            code,result=module.get_chart("https://localhost/internal","5Y")
        self.assertEqual(code,422)
        self.assertEqual(result["status"],"UNSUPPORTED_SYMBOL")
        fetch.assert_not_called()
    def test_provider_failure_is_not_replaced_by_fabricated_prices(self):
        exc=HTTPError("https://query1.finance.yahoo.com",429,"rate limited",{},None)
        with patch.object(module.urllib.request,"urlopen",side_effect=exc):
            code,result=module.get_chart("NASDAQ:MSFT","1D")
        self.assertEqual(code,503)
        self.assertEqual(result["status"],"DATA_UNAVAILABLE")
        self.assertNotIn("bars",result)
    def test_timeframe_contract(self):
        self.assertEqual(module.PERIODS["5Y"],("5y","1d"))
        self.assertEqual(module.PERIODS["1D"],("5d","5m"))

if __name__=="__main__":unittest.main()
