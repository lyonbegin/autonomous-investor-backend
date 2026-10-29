"""WF-01 intake tests: immutable versions, duplicates, and gating."""
import pytest
from app.alpha_nodes.pine_intake import PineIntake, register_source

BASE = dict(source_id="STR_A", script_type="strategy", pine_version=6,
            source_code='//@version=6\nstrategy("X")\nplot(close)', author="test",
            rights_evidence="Submitted for a manual licensing review")

def test_version_and_rights_gate(tmp_path, monkeypatch):
    monkeypatch.setenv("PINE_INTAKE_DB", str(tmp_path / "pine.sqlite"))
    first = register_source(PineIntake(**BASE))
    assert first["version"] == 1 and first["rights_state"] == "PENDING_REVIEW"
    assert first["conversion_allowed"] is False and first["paper_allowed"] is False
    assert register_source(PineIntake(**BASE))["duplicate"] is True
    newer = register_source(PineIntake(**{**BASE, "source_code": BASE["source_code"]+"\nplot(open)"}))
    assert newer["version"] == 2 and newer["sha256"] != first["sha256"]

def test_unsupported_declarations_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("PINE_INTAKE_DB", str(tmp_path / "pine.sqlite"))
    with pytest.raises(ValueError):
        register_source(PineIntake(**{**BASE, "script_type": "indicator"}))
    with pytest.raises(ValueError):
        register_source(PineIntake(**{**BASE, "pine_version": 5}))
    with pytest.raises(ValueError):
        register_source(PineIntake(**{**BASE, "source_url": "https://u:secret@example.com/x"}))

def test_review_gate_and_pinned_conversion(tmp_path, monkeypatch):
    from fastapi import HTTPException
    from app.alpha_nodes.pine_intake import (
        RightsReview, review_rights, conversion_input, _require_reviewer
    )
    monkeypatch.setenv("PINE_INTAKE_DB", str(tmp_path / "pine.sqlite"))
    monkeypatch.setenv("PINE_RIGHTS_REVIEW_KEY", "test-separate-reviewer-secret")
    registered = register_source(PineIntake(**BASE))
    with pytest.raises(HTTPException) as blocked:
        conversion_input("STR_A", registered["version"])
    assert blocked.value.status_code == 403
    with pytest.raises(HTTPException) as unauthorized:
        _require_reviewer("ordinary-api-key")
    assert unauthorized.value.status_code == 403
    _require_reviewer("test-separate-reviewer-secret")
    decision = RightsReview(decision="APPROVED", reviewer="operator-1",
                            reason="Permission and source evidence were reviewed")
    approved = review_rights("STR_A", 1, decision)
    assert approved["conversion_allowed"] is True
    assert approved["paper_allowed"] is False
    assert conversion_input("STR_A", 1)["sha256"] == registered["sha256"]
    with pytest.raises(HTTPException) as repeated:
        review_rights("STR_A", 1, decision)
    assert repeated.value.status_code == 409

def test_rejection_remains_blocked(tmp_path, monkeypatch):
    from fastapi import HTTPException
    from app.alpha_nodes.pine_intake import RightsReview, review_rights, conversion_input
    monkeypatch.setenv("PINE_INTAKE_DB", str(tmp_path / "pine.sqlite"))
    register_source(PineIntake(**BASE))
    review_rights("STR_A", 1, RightsReview(
        decision="REJECTED", reviewer="operator-2",
        reason="Redistribution and conversion rights not demonstrated"))
    with pytest.raises(HTTPException) as rejected:
        conversion_input("STR_A", 1)
    assert rejected.value.status_code == 403
