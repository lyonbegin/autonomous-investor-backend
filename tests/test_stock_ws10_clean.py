import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"research/serial10"))
import ws_ten_runner as mod

class CleanNativeSerialTenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=mod.originals()

    def reply(self,batch,zero=True):
        arr=mod.group(self.rows,batch)
        return {"schema":mod.SCHEMA,"batch_number":batch,"research_only":True,
                "source_results":[{"source_order":r["order"],"script_id":r["id"],
                   "title":r["title"],"research_status":"SEARCHED",
                   "search_queries":["actual trade evidence search"],
                   "cases":[],"exclusions":[],"limitations":"no verified execution"} for r in arr]}

    def test_real_manifest_exact_4428_and_ten_source_groups(self):
        self.assertEqual(len(self.rows),4428)
        self.assertEqual((self.rows[0]["id"],self.rows[9]["id"],self.rows[10]["id"]),
                         ("02yfhjiz","08R4aSqS","08eSyDlq"))
        for b,edges in ((1,(1,10)),(2,(11,20)),(3,(21,30)),(443,(4421,4428))):
            g=mod.group(self.rows,b)
            self.assertEqual((g[0]["order"],g[-1]["order"]),edges)
            self.assertLess(len(mod.question(g,b)),24000)
        with self.assertRaises(ValueError):
            mod.group(self.rows,444)

    def test_zero_cases_permitted_all_ten_sources_required(self):
        response=self.reply(1)
        self.assertEqual(len(mod.validate(json.dumps(response),mod.group(self.rows,1),1)["source_results"]),10)
        response["source_results"].pop()
        with self.assertRaises(ValueError):mod.validate(json.dumps(response),mod.group(self.rows,1),1)

    def test_wrong_original_id_and_cross_batch_rejected(self):
        answer=self.reply(1)
        answer["source_results"][6]["script_id"]="INVALID0"
        with self.assertRaises(ValueError):mod.validate(json.dumps(answer),mod.group(self.rows,1),1)
        with self.assertRaises(ValueError):mod.validate(json.dumps(self.reply(2)),mod.group(self.rows,1),1)

    def test_exactly_one_native_send_same_client_state_is_reused_without_resending(self):
        payload=self.reply(1)
        text=json.dumps(payload,ensure_ascii=False)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            client=root/"hitel_client.py";client.write_text("# existing official client")
            calls=[]
            def simulate(args,**kw):
                calls.append(args)
                statefile=Path(args[args.index("--state")+1])
                mod.atomic(statefile,{"status":"completed",
                    "room_name":mod.room_name(1),"room_id":"room_mock",
                    "request_id":"req_mock","job_id":"job_mock","answer":text,
                    "sha256":mod.checksum(text),
                    "text_sha256":mod.checksum(mod.question(mod.group(self.rows,1),1))})
                return type("Result",(),{"returncode":0})()
            with patch.object(mod,"preflight") as pf,patch.object(mod.subprocess,"run",side_effect=simulate):
                mod.execute(1,root,client)
                mod.execute(1,root,client)
            self.assertEqual(len(calls),1)
            self.assertIn("--text",calls[0])
            pf.assert_called_once()
            self.assertEqual(json.loads((root/"batch_0001"/"summary.json").read_text())["total_cases"],0)

    def test_same_pending_job_must_resume_never_new_text(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);client=root/"native.py";client.write_text("# client")
            g=mod.group(self.rows,1);prompt=mod.question(g,1)
            folder=root/"batch_0001";folder.mkdir()
            mod.atomic(folder/"intent.json",{"batch":1,
              "room_name":mod.room_name(1),"source_ids":[x["id"] for x in g],
              "prompt_sha256":mod.checksum(prompt),"transport":"HITEL_PUBLIC_WEBSOCKET"})
            mod.atomic(folder/"client_state.json",{"status":"running","room_name":mod.room_name(1),
              "request_id":"req_saved","job_id":"job_saved","text_sha256":mod.checksum(prompt)})
            with patch.object(mod.subprocess,"run",return_value=type("R",(),{"returncode":1})()) as call,patch.object(mod,"preflight") as pf:
                with self.assertRaises(RuntimeError):mod.execute(1,root,client)
            pf.assert_not_called()
            args=call.call_args.args[0]
            self.assertIn("--resume",args)
            self.assertNotIn("--text",args)

    def test_next_batch_blocked_without_committed_previous(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(mod,"preflight") as pf,patch.object(mod.subprocess,"run") as native:
                with self.assertRaises(RuntimeError):mod.execute(2,Path(d),Path(d)/"native.py")
                pf.assert_not_called();native.assert_not_called()

    def test_reply_without_native_sha256_must_never_commit(self):
        text=json.dumps(self.reply(1),ensure_ascii=False)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);client=root/"native.py";client.write_text("# native")
            folder=root/"batch_0001";folder.mkdir()
            g=mod.group(self.rows,1)
            mod.atomic(folder/"intent.json",{"batch":1,"room_name":mod.room_name(1),
                "source_ids":[r["id"] for r in g],"prompt_sha256":mod.checksum(mod.question(g,1)),
                "transport":"HITEL_PUBLIC_WEBSOCKET"})
            mod.atomic(folder/"client_state.json",{"status":"completed","room_name":mod.room_name(1),
                "answer":text,"sha256":"bad_digest",
                "text_sha256":mod.checksum(mod.question(g,1))})
            with self.assertRaises(RuntimeError):mod.execute(1,root,client)
            self.assertFalse((folder/"result.json").exists())

    def test_capacity_recovery_must_have_remote_proof_and_new_room(self):
        g=mod.group(self.rows,1)
        prompt=mod.question(g,1)
        old={"status":"unverified","error_code":"web2api_failed","room_name":mod.room_name(1),
             "text_sha256":mod.checksum(prompt),"request_id":"req_veryold",
             "room_id":"room_old","job_id":"job_veryold"}
        remote={"job_id":"job_veryold","room_id":"room_old","request_id":"req_veryold",
                "status":"failed","stage":"web2api_failed","error":"ROOM_TAB_CAPACITY_EXCEEDED",
                "chatgpt_send_confirmed":None,"assistant_reply_observed":None,"result_ready":False}
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);native=root/"client.py";native.write_text("# exists",encoding="utf-8")
            folder=root/"batch_0001";folder.mkdir()
            mod.atomic(folder/"client_state.json",old)
            mod.atomic(folder/"intent.json",{"batch":1,"room_name":mod.room_name(1),
                "source_ids":[x["id"] for x in g],"prompt_sha256":mod.checksum(prompt),
                "transport":"HITEL_PUBLIC_WEBSOCKET"})
            with patch.object(mod,"urlopen",return_value=Response()),patch.object(mod.json,"load",return_value=remote),patch.object(mod,"preflight"),patch.object(mod.subprocess,"run",return_value=type("R",(),{"returncode":1})()) as called:
                with self.assertRaises(RuntimeError):mod.execute(1,root,native,recover_capacity=True)
            self.assertTrue((folder/"capacity_recovery1_verified.json").exists())
            cmd=called.call_args.args[0]
            self.assertIn(mod.room_name(1)+"-CAPACITY-RECOVERY1",cmd)
            self.assertIn("--text",cmd)
            self.assertNotIn("--resume",cmd)
            self.assertFalse((folder/"result.json").exists())

    def test_unverified_or_ambiguous_failure_never_allows_new_room(self):
        base={"status":"unverified","error_code":"web2api_failed",
              "request_id":"req_test","room_id":"room_test","job_id":"job_test"}
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
        remote={"job_id":"job_test","room_id":"room_test","request_id":"req_test",
                "status":"failed","stage":"web2api_failed","error":"ROOM_TAB_CAPACITY_EXCEEDED",
                "chatgpt_send_confirmed":True,"assistant_reply_observed":None,"result_ready":False}
        with patch.object(mod,"urlopen",return_value=Response()),patch.object(mod.json,"load",return_value=remote):
            with self.assertRaises(RuntimeError):mod.validate_capacity_failure_without_chat_send(base)

if __name__=="__main__":unittest.main()
