"""Google TPU WF04 execution worker.

Deploy this on a GOOGLE CLOUD TPU VM with 'jax[tpu]' and Storage read access.
The Railway controller sends only a validated PLAN + SHA and a gs://*.npz
dataset. It never sends free-form LLM code for execution.

POST /execute with Authorization: Bearer <WF04_TPU_WORKER_TOKEN>
{
 "plan":{...}, "jax_tpu_code_sha256":"...", "dataset_uri":"gs://bucket/data.npz",
 "top_k":100, "min_signal_density":0.02, "lookback":100
}

NPZ contains 'ohlcv': [symbols,time,5], dtype float32 and 'symbols': [symbols].
Actual TPU backend is required and the worker fails closed otherwise.
"""
from __future__ import annotations

import io
import json
import os
import re
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlsplit

import numpy as np

from investment_wf04_one_ai_tpu import emit_code, sha

GCS_URI=re.compile(r"^gs://([A-Za-z0-9._-]+)/([A-Za-z0-9_./=-]+\.npz)$")


def read_gcs_npz(uri):
    match=GCS_URI.fullmatch(uri) if isinstance(uri,str) else None
    if not match or ".." in match[2]:
        raise ValueError("WF04_ONLY_GCS_NPZ_DATASETS_ALLOWED")
    allow=os.environ.get("WF04_TPU_ALLOWED_GCS_BUCKET")
    if not allow or match[1]!=allow:
        raise ValueError("WF04_DATASET_BUCKET_NOT_ALLOWLISTED")
    from google.cloud import storage
    blob=storage.Client().bucket(match[1]).blob(match[2])
    if blob.size is None:blob.reload()
    if blob.size is None or blob.size>900_000_000:
        raise ValueError("WF04_DATASET_SIZE_EXCEEDS_LIMIT")
    payload=blob.download_as_bytes()
    with np.load(io.BytesIO(payload),allow_pickle=False) as data:
        x=np.asarray(data["ohlcv"],dtype=np.float32)
        symbols=[str(s) for s in data["symbols"].tolist()]
    if (x.ndim!=3 or x.shape[2]!=5 or x.shape[0]!=len(symbols)
        or x.shape[0]<1 or x.shape[0]>100_000 or x.shape[1]<10 or x.shape[1]>20_000
        or not np.isfinite(x).all()):
        raise ValueError("WF04_INVALID_OHLCV_MATRIX")
    if any(not sym or len(sym)>60 for sym in symbols):
        raise ValueError("WF04_INVALID_SYMBOLS")
    return x,symbols


def run_batched(plan,ohlcv,symbols,*,code_sha,top_k=100,min_signal_density=0.02,
                lookback=100,batch_size=256,require_tpu=True):
    import jax
    from investment_wf04_one_ai_tpu import validate_plan
    # Validate structural safety and all operation types. This is *not* Pine
    # equivalence verification; the manifest still declares screening proxy.
    validate_plan(plan,
      "\n".join(str(k.get("source_evidence","")) for k in plan.get("indicators",[])),
      "")
    if type(top_k) is not int or not 1<=top_k<=2000:
        raise ValueError("WF04_TOP_K_INVALID")
    if type(lookback) is not int or not 10<=lookback<=2000:
        raise ValueError("WF04_LOOKBACK_INVALID")
    if type(batch_size) is not int or not 8<=batch_size<=1024:
        raise ValueError("WF04_BATCH_SIZE_INVALID")
    if (not isinstance(min_signal_density,(int,float)) or
        not 0.0<=min_signal_density<=1.0):
        raise ValueError("WF04_SIGNAL_DENSITY_INVALID")
    if ohlcv.ndim!=3 or ohlcv.shape[2]!=5 or ohlcv.shape[0]!=len(symbols):
        raise ValueError("WF04_OHLCV_SYMBOL_MATRIX_MISMATCH")
    if ohlcv.shape[1]<max([lookback]+[i["period"] for i in plan["indicators"]])+2:
        raise ValueError("WF04_INSUFFICIENT_BARS_FOR_LOOKBACK")
    devices=jax.devices()
    if require_tpu and (not devices or any(d.platform!="tpu" for d in devices)):
        raise RuntimeError("WF04_GOOGLE_TPU_DEVICE_NOT_PRESENT_DO_NOT_CLAIM_TPU")
    code=emit_code(plan,"jax_tpu")
    if sha(code)!=code_sha:
        raise ValueError("WF04_GENERATED_JAX_PROGRAM_SHA_MISMATCH")
    # Only our deterministic compiler generated this audited source from
    # strongly allowlisted IDs, ops and predicates. It is NOT raw AI Python.
    compiled=compile(code,"wf04_generated_allowlisted_jax.py","exec")
    namespace={}
    exec(compiled,namespace)
    run=namespace["run"]
    matches=[]
    started=time.perf_counter()
    for first in range(0,len(symbols),batch_size):
        last=min(len(symbols),first+batch_size)
        subset=np.asarray(ohlcv[first:last],dtype=np.float32)
        if subset.shape[0]<batch_size:
            subset=np.concatenate([subset,np.zeros((
                batch_size-subset.shape[0],subset.shape[1],5),dtype=np.float32)],axis=0)
        computed=run(jax.device_put(subset))
        # JAX is async; this synchronizes the device before time measurement.
        signal=np.asarray(jax.device_get(computed["signal"]))[:last-first]
        visible=signal[:,-lookback:]
        density=visible.mean(axis=1)
        for j,(score,last_signal) in enumerate(zip(density,signal[:,-1])):
            if float(score)>=min_signal_density:
                matches.append({"symbol":symbols[first+j],
                  "signal_density":round(float(score),6),
                  "latest_signal":bool(last_signal)})
    matches.sort(key=lambda x:(-x["signal_density"],not x["latest_signal"],x["symbol"]))
    return {"status":"TPU_SCREENING_PROXY_COMPLETED" if require_tpu else "CPU_JAX_PROOF_ONLY",
        "backend":devices[0].platform,"symbols_evaluated":len(symbols),
        "bars_per_symbol":ohlcv.shape[1],"selection_criteria":"INDICATOR_CONDITION_DENSITY_NOT_BACKTEST",
        "matches_count":len(matches),"top_matches":matches[:top_k],
        "elapsed_ms":round((time.perf_counter()-started)*1000,2),
        "plan_sha256":sha(plan),"jax_tpu_code_sha256":code_sha,
        "tradingview_strategy_parity_verified":False,
        "no_live_trading":True}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path!="/execute":
            return self.reply(404,{"error":"NOT_FOUND"})
        token=os.environ.get("WF04_TPU_WORKER_TOKEN")
        import hmac
        if not token or not hmac.compare_digest(
            self.headers.get("Authorization",""),"Bearer "+token):
            return self.reply(403,{"error":"WORKER_AUTH_FAILED"})
        try:
            count=int(self.headers.get("Content-Length","0"))
            if count<10 or count>100_000:
                raise ValueError("WF04_JOB_BODY_SIZE_INVALID")
            data=json.loads(self.rfile.read(count))
            if not isinstance(data,dict) or set(data)!={
                "plan","jax_tpu_code_sha256","dataset_uri",
                "top_k","min_signal_density","lookback"}:
                raise ValueError("WF04_JOB_STRUCTURE_INVALID")
            x,symbols=read_gcs_npz(data["dataset_uri"])
            result=run_batched(data["plan"],x,symbols,
                code_sha=data["jax_tpu_code_sha256"],
                top_k=data["top_k"],
                min_signal_density=data["min_signal_density"],
                lookback=data["lookback"],require_tpu=True)
            return self.reply(200,result)
        except (ValueError,RuntimeError,KeyError,TypeError) as exc:
            return self.reply(422,{"error":str(exc)[:240]})
        except Exception as exc:
            return self.reply(503,{"error":type(exc).__name__+"_WORKER_FAILED"})
    def reply(self,status,obj):
        raw=json.dumps(obj,ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(raw)))
        self.send_header("Cache-Control","no-store")
        self.end_headers()
        self.wfile.write(raw)


if __name__=="__main__":
    port=int(os.environ.get("PORT","8094"))
    print("WF04_GOOGLE_TPU_WORKER_LISTEN",port,flush=True)
    HTTPServer(("0.0.0.0",port),Handler).serve_forever()
