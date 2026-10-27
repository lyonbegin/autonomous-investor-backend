"""Local verification transport for the existing public operations UI.

Python validates upstream TLS using the platform's managed CA bundle. Only the
explicit public GET paths are forwarded; browser cookies and writes are blocked.
This is a test transport, never a deployment or an authentication bypass.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import error, request
from urllib.parse import urlsplit

UPSTREAM = "https://investment-n8n-operations-ui-production.up.railway.app"
READS = {
    "/studio-api/api/v1/ops/overview", "/studio-api/api/v1/ops/strategies",
    "/studio-api/api/v1/ops/agents", "/studio-api/api/v1/ops/events",
    "/studio-api/api/v1/ops/audit/findings", "/studio-api/api/v1/alpha/scenarios",
    "/studio-api/api/v1/alpha/scenarios/infra",
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlsplit(self.path).path
        if path != "/" and not path.startswith("/assets/") and path not in READS:
            self.send_error(403)
            return
        req = request.Request(UPSTREAM + self.path, headers={"Accept-Encoding": "identity"})
        try:
            response = request.urlopen(req, timeout=25)
        except error.HTTPError as exc:
            response = exc
        with response:
            data = response.read(5_000_001)
            if len(data) > 5_000_000:
                self.send_error(502)
                return
            self.send_response(response.code)
            self.send_header("Content-Type", response.headers.get("Content-Type", "application/octet-stream"))
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

    def do_POST(self):
        self.send_error(403)

    do_PUT = do_POST
    do_PATCH = do_POST
    do_DELETE = do_POST

    def log_message(self, *_args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8007), Handler).serve_forever()
