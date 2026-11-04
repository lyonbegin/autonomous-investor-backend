"""Markets + actual 10-year 1D inventory and manual-only collector API.

A navigation taxonomy modeled on market categories, not a TradingView data feed.
Never invent bars/market listings; distinguish listing, disk files and 10Y eligibility.
All network updates require an explicit authorized POST. No cron or startup jobs.
"""
from __future__ import annotations

import csv
import hashlib
import hmac
import json
import os
import re
import shutil
import sqlite3
import threading
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .collector import Instrument, Store, load_universe, sync, ten_year_window

ROOT = Path(os.getenv("DAILY_POOL_ROOT", "/data/market_daily_10y"))
ASSET_MENU = [
    {"id":"index","title":"지수","subtitle":"한국 · 세계 주요 지수"},
    {"id":"equity","title":"주식","subtitle":"국가 · 거래소별 종목"},
    {"id":"etf","title":"ETF","subtitle":"상장지수펀드"},
    {"id":"crypto","title":"암호화폐","subtitle":"현물 · 파생상품"},
    {"id":"futures","title":"선물·원자재","subtitle":"지수 · 에너지 · 금속 · 농산물"},
    {"id":"fx","title":"외환","subtitle":"주요 통화쌍"},
    {"id":"bonds","title":"채권","subtitle":"국채 · 채권형 ETF"},
    {"id":"economy","title":"경제","subtitle":"거시경제 지표"},
]
CATEGORY_BY_ASSET = {
    "index":"index", "equity":"equity", "etf":"etf",
    "crypto_spot":"crypto", "crypto_future":"crypto",
    "future":"futures","commodity":"futures",
    "fx":"fx", "bond":"bonds","rate":"bonds",
}
WEB = Path(__file__).parent / "web"
app = FastAPI(title="시장 및 10년 일봉 데이터 현황", version="1.0.0")
app.mount("/markets/assets", StaticFiles(directory=WEB), name="markets-assets")

def _store():
    return Store(ROOT)

def _asof():
    # Today's still-open candle is always excluded, regardless of time zone.
    return datetime.now(timezone.utc).date()

def _catalog_path():
    world = ROOT / "universe" / "world.csv"
    return world if world.exists() else Path(__file__).parent / "universe.csv"

def _stock_country(exchange):
    if exchange in ("NASDAQ","NYSE","NYSEARCA","NYSEAMERICAN","CBOE","IEX","US"):
        return "미국"
    if exchange in ("KRX","KR","KOSPI","KOSDAQ"):return "한국"
    if exchange in ("TSE","JP","JPX"):return "일본"
    if exchange in ("HKEX","HK"):return "홍콩"
    return {
        "NSE":"인도","BSE":"인도","LSE":"영국","XETRA":"독일",
        "ASX":"호주","TSX":"캐나다","SSE":"중국","SZSE":"중국",
    }.get(exchange,"기타")

def _inventory():
    """Actual catalog, plus actually stored records not present in current universe."""
    path = _catalog_path()
    entries = {}
    with path.open(encoding="utf-8-sig", newline="") as source:
        for record in csv.DictReader(source):
            try:
                inst=Instrument(record["asset_class"],record["exchange"],
                                record["symbol"],record["vendor_symbol"],
                                record["timezone"],record.get("calendar") or "weekday",
                                record.get("contract_type") or "spot")
                entries[inst.key]=inst
            except (KeyError, ValueError):
                continue
    rows = _store().status()["instruments"]
    stored = {r["key"]:r for r in rows}
    for r in rows:
        if r["key"] in entries:
            continue
        try:
            inst=Instrument(r["asset_class"],r["exchange"],r["symbol"],
                            r["vendor_symbol"],r["timezone"],r["calendar"],
                            r["contract_type"])
            entries[inst.key]=inst
        except (KeyError,ValueError):
            continue
    return entries,stored,path

def _row(inst, record, asof):
    category=CATEGORY_BY_ASSET.get(inst.asset_class,"other")
    path=_store().file(inst)
    exists=path.is_file() if record else False
    status="미확보"
    if record:
        if not exists:status="파일 누락"
        elif not record["eligible"]:status="10년 미충족"
        elif record["end_exclusive"] != str(asof):status="갱신 필요"
        else:status="10년 확보"
    return {
        "key":inst.key,"symbol":inst.symbol,"vendor_symbol":inst.vendor_symbol,
        "asset_class":inst.asset_class,"category":category,
        "country":_stock_country(inst.exchange),
        "exchange":inst.exchange,"contract_type":inst.contract_type,
        "status":status,"has_file":exists,
        "eligible":bool(record["eligible"]) and exists if record else False,
        "rows":record["rows"] if record else 0,
        "coverage":record["coverage"] if record else None,
        "first_date":record["first_date"] if record else None,
        "last_date":record["last_date"] if record else None,
        "window_start":record["start"] if record else None,
        "end_exclusive":record["end_exclusive"] if record else None,
        "updated_at":record["updated_at"] if record else None,
        "reasons":json.loads(record["reasons"] or "[]") if record else ["NOT_COLLECTED"],
    }

def _authed(auth):
    secret = os.getenv("MARKET_UPDATE_TOKEN","")
    if not secret:
        raise HTTPException(503,"수동 업데이트 관리 토큰이 설정되지 않았습니다")
    token=auth.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(token.encode(),secret.encode()):
        raise HTTPException(403,"업데이트 권한이 없습니다")

@app.get("/")
def home():
    return RedirectResponse("/markets/")

@app.get("/markets/")
def markets_home():
    return FileResponse(WEB/"index.html")

@app.get("/health")
def health():
    return {"status":"ok","collection_schedule":"MANUAL_ONLY","timeframe":"1d"}

@app.get("/api/markets/categories")
def categories():
    return {"categories":ASSET_MENU,"source":"market navigation taxonomy",
            "tradingview_prices_imported":False}

@app.get("/api/markets/summary")
def summary():
    entries,stored,source=_inventory()
    today=_asof()
    totals={"listed":len(entries),"stored_records":len(stored),"stored_files":0,
            "eligible_10y_any_snapshot":0,"eligible_10y_current_snapshot":0,
            "missing":0,"ineligible":0,"stale":0}
    groups={m["id"]:{"listed":0,"files":0,"eligible":0,"missing":0} for m in ASSET_MENU}
    for inst in entries.values():
        d=_row(inst,stored.get(inst.key),today)
        g=groups.get(d["category"])
        if g is not None:
            g["listed"]+=1
            g["files"]+=int(d["has_file"])
            g["eligible"]+=int(d["eligible"])
            g["missing"]+=int(d["status"]=="미확보")
        totals["stored_files"]+=int(d["has_file"])
        totals["eligible_10y_any_snapshot"]+=int(d["eligible"])
        totals["eligible_10y_current_snapshot"]+=int(d["status"]=="10년 확보")
        totals["missing"]+=int(d["status"]=="미확보")
        totals["ineligible"]+=int(d["status"] in ("10년 미충족","파일 누락"))
        totals["stale"]+=int(d["status"]=="갱신 필요")
    return {"totals":totals,"groups":groups,"asof_exclusive":str(today),
            "universe_file":source.name,"universe_complete_worldwide":False,
            "cron_enabled":False,"download_only_on_manual_click":True,
            "note":"상장 목록 수와 실제 가격 파일 수는 다릅니다."}

@app.get("/api/markets/instruments")
def instruments(
    category:str="equity",q:str="",exchange:str="",status:str="",
    page:int=Query(default=1,ge=1),per_page:int=Query(default=40,ge=1,le=150),
):
    entries,stored,_=_inventory()
    today=_asof()
    q=q.strip().casefold()[:120]
    matching=[]
    for inst in entries.values():
        cat=CATEGORY_BY_ASSET.get(inst.asset_class,"other")
        if category not in ("all",cat):
            continue
        if exchange and inst.exchange!=exchange:
            continue
        if q and q not in (inst.key+" "+inst.vendor_symbol).casefold():
            continue
        row=_row(inst,stored.get(inst.key),today)
        if status and row["status"]!=status:
            continue
        matching.append(row)
    matching.sort(key=lambda x:(x["exchange"],x["symbol"]))
    count=len(matching)
    return {"total":count,"page":page,"per_page":per_page,
            "items":matching[(page-1)*per_page:page*per_page],
            "exchanges":sorted({x.exchange for x in entries.values()
                if category=="all" or CATEGORY_BY_ASSET.get(x.asset_class)==category})}

@app.get("/api/markets/bars")
def bars(key:str,authorization:str|None=Header(default=None)):
    # Actual Yahoo-sourced raw price history remains private research data.
    _authed(authorization or "")
    entries,stored,_=_inventory()
    inst=entries.get(key)
    if not inst or key not in stored:
        raise HTTPException(404,"해당 종목의 저장된 일봉이 없습니다")
    record=stored[key]
    path=_store().file(inst)
    if not path.is_file():
        raise HTTPException(404,"Parquet 파일이 존재하지 않습니다")
    if hashlib.sha256(path.read_bytes()).hexdigest()!=record["sha256"]:
        raise HTTPException(409,"저장된 파일의 SHA-256 검증에 실패했습니다")
    frame=_store().read(inst)
    if frame.empty:
        raise HTTPException(404,"일봉 데이터가 비어 있습니다")
    for col in ("date","open","high","low","close","volume"):
        if col not in frame.columns:
            raise HTTPException(409,"OHLCV 컬럼 누락")
    data=[]
    for d in frame.itertuples(index=False):
        def num(x):
            try:
                value=float(x)
                return value if value==value and abs(value)!=float("inf") else None
            except (TypeError,ValueError):
                return None
        data.append({"date":str(d.date),"open":num(d.open),
                     "high":num(d.high),"low":num(d.low),
                     "close":num(d.close),"volume":num(d.volume)})
    return {"key":key,"asof_exclusive":record["end_exclusive"],
            "window_start":record["start"],"first_date":record["first_date"],
            "last_date":record["last_date"],"rows":len(data),
            "eligible":bool(record["eligible"]),"reasons":json.loads(record["reasons"]),
            "sha256":record["sha256"],"bars":data}

class UpdateRequest(BaseModel):
    scope:str=Field(pattern="^(all|category|instrument|catalog)$")
    category:str|None=None
    key:str|None=None
    max_items:int|None=Field(default=100,ge=1,le=20000)

_job_lock=threading.Lock()
_job={"state":"idle","attempted":0,"completed":0,"failed":0}

def _write_job(job):
    folder=ROOT
    folder.mkdir(parents=True,exist_ok=True)
    target=folder/"manual-update-job.json"
    tmp=folder/("manual-update-job."+str(uuid.uuid4())+".tmp")
    try:
        tmp.write_text(json.dumps(job,ensure_ascii=False,indent=2),encoding="utf-8")
        os.replace(tmp,target)
    finally:
        tmp.unlink(missing_ok=True)

def _job_state():
    with _job_lock:
        current=dict(_job)
    saved=ROOT/"manual-update-job.json"
    if current["state"]=="idle" and saved.is_file():
        try:
            previous=json.loads(saved.read_text(encoding="utf-8"))
            if previous.get("state")=="running":
                previous["state"]="interrupted"
            return previous
        except (OSError,ValueError):
            pass
    return current

@app.get("/api/markets/update-status")
def update_status():
    return _job_state()

def _manual_worker(job_id,payload,asof):
    global _job
    start,end=ten_year_window(asof)
    if payload.scope in ("all","catalog") or (payload.scope=="category"
                                   and payload.category in ("equity","etf")):
        # Only the explicit user request refreshes exchange master lists.
        # TradingView categories are navigation, never assumed to be a
        # licensed downloadable source for all listed exchange symbols.
        try:
            from .world_bootstrap import prepare_global_universe
            base=Path(__file__).parent/"universe.csv"
            jpx=os.getenv("JPX_OFFICIAL_SNAPSHOT")
            krx=os.getenv("KRX_LICENSED_SNAPSHOT") if os.getenv("KRX_LICENSE_CONFIRMED")=="1" else None
            _,evidence=prepare_global_universe(
                ROOT,base,allow_network=True,
                jpx_file=jpx if jpx and Path(jpx).is_file() else None,
                krx_file=krx if krx and Path(krx).is_file() else None)
            with _job_lock:
                if _job.get("id")!=job_id:return
                _job["catalog"]="refreshed"
                _job["catalog_count"]=evidence["world_universe_count"]
                _job["catalog_source_scope"]=evidence["source_scope"]
                _write_job(_job)
        except Exception as exc:
            with _job_lock:
                if _job.get("id")!=job_id:return
                _job["catalog"]="failed_kept_previous_list"
                _job["catalog_error"]=f"{type(exc).__name__}: {str(exc)[:240]}"
                _write_job(_job)
    entries,stored,_=_inventory()
    if payload.scope=="catalog":
        with _job_lock:
            if _job.get("id")==job_id:
                _job.update({"state":"completed" if _job.get("catalog")=="refreshed"
                             else "completed_with_errors",
                             "catalog_count":len(entries),"total":0,"attempted":0,
                             "finished_at":datetime.now(timezone.utc).isoformat()})
                _write_job(_job)
        return
    if payload.scope=="instrument":
        targets=[entries[payload.key]] if payload.key in entries else []
    else:
        targets=[inst for inst in entries.values() if payload.scope=="all"
                 or CATEGORY_BY_ASSET.get(inst.asset_class)==payload.category]
    targets.sort(key=lambda inst:(
        {"미확보":0,"파일 누락":1,"10년 미충족":2,"갱신 필요":3,"10년 확보":4}
        .get(_row(inst,stored.get(inst.key),asof)["status"],5),
        inst.exchange,inst.symbol))
    if payload.max_items is not None:
        targets=targets[:payload.max_items]
    with _job_lock:
        if _job.get("id")!=job_id:return
        _job["total"]=len(targets)
        _write_job(_job)
    for index,inst in enumerate(targets):
        if shutil.disk_usage(ROOT).free<128*1024*1024:
            with _job_lock:
                _job["state"]="stopped_disk_low"
                _job["last_error"]="남은 저장공간이 128MB 미만입니다"
                _write_job(_job)
            return
        try:
            result=sync(_store(),inst,start,end)
        except Exception as exc:
            result={"status":"FAILED","reason":f"{type(exc).__name__}: {str(exc)[:200]}"}
        with _job_lock:
            if _job.get("id")!=job_id:return
            _job["attempted"]+=1
            _job["completed"]+=int(result["status"]=="COLLECTED")
            _job["failed"]+=int(result["status"]!="COLLECTED")
            _job["current"]=inst.key
            if result["status"]!="COLLECTED":
                _job["last_error"]=result.get("reason","수집 실패")
            _job["updated_at"]=datetime.now(timezone.utc).isoformat()
            _write_job(_job)
        time.sleep(0.35)
    with _job_lock:
        if _job.get("id")==job_id:
            _job["state"]="completed" if not _job["failed"] else "completed_with_errors"
            _job["finished_at"]=datetime.now(timezone.utc).isoformat()
            _write_job(_job)


@app.post("/api/markets/update")
def update_prices(payload:UpdateRequest,authorization:str|None=Header(default=None)):
    global _job
    _authed(authorization or "")
    if payload.scope=="instrument":
        entries,_,_=_inventory()
        if payload.key not in entries:
            raise HTTPException(404,"종목 목록에 없습니다")
    if payload.scope=="category" and payload.category not in {x["id"] for x in ASSET_MENU}:
        raise HTTPException(422,"시장 분류가 올바르지 않습니다")
    if payload.scope=="category" and payload.category=="economy":
        raise HTTPException(409,"아직 등록된 경제 시계열 수집 대상이 없습니다")
    today=_asof()
    with _job_lock:
        if _job.get("state")=="running":
            raise HTTPException(409,"이미 수동 수집이 실행 중입니다")
        job_id=str(uuid.uuid4())
        _job={"id":job_id,"state":"running",
              "started_at":datetime.now(timezone.utc).isoformat(),
              "asof_exclusive":str(today),"scope":payload.scope,
              "total":0,"attempted":0,"completed":0,"failed":0,
              "current":None,"last_error":None,"catalog":"not_requested"}
        _write_job(_job)
    thread=threading.Thread(target=_manual_worker,args=(job_id,payload,today),
                            daemon=True,name="explicit-user-market-10y-update")
    thread.start()
    return JSONResponse(_job_state(),status_code=202)
