"""Built-image self-contained GET/POST smoke test for the verified admin site.

Runs only against a temporary localhost server/SQLite file and always cleans up.
No Railway prod data is read and no trading/n8n workflows execute.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.request import Request,urlopen


def call(url,body=None,origin=None,host=None):
    raw=None if body is None else json.dumps(body).encode()
    headers={"Accept":"application/json"}
    if body is not None:headers["Content-Type"]="application/json"
    if origin:headers["Origin"]=origin
    if host:headers["Host"]=host
    req=Request(url,data=raw,headers=headers,method="POST" if body is not None else "GET")
    try:
        with urlopen(req,timeout=5) as r:
            return r.status,r.read(150000).decode()
    except HTTPError as ex:
        return ex.code,ex.read(150000).decode()


def main():
    root="/app/dist"
    assert Path(root+"/admin/index.html").is_file()
    assert Path(root+"/verified/index.html").is_file()
    assert list(Path(root+"/verified/assets").glob("*.js"))
    with tempfile.TemporaryDirectory(prefix="verified-admin-smoke-") as tmp:
        port=38917
        env={**os.environ,"STUDIO_DB_PATH":tmp+"/studio.sqlite3",
             "STUDIO_STATIC_ROOT":root,"PORT":str(port)}
        # PG is not needed for an empty verified catalog; it must fail closed
        # when no canonical comparison evidence exists.
        env.pop("INVESTMENT_DATABASE_URL",None)
        process=subprocess.Popen([sys.executable,"-u","/app/investment_studio_server.py"],
          cwd="/app",env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        base="http://127.0.0.1:"+str(port)
        try:
            ready=False
            for _ in range(65):
                if process.poll() is not None:
                    raise AssertionError("STUDIO_SERVER_EXITED_"+str(process.returncode))
                try:
                    code,_=call(base+"/health")
                    if code==200:ready=True;break
                except (URLError,ConnectionError,TimeoutError):
                    time.sleep(.2)
            assert ready,"HEALTH_NOT_READY"
            code,html=call(base+"/admin/index.html?section=verified")
            assert code==200 and "검증 완료 전략" in html,(code,"ADMIN_MENU_NOT_PRESENT")
            code,html=call(base+"/verified/index.html?view=list")
            assert code==200 and "/verified/assets/" in html,(code,"MIGRATED_REACT_NOT_SERVED")
            # Do not disable clickjacking defense across the service. Only
            # same-origin migrated React is allowed inside the admin iframe.
            with urlopen(base+"/verified/index.html",timeout=5) as response:
                assert response.headers.get("X-Frame-Options")=="SAMEORIGIN",("VERIFIED_IFRAME_BLOCKED",dict(response.headers))
            with urlopen(base+"/admin/index.html",timeout=5) as response:
                assert response.headers.get("X-Frame-Options")=="DENY","ADMIN_CLICKJACKING_DEFENSE_LOST"
            code,data=call(base+"/api/investment/verified-scripts/catalog?limit=50&offset=0")
            assert code==200,(code,data[:250])
            body=json.loads(data)
            assert body["items"]==[] and body["published_only"],"UNVERIFIED_CATALOG_NOT_EMPTY"
            code,data=call(base+"/api/investment/verified-scripts/candidates")
            assert code==200,(code,data[:260])
            # A nonpublished strategy must never leak original source or
            # trigger the TradingView chart worker; no synthetic fallback.
            encoded="PUB%3B5442675d418140c58486eb4a7ae12768"
            for suffix in ("/source","/chart?symbol=NASDAQ%3AAMZN&horizon=2h"):
                code,data=call(base+"/api/investment/verified-scripts/"+encoded+suffix)
                assert code==422 and json.loads(data)["status"]=="DDDS_PUBLISHED_SOURCE_OR_WORKER_BARS_INVALID",(code,data[:260])
            code,data=call(base+"/api/investment/verified-scripts/PUB%3Banother/chart?symbol=NASDAQ%3AAMZN&horizon=2h")
            assert code==404 and json.loads(data)["status"]=="PINNED_VERIFIED_DDDS_ONLY",(code,data[:260])
            code,data=call(base+"/api/investment/verified-scripts/publish",
                {"source_id":"PUB;not-verified","version_key":"v1","pine_sha256":"a"*64},
                origin=base)
            assert code==403,"FOREIGN_OR_FAKE_ADMIN_ORIGIN_NOT_BLOCKED"
            code,data=call(base+"/api/investment/verified-scripts/publish",
                {"source_id":"PUB;not-verified","version_key":"v1","pine_sha256":"a"*64},
                origin="https://investment-n8n-native-editor-production.up.railway.app")
            assert code==403,"WRONG_HOST_PUBLISH_SHOULD_BLOCK"
            code,data=call(base+"/api/investment/verified-scripts/publish",
                {"source_id":"PUB;not-verified","version_key":"v1","pine_sha256":"a"*64},
                origin="https://investment-n8n-native-editor-production.up.railway.app",
                host="investment-n8n-native-editor-production.up.railway.app")
            assert code==422 and json.loads(data)["status"]=="PUBLISH_ONLY_ACTUALLY_VERIFIED_SOURCE",(code,data)
            code,data=call(base+"/api/investment/verified-scripts/catalog?limit=50&offset=0")
            assert code==200 and json.loads(data)["count"]==0,"UNVERIFIED_PUBLISHED"
            code,html=call(base+"/")
            assert code==200 and "<html" in html.lower(),"ORIGINAL_NODE_EDITOR_DISAPPEARED"
            print("VERIFIED_ADMIN_FULL_HTTP_SMOKE_PASS",json.dumps(
              {"admin_html":200,"original_editor":200,"copied_react":200,
               "catalog":200,"candidates":200,"unverified_publish":422,
               "default_published_count":0},ensure_ascii=False))
        except Exception as exc:
            print("VERIFIED_HTTP_SMOKE_ERROR",repr(exc),file=sys.stderr,flush=True)
            process.terminate()
            try:
                output,_=process.communicate(timeout=5)
                print("VERIFIED_HTTP_SERVER_LOG",output.decode(errors="replace")[-3500:],
                  file=sys.stderr,flush=True)
            except subprocess.TimeoutExpired:process.kill()
            raise
        finally:
            process.terminate()
            try:process.communicate(timeout=6)
            except subprocess.TimeoutExpired:process.kill();process.communicate()


if __name__=="__main__":main()
