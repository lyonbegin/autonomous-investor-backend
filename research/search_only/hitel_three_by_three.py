#!/usr/bin/env python3
"""Three actual HITEL ChatGPT calls, three original TradingView strategies per call.
Only original source references, independent live trading evidence, paper/report
contents and accessible URLs. Zero claims of graph, strategy code or backtests.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.error

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import hitel_a_one_source as transport

SOURCES=Path("research/search_only/originals_001_009.jsonl")
ROOT=Path("search-nine-hitel")
PUBLIC="/integrations/v1/public"
POLL_SECONDS=10
POLL_TIMEOUT=14400
TITLES={
"02yfhjiz":"Complex Single Trade Strategy",
"03zgCMqx":"PROP_Scalper_V2 FINAL",
"04erUlJM":"LINK Above $12.20: Is $15 Back on the Table?",
"06s9ohae":"FCPO Session-Based Momentum Scalper with ATR Volatility Filter",
"06wt9GNj":"Stochastic RSI Strategy (with SMA and VWAP Filters)",
"06zatx1k":"MM-20/100-EMA",
"07CF7RMb":"BandPass EOS - 1h",
"07xDq1rh":"Breakout Follow Trend [Strategy]",
"089fmfw1":"Dynamo Strategy Backtest"
}
BATCHES=[list(TITLES)[i:i+3] for i in (0,3,6)]

def save(path,obj):
    transport.save(path,obj)

def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def originals():
    rows=[json.loads(z) for z in SOURCES.read_text(encoding="utf-8").splitlines() if z.strip()]
    if len(rows)!=9 or [r.get("script_id") for r in rows] != list(TITLES):
        raise RuntimeError("SOURCE_ORDER_OR_COUNT_NOT_VERIFIED")
    for i,r in enumerate(rows,1):
        if r.get("strategy_order")!=i or r.get("title")!=TITLES[r["script_id"]]:
            raise RuntimeError("SOURCE_TITLE_OR_POSITION_CHANGED:"+str(i))
        if not str(r.get("url","")).startswith("https://www.tradingview.com/script/"+r["script_id"]):
            raise RuntimeError("SOURCE_URL_INVALID:"+str(i))
        if r.get("official_A_classification_verified") is not False:
            raise RuntimeError("UNSUPPORTED_A_CLASSIFICATION")
    return rows

def research_prompt(batch,round_no):
    payload=[{"source_order":r["strategy_order"],"script_id":r["script_id"],"title":r["title"],
              "author":r["author"],"url":r["url"],"source_description_preview":r["description_preview_summary"],
              "pine_full_available":False} for r in batch]
    return (
      "실제 거래 사례와 사건의 근거를 전문적으로 조사하십시오. 이번 연구 배치는 TradingView 원본 3개이며 "
      "한 메시지로만 묻습니다. 한 질문에서 이 3개 각각에 대한 연구 검색을 모두 수행하고 "
      "중간 답변 없이 최종 JSON 하나만 답하십시오.\n"
      "TradingView 원본 3건(Strategy 전체 원장 순번; A그룹 순번 아님):\n"+
      json.dumps(payload,ensure_ascii=False,separators=(",",":"))+"\n"
      "필수 목표: 각 원본의 기술적 메커니즘과 관련된 실제 실행된 거래, 공식 공시로 확인되는 거래 사건,"
      " 또는 실제 과거 거래 데이터로 체결/진입/청산이 재구성되는 실증 백테스트를 검색하십시오. "
      "검색 우선순위는 (1) REAL_EXECUTED_TRADE: 브로커/거래소/법적 공시 등 실체결 증거, "
      "(2) REAL_MARKET_TRANSACTION_EVENT: 실제 시장 거래의 시점·가격·주체·구조가 확인되는 사건, "
      "(3) REAL_MARKET_DATA_BACKTEST: 실제 시장 가격자료로 날짜·진입·청산·손익을 제시한 백테스트입니다. "
      "이론 소개만 하는 논문, 일반 지표 설명, 실제 거래 규칙·기록 없는 초록은 반드시 제외하십시오. "
      "3번 원본은 LINK 뉴스/아이디어 성격일 수 있으므로, 실제 체결과 아이디어 전망을 혼동하지 마십시오. "
      "선물·현물·코인 등 자산군을 섞거나 원본 거래의 실체결을 확인했다고 거짓 주장하지 마십시오.\n"
      "출처에는 실제 접근 가능한 DOI/저널/공식 거래소·감독기관 문서/원문 URL을 쓰십시오. "
      "원문에서 실제로 읽고 확인한 부분과 검색 결과의 초록만 읽은 것을 구분하십시오. "
      "실제 확인한 거래가격·진입·청산·기간·계약·거래비용과 실증 결과가 있으면 포함하고 "
      "없으면 null과 '증빙 없음'을 사용하십시오. 성과·논문 제목·URL을 만들어내지 마십시오. "
      "각 원본에서 가능한 한 2~5개의 독립된 사례를 찾되, 근거 없으면 0건도 허용합니다. "
      "반드시 세 원본 모두를 포함하고 본문내용·거래구조·출처 재접근 링크를 포함하십시오. "
      "이 단계에서 지식그래프/소스코드/전략구현/백테스트 실행은 하지 마십시오.\n"
      "필수 최종 JSON 규약: "
      '{"schema":"TV-NINE-REAL-CASES-v1","batch_no":'+str(round_no)+',"source_results":['
      '{"source_order":1,"script_id":"8자리","title":"원본 제목","search_status":"SEARCHED|NO_WEB_ACCESS|INSUFFICIENT_EVIDENCE",'
      '"search_queries":["실제 검색어"],"cases":['
      '{"case_id":"임의 고유번호","case_type":"REAL_EXECUTED_TRADE|REAL_MARKET_TRANSACTION_EVENT|REAL_MARKET_DATA_BACKTEST",'
      '"title":"문헌/실거래 사건 원문 제목","published_by":"실제 발행인/기관",'
      '"document_url":"https://실제 접근 가능한 링크","doi":null,'
      '"source_access":"FULL_ARTICLE|ABSTRACT_ONLY|PUBLIC_SUMMARY",'
      '"market_instrument":"정확한 거래 대상","trade_period":"명시된 기간 또는 미확인",'
      '"entry_exit_evidence":"실제 매매 규칙·진입청산·체결 증거 또는 이 자료에서 확인 가능한 항목",'
      '"trade_numbers":"논문에 적힌 사례별 실거래·백테스트 거래수·손익 등 또는 미확인",'
      '"source_excerpt_or_location":"논문 절/표/페이지·공시 번호 등 실존하는 근거 위치",'
      '"economic_mechanism":"구체적 수익·손실 발생 구조",'
      '"relationship_to_tradingview":"원본과 경제적·기술적으로 연결되는 부분",'
      '"limitations":"실체결/백테스트 여부 및 원본과의 차이"}],'
      '"exclusions":[{"title":"후보","reason":"실제 거래·원문 근거 없어서 제외한 사유"}],'
      '"search_limitations":"원문 확인불가 등"}],'
      '"all_sources_processed":true,"research_only":true}\n'
      "상기 예시의 source_order=1은 자리표시용입니다. 실제 응답은 이번 배치의 원본 순번 "
      +",".join(str(r["strategy_order"]) for r in batch)+
      "과 script_id를 정확하게 사용하십시오. 사례를 0건 반환한 원본도 source_results에서 빠뜨리지 마십시오."
    )

def parse_reply(raw,expected,batch_no):
    if not isinstance(raw,str) or not raw.strip():raise ValueError("EMPTY_FINAL_REPLY")
    s=raw.strip()
    if s.startswith(chr(96)*3):
        lines=s.splitlines()
        if len(lines)<3 or lines[-1].strip()!=chr(96)*3:raise ValueError("UNTERMINATED_JSON_FENCE")
        s="\n".join(lines[1:-1]).strip()
    dec=json.JSONDecoder()
    pos=0;objects=[]
    while pos<len(s):
        while pos<len(s) and s[pos].isspace():pos+=1
        if pos==len(s):break
        try:o,pos=dec.raw_decode(s,pos)
        except json.JSONDecodeError as exc:raise ValueError("INCOMPLETE_JSON") from exc
        if not isinstance(o,dict):raise ValueError("JSON_OBJECT_REQUIRED")
        objects.append(o)
    good=[]
    expected_ids=[r["script_id"] for r in expected]
    for item in objects:
        if item.get("schema")!="TV-NINE-REAL-CASES-v1":continue
        sr=item.get("source_results") or []
        if isinstance(sr,list) and [r.get("script_id") for r in sr if isinstance(r,dict)]==expected_ids and item.get("batch_no")==batch_no:
            good.append(item)
    if len(good)!=1 or objects[-1] is not good[0]:
        raise ValueError("EXACT_BATCH_JSON_MISSING_DUPLICATE_OR_WRONG_LAST")
    result=good[0]
    if result.get("all_sources_processed") is not True or result.get("research_only") is not True:
        raise ValueError("NOT_RESEARCH_ONLY_OR_INCOMPLETE_BATCH")
    for r,source in zip(result["source_results"],expected):
        if r.get("source_order")!=source["strategy_order"] or r.get("title")!=source["title"]:
            raise ValueError("SOURCE_NUMBER_OR_TITLE_MISMATCH")
        if r.get("search_status") not in ("SEARCHED","NO_WEB_ACCESS","INSUFFICIENT_EVIDENCE"):
            raise ValueError("INVALID_SEARCH_STATUS")
        if not isinstance(r.get("search_queries"),list):raise ValueError("MISSING_QUERIES")
        cases=r.get("cases")
        if not isinstance(cases,list) or len(cases)>7:raise ValueError("INVALID_CASE_LIST_SIZE")
        for c in cases:
            if not isinstance(c,dict):raise ValueError("INVALID_CASE_ITEM")
            for key in ("case_id","case_type","title","published_by","document_url",
                        "source_access","market_instrument","trade_period","entry_exit_evidence",
                        "trade_numbers","source_excerpt_or_location","economic_mechanism",
                        "relationship_to_tradingview","limitations"):
                if not isinstance(c.get(key),str) or not c[key].strip():
                    raise ValueError("CASE_MISSING_"+key)
            if c["case_type"] not in ("REAL_EXECUTED_TRADE","REAL_MARKET_TRANSACTION_EVENT","REAL_MARKET_DATA_BACKTEST"):
                raise ValueError("CASE_TYPE_NOT_REAL_TRADE")
            if not c["document_url"].startswith("https://"):
                raise ValueError("INVALID_CASE_LINK")
        if r["search_status"]=="NO_WEB_ACCESS" and cases:
            raise ValueError("FALSE_SEARCH_WITH_NO_ACCESS")
    return result

def run_group(batch_no,rows,out):
    group=rows[(batch_no-1)*3:batch_no*3]
    bdir=out/("batch_"+str(batch_no))
    bdir.mkdir(parents=True,exist_ok=True)
    prompt=research_prompt(group,batch_no)
    room_name="STOCK-TV-CASESEARCH-NINE-20261119-B"+str(batch_no)
    request_id="stock-tv-nine-b"+str(batch_no)+"-"+sha(room_name+"|"+prompt)[:42]
    state_file=bdir/"state.json"
    saved=json.loads(state_file.read_text("utf-8")) if state_file.exists() else {}
    if saved and (saved.get("request_id")!=request_id or saved.get("prompt_hash")!=sha(prompt)):
        raise RuntimeError("RESTORED_CHECKPOINT_NOT_SAME_PROMPT")
    state={**saved,"batch_no":batch_no,"source_ids":[r["script_id"] for r in group],
           "request_id":request_id,"prompt_hash":sha(prompt),"room_name":room_name}
    save(state_file,state)
    (bdir/"prompt.txt").write_text(prompt,encoding="utf-8")
    if state.get("phase")=="VERIFIED":
        return json.loads((bdir/"result.json").read_text(encoding="utf-8"))
    if state.get("phase") in ("FINAL_INVALID","FAILED"):
        raise RuntimeError("OLD_JOB_FAILED_NO_NEW_REQUEST_PERMITTED")
    if not state.get("room_id"):
        state["room_id"]=transport.open_named_room(room_name,bdir)
        save(state_file,state)
    if not state.get("job_id"):
        state["phase"]="SUBMIT_UNCERTAIN"
        save(state_file,state)
        accepted=None
        for attempt in range(3):
            try:
                code,resp=transport.post(PUBLIC+"/chat",{"room_id":state["room_id"],
                                                           "request_id":request_id,"text":prompt})
                if code==202 and resp.get("job_id") and resp.get("room_id")==state["room_id"]:
                    accepted=resp;break
                raise RuntimeError("HITEL_ACCEPTED_JOB_UNVERIFIED")
            except urllib.error.HTTPError as exc:
                if exc.code not in (502,503,504) or attempt==2:raise
            except (urllib.error.URLError,TimeoutError):
                if attempt==2:raise
            time.sleep(5*(attempt+1))
        if not accepted:raise RuntimeError("NO_VERIFIED_SUBMISSION")
        state["job_id"]=accepted["job_id"]
        state["phase"]="POLL"
        save(state_file,state)
        print("HITEL_TRIPLE_SUBMITTED",batch_no,state["job_id"],flush=True)
    else:print("HITEL_TRIPLE_RESUMED",batch_no,state["job_id"],flush=True)
    deadline=time.monotonic()+POLL_TIMEOUT
    last=None
    while time.monotonic()<deadline:
        try:
            code,job=transport.get(PUBLIC+"/jobs/"+state["job_id"])
        except (urllib.error.URLError,TimeoutError):
            time.sleep(POLL_SECONDS);continue
        if code!=200 or job.get("room_id")!=state["room_id"] or job.get("job_id")!=state["job_id"]:
            raise RuntimeError("JOB_ROOM_ID_MISMATCH")
        obs={"time":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
             "batch_no":batch_no,"job_id":state["job_id"],
             "status":job.get("status"),"stage":job.get("stage"),
             "updated_at":job.get("updated_at")}
        with (bdir/"poll_audit.jsonl").open("a",encoding="utf-8") as fp:
            fp.write(json.dumps(obs,ensure_ascii=False)+"\n")
        if last!=(obs["status"],obs["stage"]):
            print("HITEL_TRIPLE_JOB_STATE",json.dumps(obs,ensure_ascii=False),flush=True)
            last=(obs["status"],obs["stage"])
        state["last_seen"]=obs
        save(state_file,state)
        if job.get("status")=="completed":
            raw=job.get("result_text")
            if not isinstance(raw,str) or not raw.strip():
                state["phase"]="FINAL_INVALID";save(state_file,state)
                raise RuntimeError("COMPLETED_EMPTY_FINAL")
            (bdir/"result.raw.txt").write_text(raw,encoding="utf-8")
            state["phase"]="RAW_PRESERVED";save(state_file,state)
            try:result=parse_reply(raw,group,batch_no)
            except Exception:
                state["phase"]="FINAL_INVALID";save(state_file,state);raise
            save(bdir/"result.json",result)
            state["phase"]="VERIFIED";state["completed_source_count"]=3
            state["case_counts"]=[len(x["cases"]) for x in result["source_results"]]
            save(state_file,state)
            print("HITEL_TRIPLE_BATCH_VERIFIED",batch_no,state["case_counts"],flush=True)
            return result
        if job.get("status")=="failed":
            state["phase"]="FAILED";state["error"]=job.get("error")
            save(state_file,state)
            raise RuntimeError("HITEL_TRIPLE_JOB_FAILED:"+str(job.get("error",""))[:700])
        time.sleep(POLL_SECONDS)
    state["phase"]="POLL_TIMEOUT_JOB_PRESERVED";save(state_file,state)
    raise TimeoutError("STILL_PENDING_DO_NOT_RESUBMIT:"+state["job_id"])

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--batch",type=int,required=True)
    parser.add_argument("--output",default=str(ROOT))
    args=parser.parse_args()
    if args.batch not in (1,2,3):raise RuntimeError("ONLY_3_BATCHES")
    rows=originals()
    out=Path(args.output)
    out.mkdir(parents=True,exist_ok=True)
    result=run_group(args.batch,rows,out)
    print("TRIPLE_DONE",args.batch,"sources",len(result["source_results"]),flush=True)

if __name__=="__main__":
    main()
