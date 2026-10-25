#!/usr/bin/env python3
"""Local deterministic upstream fixture for n8n F01 integration CI ONLY.

This endpoint is not TradingView and is never deployed with production Compose.
It proves that F01 actually fetches an external HTTP payload via its real adapter,
persists hashes, and correctly gates source accessibility.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from urllib.parse import urlsplit


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path=urlsplit(self.path).path
        if path=="/api/v1/tradingview/scripts/live":
            payload={"source":"CI ONLY HTTP TradingView collector fixture",
                "script_type":"strategies","sort":"recent_extended","page":1,
                "count":1,"items":[{"script_id_part":"CI-REAL-HTTP-PINE-1","name":"CI Public Pine Strategy",
                     "author":"ci-fixture","script_type":"strategy","script_access":"open","version":"1"}]}
        elif path=="/api/v1/tradingview/scripts/catalog":
            payload={
                "count":2,"total_count":2,"has_more":False,
                "script_type":"strategies",
                "items":[
                    {"script_id_part":"CI-REAL-HTTP-PINE-1","name":"CI Public Pine Strategy",
                     "author":"ci-fixture","script_type":"strategy","script_access":"open","version":"1"},
                    {"script_id_part":"CI-PROTECTED-PINE-2","name":"CI protected Pine",
                     "author":"ci-fixture","script_type":"strategy","script_access":"protected","version":"1"},
                ],
            }
        elif path=="/api/v1/tradingview/scripts/CI-REAL-HTTP-PINE-1/source":
            payload={"ok":True,"version":"1","kind":"strategy","script_id_part":"CI-REAL-HTTP-PINE-1",
                "source":"//@version=6\nstrategy('CI fixture - not real financial strategy')\n"}
        elif path=="/api/v1/tradingview/scripts/CI-PROTECTED-PINE-2/source":
            payload={"ok":False,"protected":True,"script_id_part":"CI-PROTECTED-PINE-2",
                     "reason":"source is protected"}
        else:
            self.send_error(404)
            return
        body=json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self,fmt,*args):
        print("CI_FIXTURE "+fmt%args,flush=True)


if __name__=="__main__":
    print("CI ONLY mock TradingView-service listening on 127.0.0.1:8001",flush=True)
    ThreadingHTTPServer(("127.0.0.1",8001),Handler).serve_forever()
