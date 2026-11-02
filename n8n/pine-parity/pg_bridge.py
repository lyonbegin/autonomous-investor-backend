"""Register actual, user-submitted TradingView reference chart results in
the canonical investment PostgreSQL DB. Never infer missing CSV or screenshot.
Artifacts remain on the parity service's persistent Railway volume.
"""
import hashlib,json,os,re
import sqlite3
from datetime import datetime,timezone,timedelta
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit

STORAGE=Path(os.environ.get("PARITY_STORAGE","/data/parity"))

def _sha(raw):return hashlib.sha256(raw).hexdigest()
def _conn():
    import psycopg
    uri=os.getenv("INVESTMENT_DATABASE_URL","")
    if not uri:raise RuntimeError("INVESTMENT_DATABASE_URL_MISSING")
    u=urlsplit(uri)
    return psycopg.connect(urlunsplit((u.scheme,u.netloc,"/autonomous_investment",u.query)),connect_timeout=10)

def _timestamp(value):
    s=str(value).strip()
    try:
        v=float(s)
        if v>1e12:v/=1000
        if v>=100000000: return datetime.fromtimestamp(v,timezone.utc)
    except (ValueError,OverflowError,OSError):pass
    try:
        t=datetime.fromisoformat(s.replace("Z","+00:00"))
        return t if t.tzinfo is not None else t.replace(tzinfo=timezone.utc)
    except ValueError:
        raise ValueError("TV_CSV_TIMESTAMPS_NOT_VERIFIABLE")

def _artifact(cur,run_id,suffix,blob,media,source_class):
    sha=_sha(blob)
    record=cur.execute("""INSERT INTO platform.artifacts
      (sha256,storage_uri,media_type,byte_length,source_class)
      VALUES (%s,%s,%s,%s,%s)
      ON CONFLICT(sha256,byte_length) DO UPDATE SET
      storage_uri=platform.artifacts.storage_uri
      RETURNING artifact_id""",(sha,"parity-file://"+run_id+"/"+suffix,
         media,len(blob),source_class)).fetchone()
    return record[0],sha

def sync_saved_run(run_id):
    if not os.environ.get("INVESTMENT_DATABASE_URL"):
        return {"status":"NOT_CONFIGURED"}
    if not re.fullmatch(r"[0-9a-f]{24}",run_id):
        raise ValueError("INVALID_RUN_ID")
    with sqlite3.connect(STORAGE/"runs.sqlite3") as source:
        source.row_factory=sqlite3.Row
        r=source.execute("SELECT * FROM runs WHERE id=?",(run_id,)).fetchone()
        if not r:raise ValueError("PARITY_RUN_NOT_FOUND")
        row=dict(r)
    if not row["image_kind"]:
        return {"status":"WAITING_REAL_TV_CHART_CAPTURE"}
    files={
        "csv":STORAGE/(run_id+".csv"),
        "reference":STORAGE/(run_id+".reference"),
        "svg":STORAGE/(run_id+".svg"),
        "pine":STORAGE/(run_id+".pine")
    }
    if not all(p.is_file() for p in files.values()):
        raise ValueError("PARITY_MISSING_ORIGINAL_ARTIFACT")
    from engine import read_csv
    csv_raw=files["csv"].read_bytes()
    bars,_=read_csv(csv_raw.decode("utf-8"))
    if len(bars)<2:raise ValueError("TV_REFERENCE_TOO_FEW_BARS")
    first,last=_timestamp(bars[0]["time"]),_timestamp(bars[-1]["time"])
    if not last>first:raise ValueError("TV_CSV_TIME_RANGE_INVALID")
    symbol=row["symbol"].strip()
    venue,native=(symbol.split(":",1) if ":" in symbol else ("UNSPECIFIED",symbol))
    if not venue or not native:raise ValueError("INVALID_SYMBOL")
    pine=files["pine"].read_bytes()
    actual_sha=_sha(pine)
    with _conn() as db:
        with db.cursor() as cur:
            s=cur.execute("""SELECT sv.script_version_id
                FROM catalog.scripts s JOIN catalog.script_versions sv ON sv.script_id=s.script_id
                WHERE s.canonical_url=%s AND sv.content_sha256=%s LIMIT 1""",
                (row["source_url"],actual_sha)).fetchone()
            if not s:
                raise ValueError("SOURCE_VERSION_NOT_REGISTERED_IN_POSTGRES")
            sv=s[0]
            conv=cur.execute("""SELECT conversion_id FROM research.conversions
                  WHERE script_version_id=%s AND status='GENERATED'
                  ORDER BY finished_at DESC LIMIT 1""",(sv,)).fetchone()
            if not conv:raise ValueError("PYTHON_CONVERSION_NOT_REGISTERED")
            instrument=cur.execute("""INSERT INTO market.instruments
                (asset_class,provider,venue,native_symbol,contract_key)
                VALUES('UNKNOWN','TradingView',%s,%s,'')
                ON CONFLICT(provider,venue,native_symbol,contract_key)
                DO UPDATE SET native_symbol=EXCLUDED.native_symbol
                RETURNING instrument_id""",(venue,native)).fetchone()[0]
            csv_id,csv_sha=_artifact(cur,run_id,"tv-export.csv",csv_raw,"text/csv","REAL_TV_EXPORT")
            ref_id,_=_artifact(cur,run_id,"reference",
                files["reference"].read_bytes(),row["image_kind"],"REAL_TV_CAPTURE")
            svg_id,_=_artifact(cur,run_id,"python.svg",files["svg"].read_bytes(),
                "image/svg+xml","GENERATED_CHART")
            dataset=cur.execute("""INSERT INTO market.dataset_snapshots
                (instrument_id,provider,timeframe,time_start,time_end,session_id,
                 exchange_timezone,adjustment_policy,revision,bars_count,artifact_id,content_sha256,
                 quality_state)
                VALUES(%s,'TradingView',%s,%s,%s,'USER_UPLOAD','UNSPECIFIED','UNVERIFIED',
                       %s,%s,%s,%s,'UNVERIFIED_USER_UPLOAD')
                ON CONFLICT(instrument_id,provider,timeframe,time_start,time_end,session_id,adjustment_policy,content_sha256)
                DO UPDATE SET dataset_id=market.dataset_snapshots.dataset_id
                RETURNING dataset_id""",
                (instrument,row["timeframe"],first,last,run_id,len(bars),csv_id,csv_sha)).fetchone()[0]
            # Cannot claim that the submitted screenshot actually corresponds to
            # the plotted strategy inputs, market session, or data timestamps.
            params_sha=_sha(pine)
            settings_sha=_sha((row["symbol"]+"|"+row["timeframe"]).encode())
            reference=cur.execute("""INSERT INTO research.tv_references
                (script_version_id,instrument_id,dataset_id,timeframe,parameters_hash,
                 chart_settings_hash,tv_csv_artifact_id,tv_screenshot_artifact_id,
                 acquisition_method,capture_state,captured_at,comment)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'USER_UPLOAD',
                       'USER_SUBMITTED_UNVERIFIED',%s,
                       'Chart settings and screenshot provenance not independently authenticated')
                ON CONFLICT(script_version_id,dataset_id,parameters_hash,chart_settings_hash,tv_csv_artifact_id,tv_screenshot_artifact_id)
                DO UPDATE SET comment=research.tv_references.comment
                RETURNING reference_id""",
                (sv,instrument,dataset,row["timeframe"],params_sha,settings_sha,csv_id,ref_id,
                 datetime.fromisoformat(row["created_at"]))).fetchone()[0]
            summary=json.loads(row["summary_json"])
            match=bool(summary.get("numeric_match"))
            status=('NUMERIC_MATCH_REVIEW_REQUIRED' if match else
              'NUMERIC_MISMATCH' if row["status"]=='NUMERIC_MISMATCH' else 'WAITING_REFERENCE')
            comparison=cur.execute("""INSERT INTO research.chart_comparisons
                (conversion_id,reference_id,comparison_algorithm_version,status,
                 numeric_match,mismatch_metrics,python_chart_artifact_id,visual_verdict)
                VALUES(%s,%s,'parity-v1',%s,%s,%s::jsonb,%s,'PENDING')
                ON CONFLICT(conversion_id,reference_id,comparison_algorithm_version)
                DO UPDATE SET status=EXCLUDED.status,numeric_match=EXCLUDED.numeric_match,
                  mismatch_metrics=EXCLUDED.mismatch_metrics,
                  python_chart_artifact_id=EXCLUDED.python_chart_artifact_id
                RETURNING comparison_id""",
                (conv[0],reference,status,match,
                 json.dumps({"comparison":summary.get("comparison",[])},ensure_ascii=False),svg_id)).fetchone()[0]
        db.commit()
    return {"status":"RECORDED_UNVERIFIED","comparison_id":str(comparison),
      "reference_id":str(reference),"conversion_id":str(conv[0]),
      "dataset_id":str(dataset),"visual_verdict":"PENDING"}

def reconcile():
    if not os.environ.get("INVESTMENT_DATABASE_URL"):return {"status":"NOT_CONFIGURED"}
    with sqlite3.connect(STORAGE/"runs.sqlite3") as db:
        rows=db.execute("SELECT id FROM runs WHERE image_kind IS NOT NULL ORDER BY created_at DESC LIMIT 100").fetchall()
    summary={"attempted":len(rows),"registered":0,"unlinked":[]}
    for (rid,) in rows:
        try:
            sync_saved_run(rid);summary["registered"]+=1
        except Exception as exc:
            summary["unlinked"].append({"run_id":rid,"reason":str(exc)[:140]})
    return summary
