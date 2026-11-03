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
import investment_tv_publication as published
import investment_tv_trade_reference as official_trades


class InvestmentHandler(studio.Handler):
    def do_GET(self):
        if urlsplit(self.path).path == "/api/investment/tv-publication/trades/latest":
            sid, fresh = self._sid()
            try:
                return self._json(200, official_trades.latest(sid), sid, fresh)
            except OSError as exc:
                return self._json(503,{"status":"DDDS_TRADE_REFERENCE_STORAGE_UNAVAILABLE",
                    "reason":type(exc).__name__},sid,fresh)
        if urlsplit(self.path).path == "/api/investment/tv-publication/latest":
            sid, fresh = self._sid()
            try:
                return self._json(200, published.latest_reference(sid), sid, fresh)
            except (ValueError, OSError) as exc:
                return self._json(503, {"status":"PUBLISHED_STRATEGY_REFERENCE_UNAVAILABLE",
                                        "reason":type(exc).__name__}, sid, fresh)
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
        if urlsplit(self.path).path == "/api/investment/tv-publication/trades/capture":
            sid, fresh = self._sid()
            origin = self.headers.get("Origin")
            if origin and (urlsplit(origin).netloc != self.headers.get("Host")
                           or urlsplit(origin).scheme not in ("https", "http")):
                return self._json(403,{"status":"CROSS_ORIGIN_FORBIDDEN"},sid,fresh)
            if not self.headers.get("Content-Type","").startswith("application/json"):
                return self._json(415,{"status":"JSON_REQUIRED"},sid,fresh)
            try:
                size=int(self.headers.get("Content-Length","-1"))
                if size!=2 or self.rfile.read(size)!=b"{}":
                    return self._json(400,{"status":"FIXED_PINNED_DDDS_ONLY"},sid,fresh)
                result=official_trades.capture(sid)
                return self._json(200,result,sid,fresh)
            except (ValueError,TypeError) as exc:
                return self._json(422,{"status":"DDDS_PUBLIC_TRADE_REFERENCE_INVALID",
                    "reason":str(exc)[:240]},sid,fresh)
            except urllib.error.HTTPError as exc:
                return self._json(502,{"status":"DDDS_TRADE_WORKER_HTTP_ERROR",
                    "upstream_status":exc.code},sid,fresh)
            except (urllib.error.URLError,TimeoutError,OSError) as exc:
                return self._json(502,{"status":"DDDS_TRADE_WORKER_UNAVAILABLE",
                    "reason":type(exc).__name__},sid,fresh)
        if urlsplit(self.path).path == "/api/investment/tv-publication/register-wf02":
            sid, fresh = self._sid()
            origin = self.headers.get("Origin")
            if origin and (urlsplit(origin).netloc != self.headers.get("Host")
                           or urlsplit(origin).scheme not in ("https","http")):
                return self._json(403,{"status":"CROSS_ORIGIN_FORBIDDEN"},sid,fresh)
            if not self.headers.get("Content-Type","").startswith("application/json"):
                return self._json(415,{"status":"JSON_REQUIRED"},sid,fresh)
            try:
                length = int(self.headers.get("Content-Length","-1"))
                if not 2 <= length <= 150:
                    return self._json(413,{"status":"REGISTER_PAYLOAD_TOO_LARGE"},sid,fresh)
                body = json.loads(self.rfile.read(length))
                if not isinstance(body,dict) or set(body)!={"acknowledge_mpl"} or type(body["acknowledge_mpl"]) is not bool:
                    return self._json(400,{"status":"EXPLICIT_LICENSE_ACK_REQUIRED"},sid,fresh)
                result = published.register_for_existing_wf02(
                    sid,acknowledge_mpl=body["acknowledge_mpl"])
                return self._json(200,result,sid,fresh)
            except (ValueError, TypeError) as exc:
                return self._json(422,{"status":"WF02_SOURCE_REGISTRATION_BLOCKED",
                                       "reason":str(exc)[:200]},sid,fresh)
            except OSError as exc:
                return self._json(503,{"status":"WF02_SOURCE_STORAGE_UNAVAILABLE",
                                       "reason":type(exc).__name__},sid,fresh)
        if urlsplit(self.path).path == "/api/investment/tv-publication/import":
            sid, fresh = self._sid()
            origin = self.headers.get("Origin")
            if origin and (urlsplit(origin).netloc != self.headers.get("Host")
                           or urlsplit(origin).scheme not in ("https", "http")):
                return self._json(403, {"status":"CROSS_ORIGIN_FORBIDDEN"},sid,fresh)
            if not self.headers.get("Content-Type","").startswith("application/json"):
                return self._json(415, {"status":"JSON_REQUIRED"},sid,fresh)
            try:
                size = int(self.headers.get("Content-Length","-1"))
                if not 2 <= size <= 380_000:
                    return self._json(413, {"status":"PUBLICATION_HTML_TOO_LARGE"},sid,fresh)
                body = json.loads(self.rfile.read(size))
                if not isinstance(body,dict) or not isinstance(body.get("html"),str):
                    return self._json(400,{"status":"PUBLICATION_HTML_REQUIRED"},sid,fresh)
                result = published.parse_publication_html(body["html"])
                published.save_reference(sid,result)
                return self._json(200,result,sid,fresh)
            except (ValueError,TypeError) as exc:
                return self._json(422, {"status":"TRADINGVIEW_PUBLICATION_PARSE_FAILED",
                                        "reason":str(exc)[:200]},sid,fresh)
            except OSError as exc:
                return self._json(503, {"status":"PUBLISHED_REFERENCE_STORAGE_FAILED",
                                        "reason":type(exc).__name__},sid,fresh)
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
