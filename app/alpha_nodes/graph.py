"""AlphaForge workflow runner for EXISTING twelve-engine callable endpoints.

Run a validated DAG of native wrapper calls; bind an earlier node result into a
later node's arguments with {"$node": "node-id", "path": "result.foo"}.
Never bypass the native function gates and never submit orders through here.
SQLite stores run metadata and JSON results; Python object handles are local to
one process and expire or vanish after restart.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.alpha_nodes.inventory import OPERATION_MAP
from app.alpha_nodes.runtime import ExecuteRequest, _invoke, _validate_gate

_MAX_NODES = 40
_MAX_RUNNING = 4
_WORKERS = ThreadPoolExecutor(max_workers=2, thread_name_prefix="alpha-graph")
_INIT_LOCK = threading.RLock()
_INITIALIZED: set[str] = set()
_REDACT = ("token", "password", "secret", "authorization", "api_key", "private_key", "credential")


class GraphNodeSpec(BaseModel):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z][a-zA-Z0-9_-]*$")
    operation_id: str = Field(min_length=3, max_length=200)
    arguments: dict[str, Any] = Field(default_factory=dict)
    positional: list[Any] = Field(default_factory=list)
    init_arguments: dict[str, Any] = Field(default_factory=dict)
    instance_handle: str | dict[str, Any] | None = None
    depends_on: list[str] = Field(default_factory=list, max_length=_MAX_NODES)


class GraphSpec(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    nodes: list[GraphNodeSpec] = Field(min_length=1, max_length=_MAX_NODES)
    background: bool = True


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _conn() -> sqlite3.Connection:
    db = str(Path(os.environ.get("ALPHA_GRAPH_DB_PATH", "/tmp/autonomous_alpha_graph.sqlite3")).resolve())
    Path(db).parent.mkdir(parents=True, exist_ok=True)
    with _INIT_LOCK:
        first = db not in _INITIALIZED
        conn = sqlite3.connect(db, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS graph_runs (
                run_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                graph_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                error_json TEXT
            );
            CREATE TABLE IF NOT EXISTS graph_node_runs (
                run_id TEXT NOT NULL,
                node_id TEXT NOT NULL,
                operation_id TEXT NOT NULL,
                status TEXT NOT NULL,
                input_json TEXT,
                output_json TEXT,
                error_json TEXT,
                started_at TEXT,
                ended_at TEXT,
                PRIMARY KEY(run_id, node_id)
            );
            """
        )
        if first:
            # A prior interpreter's in-flight work cannot be resumed safely,
            # especially if its native Python object handles have expired.
            conn.execute("UPDATE graph_runs SET status='interrupted', updated_at=? "
                         "WHERE status IN ('queued','running')", (_now(),))
            conn.execute("UPDATE graph_node_runs SET status='interrupted', ended_at=? "
                         "WHERE status='running'", (_now(),))
            _INITIALIZED.add(db)
        conn.commit()
    return conn


def _refs(value: Any) -> list[str]:
    if isinstance(value, dict):
        if "$node" in value:
            if set(value) - {"$node", "path"}:
                raise ValueError("$node reference allows only $node and path")
            if not isinstance(value["$node"], str):
                raise ValueError("$node reference id must be string")
            if value.get("path") is not None and not isinstance(value["path"], str):
                raise ValueError("$node path must be string")
            return [value["$node"]]
        found: list[str] = []
        for v in value.values():
            found.extend(_refs(v))
        return found
    if isinstance(value, list):
        found: list[str] = []
        for v in value:
            found.extend(_refs(v))
        return found
    return []


def compile_graph(graph: GraphSpec) -> dict:
    ids = [n.id for n in graph.nodes]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate graph node id")
    known = set(ids)
    indexed = {node.id: node for node in graph.nodes}
    dependencies: dict[str, set[str]] = {}
    edges: set[tuple[str, str]] = set()
    blocked: list[dict] = []

    for node in graph.nodes:
        op = OPERATION_MAP.get(node.operation_id)
        if op is None:
            raise ValueError(f"unknown native operation: {node.operation_id}")
        all_refs = (
            _refs(node.arguments) + _refs(node.positional)
            + _refs(node.init_arguments) + _refs(node.instance_handle)
        )
        deps = set(node.depends_on) | set(all_refs)
        missing = deps - known
        if missing:
            raise ValueError(f"{node.id}: dependencies missing: {sorted(missing)}")
        if node.id in deps:
            raise ValueError(f"{node.id}: self-dependency is invalid")
        dependencies[node.id] = deps
        for parent in deps:
            edges.add((parent, node.id))
        try:
            _validate_gate(op)
        except HTTPException as exc:
            blocked.append({"node_id": node.id, "operation_id": node.operation_id,
                            "http_status": exc.status_code, "reason": str(exc.detail)})

    indeg = {nid: len(deps) for nid, deps in dependencies.items()}
    children: dict[str, list[str]] = {nid: [] for nid in ids}
    for parent, child in edges:
        children[parent].append(child)
    ready = [nid for nid in ids if indeg[nid] == 0]
    ordered: list[str] = []
    while ready:
        nid = ready.pop(0)
        ordered.append(nid)
        for child in children[nid]:
            indeg[child] -= 1
            if indeg[child] == 0:
                ready.append(child)
    if len(ordered) != len(ids):
        raise ValueError("cycle detected in graph dependencies")
    return {
        "valid": True, "name": graph.name, "node_count": len(graph.nodes),
        "order": ordered, "edges": [{"source": x, "target": y} for x, y in sorted(edges)],
        "nodes": [{"id": n.id, "operation_id": n.operation_id,
                   "depends_on": sorted(dependencies[n.id]),
                   "input_names": sorted(n.arguments)} for n in graph.nodes],
        "blocked": blocked, "runnable": not blocked,
    }


def _resolve(value: Any, results: dict[str, dict]) -> Any:
    if isinstance(value, dict):
        if "$node" in value:
            nid = value["$node"]
            if nid not in results:
                raise ValueError(f"node {nid} output is not ready")
            path = value.get("path") or "result"
            cursor: Any = results[nid]
            for field in path.split("."):
                if isinstance(cursor, dict):
                    if field not in cursor:
                        raise ValueError(f"node {nid}: missing output path: {path}")
                    cursor = cursor[field]
                elif isinstance(cursor, list) and field.isdecimal():
                    i = int(field)
                    if i >= len(cursor):
                        raise ValueError(f"node {nid}: index out of range: {path}")
                    cursor = cursor[i]
                else:
                    raise ValueError(f"node {nid}: invalid output path: {path}")
            if isinstance(cursor, dict) and "$handle" in cursor:
                return {"$handle": cursor["$handle"]}
            return cursor
        return {k: _resolve(v, results) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve(x, results) for x in value]
    return value


def _scrub(value: Any, depth: int = 0) -> Any:
    if depth > 6:
        return "[MAX_DEPTH]"
    if isinstance(value, dict):
        return {
            k: "[REDACTED]" if any(part in str(k).lower() for part in _REDACT)
            else _scrub(v, depth + 1)
            for k, v in list(value.items())[:100]
        }
    if isinstance(value, list):
        return [_scrub(v, depth + 1) for v in value[:100]]
    if isinstance(value, str) and len(value) > 1200:
        return value[:1200] + "...[TRUNCATED]"
    return value


def _encoded(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))


def _update_run(run_id: str, status: str, error: dict | None = None) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE graph_runs SET status=?, updated_at=?, error_json=? WHERE run_id=?",
            (status, _now(), _encoded(error) if error else None, run_id),
        )


def _update_node(run_id: str, node_id: str, *, status: str,
                 inputs: Any = None, output: Any = None, error: dict | None = None) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE graph_node_runs SET status=?, input_json=COALESCE(?,input_json), "
            "output_json=COALESCE(?,output_json), error_json=?, "
            "started_at=COALESCE(started_at,?), ended_at=? "
            "WHERE run_id=? AND node_id=?",
            (
                status, _encoded(_scrub(inputs)) if inputs is not None else None,
                _encoded(output) if output is not None else None,
                _encoded(error) if error else None,
                _now(), _now() if status in ("completed", "failed", "skipped") else None,
                run_id, node_id,
            ),
        )


def _run(run_id: str, graph: GraphSpec, plan: dict) -> None:
    nodes = {node.id: node for node in graph.nodes}
    outcomes: dict[str, dict] = {}
    ordered = plan["order"]
    _update_run(run_id, "running")
    try:
        for i, nid in enumerate(ordered):
            node = nodes[nid]
            inputs = {
                "arguments": _resolve(node.arguments, outcomes),
                "positional": _resolve(node.positional, outcomes),
                "init_arguments": _resolve(node.init_arguments, outcomes),
                "instance_handle": _resolve(node.instance_handle, outcomes),
            }
            _update_node(run_id, nid, status="running", inputs=inputs)
            try:
                handle = inputs["instance_handle"]
                if isinstance(handle, dict) and "$handle" in handle:
                    handle = handle["$handle"]
                call = ExecuteRequest(
                    arguments=inputs["arguments"], positional=inputs["positional"],
                    init_arguments=inputs["init_arguments"], instance_handle=handle,
                    background=False,
                )
                # Always enter the same native bridge invocation and safety gates
                # as the individual module execution endpoints.
                out = _invoke(node.operation_id, call)
                outcomes[nid] = out
                _update_node(run_id, nid, status="completed", output=out)
            except Exception as exc:
                error = {
                    "type": type(exc).__name__, "message": str(exc)[:1200],
                    "node_id": nid, "operation_id": node.operation_id,
                }
                _update_node(run_id, nid, status="failed", error=error)
                for remaining in ordered[i+1:]:
                    _update_node(run_id, remaining, status="skipped",
                                 error={"reason": "upstream node failed", "upstream": nid})
                _update_run(run_id, "failed", error=error)
                return
        _update_run(run_id, "completed")
    except Exception as exc:
        _update_run(run_id, "failed", {
            "type": type(exc).__name__, "message": str(exc)[:1200],
        })


def create_graph_run(graph: GraphSpec) -> dict:
    try:
        plan = compile_graph(graph)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if plan["blocked"]:
        raise HTTPException(status_code=403, detail={"blocked": plan["blocked"]})
    graph_data = graph.model_dump(mode="json")
    graph_hash = hashlib.sha256(_encoded(graph_data).encode("utf-8")).hexdigest()
    run_id = uuid.uuid4().hex
    with _conn() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM graph_runs WHERE status IN ('queued','running')"
        ).fetchone()[0]
        if count >= _MAX_RUNNING:
            raise HTTPException(status_code=429, detail="too many running graphs")
        now = _now()
        conn.execute(
            "INSERT INTO graph_runs(run_id,name,status,graph_hash,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?)",
            (run_id, graph.name, "queued", graph_hash, now, now),
        )
        conn.executemany(
            "INSERT INTO graph_node_runs(run_id,node_id,operation_id,status)"
            " VALUES (?,?,?,'waiting')",
            [(run_id, node.id, node.operation_id) for node in graph.nodes],
        )
    if graph.background:
        _WORKERS.submit(_run, run_id, graph, plan)
        return {"run_id": run_id, "status": "queued",
                "node_count": len(graph.nodes),
                "poll": f"/api/v1/alpha/graphs/runs/{run_id}"}
    _run(run_id, graph, plan)
    return get_graph_run(run_id)


def get_graph_run(run_id: str) -> dict:
    with _conn() as conn:
        run = conn.execute("SELECT * FROM graph_runs WHERE run_id=?", (run_id,)).fetchone()
        if run is None:
            raise HTTPException(status_code=404, detail="unknown graph run")
        nodes = conn.execute(
            "SELECT * FROM graph_node_runs WHERE run_id=? ORDER BY rowid", (run_id,)
        ).fetchall()
    def read(value: str | None) -> Any:
        return json.loads(value) if value else None
    return {
        "run_id": run["run_id"], "name": run["name"], "status": run["status"],
        "graph_hash": run["graph_hash"], "created_at": run["created_at"],
        "updated_at": run["updated_at"], "error": read(run["error_json"]),
        "nodes": [
            {
                "id": node["node_id"], "operation_id": node["operation_id"],
                "status": node["status"], "inputs": read(node["input_json"]),
                "output": read(node["output_json"]), "error": read(node["error_json"]),
                "started_at": node["started_at"], "ended_at": node["ended_at"],
            }
            for node in nodes
        ],
    }


def get_graph_node(run_id: str, node_id: str) -> dict:
    run = get_graph_run(run_id)
    for node in run["nodes"]:
        if node["id"] == node_id:
            return {"run_id": run_id, **node}
    raise HTTPException(status_code=404, detail="node not found in graph run")


def list_graph_runs(limit: int = 30) -> dict:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT run_id,name,status,graph_hash,created_at,updated_at "
            "FROM graph_runs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return {"count": len(rows), "runs": [dict(x) for x in rows]}
