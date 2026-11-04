"""Extend the original shared studio HTTP server without forking its workflow editor.

The only new entrypoints are bounded read-only WF-02 chart test endpoints.
Original saved workflows and SQLite session history remain managed upstream.
"""
import json
import threading
import urllib.error
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs

import studio_server as studio
import investment_tv_chart_integration as chart_integration
import investment_tv_publication as published
import investment_tv_trade_reference as official_trades
import investment_ddds_parity as ddds_parity
import investment_free_pyne as free_pyne
import investment_free_pyne_chart as free_ddds_chart
import investment_shared_bars_compare as shared_compare
import investment_verified_catalog as verified_catalog

# The public React chart is the ONLY permitted cross-origin caller.
# During cutover accept the previous public chart only for backwards compatibility.
# After its shutdown, the only maintained browser UI is the same-origin admin.
PUBLIC_CHART_ORIGIN="https://autonomous-investor-public-production.up.railway.app"
ADMIN_CHART_ORIGIN="https://investment-n8n-native-editor-production.up.railway.app"
CHART_ORIGINS={PUBLIC_CHART_ORIGIN,ADMIN_CHART_ORIGIN}
SHARED_COMPARE_ROUTE="/api/investment/free-pyne/ddds/chart/compare-input"
_SHARED_COMPARE_LOCK=threading.Lock()


class InvestmentHandler(studio.Handler):
    def send_header(self, keyword, value):
        # The original shared studio deliberately blocks framing everywhere.
        # Allow ONLY the migrated original React scripts UI to be embedded by
        # its same-origin /admin/console. Never weaken protection on admin,
        # workflow editor, API routes, or another host.
        if (keyword.lower()=="x-frame-options" and value=="DENY" and
            urlsplit(self.path).path.startswith("/verified/")):
            value="SAMEORIGIN"
        return super().send_header(keyword,value)

    def end_headers(self):
        if (urlsplit(self.path).path==SHARED_COMPARE_ROUTE and
            self.headers.get("Origin") in CHART_ORIGINS):
            self.send_header("Access-Control-Allow-Origin",self.headers.get("Origin"))
            self.send_header("Access-Control-Allow-Methods","POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers","Content-Type")
            self.send_header("Vary","Origin")
        return super().end_headers()

    def do_OPTIONS(self):
        if urlsplit(self.path).path != SHARED_COMPARE_ROUTE:
            return self.send_error(404)
        if self.headers.get("Origin") not in CHART_ORIGINS:
            return self.send_error(403)
        self.send_response(204)
        self.send_header("Content-Length","0")
        self.end_headers()

    def do_GET(self):
        current=urlsplit(self.path)
        if current.path == "/api/investment/verified-scripts/catalog":
            sid,fresh=self._sid()
            q=parse_qs(current.query)
            try:
                limit=int((q.get("limit") or ["50"])[0])
                offset=int((q.get("offset") or ["0"])[0])
                query=(q.get("q") or [""])[0]
                script_type=(q.get("type") or ["all"])[0]
                return self._json(200,verified_catalog.catalog(
                    limit=limit,offset=offset,query=query,
                    script_type=script_type),sid,fresh)
            except (ValueError,TypeError) as exc:
                return self._json(400,{"status":"VERIFIED_CATALOG_INVALID_QUERY",
                    "reason":str(exc)[:200]},sid,fresh)
            except OSError as exc:
                return self._json(503,{"status":"VERIFIED_CATALOG_DB_UNAVAILABLE",
                    "reason":type(exc).__name__},sid,fresh)
        if current.path == "/api/investment/verified-scripts/candidates":
            sid,fresh=self._sid()
            try:
                return self._json(200,verified_catalog.candidates(),sid,fresh)
            except (ValueError,TypeError,OSError) as exc:
                return self._json(503,{"status":"VERIFIED_CANDIDATES_UNAVAILABLE",
                  "reason":type(exc).__name__+": "+str(exc)[:180]},sid,fresh)
        if current.path == "/api/investment/free-pyne/ddds/chart/latest":
            sid, fresh=self._sid()
            try:
                return self._json(200,free_ddds_chart.latest(sid),sid,fresh)
            except OSError as exc:
                return self._json(503,{"status":"FREE_DDDS_CHART_STORAGE_UNAVAILABLE",
                   "reason":type(exc).__name__},sid,fresh)
        if urlsplit(self.path).path in ("/api/investment/free-pyne/ddds/latest",
                                         "/api/investment/free-pyne/ddds/python"):
            sid, fresh = self._sid()
            with_source=(urlsplit(self.path).path.endswith("/python"))
            try:
                return self._json(200, free_pyne.ddds_artifact(sid,include_code=with_source),sid,fresh)
            except (ValueError,TypeError) as exc:
                return self._json(422,{"status":"PYNE_FREE_ARTIFACT_REJECTED",
                    "reason":str(exc)[:160],"parity_verified":False,
                    "live_orders_enabled":False},sid,fresh)
            except OSError as exc:
                return self._json(503,{"status":"PYNE_FREE_ARTIFACT_STORAGE_UNAVAILABLE",
                    "reason":type(exc).__name__,"parity_verified":False,
                    "live_orders_enabled":False},sid,fresh)
        if urlsplit(self.path).path == "/api/investment/tv-publication/parity/readiness":
            sid, fresh = self._sid()
            try:
                report = ddds_parity.readiness_for_studio_session(sid)
                return self._json(200, report, sid, fresh)
            except (ValueError,TypeError) as exc:
                return self._json(422, {
                    "status":"DDDS_PARITY_READINESS_INVALID",
                    "reason":str(exc)[:200],
                    "tradingview_pynecore_parity_verified":False,
                    "paper_enabled":False,"live_orders_enabled":False
                },sid,fresh)
            except OSError as exc:
                return self._json(503, {
                    "status":"DDDS_PARITY_READINESS_STORAGE_UNAVAILABLE",
                    "reason":type(exc).__name__,
                    "tradingview_pynecore_parity_verified":False,
                    "paper_enabled":False,"live_orders_enabled":False
                },sid,fresh)
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
        if urlsplit(self.path).path == "/api/investment/verified-scripts/publish":
            sid,fresh=self._sid()
            origin=self.headers.get("Origin","")
            if origin!=ADMIN_CHART_ORIGIN or urlsplit(origin).netloc!=self.headers.get("Host"):
                return self._json(403,{"status":"VERIFIED_PUBLICATION_SAME_ORIGIN_REQUIRED"},sid,fresh)
            if not self.headers.get("Content-Type","").startswith("application/json"):
                return self._json(415,{"status":"JSON_REQUIRED"},sid,fresh)
            try:
                length=int(self.headers.get("Content-Length","-1"))
                if not 10<=length<=1500:raise ValueError("PUBLICATION_BODY_SIZE_INVALID")
                body=json.loads(self.rfile.read(length))
                if not isinstance(body,dict) or set(body)!={
                   "source_id","version_key","pine_sha256"}:
                    raise ValueError("EXACT_SELECTED_PINE_ID_VERSION_SHA_REQUIRED")
                result=verified_catalog.select_and_publish(
                   body["source_id"],body["version_key"],body["pine_sha256"])
                return self._json(200,result,sid,fresh)
            except (ValueError,TypeError) as exc:
                return self._json(422,{"status":"PUBLISH_ONLY_ACTUALLY_VERIFIED_SOURCE",
                     "reason":str(exc)[:210]},sid,fresh)
            except OSError as exc:
                return self._json(503,{"status":"VERIFIED_PUBLICATION_STORAGE_FAILED",
                     "reason":type(exc).__name__},sid,fresh)
        if urlsplit(self.path).path == SHARED_COMPARE_ROUTE:
            sid,fresh=self._sid()
            if self.headers.get("Origin") not in CHART_ORIGINS:
                return self._json(403,{"status":"APPROVED_CHART_ORIGIN_REQUIRED"},sid,fresh)
            if not self.headers.get("Content-Type","").startswith("application/json"):
                return self._json(415,{"status":"JSON_REQUIRED"},sid,fresh)
            try:
                length=int(self.headers.get("Content-Length","-1"))
                if not 1000<=length<=220_000:
                    return self._json(413,{"status":"SHARED_BARS_PAYLOAD_SIZE_INVALID"},sid,fresh)
                body=json.loads(self.rfile.read(length))
            except (ValueError,TypeError):
                return self._json(400,{"status":"INVALID_SHARED_CHART_JSON"},sid,fresh)
            if not _SHARED_COMPARE_LOCK.acquire(blocking=False):
                return self._json(429,{"status":"DDDS_COMPARISON_ALREADY_RUNNING"},sid,fresh)
            try:
                result=shared_compare.execute_shared_bars(body)
                return self._json(200,result,sid,fresh)
            except (ValueError,TypeError) as exc:
                return self._json(422,{"status":"DDDS_SHARED_CHART_COMPARISON_BLOCKED",
                   "reason":str(exc)[:220],"paper_enabled":False,
                   "live_orders_enabled":False},sid,fresh)
            except (RuntimeError,OSError) as exc:
                return self._json(502,{"status":"DDDS_SHARED_CHART_PYTHON_FAILED",
                   "reason":type(exc).__name__,"paper_enabled":False,
                   "live_orders_enabled":False},sid,fresh)
            finally:
                _SHARED_COMPARE_LOCK.release()
        if urlsplit(self.path).path == "/api/investment/free-pyne/ddds/chart/execute":
            sid,fresh=self._sid()
            origin=self.headers.get("Origin")
            if origin and (urlsplit(origin).netloc != self.headers.get("Host")
                          or urlsplit(origin).scheme not in ("https","http")):
                return self._json(403,{"status":"CROSS_ORIGIN_FORBIDDEN"},sid,fresh)
            if not self.headers.get("Content-Type","").startswith("application/json"):
                return self._json(415,{"status":"JSON_REQUIRED"},sid,fresh)
            try:
                size=int(self.headers.get("Content-Length","-1"))
                if size!=2 or self.rfile.read(size)!=b"{}":
                    return self._json(400,{"status":"EXACT_DDDS_PUBLIC_CHART_ONLY"},sid,fresh)
                return self._json(200,free_ddds_chart.execute(sid),sid,fresh)
            except (ValueError,TypeError) as exc:
                return self._json(422,{"status":"FREE_DDDS_RUNTIME_NOT_READY",
                    "reason":str(exc)[:220],
                    "tradingview_parity_verified":False},sid,fresh)
            except urllib.error.HTTPError as exc:
                return self._json(502,{"status":"DDDS_CHART_SOURCE_UPSTREAM_HTTP",
                    "upstream_status":exc.code,
                    "tradingview_parity_verified":False},sid,fresh)
            except (urllib.error.URLError,TimeoutError,OSError,RuntimeError) as exc:
                return self._json(502,{"status":"DDDS_CHART_SOURCE_OR_RUNNER_FAILED",
                    "reason":type(exc).__name__,
                    "tradingview_parity_verified":False},sid,fresh)
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
    verified_catalog.initialize()
    # Diagnostic only: does not automatically publish or copy any strategy.
    try:
        from investment_pipeline import saved_sources
        entries=saved_sources(limit=120)["sources"]
        matches=[x for x in entries if x["source_id"]==verified_catalog.DDDS_ID]
        detail=(verified_catalog.candidate_check(matches[0]) if matches else {})
        print("VERIFIED_CATALOG_DDDS_ELIGIBILITY",json.dumps({
            "saved_ddds_versions":len(matches),
            "ddds_pine_rights":detail.get("rights_state"),
            "ddds_converted":detail.get("free_pyne_generated_stored"),
            "publish_ready":detail.get("publish_ready",False),
            "reason":detail.get("reason","NOT_IN_SOURCE_STORE")},ensure_ascii=False),flush=True)
    except Exception as exc:
        print("VERIFIED_CATALOG_BOOT_DIAGNOSTIC_ONLY_FAILED",type(exc).__name__,flush=True)
    print("Investment studio with original workflow canvas and official chart-to-PyneCore WF02 verification", flush=True)
    ThreadingHTTPServer(("0.0.0.0", studio.PORT), InvestmentHandler).serve_forever()
