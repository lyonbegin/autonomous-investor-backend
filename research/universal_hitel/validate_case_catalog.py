#!/usr/bin/env python3
"""Consumer-side structural validation of case-only Universal CSV.

Does not modify the provider framework. Checks paper-to-individual-case
references, count consistency and evidence fields; never asserts real-world
truth of a cited paper merely from syntactically valid JSON.
"""
import argparse
import csv
import json
from pathlib import Path

LIST_FIELDS = ("papers_json", "cases_json", "candidate_cases_json",
               "rejection_log_json", "search_log_json")
COUNT_MAP = {"papers_json": "paper_count", "cases_json": "case_count",
             "candidate_cases_json": "candidate_count"}

def check_record(row):
    decoded = {}
    for field in LIST_FIELDS:
        try:
            parsed = json.loads(row[field])
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ValueError("Invalid or missing JSON field " + field) from exc
        if not isinstance(parsed, list):
            raise ValueError(field + " must be JSON array")
        decoded[field] = parsed

    for field, count in COUNT_MAP.items():
        if int(row[count]) != len(decoded[field]):
            raise ValueError("count mismatch: " + count)

    papers = decoded["papers_json"]
    cases = decoded["cases_json"]
    paper_ids = set()
    for p in papers:
        if not isinstance(p, dict):
            raise ValueError("paper entry not an object")
        pid = p.get("paper_id")
        if not isinstance(pid, str) or not pid.strip() or pid in paper_ids:
            raise ValueError("missing or duplicate paper_id")
        paper_ids.add(pid)
        if not str(p.get("title", "")).strip() or not (
            str(p.get("original_url", "")).strip() or str(p.get("doi", "")).strip()
        ):
            raise ValueError("paper missing title or verifiable locator")

    seen = set()
    linked = 0
    for c in cases:
        if not isinstance(c, dict):
            raise ValueError("case entry not an object")
        cid = c.get("case_id")
        if not isinstance(cid, str) or not cid.strip() or cid in seen:
            raise ValueError("missing or duplicate case_id")
        seen.add(cid)
        parent = c.get("parent_paper_id")
        if parent not in (None, ""):
            if parent not in paper_ids:
                raise ValueError("case references a paper not in papers_json: " + str(parent))
            linked += 1
        if not str(c.get("original_url", "")).strip():
            raise ValueError("case missing original_url")
        if not str(c.get("evidence_location", "")).strip():
            raise ValueError("case missing evidence_location")
        if not str(c.get("evidence_kind", "")).strip() or not str(
            c.get("relationship_to_tv_script", "")).strip():
            raise ValueError("case missing evidence or relationship classification")
    if int(row["paper_case_count"]) != linked:
        raise ValueError("paper_case_count mismatch")
    if not row.get("record_id"):
        raise ValueError("record_id missing")
    return {"record_id": row["record_id"], "papers": len(papers),
            "cases": len(cases), "paper_internal_cases": linked,
            "candidates": len(decoded["candidate_cases_json"]),
            "has_more": str(row.get("has_more", "")).strip().lower() == "true"}

def validate_csv(csv_file):
    with Path(csv_file).open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise ValueError("no rows")
    out = [check_record(row) for row in rows]
    ids = [r["record_id"] for r in out]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate TradingView record_id")
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    a = ap.parse_args()
    print(json.dumps(validate_csv(a.csv), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
