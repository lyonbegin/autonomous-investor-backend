"""Stock-project-owned WF01 node registry and execution logic.

This module belongs to autonomous-investor-backend, NOT the shared editor.
Only specifically registered N01/N02 and attributed metadata-only N03 can run.
"""
import json
import hashlib
import re
import os
import ssl
import urllib.parse
import urllib.request
from licensed_strategy_manifest import catalog_from_snapshot
from investment_source_registry import check_candidates
from verified_pine_archive import acquire_verified_pine,archive_path_for,MAX_PINE_BYTES
from investment_pine_store import save_verified_source
from investment_wf02 import WF02_PATH,execute_wf02_node01,execute_wf02_node02,execute_wf02_node03
from datetime import datetime,timezone

WF01_MODES={
    "operations/WF01-latest-strategy-one.json":"strategy",
    "operations/WF01-latest-library-one.json":"library",
    WF02_PATH:"strategy",
}

def root_input_limit(workflow_path,node_id):
    # Only explicit manual library registration carries a complete Pine text.
    return 600000 if (
        workflow_path=="operations/WF01-latest-library-one.json"
        and node_id=="wf01-library-01") else 2048

def node_binding(workflow_path,node_id):
    if workflow_path==WF02_PATH:
        commands={
          "wf02-01":("execute_wf02_node01","wf02-n01-load-db-v1","manual_collection_start"),
          "wf02-02":("execute_wf02_node02","wf02-n02-convert-v2-nonoverlay","convert_pine_to_python"),
          "wf02-03":("execute_wf02_node03","wf02-n03-conversion-result-v1","display_conversion_result")
        }
        if node_id not in commands:return None
        function,version,character=commands[node_id]
        return {"python_module":"investment_node_adapter",
                "python_function":function,"code_version":version,
                "node_character":character}
    kind=WF01_MODES.get(workflow_path)
    if not kind:return None
    prefix="wf01-"+kind+"-"
    if node_id==prefix+"01":
        return {"python_module":"investment_node_adapter",
          "python_function":"execute_node01","code_version":"wf01-n01-v2",
          "node_character":"manual_collection_start"}
    if node_id==prefix+"02":
        return {"python_module":"investment_node_adapter",
          "python_function":"execute_node02","code_version":"wf01-n02-v1",
          "node_character":"collection_request_configuration"}
    if node_id==prefix+"03":
        return {"python_module":"investment_node_adapter",
          "python_function":"execute_node03","code_version":"wf01-n03-licensed-manifest-v2",
          "node_character":"authorized_catalog_request"}
    if node_id==prefix+"04":
        return {"python_module":"investment_node_adapter",
          "python_function":"execute_node04","code_version":"wf01-n04-v2-pine-metadata",
          "node_character":"validated_catalog_candidates"}
    if node_id==prefix+"05":
        return {"python_module":"investment_node_adapter",
          "python_function":"execute_node05","code_version":"wf01-n05-sqlite-registry-v1",
          "node_character":"project_source_version_check"}
    if node_id==prefix+"06":
        return {"python_module":"investment_node_adapter",
          "python_function":"execute_node06","code_version":"wf01-n06-licensed-archive-v3",
          "node_character":"choose_single_new_strategy"}
    if node_id==prefix+"07":
        return {"python_module":"investment_node_adapter",
          "python_function":"execute_node07","code_version":"wf01-n07-if-v1",
          "node_character":"conditional_route"}
    if node_id==prefix+"08":
        return {"python_module":"investment_node_adapter","python_function":"execute_node08","code_version":"wf01-n08-more-pages-v1","node_character":"conditional_route"}
    if node_id==prefix+"09":
        return {"python_module":"investment_node_adapter","python_function":"execute_node09","code_version":"wf01-n09-next-page-v1","node_character":"next_collection_page"}
    if node_id==prefix+"10":
        return {"python_module":"investment_node_adapter","python_function":"execute_node10","code_version":"wf01-n10-exhausted-v1","node_character":"collection_exhausted"}
    if node_id==prefix+"11":
        return {"python_module":"investment_node_adapter",
          "python_function":"execute_node11","code_version":"wf01-n11-simple-pine-v1",
          "node_character":"fetch_pine_code"}
    if node_id==prefix+"15":
        return {"python_module":"investment_node_adapter",
          "python_function":"execute_node15","code_version":"wf01-n15-pine-store-v1",
          "node_character":"persist_pine_code"}
    if node_id==prefix+"16":
        return {"python_module":"investment_node_adapter","python_function":"execute_node16","code_version":"wf01-n16-result-v1","node_character":"display_source_save_result"}
    return None

def node_type(workflow_path,node_id):
    if workflow_path==WF02_PATH:
        return {"wf02-01":"n8n-nodes-base.manualTrigger",
                "wf02-02":"n8n-nodes-base.code",
                "wf02-03":"n8n-nodes-base.code"}.get(node_id)
    kind=WF01_MODES.get(workflow_path)
    if not kind:return None
    return {
      "wf01-"+kind+"-01":"n8n-nodes-base.manualTrigger",
      "wf01-"+kind+"-02":"n8n-nodes-base.code",
      "wf01-"+kind+"-03":"n8n-nodes-base.httpRequest",
      "wf01-"+kind+"-04":"n8n-nodes-base.code",
      "wf01-"+kind+"-05":"n8n-nodes-base.httpRequest",
      "wf01-"+kind+"-06":"n8n-nodes-base.code",
      "wf01-"+kind+"-07":"n8n-nodes-base.if",
      "wf01-"+kind+"-08":"n8n-nodes-base.if",
      "wf01-"+kind+"-09":"n8n-nodes-base.code",
      "wf01-"+kind+"-10":"n8n-nodes-base.code",
      "wf01-"+kind+"-11":"n8n-nodes-base.httpRequest",
      "wf01-"+kind+"-15":"n8n-nodes-base.httpRequest",
      "wf01-"+kind+"-16":"n8n-nodes-base.code",
    }.get(node_id)

def execute_node01(input_json,*,workflow_kind):
    if not isinstance(input_json,dict):raise ValueError("INPUT_JSON_OBJECT_REQUIRED")
    if workflow_kind not in ("strategy","library"):raise ValueError("UNSUPPORTED_WORKFLOW_KIND")
    allowed={"ui_selection","requested_detail_limit","max_pages"} | ({"manual_library"} if workflow_kind=="library" else set())
    if not {"ui_selection","requested_detail_limit"}.issubset(input_json) or set(input_json)-allowed:
        raise ValueError("INPUT_FIELDS_MISMATCH: ui_selection, requested_detail_limit")
    if input_json["ui_selection"]!=workflow_kind:raise ValueError("COLLECTION_KIND_MISMATCH")
    if type(input_json["requested_detail_limit"]) is not int or input_json["requested_detail_limit"]!=1:
        raise ValueError("DETAIL_LIMIT_MUST_EQUAL_ONE")
    manual=input_json.get("manual_library")
    if workflow_kind=="library" and manual is not None:
        if not isinstance(manual,dict) or set(manual)!={"source_url","version_key","pine_code"}:
            raise ValueError("LIBRARY_MANUAL_INPUT_REQUIRED")
        url=urllib.parse.urlsplit(manual["source_url"]) if isinstance(manual["source_url"],str) else None
        if not url or url.scheme!="https" or url.hostname not in (
            "www.tradingview.com","tradingview.com","kr.tradingview.com"
        ) or not re.fullmatch(r"/script/[A-Za-z0-9]{8}(?:-[A-Za-z0-9._-]+)?/?",url.path):
            raise ValueError("LIBRARY_TRADINGVIEW_SCRIPT_URL_REQUIRED")
        if not isinstance(manual["version_key"],str) or not manual["version_key"].strip() or len(manual["version_key"])>150:
            raise ValueError("LIBRARY_VERSION_REQUIRED")
        code=manual["pine_code"]
        from verified_pine_archive import MAX_PINE_BYTES
        if not isinstance(code,str) or not code.strip() or len(code.encode("utf-8"))>MAX_PINE_BYTES:
            raise ValueError("LIBRARY_PINE_CODE_REQUIRED_OR_TOO_LARGE")
        if not re.search(r"(?m)^\s*//@version=[456]\s*$",code) or not re.search(r"(?m)^\s*library\s*\(",code):
            raise ValueError("LIBRARY_PINE_DECLARATION_REQUIRED")
    pages=input_json.get("max_pages",3)
    if type(pages) is not int or not 1<=pages<=3:raise ValueError("MAX_PAGES_MUST_BE_1_TO_3")
    return {**({"manual_library":manual} if workflow_kind=="library" and manual else {}),"kind":workflow_kind,"page":1,"max_pages":pages,
        "max_detail_success":1,"sort":"recent_extended",
        "execution_mode":"ONE_NODE_ONLY","tradingview_requested":False,
        "next_node_executed":False}

def execute_node02(input_json,*,workflow_kind):
    """Preserve ALL upstream N01 fields; extend only two request parameters."""
    if not isinstance(input_json,dict):raise ValueError("INPUT_JSON_OBJECT_REQUIRED")
    if input_json.get("kind")!=workflow_kind:raise ValueError("COLLECTION_KIND_MISMATCH")
    if type(input_json.get("page")) is not int or input_json["page"]<1:
        raise ValueError("INVALID_PAGE")
    if type(input_json.get("max_pages")) is not int or not 1<=input_json["max_pages"]<=3:
        raise ValueError("INVALID_MAX_PAGES")
    if input_json.get("sort")!="recent_extended":raise ValueError("INVALID_SORT")
    if input_json.get("max_detail_success")!=1:raise ValueError("DETAIL_LIMIT_MUST_EQUAL_ONE")
    if input_json.get("tradingview_requested") is not False or input_json.get("next_node_executed") is not False:
        raise ValueError("UPSTREAM_FLAGS_MISMATCH")
    page_size=input_json.get("page_size",50)
    if type(page_size) is not int or not 1<=page_size<=100:
        raise ValueError("INVALID_PAGE_SIZE")
    selected_count=input_json.get("selected_count",0)
    if type(selected_count) is not int or selected_count!=0:
        raise ValueError("INVALID_SELECTED_COUNT")
    return {**input_json,"page_size":page_size,"selected_count":selected_count}

def execute_node03(input_json,*,workflow_kind):
    """N03 performs one REAL HTTPS call to an explicitly authorized feed.

    It does not scrape TradingView. A feed must be licensed/approved, operated
    outside the Studio and configured by the deployment administrator.
    """
    if not isinstance(input_json,dict):
        raise ValueError("N03_INPUT_OBJECT_REQUIRED")
    if input_json.get("kind")!=workflow_kind:
        raise ValueError("N03_UPSTREAM_KIND_MISMATCH")
    page=input_json.get("page")
    page_size=input_json.get("page_size")
    pages=input_json.get("max_pages")
    if any(type(x) is not int for x in (page,page_size,pages)):
        raise ValueError("N03_PAGE_CONFIG_INVALID")
    if not 1<=page<=pages<=3 or not 1<=page_size<=100:
        raise ValueError("N03_PAGE_CONFIG_OUT_OF_RANGE")
    if input_json.get("sort")!="recent_extended":
        raise ValueError("N03_SORT_MISMATCH")

    manual=input_json.get("manual_library")
    if workflow_kind=="library" and isinstance(manual,dict):
        script_id=re.match(r"/script/([A-Za-z0-9]{8})",urllib.parse.urlsplit(manual["source_url"]).path).group(1)
        row={"kind":"library","source_id":"USER_SUBMITTED_LIBRARY:"+script_id,
             "source_url":manual["source_url"],"version_key":manual["version_key"],
             "title":"사용자 제공 공개 라이브러리 "+script_id,"access":"user_supplied_code"}
        return {**input_json,"status":"ok","items":[row],"count":1,
            "has_more":False,"catalog_source":"USER_SUBMITTED_LIBRARY_SOURCE",
            "catalog_is_live":False,"tradingview_requested":False,
            "pine_source_acquired":False,"next_node_executed":False}
    url=os.environ.get("TRADINGVIEW_AUTHORIZED_CATALOG_URL","").strip()
    if not url:
        # Public, attributed metadata only. It is a dated corpus snapshot,
        # never advertised as live TradingView "latest" or as Pine source.
        manifest=catalog_from_snapshot(kind=workflow_kind,page=page,
            page_size=page_size,sort=input_json["sort"])
        return {**input_json,**manifest,
            "fetched_at":datetime.now(timezone.utc).isoformat(),
            "status":"ok","next_node_executed":False}
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme!="https" or not parsed.netloc or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("AUTHORIZED_CATALOG_FEED_URL_INVALID")
    if parsed.hostname in ("tradingview.com","www.tradingview.com","kr.tradingview.com"):
        raise ValueError("DIRECT_TRADINGVIEW_AUTOMATED_COLLECTION_DISABLED")
    # Endpoint is server-owned; upstream JSON is never accepted as a URL.
    params=urllib.parse.urlencode({"kind":workflow_kind,"page":page,"page_size":page_size,
                                   "sort":input_json["sort"]})
    sep="&" if parsed.query else "?"
    req=urllib.request.Request(url+sep+params,method="GET",headers={
       "Accept":"application/json",
       "User-Agent":"autonomous-investor-approved-source-adapter/1"})
    token=os.environ.get("TRADINGVIEW_AUTHORIZED_CATALOG_TOKEN","")
    if token:
        req.add_header("Authorization","Bearer "+token)
    try:
        with urllib.request.urlopen(req,timeout=12,context=ssl.create_default_context()) as response:
            if response.status!=200:
                raise ValueError("AUTHORIZED_CATALOG_HTTP_"+str(response.status))
            length=response.headers.get("Content-Length")
            if length and int(length)>1000000:
                raise ValueError("AUTHORIZED_CATALOG_RESPONSE_TOO_LARGE")
            raw=response.read(1000001)
            if len(raw)>1000000:
                raise ValueError("AUTHORIZED_CATALOG_RESPONSE_TOO_LARGE")
            payload=json.loads(raw.decode("utf-8"))
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("AUTHORIZED_CATALOG_REQUEST_FAILED:"+type(exc).__name__) from exc
    if not isinstance(payload,dict) or not isinstance(payload.get("items"),list):
        raise ValueError("AUTHORIZED_CATALOG_INVALID_SCHEMA")
    if payload.get("kind")!=workflow_kind or payload.get("page")!=page:
        raise ValueError("AUTHORIZED_CATALOG_INCORRECT_PAGE_OR_KIND")
    items=payload["items"]
    if len(items)>page_size:
        raise ValueError("AUTHORIZED_CATALOG_PAGE_LIMIT_EXCEEDED")
    normalized=[]
    for i,item in enumerate(items):
        if not isinstance(item,dict) or item.get("kind")!=workflow_kind:
            raise ValueError("AUTHORIZED_CATALOG_INVALID_ITEM_KIND")
        link=item.get("source_url")
        if not isinstance(link,str):
            raise ValueError("AUTHORIZED_CATALOG_SOURCE_URL_MISSING")
        parsed_link=urllib.parse.urlsplit(link)
        if parsed_link.scheme!="https" or parsed_link.hostname not in (
           "www.tradingview.com","tradingview.com","kr.tradingview.com"):
            raise ValueError("AUTHORIZED_CATALOG_SOURCE_URL_NOT_TRADINGVIEW")
        sid=item.get("source_id")
        if not isinstance(sid,str) or not sid or len(sid)>200:
            raise ValueError("AUTHORIZED_CATALOG_SOURCE_ID_INVALID")
        normalized.append({"kind":workflow_kind,"source_id":sid,
            "source_url":link,"title":str(item.get("title",""))[:300],
            "author":str(item.get("author",""))[:150],
            "version_key":str(item.get("version_key",""))[:150],
            "published_at":item.get("published_at"),"updated_at":item.get("updated_at"),
            "access":item.get("access","unknown")})
    return {
        **input_json,
        "status":"ok",
        "items":normalized,
        "count":len(normalized),
        "has_more":bool(payload.get("has_more",False)),
        "fetched_at":datetime.now(timezone.utc).isoformat(),
        "catalog_source":"AUTHORIZED_EXTERNAL_FEED",
        "tradingview_requested":False,
        "tradingview_catalog_real":True,
        "next_node_executed":False
    }

def execute_node04(input_json,*,workflow_kind):
    """Deduplicate actual catalog candidates and keep only data needed to fetch."""
    if not isinstance(input_json,dict) or input_json.get("kind")!=workflow_kind:
        raise ValueError("N04_UPSTREAM_KIND_MISMATCH")
    rows=input_json.get("items")
    if not isinstance(rows,list) or not rows:
        raise ValueError("N04_EMPTY_CATALOG")
    seen=set()
    candidates=[]
    for item in rows:
        if item.get("kind")!=workflow_kind:
            continue
        source_id=item.get("source_id")
        version=str(item.get("version_key",""))
        url=item.get("source_url")
        if not isinstance(source_id,str) or not source_id or not isinstance(url,str):
            continue
        parsed=urllib.parse.urlsplit(url)
        if parsed.scheme!="https" or parsed.hostname not in (
            "www.tradingview.com","tradingview.com","kr.tradingview.com"):
            continue
        key=(source_id,version)
        if key in seen:
            continue
        seen.add(key)
        candidates.append({"kind":workflow_kind,"source_id":source_id,
            "version_key":version,"source_url":url,"title":str(item.get("title") or ""),
            "pine_version":str(item.get("pine_version") or "")})
    if not candidates:
        raise ValueError("N04_NO_FETCHABLE_CANDIDATES")
    next_page=(input_json["page"]+1 if input_json.get("has_more") and
               input_json["page"]<input_json["max_pages"] else None)
    return {**input_json,"candidates":candidates,"candidate_count":len(candidates),
        "next_page":next_page}

def execute_node05(input_json,*,workflow_kind):
    """Exact N04 candidates -> project SQLite source version presence check."""
    if not isinstance(input_json,dict) or input_json.get("kind")!=workflow_kind:
        raise ValueError("N05_UPSTREAM_KIND_MISMATCH")
    candidates=input_json.get("candidates")
    if not isinstance(candidates,list) or not candidates or len(candidates)!=input_json.get("candidate_count"):
        raise ValueError("N05_INVALID_N04_CANDIDATES")
    check=check_candidates(workflow_kind,candidates)
    if check["checked_count"]!=len(candidates):
        raise ValueError("N05_REGISTRY_CHECK_INCOMPLETE")
    return {**input_json,
        "catalog_items":input_json.get("items"),
        **check,
        "source_registry_checked":True,
        "source_registry_checked_at":datetime.now(timezone.utc).isoformat(),
        "pine_source_acquired":False,
        "next_node_executed":False}

def execute_node06(input_json,*,workflow_kind):
    """Choose one new candidate whose Pine can be fetched from the index."""
    if not isinstance(input_json,dict) or input_json.get("kind")!=workflow_kind:
        raise ValueError("N06_UPSTREAM_KIND_MISMATCH")
    rows=input_json.get("items")
    if not isinstance(rows,list) or input_json.get("source_registry_checked") is not True:
        raise ValueError("N06_REGISTRY_UNAVAILABLE")
    new=[item for item in rows if item.get("imported") is False]
    # Prefer a known mirror path to avoid selecting an unavailable Pine file.
    manual=input_json.get("manual_library")
    fetchable=[item for item in new if archive_path_for(item) or (
        workflow_kind=="library" and isinstance(manual,dict) and
        item.get("source_url")==manual.get("source_url"))]
    one=fetchable[0] if fetchable else None
    return {**input_json,"candidate":one,"has_candidate":one is not None,
        "selected_candidate_count":1 if one else 0,
        "can_continue":isinstance(input_json.get("next_page"),int),
        "pine_source_acquired":False}

def execute_node07(input_json,*,workflow_kind):
    """Actual IF routing: choose exactly one native n8n output handle."""
    if not isinstance(input_json,dict) or input_json.get("kind")!=workflow_kind:
        raise ValueError("N07_UPSTREAM_KIND_MISMATCH")
    has_candidate=input_json.get("has_candidate")
    if type(has_candidate) is not bool:
        raise ValueError("N07_BOOLEAN_CONDITION_REQUIRED")
    if input_json.get("source_registry_checked") is not True:
        raise ValueError("N07_MISSING_REGISTRY_CHECK")
    if has_candidate and not isinstance(input_json.get("candidate"),dict):
        raise ValueError("N07_TRUE_BRANCH_REQUIRES_REAL_CANDIDATE")
    if not has_candidate and input_json.get("candidate") is not None:
        raise ValueError("N07_FALSE_BRANCH_REQUIRES_NO_CANDIDATE")
    selected=0 if has_candidate else 1
    return {**input_json,
        "_studio_active_ports":[selected],
        "condition_result":has_candidate,
        "branch_label":"HAS_NEW_CANDIDATE" if has_candidate else "NO_CANDIDATE",
        "branch_decided_at":datetime.now(timezone.utc).isoformat(),
        "next_node_executed":False}

def execute_node08(input_json,*,workflow_kind):
    """Route no-candidate to next page, or stop if no pages remain."""
    if input_json.get("kind")!=workflow_kind or input_json.get("has_candidate") is not False:
        raise ValueError("N08_REQUIRES_NO_CANDIDATE")
    more=input_json.get("can_continue")
    if type(more) is not bool:raise ValueError("N08_INVALID_CAN_CONTINUE")
    return {**input_json,"_studio_active_ports":[0 if more else 1],
            "next_page_available":more}

def execute_node09(input_json,*,workflow_kind):
    """Prepare the next actual catalog page and clear stale candidate data."""
    if input_json.get("kind")!=workflow_kind or input_json.get("next_page_available") is not True:
        raise ValueError("N09_NEXT_PAGE_NOT_APPROVED")
    nxt,max_pages=input_json.get("next_page"),input_json.get("max_pages")
    if type(nxt) is not int or type(max_pages) is not int or not 2<=nxt<=max_pages<=3:
        raise ValueError("N09_INVALID_PAGE")
    return {"kind":workflow_kind,"page":nxt,"max_pages":max_pages,
        "page_size":input_json.get("page_size",50),"sort":"recent_extended",
        "max_detail_success":1,"selected_count":0,"tradingview_requested":False,
        "next_node_executed":False}

def execute_node10(input_json,*,workflow_kind):
    """Stop without claiming code was imported."""
    if input_json.get("kind")!=workflow_kind or input_json.get("next_page_available") is not False:
        raise ValueError("N10_MORE_PAGES_REMAIN")
    return {"kind":workflow_kind,"status":"NO_FETCHABLE_NEW_PINE","saved_count":0,
            "checked_page":input_json.get("page"),"conversion_validated":False,
            "tradingview_chart_validated":False}

def execute_node11(input_json,*,workflow_kind):
    """Obtain real Pine text; do not decide authorship or code authenticity."""
    if not isinstance(input_json,dict) or input_json.get("kind")!=workflow_kind:
        raise ValueError("N11_UPSTREAM_KIND_MISMATCH")
    candidate=input_json.get("candidate")
    if not input_json.get("has_candidate") or not isinstance(candidate,dict):
        raise ValueError("N11_NO_SELECTED_CANDIDATE")
    if candidate.get("kind")!=workflow_kind:
        raise ValueError("N11_CANDIDATE_KIND_MISMATCH")
    code=input_json.get("pine_code")
    manual=input_json.get("manual_library")
    if workflow_kind=="library" and isinstance(manual,dict):
        if candidate.get("source_url")!=manual.get("source_url"):
            raise ValueError("LIBRARY_CANDIDATE_SOURCE_MISMATCH")
        code=manual.get("pine_code")
    if not isinstance(code,str) or not code.strip():
        code=acquire_verified_pine(candidate)["pine_code"]
    if len(code.encode("utf-8"))>MAX_PINE_BYTES:
        raise ValueError("N11_PINE_SOURCE_TOO_LARGE")
    if not re.search(r"(?m)^\s*//@version=[456]\s*$",code):
        raise ValueError("N11_INVALID_PINE_CONTENT")
    declaration="library" if workflow_kind=="library" else "strategy"
    if not re.search(r"(?m)^\s*"+declaration+r"\s*\(",code):
        raise ValueError("N11_WRONG_PINE_SCRIPT_TYPE")
    return {
        "kind":workflow_kind,
        "candidate":{"kind":workflow_kind,
            "source_id":candidate["source_id"],
            "version_key":str(candidate["version_key"]),
            "source_url":candidate.get("source_url",""),
            "title":candidate.get("title","")},
        "pine_code":code,
        "pine_source_acquired":True,
        "rights_state":"PENDING_REVIEW",
        "conversion_validated":False,
        "tradingview_chart_validated":False}

def execute_node15(input_json,*,workflow_kind):
    """Save the Pine text obtained at N11; N12/N13 no longer exist."""
    if not isinstance(input_json,dict) or input_json.get("kind")!=workflow_kind:
        raise ValueError("N15_UPSTREAM_KIND_MISMATCH")
    if input_json.get("pine_source_acquired") is not True:
        raise ValueError("N15_PINE_SOURCE_NOT_ACQUIRED")
    stored=save_verified_source(input_json,workflow_kind)
    return {**input_json,**stored,"status":"PINE_SAVED_CONVERSION_PENDING"}

def execute_node16(input_json,*,workflow_kind):
    """Display actual saved source result, not a duplicate source audit."""
    if not isinstance(input_json,dict) or input_json.get("kind")!=workflow_kind:
        raise ValueError("N16_UPSTREAM_KIND_MISMATCH")
    if input_json.get("source_saved") is not True or input_json.get("status")!="PINE_SAVED_CONVERSION_PENDING":
        raise ValueError("N16_SOURCE_SAVE_NOT_COMPLETE")
    return {"kind":workflow_kind,"status":"PINE_SAVED_CONVERSION_PENDING",
        "source_id":input_json["source_id"],"version_key":input_json["version_key"],
        "saved_count":input_json["saved_count"],"rights_state":"PENDING_REVIEW",
        "conversion_validated":False,"tradingview_chart_validated":False,
        "paper_enabled":False,"live_orders_enabled":False}

def execute_node(workflow_path,node_id,input_json):
    if workflow_path==WF02_PATH:
        function={"wf02-01":execute_wf02_node01,"wf02-02":execute_wf02_node02,
                  "wf02-03":execute_wf02_node03}.get(node_id)
        if function is None:raise ValueError("UNREGISTERED_PROJECT_NODE")
        return function(input_json,workflow_kind="strategy")
    kind=WF01_MODES.get(workflow_path)
    binding=node_binding(workflow_path,node_id)
    if not kind or not binding:raise ValueError("UNREGISTERED_PROJECT_NODE")
    functions={"execute_node01":execute_node01,"execute_node02":execute_node02,
               "execute_node03":execute_node03,
               "execute_node04":execute_node04,
               "execute_node05":execute_node05,
               "execute_node06":execute_node06,
               "execute_node07":execute_node07,
               "execute_node08":execute_node08,
               "execute_node09":execute_node09,
               "execute_node10":execute_node10,
               "execute_node11":execute_node11,
               "execute_node15":execute_node15,
               "execute_node16":execute_node16}
    func=functions[binding["python_function"]]
    return func(input_json,workflow_kind=kind)

def default_node_input(workflow_path,node_id):
    if workflow_path==WF02_PATH:
        return {"ui_selection":"strategy","requested_detail_limit":1} if node_id=="wf02-01" else {}
    kind=WF01_MODES.get(workflow_path)
    if not kind:return None
    if node_id=="wf01-"+kind+"-01":
        return {"ui_selection":kind,"requested_detail_limit":1}
    if node_id in ("wf01-"+kind+"-02","wf01-"+kind+"-03","wf01-"+kind+"-04","wf01-"+kind+"-05","wf01-"+kind+"-06","wf01-"+kind+"-07","wf01-"+kind+"-08","wf01-"+kind+"-09","wf01-"+kind+"-10","wf01-"+kind+"-11","wf01-"+kind+"-15","wf01-"+kind+"-16"):
        return {}
    return None
