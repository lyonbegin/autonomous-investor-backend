"""Check N03 external snapshot selection, not author/hash verification."""
import csv
import io
import unittest
from unittest.mock import patch
from licensed_strategy_manifest import catalog_from_snapshot

HEADER="id,kind,name,pine_version,script_version,tv_url,fetched_at\n"
def row(i,kind="strategy",url=None):
    return f"PUB;{i:08d},{kind},Test {i},6,1.0,{url or f'https://www.tradingview.com/script/{i:08d}/'},2026-10-02\n"

class SnapshotTests(unittest.TestCase):
    def test_actual_source_rows_and_pages(self):
        rows=list(csv.DictReader(io.StringIO(HEADER+''.join(row(i) for i in range(1,61)))))
        with patch("licensed_strategy_manifest.fetch_manifest",return_value=rows):
            first=catalog_from_snapshot(kind="strategy",page=1,page_size=50,sort="recent_extended")
            second=catalog_from_snapshot(kind="strategy",page=2,page_size=50,sort="recent_extended")
        self.assertEqual(first["count"],50)
        self.assertEqual(second["count"],10)
        self.assertFalse(first["catalog_is_live"])
        self.assertNotIn("manifest_sha256",first)
        self.assertNotIn("author",first["items"][0])
        self.assertNotIn("source_sha256_reported",first["items"][0])

    def test_unsupported_library_and_bad_url(self):
        with self.assertRaisesRegex(ValueError,"STRATEGIES_ONLY"):
            catalog_from_snapshot(kind="library",page=1,page_size=50,sort="recent_extended")
        rows=list(csv.DictReader(io.StringIO(HEADER+row(1,url="https://evil.example/script/11111111/")+row(2))))
        with patch("licensed_strategy_manifest.fetch_manifest",return_value=rows):
            got=catalog_from_snapshot(kind="strategy",page=1,page_size=5,sort="recent_extended")
        self.assertEqual(got["count"],1)

if __name__=="__main__":unittest.main()
