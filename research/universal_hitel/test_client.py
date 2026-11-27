"""Offline safety checks: no GitHub/HITEL network requests."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from . import stocktv_universal_client as c
except ImportError:
    import stocktv_universal_client as c


class UniversalStockConsumerTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {"record_id": "02yfhjiz", "order": 1, "title": "Complex Trade",
             "url": "https://www.tradingview.com/script/02yfhjiz-Complex-Trade/",
             "author": "Public", "description_preview": "sample", "source_type": "Strategy"},
            {"record_id": "03zgCMqx", "order": 2, "title": "Scalper",
             "url": "https://www.tradingview.com/script/03zgCMqx-Scalper/",
             "author": "Public", "description_preview": "sample", "source_type": "Strategy"},
        ]

    def test_mock_is_never_real_ai(self):
        p = c.project_json("stocktv-test-0001-0002", self.rows, 2, "mock", "", "pause")
        self.assertEqual(p["provider"], "mock")
        self.assertEqual(p["command"], "pause")
        self.assertEqual([r["record_id"] for r in p["records"]], ["02yfhjiz", "03zgCMqx"])

    def test_no_reuse_scribd_task(self):
        with self.assertRaises(ValueError):
            c.project_json("stocktv-test-0001-0002", self.rows, 2, "hitel", "scribd-18109", "pause")

    def test_prompt_limit_fail_closed(self):
        rows = [dict(self.rows[0], description_preview="X" * 25_000)]
        with self.assertRaises(ValueError):
            c.project_json("stocktv-test-0001-0001", rows, 1, "mock", "", "pause")

    def test_duplicate_source_id_and_order_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t) / "research" / "serial10"
            (root / "sources").mkdir(parents=True)
            (root / "source_manifest.json").write_text(json.dumps({
                "schema": "TV-STRATEGY-4428-SOURCE-20261108-v1",
                "original_count": 4428,
                "chunk_files": ["research/serial10/sources/strategies.jsonl"]}), "utf-8")
            record = {"order": 1, "id": "02yfhjiz", "title": "A",
                      "url": "https://www.tradingview.com/script/02yfhjiz-A/"}
            file = root / "sources" / "strategies.jsonl"
            file.write_text(json.dumps(record) + "\n" + json.dumps(record) + "\n", "utf-8")
            with self.assertRaises(ValueError):
                c.source_rows(root)

    def test_register_never_overwrites_existing(self):
        p = c.project_json("stocktv-test-0001-0002", self.rows, 2, "mock", "", "pause")
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / "project.json"
            f.write_text(c.canonical(p), "utf-8")
            with patch.object(c, "get_content", return_value=({"sha": "existing"}, b'{"different":true}')):
                with patch.object(c, "request", side_effect=AssertionError("MUST_NOT_WRITE")):
                    class Args: project_file = str(f)
                    with self.assertRaises(RuntimeError):
                        c.register(Args())


if __name__ == "__main__":
    unittest.main()
