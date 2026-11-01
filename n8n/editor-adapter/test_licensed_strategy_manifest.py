"""No synthetic data is ever accepted as production N03 success.

These unit tests use an in-memory CC-BY manifest fixture to validate schema,
provenance, pagination and refusal of unauthorized/malformed entries.
Real HTTPS integration is separately exercised by probe_real_chain.py.
"""
import io
import unittest
from unittest.mock import patch
from licensed_strategy_manifest import catalog_from_snapshot

HEADER="id,kind,name,author,pine_version,script_version,agree_count,license,sha256,tv_url,file,fetched_at,symbol,timeframe\n"
def item(n,date,kind="strategy",url=None):
    u=url or ("https://www.tradingview.com/script/%08d/"%n)
    return f"PUB;{n:08d},{kind},Strategy {n},RealAuthor,6,1.0,300,MPL-2.0,{'a'*64},{u},none.pine,{date},,\n"
def manifest():
    text=HEADER
    for i in range(110):
        text+=item(i+1,"2026-10-02" if i>50 else "2026-08-27")
    text+=item(123,"2026-10-03","indicator")
    return text

class ManifestContract(unittest.TestCase):
    def test_strategy_metadata_pagination_and_no_live_claim(self):
        with patch("licensed_strategy_manifest.fetch_manifest",return_value=(
             list(__import__("csv").DictReader(io.StringIO(manifest()))),"d"*64)):
            first=catalog_from_snapshot(kind="strategy",page=1,page_size=50,sort="recent_extended")
            second=catalog_from_snapshot(kind="strategy",page=2,page_size=50,sort="recent_extended")
            self.assertEqual(first["count"],50)
            self.assertEqual(first["total_count"],110)
            self.assertEqual(second["count"],50)
            self.assertEqual(len({x["source_id"] for x in first["items"]+second["items"]}),100)
            self.assertFalse(first["catalog_is_live"])
            self.assertFalse(first["latest_tradingview_verified"])
            self.assertFalse(first["pine_source_acquired"])
            self.assertIn("PyneSys",first["manifest_license"])
            self.assertEqual(first["items"][0]["published_at"],None)
            self.assertFalse(first["items"][0]["source_code_fetched"])
    def test_no_library_falsification(self):
        with self.assertRaisesRegex(ValueError,"STRATEGIES_ONLY"):
            catalog_from_snapshot(kind="library",page=1,page_size=5,sort="recent_extended")
    def test_invalid_link_or_hash_discarded(self):
        text=HEADER+item(1,"2026-10-02",url="https://evil.example/script/87654321/")+item(2,"2026-10-03")
        with patch("licensed_strategy_manifest.fetch_manifest",return_value=(
             list(__import__("csv").DictReader(io.StringIO(text))),"d"*64)):
            obj=catalog_from_snapshot(kind="strategy",page=1,page_size=5,sort="recent_extended")
            self.assertEqual(obj["count"],1)
            self.assertEqual(obj["invalid_entries_skipped"],1)

if __name__=="__main__":unittest.main()
