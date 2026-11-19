"""Ensure the one-source flow really performs one ChatGPT POST and saves returned text."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"research"/"a_one_shot"))
import one_shot_runner as a
from test_a_one_shot_runner import source, result

class OneShotLiveContractTests(unittest.TestCase):
    def setup_source(self,tmp):
        path=Path(tmp)/"official.jsonl"
        path.write_text(json.dumps(source())+"\n",encoding="utf-8")
        return path

    def test_single_actual_post_and_complete_raw_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest=self.setup_source(tmp)
            out=Path(tmp)/"out"
            calls=[]
            payload=json.dumps(result(source()),ensure_ascii=False)
            def fake_post(path,body):
                calls.append((path,body))
                return 202,{"room_id":"room_test","job_id":"job_test"}
            def fake_get(path):
                return 200,{"room_id":"room_test","job_id":"job_test",
                            "status":"completed","result_text":payload}
            with patch.object(a.transport,"open_named_room",return_value="room_test"),\
                 patch.object(a.transport,"post",side_effect=fake_post),\
                 patch.object(a.transport,"get",side_effect=fake_get):
                state=a.run(manifest,1,out,expected_count=1)
                second=a.run(manifest,1,out,expected_count=1)
            self.assertEqual(len(calls),1,"must perform exactly one AI POST")
            self.assertEqual(calls[0][0],"/integrations/v1/public/chat")
            self.assertEqual(state["job_id"],"job_test")
            self.assertEqual(second["job_id"],"job_test")
            self.assertEqual((out/"result.raw.txt").read_text(encoding="utf-8"),payload)
            self.assertTrue((out/"result.json").exists())
            self.assertTrue((out/"validation.json").exists())
            self.assertTrue((out/"prompt.txt").exists())

    def test_malformed_answer_preserved_no_repost(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest=self.setup_source(tmp)
            out=Path(tmp)/"out"
            with patch.object(a.transport,"open_named_room",return_value="room_test"),\
                 patch.object(a.transport,"post",return_value=(202,{"room_id":"room_test","job_id":"job_test"})) as post,\
                 patch.object(a.transport,"get",return_value=(200,{"room_id":"room_test","job_id":"job_test",
                    "status":"completed","result_text":"{invalid json}"})):
                with self.assertRaises(ValueError):
                    a.run(manifest,1,out,expected_count=1)
                self.assertEqual((out/"result.raw.txt").read_text(),"{invalid json}")
                with self.assertRaisesRegex(RuntimeError,"PREVIOUS_ATTEMPT"):
                    a.run(manifest,1,out,expected_count=1)
                self.assertEqual(post.call_count,1)

    def test_hash_is_not_pine_proof(self):
        s=source()
        s["pine_provenance_verified"]=False
        verdict=a.check_final_reply(result(s),s)
        self.assertFalse(verdict["can_advance"])
        self.assertIn("PINE_FULL_SOURCE_UNVERIFIED",verdict["schema_issues"])

    def test_previous_complete_json_then_current_matches_by_source(self):
        current=result(source())
        previous={**current,"source_id":"Zyz98765","a_order":0}
        raw=json.dumps(previous)+ "\n" + json.dumps(current)
        observed=a.parse_reply_for_exact_source(raw,source())
        self.assertEqual(observed["source_id"],source()["source_id"])

    def test_duplicate_current_json_rejected_without_guessing(self):
        current=json.dumps(result(source()))
        with self.assertRaisesRegex(ValueError,"DUPLICATE"):
            a.parse_reply_for_exact_source(current+"\n"+current,source())

    def test_future_or_conflicting_json_rejected(self):
        current=result(source())
        future={**current,"source_id":"Xyz99999","a_order":2}
        with self.assertRaisesRegex(ValueError,"FUTURE_OR_CONFLICTING"):
            a.parse_reply_for_exact_source(json.dumps(future)+"\n"+json.dumps(current),source())

    def test_job_poll_records_running_then_completed_without_second_post(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest=self.setup_source(tmp)
            out=Path(tmp)/"out"
            payload=json.dumps(result(source()),ensure_ascii=False)
            calls=iter([
                {"room_id":"room_test","job_id":"job_test","status":"running",
                 "stage":"web2api_running","updated_at":111},
                {"room_id":"room_test","job_id":"job_test","status":"completed",
                 "stage":"assistant_reply_stable","result_text":payload,"updated_at":222},
            ])
            with patch.object(a.transport,"open_named_room",return_value="room_test"),\
                 patch.object(a.transport,"post",return_value=(202,{"room_id":"room_test","job_id":"job_test"})) as post,\
                 patch.object(a.transport,"get",side_effect=lambda _: (200,next(calls))),\
                 patch("time.sleep",return_value=None):
                state=a.run(manifest,1,out,expected_count=1)
            self.assertEqual(post.call_count,1)
            audit=[json.loads(x) for x in (out/"poll_audit.jsonl").read_text().splitlines()]
            self.assertEqual([x["status"] for x in audit],["running","completed"])
            self.assertEqual(state["last_observation"]["stage"],"assistant_reply_stable")
            self.assertEqual(a.POLL_INTERVAL_SECONDS,10)

if __name__=="__main__":
    unittest.main()
