#!/usr/bin/env python3
"""Test the PUBLIC sandbox's *actual* isolated SQLite save without touching LIVE.

Uses a fresh anonymous cookie and a safe S01 fixture. Never sends an order or
calls an n8n workflow run endpoint. Does not use any production credentials.
"""
import copy, http.cookiejar, json, os, sys
from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.error import HTTPError
from urllib.parse import urljoin

BASE=os.getenv("STUDIO_SANDBOX_URL","https://investment-shared-n8n-studio-production.up.railway.app/")
ALLOWED={
 "https://investment-shared-n8n-studio-production.up.railway.app/",
 "https://investment-n8n-native-editor-production.up.railway.app/",
}
if BASE not in ALLOWED:
    raise SystemExit("Refusing to test unknown or LIVE trading service")
END=urljoin(BASE,"api/studio/workflows/scenarios/01-new-strategy.json")
opener=build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))

def req(url, method="GET", payload=None, opener=opener):
    body=json.dumps(payload).encode() if payload is not None else None
    request=Request(url,data=body,method=method,headers={"Content-Type":"application/json"} if body else {})
    try:
        response=opener.open(request,timeout=25)
    except HTTPError as e:
        response=e
    data=json.loads(response.read().decode())
    return response.status,data

def check(cond,label):
    if not cond:
        raise AssertionError(label)
    print("LIVE_SHARED_STUDIO_PASS "+label,flush=True)

code,health=req(urljoin(BASE,"api/studio/health"))
check(code==200 and health.get("storage")=="sqlite" and health.get("executionEnabled") is False,"public_sandbox_has_sqlite_and_no_execution")
code,start=req(END)
check(code==200 and start.get("version")==0 and len(start["workflow"]["nodes"])==6,"anonymous_s01_real_fixture_initial")
modified=copy.deepcopy(start["workflow"])
node=modified["nodes"][0]
node["name"]=node["name"]+" [REMOTE DEMO TEST]"
# Avoid altering relationships for downstream nodes, so edit a JSON parameter instead.
node["name"]=start["workflow"]["nodes"][0]["name"]
node.setdefault("parameters",{})["server_draft_probe"]="public_http_test"
code,saved=req(END,"PUT",{"workflow":modified,"expectedVersion":0})
check(code==200 and saved["version"]==1,"public_sandbox_sqlite_put_version_1")
code,loaded=req(END)
check(code==200 and loaded["source"]=="server" and loaded["workflow"]["nodes"][0]["parameters"]["server_draft_probe"]=="public_http_test","public_sandbox_sqlite_get_saved_data")
code,stale=req(END,"PUT",{"workflow":modified,"expectedVersion":0})
check(code==409 and stale.get("currentVersion")==1,"public_sandbox_conflict_409")
code,versions=req(END+"/versions")
check(code==200 and versions["versions"][0]["version"]==1,"public_sandbox_revision_history")
fresh=build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
code,new_user=req(END,opener=fresh)
check(code==200 and new_user["source"]=="original" and new_user["version"]==0,"per_browser_anonymous_data_isolated")
print("LIVE_SHARED_STUDIO_SERVER_ALL_PASS",flush=True)
