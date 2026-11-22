import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import hitel_a_task_isolated as m

class CleanRecovery(unittest.TestCase):
    def test_pending_and_new_worker_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"state.json"
            state={"request_id":"original","room_id":"room_old","job_id":"job_old",
                   "stage":"DISCOVER"}
            job={"request_id":"original","room_id":"room_old","job_id":"job_old",
                 "status":"unknown","error_code":"WORKER_CONNECTION_LOST","result_ready":False}
            with patch.object(m,"post",side_effect=[
                (202,{"accepted":False,"pending":True,"task_id":"stock-a","previous_job_id":"job_old"}),
                (202,{"accepted":True,"task_id":"stock-a","job_id":"job_new","room_id":"room_new",
                      "request_id":"hitel-clean-stock-a-test"})]) as post:
                self.assertTrue(m.recover_clean_worker(state,job,path))
                self.assertEqual(state["job_id"],"job_old")
                self.assertTrue(m.recover_clean_worker(state,job,path))
                self.assertEqual(state["job_id"],"job_new")
                self.assertEqual(state["room_id"],"room_old")
                self.assertEqual(state["request_id"],"original")
                self.assertEqual(state["stage"],"DISCOVER")
                self.assertEqual(post.call_args_list[0],post.call_args_list[1])
    def test_other_failure_and_verified_reply_never_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            state={"request_id":"original","room_id":"room_old","job_id":"job_old","stage":"DISCOVER"}
            job={"request_id":"original","room_id":"room_old","job_id":"job_old",
                 "status":"unknown","error_code":"WORKER_CONNECTION_LOST","result_ready":False}
            with patch.object(m,"post") as post:
                for change in ({"room_id":"wrong"},{"error_code":"UPSTREAM_RATE_LIMITED"},
                               {"status":"completed"},{"result_ready":True}):
                    self.assertFalse(m.recover_clean_worker(state,{**job,**change},Path(folder)/"state.json"))
                post.assert_not_called()
    def test_verified_reply_checksum(self):
        raw='{"ready":true}'
        result={"result_ready":True,"result_text":raw,"result_length_bytes":len(raw),
                "result_sha256":hashlib.sha256(raw.encode()).hexdigest()}
        self.assertEqual(m.read_verified_answer(result),raw)
        with self.assertRaisesRegex(RuntimeError,"HASH_MISMATCH"):
            m.read_verified_answer({**result,"result_sha256":"wrong"})

if __name__=="__main__":
    unittest.main()
