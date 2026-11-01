"""Investment-owned Pine/TradingView parity review service.

Public sandbox: strict text/CSV interpreter; no dynamic Python exec, no TradingView
session spoofing, no trading. TradingView screenshot is provided by the operator.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse
import base64, hashlib, json, os, re, sqlite3, time
from engine import analyze, UnsupportedPine

HERE=Path(__file__).resolve().parent
STORAGE=Path(os.environ.get("PARITY_STORAGE","/data/parity"))
DB=STORAGE/"runs.sqlite3"
RID=re.compile(r"^[0-9a-f]{24}$")

def init():
    STORAGE.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(DB,timeout=20) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS runs(
          id TEXT PRIMARY KEY,created_at TEXT NOT NULL,source_url TEXT NOT NULL,
          symbol TEXT NOT NULL,timeframe TEXT NOT NULL,
          status TEXT NOT NULL,summary_json TEXT NOT NULL,
          trace_json TEXT NOT NULL,pine_sha TEXT NOT NULL,csv_sha TEXT NOT NULL,
          image_kind TEXT,visual_review TEXT NOT NULL DEFAULT 'PENDING'
        )""")

def read_run(run_id):
    if not RID.fullmatch(run_id):return None
    with sqlite3.connect(DB,timeout=20) as db:
        db.row_factory=sqlite3.Row
        row=db.execute("SELECT * FROM runs WHERE id=?",(run_id,)).fetchone()
    return dict(row) if row else None

def stage_trace(name, status, input_data=None, output_data=None, elapsed_ms=0, error=None):
    return {"node":name,"status":status,"input":input_data or {},
            "output":output_data or {},"duration_ms":round(elapsed_ms,3),"error":error}

class Handler(BaseHTTPRequestHandler):
    server_version="InvestmentPineParity/0.1"
    def log_message(self,fmt,*args):
        print(json.dumps({"type":"HTTP","at":datetime.now(timezone.utc).isoformat(),
            "client":self.client_address[0],"message":fmt%args}),flush=True)
    def response(self,status,body,content_type="application/json; charset=utf-8"):
        data=(json.dumps(body,ensure_ascii=False,allow_nan=False).encode() if isinstance(body,(dict,list))
              else body.encode() if isinstance(body,str) else body)
        self.send_response(status)
        self.send_header("Content-Type",content_type)
        self.send_header("Content-Length",str(len(data)))
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Content-Security-Policy","default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; object-src 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)
    def do_GET(self):
        path=urlparse(self.path).path
        if path=="/health":return self.response(200,{"status":"ok","mode":"STRICT_SUBSET_NO_LIVE_TV_AUTOMATION"})
        if path in ("/","/index.html"):
            return self.response(200,(HERE/"index.html").read_bytes(),"text/html; charset=utf-8")
        if path=="/app.js":
            return self.response(200,(HERE/"app.js").read_bytes(),"application/javascript; charset=utf-8")
        parts=path.strip("/").split("/")
        if len(parts)==3 and parts[:2]==["api","runs"]:
            r=read_run(parts[2])
            if not r:return self.response(404,{"error":"RUN_NOT_FOUND"})
            detail=json.loads(r["summary_json"])
            detail.update({"run_id":r["id"],"created_at":r["created_at"],
                "source_url":r["source_url"],"symbol":r["symbol"],
                "timeframe":r["timeframe"],"status":r["status"],
                "reference_screenshot_url":f"/artifacts/{r['id']}/reference" if r["image_kind"] else None,
                "python_chart_url":f"/artifacts/{r['id']}/python.svg",
                "python_code_url":f"/artifacts/{r['id']}/strategy.py",
                "visual_review":r["visual_review"],"trace_url":f"/api/runs/{r['id']}/trace"})
            return self.response(200,detail)
        if len(parts)==4 and parts[:2]==["api","runs"] and parts[3]=="trace":
            r=read_run(parts[2])
            return self.response(200,{"run_id":parts[2],"events":json.loads(r["trace_json"])}
                                 ) if r else self.response(404,{"error":"RUN_NOT_FOUND"})
        if len(parts)==3 and parts[0]=="artifacts" and RID.fullmatch(parts[1]):
            r=read_run(parts[1])
            if not r:return self.response(404,{"error":"RUN_NOT_FOUND"})
            if parts[2]=="python.svg":
                return self.response(200,(STORAGE/(r["id"]+".svg")).read_bytes(),"image/svg+xml")
            if parts[2]=="strategy.py":
                return self.response(200,(STORAGE/(r["id"]+".py")).read_bytes(),"text/plain; charset=utf-8")
            if parts[2]=="reference" and r["image_kind"]:
                return self.response(200,(STORAGE/(r["id"]+".reference")).read_bytes(),r["image_kind"])
        return self.response(404,{"error":"NOT_FOUND"})
    def do_POST(self):
        if urlparse(self.path).path!="/api/compare":
            return self.response(404,{"error":"NOT_FOUND"})
        origin=self.headers.get("Origin")
        host=self.headers.get("Host")
        if origin and urlparse(origin).netloc!=host:
            return self.response(403,{"error":"SAME_ORIGIN_ONLY"})
        if not self.headers.get("Content-Type","").startswith("application/json"):
            return self.response(415,{"error":"JSON_REQUIRED"})
        try:
            length=int(self.headers.get("Content-Length","0"))
            if not 2<=length<=5_600_000:raise ValueError("REQUEST_TOO_LARGE")
            obj=json.loads(self.rfile.read(length))
            if not isinstance(obj,dict):raise ValueError("OBJECT_REQUIRED")
            pine=obj.get("pine_code")
            csv_text=obj.get("csv_text")
            source_url=obj.get("source_url") or ""
            symbol=str(obj.get("symbol") or "")[:100]
            timeframe=str(obj.get("timeframe") or "")[:30]
            if not isinstance(source_url,str) or len(source_url)>1000:
                raise ValueError("INVALID_SOURCE_URL")
            if source_url:
                u=urlparse(source_url)
                if u.scheme!="https" or u.hostname not in ("tradingview.com","www.tradingview.com","kr.tradingview.com"):
                    raise ValueError("SOURCE_URL_MUST_BE_TRADINGVIEW")
            if not symbol or not timeframe:raise ValueError("SYMBOL_TIMEFRAME_REQUIRED")
            image=obj.get("screenshot_data_url") or ""
            image_bytes=None;image_kind=None
            if image:
                if not isinstance(image,str) or len(image)>3_300_000:
                    raise ValueError("SCREENSHOT_TOO_LARGE")
                m=re.fullmatch(r"data:(image/png|image/jpeg);base64,([A-Za-z0-9+/=]+)",image)
                if not m:raise ValueError("PNG_OR_JPEG_SCREENSHOT_ONLY")
                image_kind=m.group(1)
                image_bytes=base64.b64decode(m.group(2),validate=True)
                if len(image_bytes)>2_400_000 or not (image_bytes.startswith(b"\x89PNG\r\n\x1a\n") if image_kind=="image/png" else image_bytes.startswith(b"\xff\xd8\xff")):
                    raise ValueError("INVALID_SCREENSHOT_CONTENT")
            t=time.perf_counter()
            events=[stage_trace("01 TradingView original/reference submission","DONE",
                {"source_url":source_url,"symbol":symbol,"timeframe":timeframe},
                {"screenshot_provided":bool(image_bytes),"tv_csv_provided":bool(csv_text)})]
            result=analyze(pine,csv_text,obj.get("columns"),title=f"{symbol} {timeframe} / Python")
            duration=(time.perf_counter()-t)*1000
            events.extend([
                stage_trace("02 Pine parse and supported syntax", "DONE",
                            {"pine_sha256":result["pine_sha256"]},
                            {"supported_subset":result["strategy"]["supported_subset"]}),
                stage_trace("03 identical TradingView CSV input","DONE",
                            {"csv_sha256":result["csv_sha256"]},
                            {"bars":result["bars"],"headers":result["csv_headers"]}),
                stage_trace("04 Python strategy execution","DONE",{},
                            {"trades":result["trade_count"]}),
                stage_trace("05 Python chart SVG rendering","DONE",{},
                            {"chart_output":"Python-rendered SVG"}),
                stage_trace("06 exported TV series vs Python numeric comparison",
                            "DONE" if result["numeric_match"] else "INCOMPLETE_OR_MISMATCH",{},
                            {"comparisons":result["comparison"],"numeric_match":result["numeric_match"]},
                            duration),
                stage_trace("07 TradingView original chart visual review","PENDING",
                            {"screenshot_provided":bool(image_bytes)},
                            {"result":"MANUAL_VISUAL_REVIEW_REQUIRED"})
            ])
            run_id=os.urandom(12).hex()
            status=result["status"]
            if not image_bytes and status=="NUMERIC_MATCH_VISUAL_REVIEW_REQUIRED":
                status="TRADINGVIEW_SCREENSHOT_REQUIRED"
            now=datetime.now(timezone.utc).isoformat()
            svg=result.pop("svg")
            generated_python=result.pop("python_code")
            (STORAGE/(run_id+".svg")).write_text(svg,encoding="utf-8")
            (STORAGE/(run_id+".py")).write_text(generated_python,encoding="utf-8")
            if image_bytes:(STORAGE/(run_id+".reference")).write_bytes(image_bytes)
            with sqlite3.connect(DB,timeout=20) as db:
                db.execute("""INSERT INTO runs
                  (id,created_at,source_url,symbol,timeframe,status,summary_json,trace_json,pine_sha,csv_sha,image_kind)
                  VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                  (run_id,now,source_url,symbol,timeframe,status,
                   json.dumps(result,ensure_ascii=False),json.dumps(events,ensure_ascii=False),
                   result["pine_sha256"],result["csv_sha256"],image_kind))
            return self.response(200,{"run_id":run_id,"status":status,"numeric_match":result["numeric_match"],
                "visual_verdict":"NOT_YET_VERIFIED","comparison":result["comparison"],
                "bars":result["bars"],"trade_count":result["trade_count"],
                "reference_screenshot_url":f"/artifacts/{run_id}/reference" if image_bytes else None,
                "python_chart_url":f"/artifacts/{run_id}/python.svg",
                "python_code_url":f"/artifacts/{run_id}/strategy.py",
                "trace_url":f"/api/runs/{run_id}/trace",
                "details_url":f"/api/runs/{run_id}","pine_sha256":result["pine_sha256"]})
        except (ValueError,UnsupportedPine,UnicodeDecodeError,json.JSONDecodeError) as e:
            return self.response(422,{"error":str(e),"status":"REJECTED_NO_PARITY_CLAIM"})
        except Exception as e:
            print("PARITY_INTERNAL_ERROR",type(e).__name__,str(e),flush=True)
            return self.response(500,{"error":"INTERNAL_ERROR"})

if __name__=="__main__":
    init()
    port=int(os.environ.get("PORT","3000"))
    print(f"Pine parity visual review listening on :{port}",flush=True)
    ThreadingHTTPServer(("0.0.0.0",port),Handler).serve_forever()
