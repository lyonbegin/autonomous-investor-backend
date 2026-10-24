"""Execute ONLY inventoried engine bridge callables.

JSON nodes can pass native Python objects to the next node using $handle.
Handles and background jobs are process-local: use one pinned worker for this
prototype. Do not use this state store as a distributed production queue.
"""
from __future__ import annotations

import asyncio
import dataclasses
import importlib
import inspect
import math
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.alpha_nodes.inventory import OPERATION_MAP

_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="alpha-node")
_LOCK = threading.RLock()
_HANDLES: dict[str, tuple[Any, float]] = {}
_JOBS: dict[str, dict[str, Any]] = {}
_TTL = 3600
_MAX_HANDLES = 1024
_MAX_JOBS = 256

TRADE_METHODS = {"market_order", "submit_order", "submit_market_intent"}


class ExecuteRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)
    positional: list[Any] = Field(default_factory=list)
    init_arguments: dict[str, Any] = Field(default_factory=dict)
    instance_handle: str | None = None
    background: bool = False


def _evict() -> None:
    now = time.monotonic()
    expired = [key for key, (_, expires) in _HANDLES.items() if expires < now]
    for key in expired:
        _HANDLES.pop(key, None)
    if len(_HANDLES) >= _MAX_HANDLES:
        oldest = next(iter(_HANDLES))
        _HANDLES.pop(oldest, None)


def save_handle(obj: Any) -> str:
    token = uuid.uuid4().hex
    with _LOCK:
        _evict()
        _HANDLES[token] = (obj, time.monotonic() + _TTL)
    return token


def load_handle(token: str) -> Any:
    with _LOCK:
        _evict()
        record = _HANDLES.get(token)
    if record is None:
        raise ValueError("unknown or expired Python object handle")
    return record[0]


def handle_info(token: str) -> dict[str, Any]:
    obj = load_handle(token)
    return {"handle": token, "type": f"{type(obj).__module__}.{type(obj).__qualname__}",
            "expires_in_seconds": _TTL, "distributed": False}


def _convert_input(value: Any) -> Any:
    if isinstance(value, dict):
        if "$handle" in value:
            if len(value) != 1 or not isinstance(value["$handle"], str):
                raise ValueError("$handle input must be an object with only a string $handle")
            return load_handle(value["$handle"])
        if "$dataframe" in value:
            if len(value) != 1:
                raise ValueError("$dataframe input contains unexpected fields")
            import pandas as pd
            return pd.DataFrame(value["$dataframe"])
        if "$series" in value:
            if len(value) != 1:
                raise ValueError("$series input contains unexpected fields")
            import pandas as pd
            return pd.Series(value["$series"])
        return {str(k): _convert_input(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_convert_input(x) for x in value]
    return value


def _coerce_contracts(arguments: dict[str, Any]) -> dict[str, Any]:
    contracts = ("TargetPortfolio", "OrderIntent", "ResearchBundle", "Hypothesis",
                 "ModelScore", "Forecast", "PolicyAction", "Signal", "RiskDecision",
                 "ExecutionReport", "ExperimentResult")
    from app.core import contracts as schemas
    for key, value in list(arguments.items()):
        if not isinstance(value, dict):
            continue
        for model in contracts:
            if value.get("$contract") == model:
                payload = {k: v for k, v in value.items() if k != "$contract"}
                arguments[key] = getattr(schemas, model).model_validate(payload)
                break
    return arguments


def _output(value: Any, *, depth: int = 0) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if depth >= 8:
        return {"truncated": True, "reason": "maximum JSON depth"}
    if isinstance(value, BaseModel):
        return _output(value.model_dump(mode="json"), depth=depth + 1)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _output(dataclasses.asdict(value), depth=depth + 1)
    if isinstance(value, dict):
        entries = list(value.items())
        return {"items": {str(k): _output(v, depth=depth + 1) for k, v in entries[:500]},
                "total": len(entries)} if len(entries) > 500 else {
                    str(k): _output(v, depth=depth + 1) for k, v in entries
                }
    if isinstance(value, (tuple, list)):
        return {"items": [_output(x, depth=depth + 1) for x in value[:500]], "total": len(value)} if len(value) > 500 else [
            _output(x, depth=depth + 1) for x in value
        ]
    module = type(value).__module__
    if module.startswith("numpy") and hasattr(value, "tolist"):
        data = value.tolist()
        return _output(data, depth=depth + 1) if getattr(value, "size", 0) < 5000 else _object_ref(value)
    if module.startswith("pandas"):
        if hasattr(value, "to_dict"):
            if len(value) <= 300:
                return {"rows": _output(value.to_dict(orient="records") if hasattr(value, "columns") else value.to_dict()),
                        "type": module}
        return _object_ref(value)
    return _object_ref(value)


def _object_ref(obj: Any) -> dict[str, Any]:
    return {"$handle": save_handle(obj),
            "python_type": f"{type(obj).__module__}.{type(obj).__qualname__}",
            "note": "pass {$handle: <id>} to the next bridge node"}


def _validate_gate(op: dict) -> None:
    method = op["function"]
    if (op["engine"] == "nautilus" and method in TRADE_METHODS) or (
        op["engine"] == "orchestration" and op["module"] == "pipeline" and method == "submit"
    ):
        raise HTTPException(status_code=403, detail="native order submission is disabled in Alpha node API; use a separately authorized Nautilus risk/order gateway")
    if op["source"] == "service" and op["engine"] == "quantlab" and method in ("quant_experiment_create", "quant_experiment_run"):
        if os.getenv("ALPHA_ALLOW_QUANT_WRITES", "false").lower() != "true":
            raise HTTPException(status_code=403, detail="Quant Lab experiment mutation disabled; require ALPHA_ALLOW_QUANT_WRITES=true")
    if op["engine"] == "orchestration" and op["module"] == "pipeline" and method == "run" and op.get("class_name") in ("ResearchCoordinator", "RDAgentCoordinator"):
        if os.getenv("ALPHA_ALLOW_RESEARCH", "false").lower() != "true":
            raise HTTPException(status_code=403, detail="orchestration research requires ALPHA_ALLOW_RESEARCH=true")
    if op["guard"] == "RESEARCH_APPROVAL" and os.getenv("ALPHA_ALLOW_RESEARCH", "false").lower() != "true":
        raise HTTPException(status_code=403, detail="research execution disabled: set ALPHA_ALLOW_RESEARCH after reviewing sandbox/costs")
    if op["guard"] == "TRAINING_APPROVAL" and os.getenv("ALPHA_ALLOW_TRAINING", "false").lower() != "true":
        raise HTTPException(status_code=403, detail="training execution disabled: set ALPHA_ALLOW_TRAINING after reviewing resource limits")
    if op["engine"] in ("tradingagents", "finrobot") and op["function"] not in ("create", "close") and (
        os.getenv("ALPHA_ALLOW_RESEARCH", "false").lower() != "true"
    ):
        raise HTTPException(status_code=403, detail="LLM research disabled by default to prevent unintended model cost")


def _invoke(operation_id: str, call: ExecuteRequest) -> dict:
    op = OPERATION_MAP[operation_id]
    _validate_gate(op)
    module = importlib.import_module(op["python_module"])
    cls = getattr(module, op["class_name"]) if op["class_name"] else None
    args = [_convert_input(x) for x in call.positional]
    kwargs = _coerce_contracts({k: _convert_input(v) for k, v in call.arguments.items()})
    init_args = {k: _convert_input(v) for k, v in call.init_arguments.items()}
    obj: Any = None
    started = time.monotonic()

    if op["call_kind"] == "constructor":
        if cls is None:
            raise ValueError("invalid constructor target")
        if call.instance_handle:
            raise ValueError("constructor cannot accept instance_handle")
        result = cls(*args, **kwargs)
        return {"operation_id": operation_id, "status": "completed",
                "result": _object_ref(result),
                "duration_ms": round((time.monotonic() - started) * 1000, 2)}

    if op["call_kind"] in ("instance", "property"):
        if call.instance_handle:
            obj = load_handle(call.instance_handle)
            if not isinstance(obj, cls):
                raise ValueError("instance handle is not an instance of the expected bridge")
        else:
            obj = cls(**init_args)
        fn = getattr(obj, op["function"])
        if op["call_kind"] == "property":
            if args or kwargs:
                raise ValueError("property getters accept no arguments")
            result = fn
        else:
            result = fn(*args, **kwargs)
    elif op["call_kind"] in ("static", "class"):
        result = getattr(cls, op["function"])(*args, **kwargs)
    elif op["call_kind"] == "function":
        result = getattr(module, op["function"])(*args, **kwargs)
    else:
        raise ValueError("unrecognized callable type")
    if inspect.isawaitable(result):
        result = asyncio.run(result)
    result_json = _output(result)
    response: dict[str, Any] = {
        "operation_id": operation_id, "status": "completed",
        "result": result_json,
        "duration_ms": round((time.monotonic() - started) * 1000, 2),
    }
    if obj is not None and call.instance_handle is None:
        response["instance"] = _object_ref(obj)
    return response


def _error(exc: BaseException) -> dict:
    return {"type": type(exc).__name__, "message": str(exc)[:1200]}


def submit_invocation(operation_id: str, call: ExecuteRequest) -> dict:
    op = OPERATION_MAP.get(operation_id)
    if not op:
        raise HTTPException(status_code=404, detail="unknown node function")
    _validate_gate(op)
    if not call.background:
        try:
            return _invoke(operation_id, call)
        except HTTPException:
            raise
        except (ValueError, TypeError, KeyError) as exc:
            raise HTTPException(status_code=422, detail=_error(exc)) from exc
        except (ImportError, ModuleNotFoundError) as exc:
            raise HTTPException(status_code=424, detail=_error(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=_error(exc)) from exc

    job_id = uuid.uuid4().hex
    with _LOCK:
        if len(_JOBS) >= _MAX_JOBS:
            for key in list(_JOBS):
                if _JOBS[key]["status"] in ("completed", "failed"):
                    _JOBS.pop(key)
                    break
        if len(_JOBS) >= _MAX_JOBS:
            raise HTTPException(status_code=429, detail="background job capacity exhausted")
        _JOBS[job_id] = {"job_id": job_id, "operation_id": operation_id,
                         "status": "queued", "created_at": datetime.now().isoformat()}

    def job_worker():
        with _LOCK:
            _JOBS[job_id]["status"] = "running"
        try:
            payload = _invoke(operation_id, call)
            with _LOCK:
                _JOBS[job_id].update(payload)
        except BaseException as exc:
            with _LOCK:
                _JOBS[job_id].update({"status": "failed", "error": _error(exc)})
    _EXECUTOR.submit(job_worker)
    return {"job_id": job_id, "operation_id": operation_id,
            "status": "queued", "poll": f"/api/v1/alpha/jobs/{job_id}"}


def get_job(job_id: str) -> dict:
    with _LOCK:
        value = _JOBS.get(job_id)
        if value is None:
            raise HTTPException(status_code=404, detail="unknown or expired job id")
        return dict(value)
