#!/usr/bin/env python3
"""No-network tests for source identity and task-isolated dispatch safety."""
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import task_isolated_client as m


def reply_for(selected, batch):
    return json.dumps({
        "schema": m.source.SCHEMA, "batch_number": batch, "research_only": True,
        "source_results": [
            {"source_order": x["order"], "script_id": x["id"], "title": x["title"],
             "research_status": "SEARCHED", "search_queries": [x["title"]],
             "cases": [], "exclusions": [], "limitations": "No externally verified trades"}
            for x in selected
        ]}, ensure_ascii=False)


class IsolatedStockTV(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = m.source.originals()

    def test_originals_four_thousand_four_hundred_twenty_eight(self):
        self.assertEqual(len(self.rows), 4428)
        self.assertEqual(len(m.source.group(self.rows, 1)), 10)
        self.assertEqual(len(m.source.group(self.rows, 443)), 8)
        self.assertEqual(m.source.group(self.rows, 1)[0]["id"], "02yfhjiz")

    def test_exactly_one_question_for_ten(self):
        selected = m.source.group(self.rows, 1)
        prompt = m.source.question(selected, 1)
        ident = m.identity(1, selected, prompt)
        self.assertEqual(ident["task_id"], "stock-tv")
        self.assertEqual(ident["source_ids"], [x["id"] for x in selected])
        self.assertIn("source_results", prompt)
        self.assertTrue(ident["request_id"].startswith("stock-tv-r3-0001-"))
        self.assertLessEqual(len(prompt), 24000)

    def test_previous_batch_must_be_saved_before_next(self):
        with tempfile.TemporaryDirectory() as t:
            with mock.patch.object(m, "RESULT_ROOT", Path(t)):
                with self.assertRaisesRegex(RuntimeError, "PREVIOUS_TEN_NOT_REMOTELY_COMMITTED"):
                    m.execute(2, Path(t) / "checks")

    def test_verified_answer_saved_without_parallel_requests(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            selected = m.source.group(self.rows, 1)
            raw = reply_for(selected, 1)
            prompt = m.source.question(selected, 1)
            rid = m.identity(1, selected, prompt)["request_id"]
            jobid = "job_" + "1" * 32
            roomid = "room_" + "2" * 32
            completed = {
                "job_id": jobid, "room_id": roomid, "request_id": rid,
                "status": "completed", "result_ready": True,
                "result_text": raw, "result_length_bytes": len(raw.encode("utf-8")),
                "result_sha256": m.digest(raw)}
            def fake_get(path):
                if "/requests/" in path:
                    raise urllib.error.HTTPError(path, 404, "not found", {}, None)
                return completed
            with mock.patch.object(m, "RESULT_ROOT", root / "results"), \
                 mock.patch.object(m, "get", side_effect=fake_get), \
                 mock.patch.object(m, "post_isolated", return_value={
                     "accepted": True, "task_id": "stock-tv", "request_id": rid,
                     "room_id": roomid, "job_id": jobid}) as post:
                m.execute(1, root / "check")
                self.assertEqual(post.call_count, 1)
                self.assertEqual(post.call_args.args[0]["room_name"], "TV-STRATEGY-R3-0001")
                self.assertTrue((root / "check/batch_0001/result.json").exists())
                m.execute(1, root / "check", resume_only=True)
                self.assertEqual(post.call_count, 1)

    def test_uncertain_post_must_never_resend(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            def missing(path):
                raise urllib.error.HTTPError(path, 404, "missing", {}, None)
            with mock.patch.object(m, "RESULT_ROOT", root / "results"), \
                 mock.patch.object(m, "get", side_effect=missing), \
                 mock.patch.object(m, "post_isolated", side_effect=TimeoutError) as post:
                with self.assertRaisesRegex(RuntimeError, "POST_OUTCOME_UNKNOWN"):
                    m.execute(1, root / "check")
                with self.assertRaisesRegex(RuntimeError, "UNKNOWN_DELIVERY_NO_SECOND"):
                    m.execute(1, root / "check")
                self.assertEqual(post.call_count, 1)

    def test_read_only_lookup_recovers_unknown_request(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            prompt = m.source.question(m.source.group(self.rows, 1), 1)
            identity = m.identity(1, m.source.group(self.rows, 1), prompt)
            path = root / "check/batch_0001/client_state.json"
            m.atomic(path, {**identity, "phase": "UNKNOWN_DELIVERY", "post_attempted": True})
            req = {"request_id": identity["request_id"], "job_id": "job_" + "a"*32,
                   "room_id": "room_" + "b"*32}
            with mock.patch.object(m, "RESULT_ROOT", root / "results"), \
                 mock.patch.object(m, "get", side_effect=[
                     req, {"job_id": req["job_id"], "request_id": req["request_id"],
                           "room_id": req["room_id"], "status": "failed", "error_code": "UNKNOWN"}]), \
                 mock.patch.object(m, "post_isolated") as post:
                with self.assertRaisesRegex(RuntimeError, "TASK_JOB_TERMINAL_FAILURE"):
                    m.execute(1, root / "check", resume_only=True)
                self.assertEqual(post.call_count, 0)


    def test_clean_restart_keeps_root_identity_and_does_not_repeat_batch(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/"state.json"
            state={"request_id":"stock-tv-root","room_id":"room_old","job_id":"job_old",
                   "batch_number":3,"phase":"ACCEPTED"}
            job={"request_id":"stock-tv-root","room_id":"room_old","job_id":"job_old",
                 "status":"unknown","error_code":"WORKER_CONNECTION_LOST","result_ready":False}
            with mock.patch.object(m,"post_isolated",side_effect=[
                {"accepted":False,"pending":True,"task_id":"stock-tv","previous_job_id":"job_old"},
                {"accepted":True,"task_id":"stock-tv","job_id":"job_new",
                 "room_id":"room_new","request_id":"hitel-clean-stock-tv-receipt"}]) as post:
                self.assertTrue(m.recover_clean_worker(state,job,path))
                self.assertEqual(state["job_id"],"job_old")
                self.assertTrue(m.recover_clean_worker(state,job,path))
                self.assertEqual(state["job_id"],"job_new")
                self.assertEqual(state["request_id"],"stock-tv-root")
                self.assertEqual(state["batch_number"],3)
                self.assertEqual(state["recovery_audit"][0]["previous_job_id"],"job_old")
                self.assertEqual(post.call_count,2)
                self.assertEqual(post.call_args_list[0],post.call_args_list[1])

    def test_clean_restart_refuses_rate_limit_or_completed_or_wrong_room(self):
        with tempfile.TemporaryDirectory() as t:
            state={"request_id":"original","room_id":"room_old","job_id":"job_old","batch_number":3}
            job={"request_id":"original","room_id":"room_old","job_id":"job_old",
                 "status":"unknown","error_code":"WORKER_CONNECTION_LOST","result_ready":False}
            with mock.patch.object(m,"post_isolated") as post:
                for wrong in ({"error_code":"UPSTREAM_RATE_LIMITED"},{"status":"completed"},
                              {"result_ready":True},{"room_id":"wrong"}):
                    self.assertFalse(m.recover_clean_worker(state,{**job,**wrong},Path(t)/"state.json"))
                post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
