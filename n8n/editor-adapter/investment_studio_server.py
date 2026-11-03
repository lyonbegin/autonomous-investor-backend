"""Extend the original shared studio HTTP server without forking its workflow editor.

The only new entrypoints are bounded read-only WF-02 chart test endpoints.
Original saved workflows and SQLite session history remain managed upstream.
"""
import json
import urllib.error
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit

import studio_server as studio
import investment_tv_chart_integration as chart_integration


class InvestmentHandler(studio.Handler):
    def do_GET(self):
        if urlsplit(self.path).path == "/api/investment/tv-chart/latest":
            sid, fresh = self._sid()
            try:
                result = chart_integration.latest(sid)
                return self._json(200, result, sid, fresh)
            except Exception as exc:
                return self._json(503, {"status": "TV_CHART_EVIDENCE_NOT_AVAILABLE",
                                        "error": type(exc).__name__}, sid, fresh)
        return super().do_GET()

    def do_POST(self):
        if urlsplit(self.path).path != "/api/investment/tv-chart/verify":
            return super().do_POST()
        sid, fresh = self._sid()
        origin = self.headers.get("Origin")
        if origin and (urlsplit(origin).netloc != self.headers.get("Host")
                       or urlsplit(origin).scheme not in ("https", "http")):
            return self._json(403, {"status": "CROSS_ORIGIN_FORBIDDEN"}, sid, fresh)
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            return self._json(415, {"status": "JSON_REQUIRED"}, sid, fresh)
        try:
            size = int(self.headers.get("Content-Length", "-1"))
            if not 2 <= size <= 32:
                return self._json(413, {"status": "REQUEST_TOO_LARGE"}, sid, fresh)
            body = json.loads(self.rfile.read(size))
            if body != {}:
                return self._json(400, {"status": "FIXED_OFFICIAL_AAPL_TEST_ONLY"}, sid, fresh)
            result = chart_integration.execute(sid)
            return self._json(200, result, sid, fresh)
        except urllib.error.HTTPError as exc:
            return self._json(502, {
                "status": "TRADINGVIEW_BROWSER_HTTP_FAILURE",
                "upstream_status": exc.code, "tv_strategy_parity_verified": False
            }, sid, fresh)
        except urllib.error.URLError as exc:
            return self._json(502, {
                "status": "TRADINGVIEW_BROWSER_CONNECTION_FAILURE",
                "reason": type(exc.reason).__name__, "tv_strategy_parity_verified": False
            }, sid, fresh)
        except (ValueError, TypeError, RuntimeError, OSError) as exc:
            return self._json(422, {
                "status": "WF02_OFFICIAL_CHART_TEST_FAILED",
                "reason": str(exc)[:200], "tv_strategy_parity_verified": False
            }, sid, fresh)


if __name__ == "__main__":
    studio.archive_verified_old_sqlite_backup()
    studio.init_db()
    print("Investment studio with original workflow canvas and official chart-to-PyneCore WF02 verification", flush=True)
    ThreadingHTTPServer(("0.0.0.0", studio.PORT), InvestmentHandler).serve_forever()
