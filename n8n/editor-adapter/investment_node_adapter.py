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
from datetime import datetime,timezone

WF01_MODES={
    "operations/WF01-latest-strategy-one.json":"strategy",
    "operations/WF01-latest-library-one.json":"library",
}

def node_binding(workflow_path,node_id):
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
          "python_function":"execute_node06","code_version":"wf01-n06-select-compatible-v2",
          "node_character":"choose_single_new_strategy"}
    if node_id==prefix+"07":
        return {"python_module":"investment_node_adapter",
          "python_function":"execute_node07","code_version":"wf01-n07-if-v1",
          "node_character":"conditional_route"}
    if node_id==prefix+"11":
        return {"python_module":"investment_node_adapter",
          "python_function":"execute_node11","code_version":"wf01-n11-original-pine-hash-v1",
          "node_character":"verified_operator_pine_source"}
    return None

def node_type(workflow_path,node_id):
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
      "wf01-"+kind+"-11":"n8n-nodes-base.httpRequest",
    }.get(node_id)

def execute_node01(input_json,*,workflow_kind):
    if not isinstance(input_json,dict):raise ValueError("INPUT_JSON_OBJECT_REQUIRED")
    if workflow_kind not in ("strategy","library"):raise ValueError("UNSUPPORTED_WORKFLOW_KIND")
    allowed={"ui_selection","requested_detail_limit","max_pages"}
    if not {"ui_selection","requested_detail_limit"}.issubset(input_json) or set(input_json)-allowed:
        raise ValueError("INPUT_FIELDS_MISMATCH: ui_selection, requested_detail_limit")
    if input_json["ui_selection"]!=workflow_kind:raise ValueError("COLLECTION_KIND_MISMATCH")
    if type(input_json["requested_detail_limit"]) is not int or input_json["requested_detail_limit"]!=1:
        raise ValueError("DETAIL_LIMIT_MUST_EQUAL_ONE")
    pages=input_json.get("max_pages",3)
    if type(pages) is not int or not 1<=pages<=3:raise ValueError("MAX_PAGES_MUST_BE_1_TO_3")
    return {"kind":workflow_kind,"page":1,"max_pages":pages,
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
    """Validate real N03 candidates; preserve full input and never invent dates."""
    if not isinstance(input_json,dict) or input_json.get("kind")!=workflow_kind:
        raise ValueError("N04_UPSTREAM_KIND_MISMATCH")
    if input_json.get("status")!="ok" or not isinstance(input_json.get("items"),list):
        raise ValueError("N04_CATALOG_UNAVAILABLE")
    if not input_json.get("catalog_source") or type(input_json.get("count")) is not int:
        raise ValueError("N04_CATALOG_PROVENANCE_MISSING")
    page,max_pages=input_json.get("page"),input_json.get("max_pages")
    if type(page) is not int or type(max_pages) is not int or not 1<=page<=max_pages<=3:
        raise ValueError("N04_PAGE_CONFIG_MISMATCH")
    items=input_json["items"]
    if len(items)!=input_json["count"] or not items:
        raise ValueError("N04_CATALOG_COUNT_MISMATCH")
    candidates=[];seen=set();removed=0
    for item in items:
        if not isinstance(item,dict) or item.get("kind")!=workflow_kind:
            raise ValueError("N04_INVALID_ITEM_KIND")
        sid,version,url=item.get("source_id"),item.get("version_key"),item.get("source_url")
        if not isinstance(sid,str) or not sid or not isinstance(version,str):
            raise ValueError("N04_SOURCE_ID_OR_VERSION_MISSING")
        if not isinstance(url,str):
            raise ValueError("N04_INVALID_TRADINGVIEW_URL")
        parsed=urllib.parse.urlsplit(url)
        if parsed.hostname not in ("www.tradingview.com","tradingview.com","kr.tradingview.com") or parsed.scheme!="https":
            raise ValueError("N04_INVALID_TRADINGVIEW_URL")
        key=(sid,version)
        if key in seen:
            removed+=1;continue
        seen.add(key)
        candidates.append({"kind":workflow_kind,"source_id":sid,"version_key":version,
            "source_url":url,"title":str(item.get("title") or "")[:300],
            "author":str(item.get("author") or "")[:150],
            "source_sha256_reported":item.get("source_sha256_reported"),
            "pine_version":item.get("pine_version"),
            "published_at":item.get("published_at"),"updated_at":item.get("updated_at"),
            "catalog_observed_at":item.get("catalog_observed_at"),
            "metadata_origin":item.get("metadata_origin") or input_json["catalog_source"],
            "access":item.get("access","unknown"),
            "source_code_fetched":item.get("source_code_fetched",False),
            "source_license_reported":item.get("source_license_reported","unknown")})
    if not candidates:
        raise ValueError("N04_NO_VALID_CANDIDATES")
    is_live=input_json.get("catalog_is_live") is True
    # Research corpus fetched_at must NEVER be passed off as TradingView updated_at.
    candidates.sort(key=lambda item:(
        str(item["updated_at"] or "") if is_live else str(item["catalog_observed_at"] or ""),
        item["source_id"]),reverse=True)
    next_page=page+1 if input_json.get("has_more") and page<max_pages else None
    return {**input_json,
        "candidates":candidates,"candidate_count":len(candidates),
        "duplicates_removed":removed,"next_page":next_page,
        "latest_tradingview_checked":bool(is_live),
        "validated_catalog_is_snapshot":not is_live,
        "candidate_sort_basis":"updated_at_from_live_provider" if is_live
                          else "third_party_manifest_observed_at",
        "source":"project_approved_catalog_validation",
        "node04_validated_at":datetime.now(timezone.utc).isoformat(),
        "next_node_executed":False}

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
    """Select ONE genuinely unregistered source version from N05's SQLite results."""
    if not isinstance(input_json,dict) or input_json.get("kind")!=workflow_kind:
        raise ValueError("N06_UPSTREAM_KIND_MISMATCH")
    if input_json.get("source_registry_checked") is not True:
        raise ValueError("N06_REGISTRY_NOT_CHECKED")
    rows=input_json.get("items")
    if not isinstance(rows,list) or len(rows)!=input_json.get("checked_count"):
        raise ValueError("N06_INVALID_N05_ITEMS")
    if any(x.get("kind")!=workflow_kind for x in rows):
        raise ValueError("N06_CROSS_KIND_ITEM")
    valid=[x for x in rows if x.get("imported") is False and
           isinstance(x.get("source_id"),str) and x.get("source_id") and
           isinstance(x.get("version_key"),str) and
           isinstance(x.get("source_url"),str) and
           x["source_url"].startswith("https://www.tradingview.com/script/")]
    def preference(candidate):
        version=str(candidate.get("pine_version") or "")
        # Version compatibility is a preliminary filter, not a promise that
        # its Pine operations are supported by the current Python compiler.
        license_id=str(candidate.get("source_license_reported") or "").upper()
        licensed=license_id in ("MPL-2.0","MIT","APACHE-2.0","BSD-3-CLAUSE")
        if version=="6":return 0 if licensed else 1
        if version=="5":return 2 if licensed else 3
        return 4
    one=min(valid,key=preference) if valid else None
    # No Pine source has yet been downloaded; this chooses metadata for N11.
    return {**input_json,
      "candidate":one,
      "has_candidate":one is not None,
      "selected_candidate_count":1 if one else 0,
      "selected_count":input_json.get("selected_count",0),
      "can_continue":isinstance(input_json.get("next_page"),int) and
                     input_json["next_page"]>input_json.get("page",0) and
                     input_json["next_page"]<=input_json.get("max_pages",0),
      "candidate_selection_basis":"prioritize_Pine_v6_v5_with_reported_license_then_catalog_order",
      "candidate_pine_version_supported_by_current_converter":
          bool(one and str(one.get("pine_version")) in ("5","6")),
      "pine_source_acquired":False,
      "node06_selected_at":datetime.now(timezone.utc).isoformat(),
      "next_node_executed":False}

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

def execute_node11(input_json,*,workflow_kind):
    """Accept genuine operator-provided Pine ONLY when it matches source hash.

    N03 corpus carries metadata, not Pine. Never pretend a metadata URL or a
    string created by the program is the author's actual published source.
    """
    if not isinstance(input_json,dict) or input_json.get("kind")!=workflow_kind:
        raise ValueError("N11_UPSTREAM_KIND_MISMATCH")
    candidate=input_json.get("candidate")
    if not isinstance(candidate,dict) or not input_json.get("has_candidate"):
        raise ValueError("N11_NO_SELECTED_SOURCE_CANDIDATE")
    if candidate.get("kind")!=workflow_kind:
        raise ValueError("N11_SELECTED_KIND_MISMATCH")
    expected=candidate.get("source_sha256_reported")
    if not isinstance(expected,str) or not re.fullmatch(r"[a-fA-F0-9]{64}",expected):
        raise ValueError("N11_ORIGINAL_SOURCE_HASH_NOT_AVAILABLE")
    code=input_json.get("pine_code")
    if not isinstance(code,str) or not code.strip():
        raise ValueError("N11_ORIGINAL_PINE_NOT_SUPPLIED")
    if len(code.encode("utf-8"))>60000:
        raise ValueError("N11_PINE_SOURCE_TOO_LARGE")
    if not re.search(r"(?m)^\s*//@version=(4|5|6)\s*$",code):
        raise ValueError("N11_PINE_VERSION_DECLARATION_MISSING")
    if not re.search(r"(?m)^\s*(strategy|indicator|library)\s*\(",code):
        raise ValueError("N11_PINE_DECLARATION_MISSING")
    actual=hashlib.sha256(code.encode("utf-8")).hexdigest()
    if actual.lower()!=expected.lower():
        raise ValueError("N11_PINE_SHA256_DOES_NOT_MATCH_PUBLISHED_SNAPSHOT")
    # No automatic non-display TradingView ingestion, no rights approval.
    return {**input_json,
        "pine_source_acquired":True,
        "pine_source_sha256":actual,
        "source_hash_verified":True,
        "pine_source_origin":"OPERATOR_PROVIDED_MATCHING_RESEARCH_HASH",
        "rights_state":"PENDING_REVIEW",
        "source_verified_at":datetime.now(timezone.utc).isoformat(),
        "tradingview_requested":False,
        "next_node_executed":False}

def execute_node(workflow_path,node_id,input_json):
    kind=WF01_MODES.get(workflow_path)
    binding=node_binding(workflow_path,node_id)
    if not kind or not binding:raise ValueError("UNREGISTERED_PROJECT_NODE")
    functions={"execute_node01":execute_node01,"execute_node02":execute_node02,
               "execute_node03":execute_node03,
               "execute_node04":execute_node04,
               "execute_node05":execute_node05,
               "execute_node06":execute_node06,
               "execute_node07":execute_node07,
               "execute_node11":execute_node11}
    func=functions[binding["python_function"]]
    return func(input_json,workflow_kind=kind)

def default_node_input(workflow_path,node_id):
    kind=WF01_MODES.get(workflow_path)
    if not kind:return None
    if node_id=="wf01-"+kind+"-01":
        return {"ui_selection":kind,"requested_detail_limit":1}
    if node_id in ("wf01-"+kind+"-02","wf01-"+kind+"-03","wf01-"+kind+"-04","wf01-"+kind+"-05","wf01-"+kind+"-06","wf01-"+kind+"-07","wf01-"+kind+"-11"):
        return {}
    return None
