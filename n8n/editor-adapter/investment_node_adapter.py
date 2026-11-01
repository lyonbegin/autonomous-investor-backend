"""Stock-project-owned WF01 node registry and execution logic.

This module belongs to autonomous-investor-backend, NOT the shared editor.
Only bounded, side-effect-free N01/N02 test functions are registered.
"""
import json
import os
import ssl
import urllib.parse
import urllib.request
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
          "python_function":"execute_node03","code_version":"wf01-n03-authorized-catalog-v1",
          "node_character":"authorized_catalog_request"}
    return None

def node_type(workflow_path,node_id):
    kind=WF01_MODES.get(workflow_path)
    if not kind:return None
    return {
      "wf01-"+kind+"-01":"n8n-nodes-base.manualTrigger",
      "wf01-"+kind+"-02":"n8n-nodes-base.code",
      "wf01-"+kind+"-03":"n8n-nodes-base.httpRequest",
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
        raise ValueError("AUTHORIZED_CATALOG_FEED_UNCONFIGURED")
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

def execute_node(workflow_path,node_id,input_json):
    kind=WF01_MODES.get(workflow_path)
    binding=node_binding(workflow_path,node_id)
    if not kind or not binding:raise ValueError("UNREGISTERED_PROJECT_NODE")
    functions={"execute_node01":execute_node01,"execute_node02":execute_node02,
               "execute_node03":execute_node03}
    func=functions[binding["python_function"]]
    return func(input_json,workflow_kind=kind)

def default_node_input(workflow_path,node_id):
    kind=WF01_MODES.get(workflow_path)
    if not kind:return None
    if node_id=="wf01-"+kind+"-01":
        return {"ui_selection":kind,"requested_detail_limit":1}
    if node_id in ("wf01-"+kind+"-02","wf01-"+kind+"-03"):
        return {}
    return None
