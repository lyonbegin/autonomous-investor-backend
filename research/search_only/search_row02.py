#!/usr/bin/env python3
"""Actual HITEL search-only experiment on 2nd TradingView strategy. No graph."""
import hashlib
import json
import time
import urllib.error
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import hitel_a_one_source as t

SOURCE_ID="03zgCMqx"
ROOM="STOCK-TV-ROW02-03zgCMqx-SEARCH-ONLY-20261119"
BASE="/integrations/v1/public"
OUT=Path("search-only-output")
OUT.mkdir(parents=True,exist_ok=True)

def save(name,value):
    t.save(OUT/name,value)

def one_source():
    lines=[json.loads(x) for x in Path("research/queue/seed.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    item=lines[1]
    if item.get("strategy_id")!=SOURCE_ID or item.get("title")!="PROP_Scalper_V2 FINAL":
        raise RuntimeError("SOURCE_ROW_2_CHANGED")
    return item

def make_prompt(item):
    return (
      "실제 사례 검색 전담 AI입니다. 지식그래프·전략 구현·백테스트 생성은 하지 마십시오. "
      "TradingView Strategy 원장 두 번째(확정 A그룹 순번 아님) 원본만 조사하십시오.\n"
      "원본: "+item["title"]+" / "+item["url"]+" / ID "+SOURCE_ID+"\n"
      "공개 설명 기반 관련 검색 주제: XAUUSD 금 스캘핑, 적응 이동평균, ADX/ATR 필터, "
      "시간대 세션, 부분익절과 break-even stop. 공개 Pine 전문 검증은 아직 안 됨.\n"
      "학술논문·실증 사례·구체적 백테스트와 교육용 실제 거래 예시를 직접 검색하십시오. "
      "접근하지 않은 원문을 읽은 척하지 말고, 없는 링크/수익률/체결을 만들지 마십시오. "
      "연관 논문이 현재 TradingView 원본과 완전히 동일한 전략인 척하지 마십시오. "
      "최대 10개, 근거 없는 경우 0개 허용. 검색 불가라면 NOT_EXECUTED 표시.\n"
      "중간 답변 없이 마지막에 JSON 객체 1개만 출력하십시오. 정확한 스키마 예시: "
      '{"schema":"TV-ROW02-SEARCH-v1","source_id":"03zgCMqx","row_no":2,'
      '"status":"EXECUTED|PARTIAL|NOT_EXECUTED","queries":["검색어"],'
      '"items":[{"title":"원문 제목","url":"https://실제URL","kind":"TRADE|BACKTEST|EDUCATIONAL|RESEARCH",'
      '"access":"FULL_BODY|PREVIEW_ONLY","evidence":"실제 규칙/거래 수치나 검증 사실",'
      '"location":"쪽수/절/표/미확인","relevance":"원본과 관련된 이유",'
      '"limitation":"현재 원본과 동일하지 않은 점"}],'
      '"summary_ko":"결과 요약","pine_full_verified":false}. '
      "완료되기 전에는 답하지 말고, 실제 검색 못했으면 items=[]로 출력하십시오."
    )

def parse(text):
    x=str(text or "").strip()
    if x.startswith(chr(96)*3):
        lines=x.splitlines()
        if len(lines)<3 or lines[-1].strip()!=chr(96)*3:raise ValueError("FENCE_INCOMPLETE")
        x="\n".join(lines[1:-1]).strip()
    dec=json.JSONDecoder()
    pos=0
    objs=[]
    while pos<len(x):
        while pos<len(x) and x[pos].isspace():pos+=1
        if pos==len(x):break
        obj,pos=dec.raw_decode(x,pos)
        objs.append(obj)
    matches=[y for y in objs if isinstance(y,dict) and y.get("source_id")==SOURCE_ID
             and y.get("row_no")==2]
    if len(matches)!=1 or objs[-1] is not matches[0]:raise ValueError("MISMATCH_OR_DUPLICATE_RESULT")
    o=matches[0]
    if o.get("schema")!="TV-ROW02-SEARCH-v1" or o.get("status") not in ("EXECUTED","PARTIAL","NOT_EXECUTED"):
        raise ValueError("INVALID_SCHEMA_OR_STATUS")
    if o.get("pine_full_verified") is not False:raise ValueError("PINE_FALSE_CLAIM")
    items=o.get("items")
    if not isinstance(items,list) or len(items)>10:raise ValueError("INVALID_LIST")
    urls=set()
    for item in items:
        if not isinstance(item,dict):raise ValueError("BAD_ITEM")
        for field in ("title","url","kind","access","evidence","location","relevance","limitation"):
            if not isinstance(item.get(field),str) or not item[field].strip():raise ValueError("MISSING_"+field)
        if not item["url"].startswith(("https://","http://")):raise ValueError("BAD_URL")
        if item["url"] in urls:raise ValueError("DUPLICATE_URL")
        urls.add(item["url"])
        if item["kind"] not in ("TRADE","BACKTEST","EDUCATIONAL","RESEARCH"):raise ValueError("BAD_KIND")
        if item["access"] not in ("FULL_BODY","PREVIEW_ONLY"):raise ValueError("BAD_ACCESS")
    if o["status"]=="NOT_EXECUTED" and items:raise ValueError("FALSE_SEARCH_CLAIM")
    return o

def main():
    source=one_source()
    question=make_prompt(source)
    request_id="stock-row02-search-"+hashlib.sha256((ROOM+"|"+question).encode()).hexdigest()[:40]
    statefile=OUT/"state.json"
    state=json.loads(statefile.read_text(encoding="utf-8")) if statefile.exists() else {}
    if state.get("request_id") not in (None,request_id):raise RuntimeError("CHECKPOINT_MISMATCH")
    state.update({"source_id":SOURCE_ID,"row_no":2,"request_id":request_id,
                  "prompt_sha":hashlib.sha256(question.encode()).hexdigest()})
    save("state.json",state)
    (OUT/"prompt.txt").write_text(question,encoding="utf-8")
    if state.get("phase") in ("FAILED","INVALID_JSON"):raise RuntimeError("PREVIOUS_TERMINAL_NO_REPOST")
    if state.get("phase")=="DONE":return
    if not state.get("room_id"):
        state["room_id"]=t.open_named_room(ROOM,OUT)
        save("state.json",state)
    if not state.get("job_id"):
        state["phase"]="POST_UNCERTAIN"
        save("state.json",state)
        code,accept=t.post(BASE+"/chat",{"room_id":state["room_id"],
                                            "request_id":request_id,"text":question})
        if code!=202 or not accept.get("job_id") or accept.get("room_id")!=state["room_id"]:
            raise RuntimeError("POST_FAILED_OR_ROOM_MISMATCH")
        state["job_id"]=accept["job_id"]
        state["phase"]="POLLING"
        save("state.json",state)
    print("HITEL_ACCEPTED_JOB",state["job_id"],flush=True)
    deadline=time.monotonic()+1200
    while time.monotonic()<deadline:
        try:
            code,j=t.get(BASE+"/jobs/"+state["job_id"])
        except (urllib.error.URLError,TimeoutError):
            time.sleep(10);continue
        if code!=200 or j.get("job_id")!=state["job_id"] or j.get("room_id")!=state["room_id"]:
            raise RuntimeError("JOB_OR_ROOM_MISMATCH")
        audit={"at":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),"job_id":state["job_id"],
               "status":j.get("status"),"stage":j.get("stage")}
        with (OUT/"poll_audit.jsonl").open("a",encoding="utf-8") as f:
            f.write(json.dumps(audit,ensure_ascii=False)+"\n")
        print("HITEL_SEARCH_POLL",json.dumps(audit),flush=True)
        if j.get("status")=="completed":
            raw=j.get("result_text")
            if not isinstance(raw,str) or not raw.strip():raise ValueError("EMPTY_AI_ANSWER")
            (OUT/"result.raw.txt").write_text(raw,encoding="utf-8")
            try:r=parse(raw)
            except Exception:
                state["phase"]="INVALID_JSON";save("state.json",state);raise
            save("results.json",r)
            state.update({"phase":"DONE","items_count":len(r["items"]),"search_status":r["status"]})
            save("state.json",state)
            print("HITEL_SEARCH_COMPLETED",len(r["items"]),flush=True)
            return
        if j.get("status")=="failed":
            state.update({"phase":"FAILED","error":j.get("error")})
            save("state.json",state)
            raise RuntimeError("HITEL_SEARCH_FAILED "+str(j.get("error")))
        time.sleep(10)
    state["phase"]="TIMEOUT_SAME_JOB";save("state.json",state)
    raise TimeoutError("JOB_NOT_COMPLETE "+state["job_id"])

if __name__=="__main__":
    try:main()
    except Exception as exc:
        p=OUT/"state.json"
        d=json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        d["last_error"]=str(exc)[:800]
        save("state.json",d)
        raise
