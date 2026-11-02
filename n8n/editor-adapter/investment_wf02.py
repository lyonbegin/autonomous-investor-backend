"""WF02: load one previously collected Pine script, convert supported subset.

Only two substantive jobs: read actual WF01 SQLite Pine, produce an actual
Python function from supported grammar. Unsupported is a result, never fake
Python code or a trading signal. No source/author/hash ledger.
"""
from contextlib import closing
from datetime import datetime,timezone
from investment_source_registry import open_registry

WF02_PATH="operations/WF02-pine-to-python.json"

def execute_wf02_node01(input_json,*,workflow_kind):
    """Read persisted Pine directly from the existing investment SQLite DB."""
    if workflow_kind!="strategy" or not isinstance(input_json,dict):
        raise ValueError("WF02_STRATEGY_INPUT_REQUIRED")
    if input_json.get("ui_selection")!="strategy" or input_json.get("requested_detail_limit")!=1:
        raise ValueError("WF02_MANUAL_SELECTION_REQUIRED")
    source_id=input_json.get("source_id")
    version_key=input_json.get("version_key")
    if (source_id is not None and (not isinstance(source_id,str) or not source_id.strip())) or (
            version_key is not None and not isinstance(version_key,str)):
        raise ValueError("WF02_INVALID_SOURCE_SELECTOR")
    if (source_id is None)!=(version_key is None):
        raise ValueError("WF02_ID_AND_VERSION_REQUIRED_TOGETHER")
    with closing(open_registry()) as db:
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "investment_pine_payloads" not in tables:
            raise ValueError("WF02_NO_STORED_PINE")
        if source_id is None:
            row=db.execute("""SELECT source_id,version_key,pine_code,rights_state
              FROM investment_pine_payloads WHERE kind='strategy'
              ORDER BY saved_at DESC,rowid DESC LIMIT 1""").fetchone()
        else:
            row=db.execute("""SELECT source_id,version_key,pine_code,rights_state
              FROM investment_pine_payloads WHERE kind='strategy'
              AND source_id=? AND version_key=?""",(source_id,version_key)).fetchone()
    if not row or not row["pine_code"].strip():
        raise ValueError("WF02_PINE_NOT_IN_DATABASE")
    canonical=None
    if __import__("os").environ.get("INVESTMENT_DATABASE_URL"):
        from investment_pg import get_source
        canonical=get_source(row["source_id"],row["version_key"])
        if canonical["pine_code"]!=row["pine_code"]:
            raise ValueError("POSTGRES_SQLITE_SOURCE_CONTENT_MISMATCH")
    return {"kind":"strategy","script_version_id":canonical["script_version_id"] if canonical else None,
        "source_id":row["source_id"],
        "version_key":row["version_key"],"pine_code":row["pine_code"],
        "status":"PINE_LOADED","conversion_validated":False,
        "tradingview_chart_validated":False}

def execute_wf02_node02(input_json,*,workflow_kind):
    """Produce real Python only for supported Pine; otherwise return diagnostics."""
    if workflow_kind!="strategy" or input_json.get("status")!="PINE_LOADED":
        raise ValueError("WF02_PINE_INPUT_MISSING")
    code=input_json.get("pine_code")
    if not isinstance(code,str) or not code.strip():
        raise ValueError("WF02_EMPTY_PINE")
    # Reuse the existing, strictly scoped Pine converter; never exec Pine input.
    from engine import parse_pine,generate_python,UnsupportedPine
    from sequence_reversal import (parse_sequence_pine,generate_sequence_python,
                                    UnsupportedSequencePine)
    try:
        spec=parse_pine(code)
        python_code=generate_python(spec)
    except UnsupportedPine as first_error:
        try:
            spec=parse_sequence_pine(code)
            python_code=generate_sequence_python(spec)
        except UnsupportedSequencePine as second_error:
            return {k:v for k,v in input_json.items() if k!="pine_code"} | {
                "status":"UNSUPPORTED_PINE",
                "unsupported_reason":str(second_error),
                "basic_converter_reason":str(first_error),
                "python_code":None,"converter_scope":None,
                "conversion_validated":False,"tradingview_chart_validated":False}
    # Only verify the emitted code compiles, not that TradingView signals match.
    compile(python_code,"<WF02 generated Python>","exec")
    if "def run_strategy(bars):" not in python_code:
        raise ValueError("WF02_PYTHON_GENERATION_FAILED")
    with closing(open_registry()) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS investment_python_conversions (
            kind TEXT NOT NULL, source_id TEXT NOT NULL, version_key TEXT NOT NULL,
            python_code TEXT NOT NULL, converter_scope TEXT NOT NULL, converted_at TEXT NOT NULL,
            PRIMARY KEY(kind,source_id,version_key)
        )""")
        db.execute("""INSERT INTO investment_python_conversions
            (kind,source_id,version_key,python_code,converter_scope,converted_at)
            VALUES(?,?,?,?,?,?) ON CONFLICT(kind,source_id,version_key)
            DO UPDATE SET python_code=excluded.python_code,
                converter_scope=excluded.converter_scope,converted_at=excluded.converted_at""",
            ("strategy",input_json["source_id"],input_json["version_key"],python_code,
             spec["supported_subset"],datetime.now(timezone.utc).isoformat()))
        db.commit()
    pg_result=None
    if __import__("os").environ.get("INVESTMENT_DATABASE_URL"):
        from investment_pg import record_conversion
        pg_result=record_conversion(input_json["source_id"],input_json["version_key"],
            python_code, "wf02-n02-convert-v2-nonoverlay",spec["supported_subset"])
    return {"kind":"strategy","source_id":input_json["source_id"],
        "version_key":input_json["version_key"],
        "conversion_id":pg_result["conversion_id"] if pg_result else None,
        "script_version_id":pg_result["script_version_id"] if pg_result else input_json.get("script_version_id"),
        "postgres_sync":pg_result is not None,
        "status":"PYTHON_GENERATED","python_code":python_code,
        "converter_scope":spec["supported_subset"],
        "strategy_spec":spec,"conversion_validated":False,
        "tradingview_chart_validated":False}

def execute_wf02_node03(input_json,*,workflow_kind):
    """Present actual conversion result without announcing TV parity or approval."""
    if workflow_kind!="strategy" or input_json.get("status") not in (
            "UNSUPPORTED_PINE","PYTHON_GENERATED"):
        raise ValueError("WF02_CONVERSION_RESULT_REQUIRED")
    return {**input_json,"paper_enabled":False,"live_orders_enabled":False,
        "conversion_validated":False,"tradingview_chart_validated":False}
