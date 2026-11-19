"""A-only recovery regression tests. No HTTP calls and no new ChatGPT rooms."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC=importlib.util.spec_from_file_location("recovery_module",Path("research/hitel_a_recover_discovery.py"))
mod=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

SOURCE=json.loads(Path("research/queue/a_one_source_pilot.json").read_text("utf-8"))

def seed(out):
    original={
        "stage":"0LJUxO7T-DISCOVER",
        "job_id":mod.ORIGINAL_JOB_ID,
        "request_id":mod.ORIGINAL_REQUEST_ID,
        "room_id":mod.EXPECTED_ROOM_ID,
        "status":"failed",
        "error":"Server restarted; delivery unknown; not automatically retried",
    }
    mod.checkpoint(out,"jobs/"+mod.ORIGINAL_JOB_FILE,original)

class Tests(unittest.TestCase):
    def test_failed_original_gets_distinct_followup_in_same_room(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);seed(out)
            seen=[]
            def fake_get(path):
                if path.startswith("/integrations/v1/public/jobs/"):
                    self.assertEqual(path.rsplit("/",1)[-1],mod.ORIGINAL_JOB_ID)
                    return 200,{"job_id":mod.ORIGINAL_JOB_ID,"room_id":mod.EXPECTED_ROOM_ID,
                                "room_name":mod.EXPECTED_ROOM,"status":"failed",
                                "stage":"server_restarted","error":"Server restarted"}
                if path=="/integrations/v1/public/rooms":
                    return 200,{"rooms":[{"room_id":mod.EXPECTED_ROOM_ID,
                                         "room_name":mod.EXPECTED_ROOM,"conversation_linked":True}]}
                self.fail("Unexpected URL "+path)
            def fake_ask(room_id,stage,prompt,out,timeout):
                seen.append((room_id,stage,prompt))
                return {"source_id":SOURCE["source_id"],"source_access_status":"PREVIEW_ONLY",
                        "cases":[],"blockers":["Pine source missing"]}
            with patch.object(mod.kg,"get",side_effect=fake_get),patch.object(mod.kg,"ask",side_effect=fake_ask):
                result=mod.run(SOURCE,out,5,1)
            self.assertEqual(len(seen),1)
            self.assertEqual(seen[0][0],mod.EXPECTED_ROOM_ID)
            self.assertIn("RECOVERY-FOLLOWUP",seen[0][1])
            self.assertNotEqual(seen[0][1],"0LJUxO7T-DISCOVER")
            self.assertTrue((out/"discovery.json").exists())
            self.assertFalse(result["next_source_allowed"])
            self.assertEqual(result["source_completion_count"],0)
            self.assertEqual(result["original_job_api_status"],"failed")

    def test_running_original_prohibits_any_send(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);seed(out)
            with patch.object(mod.kg,"get",return_value=(200,{
                    "job_id":mod.ORIGINAL_JOB_ID,"room_id":mod.EXPECTED_ROOM_ID,
                    "room_name":mod.EXPECTED_ROOM,"status":"running"})),\
                 patch.object(mod.kg,"ask") as ask:
                with self.assertRaisesRegex(RuntimeError,"STILL_RUNNING"):
                    mod.run(SOURCE,out,5,1)
                ask.assert_not_called()

    def test_original_completed_response_is_reused_without_new_turn(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);seed(out)
            content=json.dumps({"source_id":"0LJUxO7T","cases":[]})
            with patch.object(mod.kg,"get",return_value=(200,{
                    "job_id":mod.ORIGINAL_JOB_ID,"room_id":mod.EXPECTED_ROOM_ID,
                    "room_name":mod.EXPECTED_ROOM,"status":"completed","result_text":content})),\
                 patch.object(mod.kg,"ask") as ask:
                result=mod.run(SOURCE,out,5,1)
                ask.assert_not_called()
            self.assertEqual(result["recovery_mode"],"ORIGINAL_COMPLETED_FROM_API")

    def test_unlinked_room_refuses_followup(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);seed(out)
            def fake_get(path):
                if "/jobs/" in path:
                    return 200,{"job_id":mod.ORIGINAL_JOB_ID,"room_id":mod.EXPECTED_ROOM_ID,
                                "room_name":mod.EXPECTED_ROOM,"status":"failed"}
                return 200,{"rooms":[{"room_id":mod.EXPECTED_ROOM_ID,
                                      "room_name":mod.EXPECTED_ROOM,"conversation_linked":False}]}
            with patch.object(mod.kg,"get",side_effect=fake_get),patch.object(mod.kg,"ask") as ask:
                with self.assertRaisesRegex(RuntimeError,"CONVERSATION_LINK_NOT_VERIFIED"):
                    mod.run(SOURCE,out,5,1)
                ask.assert_not_called()

if __name__=="__main__":
    unittest.main()
