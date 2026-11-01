import unittest
import json
import os
from unittest.mock import patch
from investment_node_adapter import execute_node01,execute_node02,node_binding,WF01_MODES

class InvestmentNodeAdapterTests(unittest.TestCase):
    def test_both_modes_n01_to_n02_passthrough(self):
        for workflow,kind in WF01_MODES.items():
            n1=execute_node01({"ui_selection":kind,"requested_detail_limit":1,"max_pages":2},workflow_kind=kind)
            n2=execute_node02(n1,workflow_kind=kind)
            for k,v in n1.items():self.assertEqual(n2[k],v)
            self.assertEqual(n2["page_size"],50)
            self.assertEqual(n2["selected_count"],0)
            self.assertEqual(node_binding(workflow,"wf01-"+kind+"-02")["python_function"],"execute_node02")
            self.assertEqual(execute_node02({**n1,"page_size":25},workflow_kind=kind)["page_size"],25)

    def test_fails_closed(self):
        for kind in ("strategy","library"):
            n=execute_node01({"ui_selection":kind,"requested_detail_limit":1},workflow_kind=kind)
            for bad in ({**n,"max_pages":20},{**n,"sort":"updated_desc"},
                        {**n,"kind":"wrong"},{**n,"page_size":0},
                        {**n,"selected_count":3}):
                with self.assertRaises(ValueError):
                    execute_node02(bad,workflow_kind=kind)
            for limit in (True,0,2):
                with self.assertRaises(ValueError):
                    execute_node01({"ui_selection":kind,"requested_detail_limit":limit},workflow_kind=kind)

    def test_n03_reads_exact_n02_output_and_blocks_without_approved_provider(self):
        from investment_node_adapter import execute_node03
        start={"ui_selection":"strategy","requested_detail_limit":1}
        n1=execute_node01(start,workflow_kind="strategy")
        n2=execute_node02(n1,workflow_kind="strategy")
        with patch.dict(os.environ,{"TRADINGVIEW_AUTHORIZED_CATALOG_URL":""}):
            snapshot={"kind":"strategy","page":1,"items":[{"kind":"strategy","source_id":"PUB;sample",
                "source_url":"https://www.tradingview.com/script/abc12345/"}],
                "count":1,"catalog_source":"PYNE_GITHUB_CC_BY_4_METADATA_SNAPSHOT",
                "catalog_is_live":False,"pine_source_acquired":False}
            with patch("investment_node_adapter.catalog_from_snapshot",return_value=snapshot) as catalog:
                real=execute_node03(n2,workflow_kind="strategy")
                self.assertEqual(real["count"],1)
                self.assertFalse(real["catalog_is_live"])
                self.assertFalse(real["pine_source_acquired"])
                catalog.assert_called_once_with(kind="strategy",page=1,page_size=50,sort="recent_extended")
        with patch.dict(os.environ,{"TRADINGVIEW_AUTHORIZED_CATALOG_URL":"https://www.tradingview.com/api/scrape"}):
            with self.assertRaisesRegex(ValueError,"DIRECT_TRADINGVIEW_AUTOMATED_COLLECTION_DISABLED"):
                execute_node03(n2,workflow_kind="strategy")

    def test_n03_authorized_response_is_validated_not_fabricated(self):
        from investment_node_adapter import execute_node03
        n1=execute_node01({"ui_selection":"strategy","requested_detail_limit":1},workflow_kind="strategy")
        n2=execute_node02(n1,workflow_kind="strategy")
        payload={"kind":"strategy","page":1,"has_more":False,
                 "items":[{"kind":"strategy","source_id":"ABC-real-provider-sample",
                           "source_url":"https://www.tradingview.com/script/abc123/",
                           "title":"Provider fixture; not a collected real strategy",
                           "version_key":"1","author":"ci"}]}
        class FakeResponse:
            status=200
            headers={"Content-Length":"1000"}
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,n=-1):return json.dumps(payload).encode()
        with patch.dict(os.environ,{"TRADINGVIEW_AUTHORIZED_CATALOG_URL":"https://approved.example.com/catalog"}):
            with patch("investment_node_adapter.urllib.request.urlopen",return_value=FakeResponse()) as fn:
                output=execute_node03(n2,workflow_kind="strategy")
                self.assertEqual(output["status"],"ok")
                self.assertEqual(output["count"],1)
                self.assertEqual(output["items"][0]["source_id"],"ABC-real-provider-sample")
                self.assertEqual(output["page_size"],n2["page_size"])
                self.assertFalse(output["tradingview_requested"])
                req=fn.call_args.args[0]
                self.assertIn("page=1",req.full_url)
                self.assertIn("kind=strategy",req.full_url)
                self.assertIn("page_size=50",req.full_url)
        with patch.dict(os.environ,{"TRADINGVIEW_AUTHORIZED_CATALOG_URL":"https://approved.example.com/catalog"}):
            payload["page"]=2
            with patch("investment_node_adapter.urllib.request.urlopen",return_value=FakeResponse()):
                with self.assertRaisesRegex(ValueError,"AUTHORIZED_CATALOG_INCORRECT_PAGE_OR_KIND"):
                    execute_node03(n2,workflow_kind="strategy")

    def test_n04_processes_exact_n03_snapshot_and_preserves_metadata(self):
        from investment_node_adapter import execute_node04
        n3={"kind":"strategy","status":"ok","page":1,"max_pages":3,
            "has_more":True,"catalog_source":"PYNE_GITHUB_CC_BY_4_METADATA_SNAPSHOT",
            "catalog_is_live":False,"count":3,"manifest_sha256":"a"*64,
            "items":[
                {"kind":"strategy","source_id":"PUB;one","version_key":"1",
                 "source_url":"https://www.tradingview.com/script/ABCDEF12/",
                 "title":"Older","catalog_observed_at":"2026-08-27",
                 "updated_at":None,"source_code_fetched":False},
                {"kind":"strategy","source_id":"PUB;two","version_key":"2",
                 "source_url":"https://www.tradingview.com/script/87654321/",
                 "title":"Newer observed","catalog_observed_at":"2026-10-02",
                 "updated_at":None,"source_code_fetched":False},
                {"kind":"strategy","source_id":"PUB;two","version_key":"2",
                 "source_url":"https://www.tradingview.com/script/87654321/",
                 "title":"Duplicate","catalog_observed_at":"2026-10-02",
                 "updated_at":None,"source_code_fetched":False}]}
        out=execute_node04(n3,workflow_kind="strategy")
        for key,value in n3.items():self.assertEqual(out[key],value)
        self.assertEqual(out["candidate_count"],2)
        self.assertEqual(out["duplicates_removed"],1)
        self.assertEqual(out["next_page"],2)
        self.assertFalse(out["latest_tradingview_checked"])
        self.assertTrue(out["validated_catalog_is_snapshot"])
        self.assertEqual(out["candidates"][0]["source_id"],"PUB;two")
        self.assertIsNone(out["candidates"][0]["updated_at"])
        self.assertFalse(out["candidates"][0]["source_code_fetched"])
        with self.assertRaisesRegex(ValueError,"N04_CATALOG_COUNT_MISMATCH"):
            execute_node04({**n3,"count":4},workflow_kind="strategy")

    def test_n05_queries_real_sqlite_version_registry_not_metadata_hash(self):
        import sqlite3
        import tempfile
        from pathlib import Path
        from investment_node_adapter import execute_node05
        candidate={"kind":"strategy","source_id":"PUB;test","version_key":"3",
            "source_url":"https://www.tradingview.com/script/ABCdef12/",
            "source_sha256_reported":"a"*64,"source_code_fetched":False}
        n4={"kind":"strategy","candidate_count":1,"candidates":[candidate],
            "items":[candidate],"page":1,"max_pages":3}
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ,{"STUDIO_DB_PATH":str(Path(tmp)/"registry.sqlite3")}):
                first=execute_node05(n4,workflow_kind="strategy")
                self.assertEqual(first["new_count"],1)
                self.assertEqual(first["imported_count"],0)
                self.assertFalse(first["items"][0]["imported"])
                self.assertEqual(first["candidate_count"],1)
                with sqlite3.connect(str(Path(tmp)/"registry.sqlite3")) as db:
                    db.execute("""INSERT INTO investment_pine_versions
                       (kind,source_id,version_key,pine_sha256,verified_source,
                        approved_for_conversion,saved_at) VALUES(?,?,?,?,?,?,?)""",
                       ("strategy","PUB;test","3","b"*64,1,0,"2026-11-01T00:00:00Z"))
                second=execute_node05(n4,workflow_kind="strategy")
                self.assertEqual(second["imported_count"],1)
                self.assertTrue(second["items"][0]["imported"])
                self.assertFalse(second["items"][0]["conversion_approved"])
                self.assertEqual(second["input_json"] if "input_json" in second else second["candidates"],n4["candidates"])

    def test_n06_selects_only_one_unregistered_source_and_preserves_n05(self):
        from investment_node_adapter import execute_node06
        a={"kind":"strategy","source_id":"PUB;first","version_key":"1",
           "source_url":"https://www.tradingview.com/script/12345678/","imported":False}
        b={**a,"source_id":"PUB;second","imported":False}
        n5={"kind":"strategy","source_registry_checked":True,
            "items":[a,b],"checked_count":2,"page":1,"max_pages":3,
            "next_page":2,"candidate_sort_basis":"third_party_manifest_observed_at",
            "selected_count":0}
        result=execute_node06(n5,workflow_kind="strategy")
        for key,val in n5.items():self.assertEqual(result[key],val)
        self.assertEqual(result["candidate"]["source_id"],"PUB;first")
        self.assertEqual(result["selected_candidate_count"],1)
        self.assertTrue(result["has_candidate"])
        self.assertFalse(result["pine_source_acquired"])
        all_imported=execute_node06({**n5,"items":[{**a,"imported":True},{**b,"imported":True}]},workflow_kind="strategy")
        self.assertIsNone(all_imported["candidate"])
        self.assertFalse(all_imported["has_candidate"])
        with self.assertRaisesRegex(ValueError,"N06_REGISTRY_NOT_CHECKED"):
            execute_node06({**n5,"source_registry_checked":False},workflow_kind="strategy")

if __name__=="__main__":unittest.main()
