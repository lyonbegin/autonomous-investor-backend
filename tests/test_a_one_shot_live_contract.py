"""Synthetic one-A-source transport contract; NEVER sends a real ChatGPT request."""
import base64
import hashlib
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs,urlsplit

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"research"/"a_one_shot"))
import one_shot_runner as a
from test_a_one_shot_runner import source, result

class OneShotLiveContractTests(unittest.TestCase):
    def setup_source(self,tmp):
        path=Path(tmp)/"official.jsonl"
        path.write_text(json.dumps(source())+"\n",encoding="utf-8")
        return path

    def make_transport(self,payload,polls=None,invalid=False):
        data=payload.encode("utf-8")
        digest=hashlib.sha256(data).hexdigest()
        calls={"posts":[],"gets":[]}
        state_count=[0]
        statuses=list(polls or ["completed"])
        request_id=[None]
        def fake_post(path,body):
            calls["posts"].append((path,body))
            request_id[0]=body["request_id"]
            return 202,{"room_id":"room_test","job_id":"job_test",
                        "request_id":request_id[0]}
        def fake_get(path):
            calls["gets"].append(path)
            if path.startswith("/integrations/v1/public/requests/"):
                return 200,{"request_id":path.rsplit("/",1)[-1],
                            "room_id":"room_test","job_id":"job_test","status":"running"}
            if "/result?" in path:
                params=parse_qs(urlsplit(path).query)
                offset=int(params["offset"][0])
                chunk=data[offset:offset+65536]
                return 200,{"job_id":"job_test","room_id":"room_test",
                            "request_id":request_id[0],
                            "offset":offset,"bytes_returned":len(chunk),
                            "next_offset":offset+len(chunk),
                            "result_length_bytes":len(data),
                            "result_sha256":digest,
                            "content_base64":base64.b64encode(chunk).decode("ascii")}
            idx=min(state_count[0],len(statuses)-1)
            state_count[0]+=1
            status=statuses[idx]
            return 200,{"job_id":"job_test","room_id":"room_test",
                        "request_id":request_id[0],
                        "status":status,"stage":"waiting_for_verified_reply",
                        "worker_connected":True,"worker_heartbeat_at":100,
                        "job_last_progress_at":50,
                        "result_ready":status=="completed",
                        "result_url":"/integrations/v1/public/jobs/job_test/result",
                        "result_length_bytes":len(data),"result_sha256":digest,
                        "result_json_complete":not invalid}
        return fake_post,fake_get,calls,request_id

    def test_single_post_three_polls_and_exact_multibyte_reply(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest=self.setup_source(tmp)
            out=Path(tmp)/"out"
            payload=json.dumps(result(source()),ensure_ascii=False)
            # Ensure several byte chunks and real Hangul byte boundaries.
            payload=payload[:-1]+',"long_unicode":"'+("연구결과"*14000)+'"}'
            post,get,calls,_=self.make_transport(
                payload,["queued","running","running","completed"])
            with patch.object(a.transport,"open_named_room",return_value="room_test"),\\
                 patch.object(a.transport,"post",side_effect=post),\\
                 patch.object(a.transport,"get",side_effect=get),\\
                 patch("time.sleep") as pause:
                state=a.run(manifest,1,out,expected_count=1)
                replay=a.run(manifest,1,out,expected_count=1)
            self.assertEqual(len(calls["posts"]),1)
            self.assertEqual(pause.call_count,3)
            pause.assert_any_call(10)
            self.assertEqual(state["job_id"],"job_test")
            self.assertEqual(replay["job_id"],"job_test")
            self.assertEqual((out/"result.raw.txt").read_bytes(),payload.encode("utf-8"))
            self.assertEqual(state["result_sha256"],hashlib.sha256(payload.encode()).hexdigest())
            lines=(out/"polling.jsonl").read_text().splitlines()
            self.assertEqual(len(lines),4)
            self.assertEqual([json.loads(x)["status"] for x in lines],
                             ["queued","running","running","completed"])
            self.assertTrue((out/"validation.json").exists())

    def test_invalid_json_stays_raw_and_never_resubmits(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest=self.setup_source(tmp)
            out=Path(tmp)/"out"
            post,get,calls,_=self.make_transport("{bad JSON",invalid=True)
            with patch.object(a.transport,"open_named_room",return_value="room_test"),\\
                 patch.object(a.transport,"post",side_effect=post),\\
                 patch.object(a.transport,"get",side_effect=get):
                with self.assertRaisesRegex(RuntimeError,"NOT_COMPLETE_JSON"):
                    a.run(manifest,1,out,expected_count=1)
                self.assertEqual((out/"result.raw.txt").read_bytes(),b"{bad JSON")
                with self.assertRaisesRegex(RuntimeError,"PRIOR_UNCERTAIN"):
                    a.run(manifest,1,out,expected_count=1)
            self.assertEqual(len(calls["posts"]),1)

    def test_lost_post_response_uses_read_only_request_lookup(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest=self.setup_source(tmp)
            out=Path(tmp)/"out"
            payload=json.dumps(result(source()),ensure_ascii=False)
            post,get,calls,request_id=self.make_transport(payload)
            def first_post(path,body):
                request_id[0]=body["request_id"]
                calls["posts"].append((path,body))
                raise urllib.error.URLError("post response lost")
            with patch.object(a.transport,"open_named_room",return_value="room_test"),\\
                 patch.object(a.transport,"post",side_effect=first_post),\\
                 patch.object(a.transport,"get",side_effect=get):
                with self.assertRaises(urllib.error.URLError):
                    a.run(manifest,1,out,expected_count=1)
                state=a.run(manifest,1,out,expected_count=1)
            self.assertEqual(state["job_id"],"job_test")
            self.assertEqual(len(calls["posts"]),1)
            self.assertTrue(any("/requests/" in x for x in calls["gets"]))

    def test_worker_disconnected_preserves_id_without_repeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest=self.setup_source(tmp);out=Path(tmp)/"out"
            post,get,calls,_=self.make_transport("{}",polls=["stalled"])
            with patch.object(a.transport,"open_named_room",return_value="room_test"),\\
                 patch.object(a.transport,"post",side_effect=post),\\
                 patch.object(a.transport,"get",side_effect=get):
                with self.assertRaisesRegex(RuntimeError,"UNCERTAIN_PRESERVE_ID"):
                    a.run(manifest,1,out,expected_count=1)
                with self.assertRaisesRegex(RuntimeError,"PRIOR_UNCERTAIN"):
                    a.run(manifest,1,out,expected_count=1)
            self.assertEqual(len(calls["posts"]),1)
            self.assertEqual(json.loads((out/"state.json").read_text())["job_id"],"job_test")

    def test_hash_is_not_pine_proof(self):
        s=source();s["pine_provenance_verified"]=False
        verdict=a.check_final_reply(result(s),s)
        self.assertFalse(verdict["can_advance"])
        self.assertIn("PINE_FULL_SOURCE_UNVERIFIED",verdict["schema_issues"])

if __name__=="__main__":
    unittest.main()
