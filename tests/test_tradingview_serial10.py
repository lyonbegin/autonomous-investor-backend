import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"research"/"serial10"))
import ten_source_runner as sut

class TenSourceSequentialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=sut.source_rows()

    def test_original_4428_complete_and_ordered(self):
        self.assertEqual(len(self.rows),4428)
        self.assertEqual(len(set(x["id"] for x in self.rows)),4428)
        self.assertEqual(self.rows[0]["id"],"02yfhjiz")
        self.assertEqual(self.rows[9]["id"],"08R4aSqS")
        self.assertEqual(self.rows[10]["id"],"08eSyDlq")
        self.assertEqual(self.rows[-1]["id"],"zzLiSsEc")

    def test_first_three_groups_and_last_exact(self):
        for n,expect in ((1,(1,10)),(2,(11,20)),(3,(21,30)),(443,(4421,4428))):
            batch=sut.batch_rows(self.rows,n)
            self.assertEqual((batch[0]["order"],batch[-1]["order"]),expect)
            self.assertEqual(len(batch),expect[1]-expect[0]+1)
            self.assertLess(len(sut.prompt_for(batch,n)),sut.MAX_PROMPT)

    def test_invalid_group_rejected(self):
        for i in (0,-1,444,99999):
            with self.assertRaises(ValueError):
                sut.batch_rows(self.rows,i)

    def synthetic_reply(self,group,batch):
        return {
            "schema":sut.SCHEMA,"batch_number":batch,"research_only":True,
            "source_results":[{
                "source_order":x["order"],"script_id":x["id"],"title":x["title"],
                "research_status":"SEARCHED","search_queries":["실제 거래 검색어"],
                "cases":[],"exclusions":[],"limitations":"검색했지만 구체적 거래 증빙 없음"
            } for x in group]
        }

    def test_zero_cases_allowed_and_source_identity_enforced(self):
        group=sut.batch_rows(self.rows,1)
        valid=self.synthetic_reply(group,1)
        recovered=sut.parse_reply(json.dumps(valid,ensure_ascii=False),group,1)
        self.assertEqual(len(recovered["source_results"]),10)
        self.assertEqual(sum(len(x["cases"]) for x in recovered["source_results"]),0)
        bad=self.synthetic_reply(group,1)
        bad["source_results"][3]["script_id"]="WRONGID0"
        with self.assertRaises(ValueError):
            sut.parse_reply(json.dumps(bad,ensure_ascii=False),group,1)
        missing=self.synthetic_reply(group,1)
        missing["source_results"].pop()
        with self.assertRaises(ValueError):
            sut.parse_reply(json.dumps(missing,ensure_ascii=False),group,1)

    def test_one_chat_post_then_save_then_retry_no_post(self):
        group=sut.batch_rows(self.rows,1)
        response=self.synthetic_reply(group,1)
        real_json=json.dumps(response,ensure_ascii=False)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            get_result={"job_id":"job_test_123","room_id":"room_test_123",
                        "status":"completed","stage":"assistant_reply_stable",
                        "result_text":real_json}
            with patch.object(sut.transport,"open_named_room",return_value="room_test_123") as room, \
                 patch.object(sut.transport,"post",return_value=(202,{
                     "job_id":"job_test_123","room_id":"room_test_123"
                 })) as chat, \
                 patch.object(sut.transport,"get",side_effect=lambda url: (200,{
                     "worker_connected":True,"worker_capacity":3,
                     "prewarmed_room_count":1,"worker_active_jobs_count":0
                 }) if url.endswith("/status") else (200,get_result)) as status:
                sut.execute(1,p,False,5)
                self.assertEqual(chat.call_count,1)
                self.assertEqual(status.call_count,2)
                self.assertTrue((p/"batch_0001"/"result.json").is_file())
                self.assertTrue((p/"batch_0001"/"summary.json").is_file())
                summary=json.loads((p/"batch_0001"/"summary.json").read_text())
                self.assertEqual(summary["total_cases"],0)
                sut.execute(1,p,False,5)
                self.assertEqual(chat.call_count,1,"second execution must not re-POST")
                self.assertEqual(room.call_count,1)

    def test_no_next_batch_on_failed_or_incomplete_response(self):
        group=sut.batch_rows(self.rows,1)
        incomplete=self.synthetic_reply(group,1)
        incomplete["source_results"]=incomplete["source_results"][:9]
        with tempfile.TemporaryDirectory() as d:
            with patch.object(sut.transport,"open_named_room",return_value="room_test_1"), \
                 patch.object(sut.transport,"post",return_value=(202,{
                     "job_id":"job_test_1","room_id":"room_test_1"
                 })) as post, \
                 patch.object(sut.transport,"get",side_effect=lambda url: (200,{
                     "worker_connected":True,"worker_capacity":3,
                     "prewarmed_room_count":1,"worker_active_jobs_count":0
                 }) if url.endswith("/status") else (200,{
                     "job_id":"job_test_1","room_id":"room_test_1",
                     "status":"completed",
                     "result_text":json.dumps(incomplete,ensure_ascii=False)
                 })):
                with self.assertRaises(ValueError):
                    sut.execute(1,Path(d),False,5)
                self.assertEqual(post.call_count,1)
                self.assertFalse((Path(d)/"batch_0001"/"result.json").exists())
                self.assertTrue((Path(d)/"batch_0001"/"result.raw.txt").exists())

if __name__=="__main__":
    unittest.main()
