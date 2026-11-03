import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from official_ddds_trades import parse_visible_trade

REAL_PUBLICATION_ROW = """299Short
Exit
Entry
Oct 19, 2026, 13:30
Oct 16, 2026, 17:30
255.60
USD
250.04
USD
113
28.25 KUSD
−656.85
USD
−2.32%"""

class PublishedDDDSParseTest(unittest.TestCase):
    def test_real_published_299_two_line_trade(self):
        row=parse_visible_trade(REAL_PUBLICATION_ROW)
        self.assertEqual(row["trade_number"],299)
        self.assertEqual(row["side"],"SHORT")
        self.assertEqual(row["entry_time_display"],"Oct 16, 2026, 17:30")
        self.assertEqual(row["exit_time_display"],"Oct 19, 2026, 13:30")
        self.assertEqual(row["entry_price_display"],250.04)
        self.assertEqual(row["exit_price_display"],255.60)
        self.assertEqual(row["quantity_display"],113)
        self.assertEqual(row["net_pnl_display"],-656.85)
        self.assertEqual(row["return_percent_display"],-2.32)
        self.assertEqual(row["time_zone"],"NOT_DECLARED_IN_PUBLISHED_ROW")
    def test_never_make_up_a_nontrade(self):
        self.assertIsNone(parse_visible_trade("Trade number Type Date Price"))
        self.assertIsNone(parse_visible_trade("1000Long Exit Entry"))
    def test_short_row_is_partial_not_fabricated(self):
        row=parse_visible_trade("1Long\nExit\nEntry")
        self.assertEqual(row["trade_number"],1)
        self.assertIsNone(row["entry_price_display"])
        self.assertIsNone(row["entry_time_display"])
if __name__=="__main__":unittest.main()
