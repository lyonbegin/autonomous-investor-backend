import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"editor-adapter"))
import investment_tv_publication as tv


class PublishedStrategyReferenceTest(unittest.TestCase):
    def test_bundled_actual_user_ddds_source_is_complete_and_pinned(self):
        ref=tv.bundled_ddds_reference()
        pine=ref["pine_source"]
        self.assertEqual(ref["source_line_count"],141)
        self.assertEqual(ref["source_sha256"],hashlib.sha256(pine.encode()).hexdigest())
        self.assertTrue(pine.startswith("// This Pine Script"))
        self.assertIn('strategy("Displaced Donchian Decycler Strategy"',pine)
        self.assertIn('strategy.entry("Long"',pine)
        self.assertIn('strategy.exit("Short Exit"',pine)
        self.assertEqual(ref["source_rights"],"MPL-2.0")
        self.assertEqual(ref["chart_id"],"LkgKT3TG")
        self.assertIn("88/299"," ".join(ref["report_key_facts"]))
        self.assertFalse(ref["tradingview_pynecore_strategy_parity_verified"])
        self.assertFalse(ref["strategy_orders_extracted"])

    def test_real_dom_structure_parse_extracts_pine_and_report_without_js_execution(self):
        source=tv.bundled_ddds_reference()["pine_source"]
        body="<br/>".join("<span>"+line.replace("&","&amp;").replace("<","&lt;")+"</span>"
                          for line in source.split("\n"))
        html=("<div data-name='publication-view-chart-container'>"
              "<div data-qa-id='legend-source-item'>DDDS</div>"
              "<div data-qa-id='title-wrapper legend-source-title'>Amazon.com, Inc.</div>"
              "<div data-qa-id='title-wrapper legend-source-interval'>2시</div></div>"
              "<img src='https://s3.tradingview.com/l/LkgKT3TG_mid.webp'/>"
              "<div data-qa-id='backtesting-static'>"
              "<div data-strategy-title='DDDS 보고서'></div>"
              "<div data-qa-id='strategy-key-facts'>"
              "<div class='containerCell-dJrHEJrZ'>총 PnL +17,961.73 USD</div></div>"+
              "".join("<button role='tab' id='"+tab+"'>"+tab+"</button>"
                      for tab in ("Overview","Performance","Trades Analysis","Ratios","List of Trades","Properties"))+
              "</div><a href='/pine/?id=PUB;5442675d418140c58486eb4a7ae12768'>코드</a>"
              "<div class='monaco-editor-tv-pine-light'>"+body+"</div>")
        result=tv.parse_publication_html(html)
        self.assertEqual(result["status"],"TRADINGVIEW_PUBLISHED_STRATEGY_REFERENCE_PARSED")
        self.assertEqual(result["source_line_count"],141)
        self.assertEqual(result["source_sha256"],tv.bundled_ddds_reference()["source_sha256"])
        self.assertEqual(result["source_id"],"PUB;5442675d418140c58486eb4a7ae12768")
        self.assertEqual(result["chart_id"],"LkgKT3TG")
        self.assertTrue(result["published_strategy_report_present"])
        self.assertFalse(result["python_execution_complete"])
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            tv.save_reference("sid-1",result,root)
            self.assertEqual(tv.latest_reference("sid-1",root)["source_sha256"],result["source_sha256"])
            self.assertEqual(tv.latest_reference("sid-2",root)["chart_id"],"LkgKT3TG")

    def test_reject_lacking_real_published_strategy_report(self):
        html="<html><div class='monaco-editor-tv-pine-light'>//@version=6<br/>strategy(\"Other\")</div></html>"
        with self.assertRaisesRegex(ValueError,"TRADINGVIEW_PUBLISHED_STRATEGY_CHART_REPORT_SOURCE_NOT_FOUND"):
            tv.parse_publication_html(html)

if __name__=="__main__":
    unittest.main()
