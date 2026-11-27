"""Offline milestone and webhook-configuration contract tests; no HTTP calls."""
import json
import unittest

try:
    from . import case_milestone_monitor as m
    from . import case_event_api as e
except ImportError:
    import case_milestone_monitor as m
    import case_event_api as e


def record(rid, has_more=False, paper=False):
    papers = ([{"paper_id": "paper-" + rid, "title": "Research with actual study",
                "original_url": "https://example.org/paper/" + rid}] if paper else [])
    cases = ([{"case_id": "case-" + rid, "parent_paper_id": "paper-" + rid,
               "original_url": "https://example.org/paper/" + rid,
               "evidence_location": "Table 1", "evidence_kind": "historical_backtest",
               "relationship_to_tv_script": "independent_matching_mechanism"}] if paper else [])
    return {"record_id": rid, "papers_json": json.dumps(papers),
            "cases_json": json.dumps(cases), "candidate_cases_json": "[]",
            "rejection_log_json": "[]", "search_log_json": "[]",
            "paper_count": len(papers), "case_count": len(cases),
            "paper_case_count": len(cases), "candidate_count": 0,
            "has_more": has_more, "continuation_query": "",
            "research_status": "SEARCH_EXECUTED_AND_ASSESSED"}


def reader(project_id, records, status="complete", provider="hitel"):
    p = {"project_id": project_id, "provider": provider,
         "fields": {"papers_json": "string", "cases_json": "string",
                    "paper_case_count": "number"},
         "records": [{"record_id": r["record_id"]} for r in records]}
    state = {"provider": provider, "total": len(records),
             "verified_ai_completed": len(records) if provider == "hitel" else 0,
             "results": records if provider == "hitel" else [],
             "status": status, "no_progress": 0}
    events = {"project_id": project_id, "events": []}
    return {f"universal/projects/{project_id}/project.json": json.dumps(p).encode(),
            f"universal/state/{project_id}/state.json": json.dumps(state).encode(),
            f"universal/state/{project_id}/events.json": json.dumps(events).encode()}


class Milestones(unittest.TestCase):
    def check(self, data, project_ids, previous=0):
        def fetch(path):
            return ({}, data[path]) if path in data else (None, None)
        return m.snapshot(fetch, project_ids, previous)

    def test_49_not_reported_50_reported(self):
        pid = "stocktv-1"
        first49 = [record(f"id-{i}") for i in range(49)]
        self.assertEqual(self.check(reader(pid, first49), [pid])["new_milestones"], [])
        first50 = first49 + [record("id-49", paper=True)]
        result = self.check(reader(pid, first50), [pid])
        self.assertEqual(result["new_milestones"], [50])
        self.assertEqual(result["paper_internal_case_count"], 1)
        self.assertEqual(result["case_count"], 1)
        self.assertEqual(self.check(reader(pid, first50), [pid], 50)["new_milestones"], [])

    def test_100_across_projects(self):
        a, b = "stocktv-a", "stocktv-b"
        data = reader(a, [record("a" + str(i)) for i in range(50)])
        data.update(reader(b, [record("b" + str(i)) for i in range(50)]))
        x = self.check(data, [a, b])
        self.assertEqual(x["new_milestones"], [50, 100])
        self.assertEqual(x["completed_unique_scripts"], 100)

    def test_unfinished_research_pass_not_counted(self):
        pid = "stocktv-50"
        rows = [record(str(i)) for i in range(49)] + [record("49", has_more=True)]
        res = self.check(reader(pid, rows), [pid])
        self.assertEqual(res["completed_unique_scripts"], 49)
        self.assertEqual(res["new_milestones"], [])
        self.assertEqual(len(res["pending_continuations"]), 1)

    def test_mock_does_not_count(self):
        pid = "stocktv-mock"
        d = reader(pid, [record(str(i)) for i in range(50)], provider="mock")
        self.assertEqual(self.check(d, [pid])["completed_unique_scripts"], 0)

    def test_fail_closed_wrong_counts(self):
        pid = "stocktv-bad"
        bad = record("a", paper=True)
        bad["case_count"] = 0
        with self.assertRaises(ValueError):
            self.check(reader(pid, [bad]), [pid])

    def test_webhook_requires_approval(self):
        self.assertEqual(e.notifications("webhook")["channel"], "webhook")
        with self.assertRaises(ValueError):
            e.notifications("github_pr")
        with self.assertRaises(ValueError):
            e.notifications("webhook", heartbeat_seconds=1)

    def test_two_passes_only_one_source(self):
        pid1, pid2 = "stocktv-p01", "stocktv-p02"
        row1, row2 = record("same", has_more=True, paper=True), record("same", has_more=False)
        d = reader(pid1, [row1])
        e = reader(pid2, [row2])
        e[f"universal/projects/{pid2}/project.json"] = json.dumps({
            "project_id": pid2, "provider": "hitel",
            "fields": {"papers_json": "string", "cases_json": "string",
                       "paper_case_count": "number"},
            "records": [{"record_id": "same", "search_pass": 2}]
        }).encode()
        d.update(e)
        res = self.check(d, [pid1, pid2])
        self.assertEqual(res["completed_unique_scripts"], 1)
        self.assertEqual(res["paper_count"], 1)
        self.assertEqual(res["paper_internal_case_count"], 1)


if __name__ == "__main__":
    unittest.main()
