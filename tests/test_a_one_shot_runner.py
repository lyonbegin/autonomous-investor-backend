import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "a_one_shot"))
import one_shot_runner as a

def source(has_pine=True):
    pine='//@version=6\nstrategy("unit")\n'
    return {
      "group":"A","a_order":1,"official_a_source_verified":True,
      "source_id":"AbC12345","source_type":"strategy",
      "url":"https://www.tradingview.com/script/AbC12345-Unit/",
      "title":"Unit test","description_preview":"test only",
      "pine_source":pine if has_pine else "",
      "pine_source_sha256":hashlib.sha256(pine.encode()).hexdigest() if has_pine else None,
      "pine_provenance_verified":bool(has_pine),
      "prior_87_catalog_excerpt":"test verified reference",
      "prior_12_catalog_excerpt":"test verified reference",
      "ontology_definitions":"test",
      "strategy_indicator_edges":[]
    }

def result(src):
    case={
      "case_id":"AbC12345-C01","kind":"SPECIFIED_BACKTEST","economic_mechanism":"Test",
      "factual_evidence":[{"source_url":"https://example.org/paper","location":"§1","claim":"entry","access_status":"VERIFIED"}],
      "inferences":[],"prior_87_links":[],"prior_12_links":[],"indicator_links":[],
      "fact_register":[{"fact_id":"F01","fact":"entry","verification":"VERIFIED"}],
      "rounds":[{"round_no":1,"previous_graph_state":"NONE","error_types":[],
        "failure_matrix":[],"graph_rebuild_changes":[],"internal_reconstruction_summary":"replayed",
        "comparison_summary":"matched","verdict":"SELF_CHECK_PASS"}],
      "final_graph":{"nodes":[{"id":"A","type":"Rule","properties":{"entry":"true"},"source_fact_ids":["F01"]},
                            {"id":"B","type":"Position","properties":{"side":"long"},"source_fact_ids":["F01"]}],
                     "edges":[{"source":"A","target":"B","relation":"TRIGGERS","properties":{}}]},
      "final_reconstruction":{"entry":"true"},
      "final_comparison":{"checks":[{"fact_id":"F01","graph_path":["A","B"],
                           "reconstructed_value":"true","match":True,"reasoning":"graph path"}],
                          "source_coverage_pass":True,"self_check_pass":True},
      "internal_verdict":"SELF_CHECK_PASS","independent_blind_verified":False,"unresolved":[]
    }
    return {"schema_version":"A-ONE-SHOT-v1","group":"A","source_id":src["source_id"],"a_order":1,
       "source_verification":{"pine_verified":bool(src["pine_source"]), "pine_sha256":src["pine_source_sha256"],
         "source_access_status":"FULL_PINE" if src["pine_source"] else "PREVIEW_ONLY",
         "source_facts":[],"unverified_source_items":[]},
       "case_discovery":{"method":"unit","candidates_considered":1,"cases_discovered":1,"cases":[case]},
       "summary":{"total_cases":1,"internally_passed":1,"blocked":0,"incomplete":0,
                  "unresolved_claims":[],"overall":"INTERNAL_COMPLETE","report_ko":"테스트"},
       "independent_blind_verified":False}

class Tests(unittest.TestCase):
    def test_manifest_missing_fails_not_invents_order(self):
        with self.assertRaisesRegex(RuntimeError,"OFFICIAL_A_MANIFEST_MISSING"):
            a.read_manifest("/does/not/exist/a.jsonl")
    def test_official_A_count_and_order_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/"m.jsonl"
            f.write_text(json.dumps(source())+"\n")
            with self.assertRaisesRegex(RuntimeError,"OFFICIAL_A_COUNT_NOT_VERIFIED"):
                a.read_manifest(f)
            self.assertEqual(len(a.read_manifest(f,expected=1)),1)
    def test_full_final_json_internal_pass_with_provenance(self):
        s=source()
        v=a.check_final_reply(result(s),s)
        self.assertEqual(v["status"],"INTERNAL_COMPLETE")
        self.assertTrue(v["can_advance"])
        self.assertIn("NOT_INDEPENDENT",v["verification_level"])
    def test_pine_absence_blocks_false_completion(self):
        s=source(False)
        v=a.check_final_reply(result(s),s)
        self.assertFalse(v["can_advance"])
        self.assertIn("PINE_FULL_SOURCE_UNVERIFIED",v["schema_issues"])
    def test_graph_edge_loss_blocks(self):
        s=source()
        r=result(s)
        r["case_discovery"]["cases"][0]["final_graph"]["edges"]=[]
        self.assertFalse(a.check_final_reply(r,s)["can_advance"])
    def test_blind_false_claim_blocks(self):
        s=source()
        r=result(s)
        r["independent_blind_verified"]=True
        self.assertFalse(a.check_final_reply(r,s)["can_advance"])
    def test_dry_run_creates_prompt_without_ai_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/"m.jsonl"
            f.write_text(json.dumps(source(False))+"\n")
            with patch.object(a.transport,"ask") as ask, patch.object(a.transport,"open_named_room") as room:
                state=a.run(f,1,Path(tmp)/"out",expected_count=1,dry_run=True)
                ask.assert_not_called()
                room.assert_not_called()
            self.assertEqual(state["stage"],"DRY_RUN_NO_AI_REQUEST")
            self.assertTrue((Path(tmp)/"out"/"prompt.txt").exists())

if __name__=="__main__":
    unittest.main()
