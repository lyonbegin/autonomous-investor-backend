import unittest
from keypoint_parity import compare_keypoints

def csv(rows):
    return "time,open,high,low,close,RSI,signal,stop\n"+"\n".join(rows)+"\n"

class KeypointDiffTests(unittest.TestCase):
    def setUp(self):
        self.tv=csv(["2026-01-01T00:00:00Z,100,105,98,102,51,ENTRY,98",
                     "2026-01-01T01:00:00Z,102,109,101,105,63,EXIT,99"])
    def test_exact_data_and_signals_require_visual_review(self):
        r=compare_keypoints(self.tv,self.tv)
        self.assertEqual(r["status"],"KEYPOINTS_MATCH_REVIEW_REQUIRED")
        self.assertTrue(r["numeric_match"])
        self.assertFalse(r["verified"])
        self.assertEqual(r["aligned_bars"],2)
    def test_action_delta_prioritized_for_visual_focus(self):
        changed=self.tv.replace(",63,EXIT,99",",63,ENTRY,99")
        r=compare_keypoints(self.tv,changed)
        self.assertEqual(r["status"],"KEYPOINTS_DIFFER")
        self.assertEqual(r["keypoints"][0]["group"],"ORDER_OR_SIGNAL")
        self.assertEqual(r["keypoints"][0]["field"],"signal")
    def test_price_differences_never_allow_pass(self):
        changed=self.tv.replace(",105,63,EXIT",",108,63,EXIT")
        r=compare_keypoints(self.tv,changed)
        self.assertFalse(r["numeric_match"])
        self.assertEqual(r["keypoints"][0]["group"],"OHLC")
    def test_misaligned_date_range_is_blocked(self):
        changed=self.tv.replace("2026-01-01T01:00:00Z","2026-01-01T02:00:00Z")
        r=compare_keypoints(self.tv,changed)
        self.assertEqual(r["status"],"BLOCKED_OHLC_TIMESET_MISMATCH")
        self.assertFalse(r["verified"])
    def test_no_plot_or_trade_export_is_not_full_parity(self):
        tv="time,open,high,low,close\n2026-01-01T00:00:00Z,1,2,0.5,1.5\n"
        r=compare_keypoints(tv,tv)
        self.assertEqual(r["status"],"KEYPOINTS_PARTIAL_NO_ORDER_OR_PLOT_EXPORT")
        self.assertFalse(r["numeric_match"])
    def test_duplicate_timestamps_block(self):
        r=compare_keypoints(self.tv,self.tv+self.tv.splitlines()[1]+"\n")
        self.assertEqual(r["status"],"CSV_DUPLICATE_BAR_TIMESTAMP")
if __name__=="__main__":unittest.main()
