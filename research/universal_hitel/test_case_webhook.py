"""Offline cryptographic verification and dedup tests for stock-only receiver."""
import hashlib
import hmac
import json
from pathlib import Path
import tempfile
import time
import unittest

try:
    from . import case_webhook_wsgi as w
except ImportError:
    import case_webhook_wsgi as w


class TestStockCaseWebhook(unittest.TestCase):
    def setUp(self):
        self.secret = "test-only-secret"
        self.now = 1800000000
        self.payload = {
            "schema": "hitel.progress.v1",
            "event_id": "a" * 64,
            "sequence": 3,
            "project_id": "stocktv-cases-20261127-0001-p01-v2",
            "provider": "hitel",
            "event": "batch.verified",
            "verified_ai_completed": 1,
            "occurred_at": "2026-11-27T01:00:00Z"
        }
        self.raw = json.dumps(self.payload, ensure_ascii=False).encode()
        self.ts = str(self.now)
        self.sig = "sha256=" + hmac.new(
            self.secret.encode(), self.ts.encode() + b"." + self.raw,
            hashlib.sha256).hexdigest()
        self.headers = {"X-HITEL-Event-ID": self.payload["event_id"],
                        "X-HITEL-Timestamp": self.ts,
                        "X-HITEL-Signature": self.sig}

    def test_signed_event_passes(self):
        self.assertEqual(w.verify(self.raw, self.headers, self.secret, now=self.now),
                         self.payload)

    def test_wrong_signature_fails(self):
        changed = dict(self.headers, **{"X-HITEL-Signature": "sha256=" + "0" * 64})
        with self.assertRaises(ValueError):
            w.verify(self.raw, changed, self.secret, now=self.now)

    def test_old_timestamp_fails(self):
        with self.assertRaises(ValueError):
            w.verify(self.raw, self.headers, self.secret, now=self.now + 301)

    def test_mock_provider_rejected(self):
        changed = dict(self.payload, provider="mock")
        raw = json.dumps(changed).encode()
        sign = "sha256=" + hmac.new(self.secret.encode(),
                                   self.ts.encode() + b"." + raw,
                                   hashlib.sha256).hexdigest()
        with self.assertRaises(ValueError):
            w.verify(raw, dict(self.headers, **{"X-HITEL-Signature": sign}),
                     self.secret, now=self.now)

    def test_database_is_idempotent(self):
        with tempfile.TemporaryDirectory() as dirname:
            db = str(Path(dirname) / "events.sqlite3")
            self.assertTrue(w.save(db, self.payload))
            self.assertFalse(w.save(db, self.payload))

    def test_no_persistence_path(self):
        with self.assertRaises(RuntimeError):
            w.save(":memory:", self.payload)


if __name__ == "__main__":
    unittest.main()
