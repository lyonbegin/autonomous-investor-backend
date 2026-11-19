#!/usr/bin/env python3
"""Real external scholarly search for exactly the first three TradingView Strategy originals.

Read-only search; no HITEL duplicate message, AI research graph, Python strategy,
trade execution, author classification, or fabricated paper data.
"""
import csv
import datetime
import json
import os
from pathlib import Path
import re
import time
import urllib.parse
import urllib.request

QUEUE = Path("research/queue/seed.jsonl")
DEST = Path("research/search_only/batch_001_003")
SEARCH_URI = "https://api.openalex.org/works"
PAPER_LIMIT = 7
SEARCH_PLAN = [
 {"id": "02yfhjiz", "topic": "single-position stop-loss, initial and regular trailing stops, four partial profit exits",
  "queries": ["optimal trading trailing stop take profit", "risk reduction using trailing stop loss rules", "take profit stop loss exit trading empirical evidence"],
  "essential": ["stop", "trailing", "profit", "loss", "exit", "trading"]},
 {"id": "03zgCMqx", "topic": "XAUUSD gold scalping with ADX/ATR, moving-average and session filters, partial profit",
  "queries": ["XAUUSD ADX ATR gold trading strategy", "gold intraday trading technical indicators algorithmic", "precious metals intraday technical trading moving average"],
  "essential": ["gold", "xau", "precious", "metal", "trading"]},
 {"id": "04erUlJM", "topic": "Chainlink LINK breakout above 12.20, support retest, technical momentum",
  "queries": ["Chainlink LINK technical trading momentum volatility", "cryptocurrency breakout support resistance empirical trading", "cryptocurrency technical trading filter channel breakout"],
  "essential": ["crypto", "chainlink", "link", "breakout", "bitcoin", "momentum"]},
]

def fetch(query):
    args = urllib.parse.urlencode({
      "search": query, "per-page": 15, "filter": "from_publication_date:2005-01-01",
    })
    req = urllib.request.Request(SEARCH_URI+"?"+args, headers={
      "User-Agent": "stock-research-literature-catalogue/1.0 (read-only)",
      "Accept": "application/json"
    })
    with urllib.request.urlopen(req, timeout=28) as res:
        return json.load(res).get("results", [])

def reconstruct_abstract(inverted):
    if not isinstance(inverted,dict) or not inverted: return ""
    tokens={}
    for word,positions in inverted.items():
        for pos in positions:
            if 0 <= pos < 3000: tokens[int(pos)] = word
    return " ".join(tokens.get(i,"") for i in range(max(tokens)+1)).strip() if tokens else ""

def score(item,query,plan):
    title=str(item.get("title") or "")
    abstract=reconstruct_abstract(item.get("abstract_inverted_index"))
    txt=(title+" "+abstract).lower()
    if not title or not item.get("doi") or not abstract: return -1
    keys=set(re.findall(r"[a-zA-Z]{3,}", query.lower()))
    hits=sum(1 for k in keys if k in txt)
    specific=sum(1 for k in plan["essential"] if k in txt)
    if specific==0 or hits<2:return -1
    return 2*specific+hits+int("trading" in title.lower())+int("stop" in title.lower())

def run():
    originals=[json.loads(line) for line in QUEUE.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(originals)<3: raise ValueError("ORIGINAL_3_ROWS_NOT_FOUND")
    originals=originals[:3]
    if [x["strategy_id"] for x in originals] != [p["id"] for p in SEARCH_PLAN]:
        raise ValueError("ORIGINAL_ID_OR_ROW_ORDER_CHANGED")
    DEST.mkdir(parents=True, exist_ok=True)
    results=[]
    for i,(row,plan) in enumerate(zip(originals,SEARCH_PLAN),1):
        observations=[]
        ranked={}
        print("BEGIN_SOURCE_SEARCH",i,row["strategy_id"],flush=True)
        for query in plan["queries"]:
            try:
                candidates=fetch(query)
                observations.append({"query":query,"status":"HTTP_OK","candidates":len(candidates)})
            except Exception as ex:
                observations.append({"query":query,"status":"FETCH_ERROR",
                                     "error":str(ex)[:220],"candidates":0})
                print("SEARCH_ERROR",i,query,type(ex).__name__,str(ex)[:180],flush=True)
                continue
            for candidate in candidates:
                sc=score(candidate,query,plan)
                if sc<0:continue
                doi=candidate.get("doi")
                abstract=reconstruct_abstract(candidate.get("abstract_inverted_index"))
                best=candidate.get("best_oa_location") or {}
                source=(candidate.get("primary_location") or {}).get("source") or {}
                paper={
                  "title":candidate.get("title"),"doi":doi,
                  "landing_url":doi,
                  "open_access_url":best.get("landing_page_url") or best.get("pdf_url"),
                  "authors":[a.get("author",{}).get("display_name")
                             for a in candidate.get("authorships",[])[:6]],
                  "publication_year":candidate.get("publication_year"),
                  "journal":source.get("display_name"),
                  "published_at":candidate.get("publication_date"),
                  "type":candidate.get("type"),
                  "abstract_excerpt":abstract[:2000],
                  "evidence_location":"OpenAlex indexed abstract; full paper NOT claimed read",
                  "evidence_status":"ABSTRACT_INDEXED_NOT_FULLTEXT_VERIFIED",
                  "relation_to_original":plan["topic"],
                  "same_as_original_strategy":False,
                  "search_match_score":sc,
                  "source_openalex_id":candidate.get("id")
                }
                prior=ranked.get(doi)
                if not prior or prior["search_match_score"]<sc: ranked[doi]=paper
        papers=sorted(ranked.values(),key=lambda x:(-x["search_match_score"],x["title"]))[:PAPER_LIMIT]
        data={
          "schema_version":"TV-SEARCH-FIRST-THREE-v1",
          "source_order_in_full_strategy_csv":i,
          "source_script_id":row["strategy_id"],
          "tradingview_title":row["title"],"tradingview_url":row["url"],
          "is_official_A_group_rank":False,
          "source_metadata_origin":row["source"],
          "search_type":"REAL_READ_ONLY_OPENALEX_SCHOLARLY_METADATA_SEARCH",
          "search_started_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "topic":plan["topic"],"queries":observations,
          "papers":papers,"paper_count":len(papers),
          "notes":"Real bibliographic index and indexed abstracts; source Pine and full papers not verified. No inference about trading performance, backtests or exact strategy equivalence."
        }
        path=DEST/f"strategy_{i:06d}_{row['strategy_id']}.json"
        tmp=path.with_suffix(".partial")
        tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
        os.replace(tmp,path)
        results.append({"order":i,"id":row["strategy_id"],
            "search_http_success":sum(z["status"]=="HTTP_OK" for z in observations),
            "papers":len(papers),"file":str(path)})
        print("FINISHED_SOURCE_SEARCH",i,row["strategy_id"],"papers",len(papers),flush=True)
    summary={"schema_version":"TV-SEARCH-FIRST-THREE-v1","sources":results,
             "all_three_searched":len(results)==3 and all(x["search_http_success"]>0 for x in results),
             "all_three_have_evidence":len(results)==3 and all(x["papers"]>0 for x in results)}
    (DEST/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print("FINAL_THREE_SOURCE_SUMMARY",json.dumps(summary,ensure_ascii=False),flush=True)
    if not summary["all_three_have_evidence"]:
        raise RuntimeError("THREE_ORIGINALS_SEARCH_NOT_FULLY_VERIFIED; SEE_ARTIFACTS")

if __name__=="__main__":
    run()
