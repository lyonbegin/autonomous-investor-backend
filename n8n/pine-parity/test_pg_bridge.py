"""PostgreSQL parity linking tests use SYNTHETIC fixtures in an isolated DB.
No test result is real TradingView evidence.
"""
import json,os,sqlite3,tempfile,unittest
from pathlib import Path

class ChartPostgresTests(unittest.TestCase):
 def test_chart_reference_links_exact_source_conversion_and_is_idempotent(self):
  if not os.getenv("INVESTMENT_DATABASE_URL"):self.skipTest("requires isolated PG test server")
  with tempfile.TemporaryDirectory() as directory:
   os.environ["INVESTMENT_ARTIFACT_ROOT"]=directory+"/artifacts"
   os.environ["INVESTMENT_BACKUP_ROOT"]=directory+"/backups"
   os.environ["PARITY_STORAGE"]=directory+"/parity"
   os.environ["STUDIO_DB_PATH"]=directory+"/studio.sqlite"
   import investment_pg as pg
   pg.ARTIFACT_ROOT=Path(directory+"/artifacts")
   pg.SQLITE_PATH=Path(directory+"/studio.sqlite")
   pg.bootstrap()
   from test_investment_wf02 import SUPPORTED
   x=pg.record_source("strategy","PUB;parity-fixture","1",SUPPORTED,
      "https://www.tradingview.com/script/abcdefgh/","PENDING_REVIEW")
   python_code="def run_strategy(bars):\n    return {'trades': []}\n"
   conversion=pg.record_conversion("PUB;parity-fixture","1",python_code,"fixture-converter")
   import pg_bridge
   pg_bridge.STORAGE=Path(directory+"/parity")
   pg_bridge.STORAGE.mkdir()
   rid="a"*24
   lines=["time,open,high,low,close"]
   for i in range(42):
    lines.append(f"2026-01-01T{i//24:02d}:{i%24:02d}:00Z,100,101,99,100")
   csv_bytes=("\n".join(lines)+"\n").encode()
   (pg_bridge.STORAGE/(rid+".csv")).write_bytes(csv_bytes)
   (pg_bridge.STORAGE/(rid+".pine")).write_text(SUPPORTED)
   (pg_bridge.STORAGE/(rid+".svg")).write_text("<svg xmlns='http://www.w3.org/2000/svg'></svg>")
   (pg_bridge.STORAGE/(rid+".reference")).write_bytes(b"\x89PNG\r\n\x1a\n"+b"synthetic-only")
   dbpath=pg_bridge.STORAGE/"runs.sqlite3"
   with sqlite3.connect(dbpath) as db:
    db.execute("""CREATE TABLE runs(id TEXT PRIMARY KEY,created_at TEXT,source_url TEXT,
     symbol TEXT,timeframe TEXT,status TEXT,summary_json TEXT,trace_json TEXT,pine_sha TEXT,
     csv_sha TEXT,image_kind TEXT,visual_review TEXT)""")
    db.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(
       rid,"2026-01-03T00:00:00+00:00",
       "https://www.tradingview.com/script/abcdefgh/","NASDAQ:AAPL","1h",
       "REFERENCE_COLUMNS_REQUIRED",
       json.dumps({"numeric_match":False,"comparison":[]}),"[]",x["sha256"],"0"*64,
       "image/png","PENDING"))
   a=pg_bridge.sync_saved_run(rid)
   b=pg_bridge.sync_saved_run(rid)
   self.assertEqual(a["comparison_id"],b["comparison_id"])
   self.assertEqual(a["status"],"RECORDED_UNVERIFIED")
   with pg.connect() as db:
    row=db.execute("""SELECT c.status,c.visual_verdict,v.script_version_id
        FROM research.chart_comparisons c
        JOIN research.tv_references v ON v.reference_id=c.reference_id
        WHERE c.comparison_id=%s""",(a["comparison_id"],)).fetchone()
    self.assertEqual(row[0],"WAITING_REFERENCE")
    self.assertEqual(row[1],"PENDING")
    self.assertEqual(str(row[2]),x["script_version_id"])
   print("SYNTHETIC_FIXTURE_PG_CHART_FK_AND_IDEMPOTENCY_OK")

if __name__=="__main__":unittest.main()
