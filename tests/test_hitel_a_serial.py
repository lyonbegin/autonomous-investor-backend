"""Local-only tests for A single-source HITEL transport and honest evidence gates."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

TARGET = Path("research/hitel_a_one_source.py")
SPEC = importlib.util.spec_from_file_location("a_transport", TARGET)
a = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(a)

class TestASerialTransport(unittest.TestCase):
    def test_public_limit_has_headroom(self):
        self.assertLessEqual(a.MAX_PROMPT, 24000)

    def test_source_preview_never_promotes_to_verified(self):
        import json
        src=json.loads(Path("research/queue/a_one_source_pilot.json").read_text("utf-8"))
        self.assertEqual(src["group"],"A")
        self.assertFalse(src["official_a_order_verified"])
        self.assertNotEqual(src["pine_source_status"],"VERIFIED")

    def test_failed_job_is_not_reposted(self):
        with tempfile.TemporaryDirectory() as temp:
            calls=[]
            def fake_post(path,body):
                calls.append((path,body["request_id"]))
                return 202, {"job_id":"job_"+"a"*32, "room_id":"room_"+"b"*32}
            def fake_get(path):
                return 200,{"status":"failed","room_id":"room_"+"b"*32,
                            "error":"WEB2API_SEND_OR_VERIFY_FAILED"}
            room_id="room_"+"b"*32
            with patch.object(a,"post",side_effect=fake_post),patch.object(a,"get",side_effect=fake_get):
                with self.assertRaisesRegex(RuntimeError,"WEB2API"):
                    a.ask(room_id,"DISCOVERY","test",Path(temp),10)
                with self.assertRaisesRegex(RuntimeError,"PRIOR_TERMINAL_JOB_FAILED"):
                    a.ask(room_id,"DISCOVERY","test",Path(temp),10)
            self.assertEqual(len(calls),1)
            saved=list((Path(temp)/"jobs").glob("*.json"))
            self.assertEqual(len(saved),1)

    def test_incorrect_edge_rejected(self):
        good={"graph":{"nodes":[
            {"id":"root","type":"Case","properties":{"asset":"ETF"}},
            {"id":"leg","type":"Position","properties":{"direction":"LONG"}}],
            "edges":[{"source":"root","target":"leg","relation":"USES"}]}}
        self.assertTrue(a.validate_graph(good)[0])
        good["graph"]["edges"][0]["target"]="missing"
        self.assertFalse(a.validate_graph(good)[0])

    def test_blind_removes_source_labels_but_keeps_financial_rules(self):
        graph={"graph":{"nodes":[{"id":"A","type":"Case",
                "properties":{"source_url":"hidden.example","entry_price":100,"origin_title":"hide"}}],
                "edges":[],"source_facts":["hidden"]}}
        redacted=a.blind_graph(graph)
        self.assertNotIn("source_url", redacted["nodes"][0]["properties"])
        self.assertNotIn("origin_title", redacted["nodes"][0]["properties"])
        self.assertNotIn("source_facts",redacted)
        self.assertEqual(redacted["nodes"][0]["properties"]["entry_price"],100)

if __name__ == "__main__":
    unittest.main()
