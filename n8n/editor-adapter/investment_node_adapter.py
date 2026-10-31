"""Stock-project-owned WF01 node registry and execution logic.

This module belongs to autonomous-investor-backend, NOT the shared editor.
Only bounded, side-effect-free N01/N02 test functions are registered.
"""
import json

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
    return None

def node_type(workflow_path,node_id):
    kind=WF01_MODES.get(workflow_path)
    if not kind:return None
    return {
      "wf01-"+kind+"-01":"n8n-nodes-base.manualTrigger",
      "wf01-"+kind+"-02":"n8n-nodes-base.code",
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

def execute_node(workflow_path,node_id,input_json):
    kind=WF01_MODES.get(workflow_path)
    binding=node_binding(workflow_path,node_id)
    if not kind or not binding:raise ValueError("UNREGISTERED_PROJECT_NODE")
    func=execute_node01 if binding["python_function"]=="execute_node01" else execute_node02
    return func(input_json,workflow_kind=kind)

def default_node_input(workflow_path,node_id):
    kind=WF01_MODES.get(workflow_path)
    if not kind:return None
    if node_id=="wf01-"+kind+"-01":
        return {"ui_selection":kind,"requested_detail_limit":1}
    if node_id=="wf01-"+kind+"-02":
        return {}
    return None
