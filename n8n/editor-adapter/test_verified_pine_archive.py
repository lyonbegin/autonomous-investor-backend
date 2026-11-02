"""Pine fetch tests: retrieve usable text; author/hash mismatch is not a gate."""
import unittest
from unittest.mock import patch
from verified_pine_archive import acquire_verified_pine,archive_path_for,MAX_PINE_BYTES

class Response:
    status=200
    def __init__(self,content):self.content=content
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,length):return self.content[:length]

class PineFetchTests(unittest.TestCase):
    def test_fetch_real_text_without_author_or_hash_comparison(self):
        item={"source_url":"https://www.tradingview.com/script/Hrc7Gfqe/",
              "author":"DIFFERENT AUTHOR","source_sha256_reported":"WRONG"}
        content=b"//@version=6\nstrategy('My Test')\nplot(close)\n"
        with patch("verified_pine_archive.urllib.request.urlopen",
                   return_value=Response(content)) as fetch:
            output=acquire_verified_pine(item)
        self.assertEqual(output["pine_code"],content.decode())
        self.assertTrue(output["pine_source_acquired"])
        self.assertFalse(output["source_identity_verified"])
        self.assertNotIn("pine_source_sha256",output)
        self.assertTrue(fetch.called)

    def test_realistic_127kb_pine_source_is_not_truncated(self):
        item={"source_url":"https://www.tradingview.com/script/nmnHkA02/"}
        content=("//@version=6\\nstrategy('Long Pine')\\n" + "// substantial Pine logic\\n"*8500).encode("utf-8")
        self.assertGreater(len(content),60000)
        self.assertLess(len(content),MAX_PINE_BYTES)
        with patch("verified_pine_archive.urllib.request.urlopen",
                   return_value=Response(content)):
            result=acquire_verified_pine(item)
        self.assertEqual(result["pine_code"].encode("utf-8"),content)

    def test_missing_and_excessive_sources_fail_without_truncation(self):
        item={"source_url":"https://www.tradingview.com/script/nmnHkA02/"}
        for content,expected in [(b"","PINE_SOURCE_EMPTY"),(b"x"*(MAX_PINE_BYTES+1),"PINE_SOURCE_TOO_LARGE")]:
            with self.subTest(expected=expected),patch(
                "verified_pine_archive.urllib.request.urlopen",
                return_value=Response(content)):
                with self.assertRaisesRegex(ValueError,"^"+expected+"$"):
                    acquire_verified_pine(item)

    def test_no_known_file_is_not_reported_as_collected(self):
        self.assertIsNone(archive_path_for({
          "source_url":"https://www.tradingview.com/script/FAKE1234/"}))
        with self.assertRaisesRegex(ValueError,"PINE_SOURCE_NOT_AVAILABLE"):
            acquire_verified_pine({"source_url":"https://www.tradingview.com/script/FAKE1234/"})

if __name__=="__main__":unittest.main()
