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
