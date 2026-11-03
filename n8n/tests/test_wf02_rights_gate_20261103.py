"""Regression: WF-02 must not expose unapproved Pine to the remote compiler."""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "editor-adapter"))
from investment_wf02 import execute_wf02_node01


class TestWF02RightsGate(unittest.TestCase):
    def test_pending_and_rejected_are_blocked_before_remote_compile(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "sources.sqlite3")
            with sqlite3.connect(db_path) as db:
                db.execute("""CREATE TABLE investment_pine_payloads
                    (kind TEXT, source_id TEXT, version_key TEXT,
                     pine_code TEXT, rights_state TEXT, saved_at TEXT)""")
                for state in ("PENDING_REVIEW", "REJECTED", "UNVERIFIED"):
                    db.execute("""INSERT INTO investment_pine_payloads
                        VALUES ('strategy', ?, '1.0', ?, ?, '2026-11-03')""",
                        (state, '//@version=6\nstrategy("Test")\nplot(close)', state))
                db.commit()

            def get_db():
                connection = sqlite3.connect(db_path)
                connection.row_factory = sqlite3.Row
                return connection

            with patch("investment_wf02.open_registry", side_effect=get_db), \
                 patch.dict(os.environ, {"INVESTMENT_DATABASE_URL": ""}):
                for state in ("PENDING_REVIEW", "REJECTED", "UNVERIFIED"):
                    with self.subTest(state=state), self.assertRaisesRegex(
                        ValueError, "WF02_SOURCE_RIGHTS_NOT_APPROVED"
                    ):
                        execute_wf02_node01({
                            "ui_selection": "strategy",
                            "requested_detail_limit": 1,
                            "source_id": state,
                            "version_key": "1.0"
                        }, workflow_kind="strategy")

    def test_approved_source_can_enter_dependency_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "sources.sqlite3")
            pine = '//@version=6\nstrategy("Approved")\nplot(close)'
            with sqlite3.connect(db_path) as db:
                db.execute("""CREATE TABLE investment_pine_payloads
                    (kind TEXT, source_id TEXT, version_key TEXT,
                     pine_code TEXT, rights_state TEXT, saved_at TEXT)""")
                db.execute("""INSERT INTO investment_pine_payloads
                    VALUES ('strategy','source-1','1.0',?,'APPROVED','2026-11-03')""", (pine,))
                db.commit()

            def get_db():
                connection = sqlite3.connect(db_path)
                connection.row_factory = sqlite3.Row
                return connection

            with patch("investment_wf02.open_registry", side_effect=get_db), \
                 patch.dict(os.environ, {"INVESTMENT_DATABASE_URL": ""}):
                result = execute_wf02_node01({
                    "ui_selection": "strategy", "requested_detail_limit": 1,
                    "source_id": "source-1", "version_key": "1.0"
                }, workflow_kind="strategy")
            self.assertEqual(result["status"], "PINE_LOADED")
            self.assertEqual(result["pine_code"], pine)
            self.assertFalse(result["conversion_validated"])


if __name__ == "__main__":
    unittest.main()
