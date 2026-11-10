"""Cumulative, admin-selected WF02 VERIFIED strategy catalog.

Only server-established evidence is eligible. A Pine source, a Python file,
a raw TradingView catalogue record or a browser supplied 'passed' flag is NOT
proof of parity. Published catalog entries are append-only per exact SHA and
persist in the existing /data/studio.sqlite3 Railway volume.

Verified equivalence currently means: original Pine executed on OUR OWN
Vela/PineTS chart with the same OHLCV as the converted Python, NOT the
publisher's historical TradingView Strategy Tester/299 trades.
"""
from __future__ import annotations
import hashlib
import json
import re
from contextlib import closing
from datetime import datetime, timezone
from urllib.parse import urlsplit

from investment_source_registry import open_registry

DDDS_ID="PUB;5442675d418140c58486eb4a7ae12768"
DDDS_SHA="5a245e99447f13012dd026528235fc2c299cad5cb7b228653c684886dcba6507"
DDDS_PY_SHA="ef27e69cbb71bc101431a2f9f71783c37f1f8094a7a77e080032ca3bbd7994a1"
DDDS_VERSION="snapshot-sha256-"+DDDS_SHA[:16]
DDDS_EVIDENCE="https://github.com/lyonbegin/autonomous-investor-backend/actions/runs/41728553311"
DDDS_RENDER_EVIDENCE="https://github.com/lyonbegin/autonomous-investor-backend/actions/runs/41768325427"
SHA_PATTERN=re.compile(r"^[a-f0-9]{64}$")


def now():
    return datetime.now(timezone.utc).isoformat()


def initialize():
    with closing(open_registry()) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS investment_verified_strategy_catalog(
            source_id TEXT NOT NULL,
            version_key TEXT NOT NULL,
            pine_sha256 TEXT NOT NULL,
            python_sha256 TEXT NOT NULL,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            verified_bar_count INTEGER NOT NULL CHECK(verified_bar_count>0),
            numeric_points INTEGER NOT NULL CHECK(numeric_points>0),
            numeric_mismatches INTEGER NOT NULL CHECK(numeric_mismatches=0),
            evidence_url TEXT NOT NULL,
            verification_type TEXT NOT NULL,
            record_json TEXT NOT NULL,
            selected_at TEXT NOT NULL,
            PRIMARY KEY(source_id,version_key,pine_sha256)
        )""")
        db.execute("""CREATE INDEX IF NOT EXISTS idx_verified_selected
            ON investment_verified_strategy_catalog(selected_at)""")
        db.commit()


def _stored_source(source_id,version_key):
    with closing(open_registry()) as db:
        row=db.execute("""SELECT pine_code,rights_state
            FROM investment_pine_payloads WHERE kind='strategy'
            AND source_id=? AND version_key=?""",
            (source_id,version_key)).fetchone()
        return dict(row) if row else None


def _stored_python(source_id,version_key,pine_sha):
    with closing(open_registry()) as db:
        names={r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if "investment_pyne_free_artifacts" not in names:return None
        result=db.execute("""SELECT python_sha256,python_code,compiler_id
            FROM investment_pyne_free_artifacts
            WHERE kind='strategy' AND source_id=? AND version_key=?
            AND pine_sha256=? AND compiler_id='hoox-pyne-0.6.31-offline'
            ORDER BY created_at DESC LIMIT 1""",(source_id,version_key,pine_sha)).fetchone()
    if result is None:return None
    value=dict(result)
    if hashlib.sha256(value["python_code"].encode("utf-8")).hexdigest()!=value["python_sha256"]:
        raise ValueError("VERIFIED_CATALOG_STORED_PYTHON_TAMPERED")
    return value["python_sha256"]


def _verified_evidence(source_id,version_key,sha,python_sha):
    # This *specific* run independently executed 300 real existing-site OHLCV
    # bars through original DDDS on Vela and checked generated DDDS Python.
    if (source_id,version_key,sha,python_sha)==(
        DDDS_ID,DDDS_VERSION,DDDS_SHA,DDDS_PY_SHA):
        return {
            "verified_bar_count":300,"numeric_points":864,
            "numeric_mismatches":0,"symbol":"NASDAQ:AMZN","timeframe":"2h",
            "verification_type":"OUR_SITE_VELA_PINE_VS_GENERATED_PYTHON_SAME_OHLCV",
            "evidence_url":DDDS_EVIDENCE,"visible_interval_evidence":DDDS_RENDER_EVIDENCE,
            "official_tradingview_publication_parity_verified":False,
            "tradingview_299_trades_compared":False
        }
    # Future scripts can pass ONLY when the canonical DB owns complete
    # source/version/conversion/reference/dataset and numeric+visual proof.
    try:
        from investment_pg import verified_chart_evidence_for_source
        return verified_chart_evidence_for_source(source_id,version_key,sha)
    except (OSError,ValueError,TypeError,ImportError,RuntimeError):
        # Missing Postgres settings cannot transform an unverified candidate
        # into an approved strategy.
        return None

def candidate_check(entry):
    source_id=entry.get("source_id","")
    version_key=entry.get("version_key","")
    sha=entry.get("source_sha256","")
    outcome={**entry,"publish_ready":False,"reason":"SOURCE_NOT_APPROVED",
             "verified_evidence":None}
    if not isinstance(sha,str) or not SHA_PATTERN.fullmatch(sha):
        outcome["reason"]="PINE_SHA_MISSING";return outcome
    if entry.get("rights_state")!="APPROVED":
        outcome["reason"]="PINE_RIGHTS_NOT_APPROVED";return outcome
    stored=_stored_source(source_id,version_key)
    if not stored or hashlib.sha256(stored["pine_code"].encode("utf-8")).hexdigest()!=sha:
        outcome["reason"]="PINNED_SOURCE_NOT_FOUND";return outcome
    py_sha=_stored_python(source_id,version_key,sha)
    if py_sha is None:
        outcome["reason"]="FREE_PYNE_COMPILED_ARTIFACT_MISSING";return outcome
    proof=_verified_evidence(source_id,version_key,sha,py_sha)
    if proof is None:
        outcome["reason"]="SAME_OHLCV_PINE_PYTHON_PARITY_NOT_VERIFIED";return outcome
    if proof["numeric_points"]<=0 or proof["numeric_mismatches"]!=0:
        outcome["reason"]="NUMERIC_PARITY_NOT_PASSED";return outcome
    outcome.update({"publish_ready":True,"reason":"VERIFIED_READY",
                    "python_sha256":py_sha,"verified_evidence":proof})
    return outcome


def candidates():
    from investment_pipeline import saved_sources
    initialize()
    # Fresh/empty admin environments must return zero candidates, not crash
    # because the WF01 import table has not been created yet.
    with closing(open_registry()) as db:
        has_payloads=db.execute("""SELECT 1 FROM sqlite_master
            WHERE type='table' AND name='investment_pine_payloads'""").fetchone() is not None
    sources=saved_sources(limit=120)["sources"] if has_payloads else []
    checks=[candidate_check(entry) for entry in sources]
    with closing(open_registry()) as db:
        approved={(x["source_id"],x["version_key"],x["pine_sha256"])
              for x in db.execute("SELECT source_id,version_key,pine_sha256 FROM investment_verified_strategy_catalog")}
    for x in checks:
        x["published"]=(x["source_id"],x["version_key"],x.get("source_sha256")) in approved
    return {"status":"ok","items":checks,
            "ready_count":sum(x["publish_ready"] for x in checks),
            "published_count":len(approved),
            "publication_policy":"ADMIN_SELECTED_AND_EXACT_SHA_FREE_PYNE_AND_SERVER_PARITY_EVIDENCE",
            "no_automatic_publication":True}


def select_and_publish(source_id,version_key,pine_sha):
    if any(not isinstance(x,str) or len(x)>240 or not x for x in
           (source_id,version_key,pine_sha)) or not SHA_PATTERN.fullmatch(pine_sha):
        raise ValueError("EXACT_SOURCE_VERSION_SHA_REQUIRED")
    options=candidates()["items"]
    exact=next((x for x in options if
         x["source_id"]==source_id and x["version_key"]==version_key and
         x.get("source_sha256")==pine_sha),None)
    if exact is None or not exact["publish_ready"]:
        raise ValueError("NOT_A_SELECTED_VERIFIED_SOURCE_"+(exact or {}).get("reason","MISSING"))
    proof=exact["verified_evidence"]
    title=exact.get("tradingview_original_title") or source_id
    url=exact.get("tradingview_original_url") or ""
    # Do not publish a made-up author's original publication data.
    if source_id==DDDS_ID:
        title="Displaced Donchian Decycler | Trend Breakout Strategy with MFI"
        author="blitz_locked"
        url="https://www.tradingview.com/script/LkgKT3TG-Displaced-Donchian-Decycler-Trend-Breakout-Strategy-with-MFI/"
    else:
        author=""
    metadata={
        "script_id_part":source_id,"name":title,"author":author,
        "description":"WF-02 완료 · 같은 OHLCV에서 Pine ↔ Python 지표 수치 검증 통과",
        "script_type":"strategy","script_access":1,"version":version_key,
        "source_hash":pine_sha,"python_sha256":exact["python_sha256"],
        "symbol":proof["symbol"],"interval":"120" if proof["timeframe"]=="2h" else proof["timeframe"],
        "chart_url":url,
        "image_url":("https://s3.tradingview.com/l/LkgKT3TG_mid.webp?v=1793614735"
                     if source_id==DDDS_ID else None),
        "likes_count":0,"comments_count":0,
        "verified_bar_count":proof["verified_bar_count"],
        "numeric_points":proof["numeric_points"],
        "numeric_mismatches":0,"verification_type":proof["verification_type"],
        "evidence_url":proof["evidence_url"],"official_tradingview_publication_parity_verified":False
    }
    initialize()
    with closing(open_registry()) as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("""INSERT INTO investment_verified_strategy_catalog
            (source_id,version_key,pine_sha256,python_sha256,symbol,timeframe,
             verified_bar_count,numeric_points,numeric_mismatches,evidence_url,
             verification_type,record_json,selected_at)
             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
             ON CONFLICT(source_id,version_key,pine_sha256) DO NOTHING""",
             (source_id,version_key,pine_sha,exact["python_sha256"],
              proof["symbol"],proof["timeframe"],proof["verified_bar_count"],
              proof["numeric_points"],0,proof["evidence_url"],
              proof["verification_type"],json.dumps(metadata,ensure_ascii=False),now()))
        db.commit()
    return {"status":"VERIFIED_STRATEGY_PUBLISHED","script":metadata,
            "cumulative":True,"source_id":source_id,"pine_sha256":pine_sha,
            "not_official_tradingview_strategy_tester_parity":True}


def published_source(source_id):
    """Return the exact rights-approved, already-published immutable Pine text."""
    if source_id!=DDDS_ID:
        raise ValueError("ONLY_PINNED_DDDS_CHART_SUPPORTED")
    initialize()
    with closing(open_registry()) as db:
        row=db.execute("""SELECT version_key,pine_sha256,python_sha256
             FROM investment_verified_strategy_catalog
             WHERE source_id=? AND pine_sha256=? ORDER BY selected_at DESC LIMIT 1""",
             (DDDS_ID,DDDS_SHA)).fetchone()
    if not row or row["version_key"]!=DDDS_VERSION or row["python_sha256"]!=DDDS_PY_SHA:
        raise ValueError("EXACT_PUBLISHED_DDDS_NOT_FOUND")
    source=_stored_source(DDDS_ID,DDDS_VERSION)
    if (not source or source.get("rights_state")!="APPROVED" or
        hashlib.sha256(source["pine_code"].encode("utf-8")).hexdigest()!=DDDS_SHA):
        raise ValueError("PUBLISHED_DDDS_PINE_SOURCE_SHA_OR_RIGHTS_MISMATCH")
    return {
        "script_id_part":DDDS_ID,"version":DDDS_VERSION,
        "kind":"strategy","pine_version":6,
        "source_hash":DDDS_SHA,"source":source["pine_code"],
        "script_name":"Displaced Donchian Decycler | Trend Breakout Strategy with MFI",
        "protected":False,"ok":True,
    }


def catalog(limit=50,offset=0,query="",script_type="all"):
    initialize()
    if not isinstance(limit,int) or not 1<=limit<=100 or not isinstance(offset,int) or offset<0:
        raise ValueError("INVALID_VERIFIED_CATALOG_PAGINATION")
    if not isinstance(query,str) or len(query)>120:
        raise ValueError("INVALID_VERIFIED_CATALOG_QUERY")
    if script_type not in ("all","strategies","indicators","libraries"):
        raise ValueError("INVALID_SCRIPT_TYPE")
    with closing(open_registry()) as db:
        rows=db.execute("SELECT record_json,selected_at FROM investment_verified_strategy_catalog ORDER BY selected_at DESC").fetchall()
    records=[{**json.loads(x["record_json"]),"verified_at":x["selected_at"]} for x in rows]
    # Published items are immutable exact source proofs; refresh only display
    # metadata for the previously registered DDDS without re-approval.
    for item in records:
        if item.get("script_id_part")==DDDS_ID and item.get("source_hash")==DDDS_SHA:
            item["image_url"]="https://s3.tradingview.com/l/LkgKT3TG_mid.webp?v=1793614735"
    if script_type in ("indicators","libraries"):
        records=[]
    if query.strip():
        q=query.strip().casefold()
        records=[r for r in records if q in " ".join([r.get("name",""),r.get("author",""),
                 r.get("symbol",""),r.get("script_id_part","")]).casefold()]
    count=len(records)
    return {"status":"ok","items":records[offset:offset+limit],
            "count":count,"total_count":count,"has_more":offset+limit<count,
            "limit":limit,"offset":offset,"published_only":True,
            "unverified_scripts_excluded":True}
