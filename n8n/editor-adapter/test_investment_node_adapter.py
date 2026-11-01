"""WF01 checks the real node jobs, not writer names or hashes."""
import os
import tempfile
import unittest
from unittest.mock import patch
from investment_node_adapter import (execute_node01,execute_node02,execute_node03,
    execute_node04,execute_node05,execute_node06,execute_node07,
    execute_node11,node_binding)

class WF01UsefulNodes(unittest.TestCase):
    def test_configuration_carries_forward(self):
        n1=execute_node01({"ui_selection":"strategy","requested_detail_limit":1},workflow_kind="strategy")
        n2=execute_node02(n1,workflow_kind="strategy")
        self.assertEqual(n2["page_size"],50)
        self.assertTrue(all(n2[k]==v for k,v in n1.items()))

    def test_fetched_candidates_are_not_fake_and_do_not_require_author_or_hash(self):
        n2=execute_node02(execute_node01({"ui_selection":"strategy",
            "requested_detail_limit":1},workflow_kind="strategy"),workflow_kind="strategy")
        item={"kind":"strategy","source_id":"PUB;example","version_key":"1.0",
            "source_url":"https://www.tradingview.com/script/Hrc7Gfqe/",
            "title":"Example","pine_version":"6"}
        with patch("investment_node_adapter.catalog_from_snapshot",
                   return_value={"kind":"strategy","page":1,"items":[item],
                   "count":1,"has_more":False,"catalog_source":"snapshot"}):
            n3=execute_node03(n2,workflow_kind="strategy")
        n4=execute_node04(n3,workflow_kind="strategy")
        self.assertEqual(n4["candidate_count"],1)
        self.assertEqual(n4["candidates"][0]["source_id"],item["source_id"])
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{"STUDIO_DB_PATH":folder+"/x.db"}):
            n5=execute_node05(n4,workflow_kind="strategy")
            n6=execute_node06(n5,workflow_kind="strategy")
            n7=execute_node07(n6,workflow_kind="strategy")
            self.assertEqual(n7["_studio_active_ports"],[0])
            self.assertTrue(n6["has_candidate"])
        self.assertNotIn("source_sha256_reported",n4["candidates"][0])

    def test_n11_accepts_actual_pine_without_author_or_hash_match(self):
        input_json={"kind":"strategy","has_candidate":True,
          "candidate":{"kind":"strategy","source_id":"PUB;001","version_key":"v1",
          "author":"WRONG NAME","source_sha256_reported":"WRONG HASH"},
          "pine_code":"//@version=6\nstrategy('a', overlay=true)\nplot(close)\n"}
        got=execute_node11(input_json,workflow_kind="strategy")
        self.assertIn("plot(close)",got["pine_code"])
        self.assertTrue(got["pine_source_acquired"])
        self.assertNotIn("author",got["candidate"])
        self.assertNotIn("pine_source_sha256",got)
        self.assertEqual(got["rights_state"],"PENDING_REVIEW")

    def test_removed_nodes_cannot_execute(self):
        path="operations/WF01-latest-strategy-one.json"
        self.assertIsNone(node_binding(path,"wf01-strategy-12"))
        self.assertIsNone(node_binding(path,"wf01-strategy-13"))
        self.assertEqual(node_binding(path,"wf01-strategy-15")["python_function"],
                         "execute_node15")

if __name__=="__main__":unittest.main()
