"""Enumerate every existing Python bridge function without importing heavy engines.

Source of truth: 12 app/integrations wrappers, their 12 lab/bridges
counterparts, and existing orchestration functions/classes. The native
libraries themselves are not flattened into thousands of unsupported methods.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ENGINES = (
    "tradingagents", "finrobot", "rdagent", "qlib", "chronos", "sb3",
    "rllib", "vectorbt", "finrl", "riskfolio", "pypfopt", "nautilus",
)
ORCHESTRATION = ("research", "rdagent", "quant", "allocation", "runtime", "pipeline")
SIDE_EFFECTS = {
    ("nautilus", "market_order"): "TRADE_BLOCKED",
    ("nautilus", "submit_order"): "TRADE_BLOCKED",
    ("nautilus", "submit_market_intent"): "TRADE_BLOCKED",
    ("rdagent", "run"): "RESEARCH_APPROVAL",
    ("sb3", "learn"): "TRAINING_APPROVAL",
    ("rllib", "train"): "TRAINING_APPROVAL",
    ("rllib", "build"): "TRAINING_APPROVAL",
}


def _ast_default(value: ast.expr | None) -> Any:
    if value is None:
        return None
    try:
        return ast.literal_eval(value)
    except (ValueError, TypeError, SyntaxError, RecursionError):
        return ast.unparse(value)


def _parameters(fn: ast.FunctionDef | ast.AsyncFunctionDef, *, instance: bool) -> list[dict]:
    args = fn.args
    pos = list(args.posonlyargs) + list(args.args)
    default_start = len(pos) - len(args.defaults)
    result: list[dict] = []
    for i, a in enumerate(pos):
        if i == 0 and instance and a.arg in ("self", "cls"):
            continue
        optional = i >= default_start
        result.append({
            "name": a.arg,
            "kind": "positional",
            "required": not optional,
            "annotation": ast.unparse(a.annotation) if a.annotation else "Any",
            "default": _ast_default(args.defaults[i - default_start]) if optional else None,
        })
    for i, a in enumerate(args.kwonlyargs):
        value = args.kw_defaults[i]
        result.append({
            "name": a.arg, "kind": "keyword_only",
            "required": value is None,
            "annotation": ast.unparse(a.annotation) if a.annotation else "Any",
            "default": _ast_default(value),
        })
    if args.vararg:
        result.append({"name": args.vararg.arg, "kind": "varargs", "required": False, "annotation": "Any", "default": None})
    if args.kwarg:
        result.append({"name": args.kwarg.arg, "kind": "kwargs", "required": False, "annotation": "Any", "default": None})
    return result


def _decorators(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    return {ast.unparse(x) for x in fn.decorator_list}


def _scan_module(path: Path, *, project: str, source: str, module: str) -> list[dict]:
    if not path.is_file():
        return []
    parsed = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    operations: list[dict] = []
    def add(fn: ast.FunctionDef | ast.AsyncFunctionDef, *, cls: str | None = None):
        dec = _decorators(fn)
        if fn.name.startswith("_") and fn.name != "__init__":
            return
        if fn.name == "__init__":
            kind = "constructor"
        elif "property" in dec:
            kind = "property"
        elif "staticmethod" in dec:
            kind = "static"
        elif "classmethod" in dec:
            kind = "class"
        elif cls:
            kind = "instance"
        else:
            kind = "function"
        name = "create" if kind == "constructor" else fn.name
        operation_name = f"{cls.lower()}-{name}" if source == "orchestration" and cls else name
        operation_id = f"{project}.{source}.{module}.{operation_name}"
        blocked = (
            SIDE_EFFECTS.get((project, fn.name), "NONE")
            if source in ("app", "lab") else "NONE"
        )
        operations.append({
            "id": operation_id,
            "engine": project,
            "source": source,
            "module": module,
            "class_name": cls,
            "function": fn.name,
            "call_kind": kind,
            "is_async": isinstance(fn, ast.AsyncFunctionDef),
            "inputs": _parameters(fn, instance=bool(cls)),
            "output": ast.unparse(fn.returns) if fn.returns else "Any",
            "python_module": path.relative_to(ROOT).with_suffix("").as_posix().replace("/", "."),
            "source_path": str(path.relative_to(ROOT)),
            "source_line": fn.lineno,
            "guard": blocked,
            "endpoint": f"/api/v1/alpha/modules/{project}/{source}/{module}/{operation_name}/execute",
        })
    for item in parsed.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and source == "orchestration":
            add(item)
        elif isinstance(item, ast.ClassDef):
            for member in item.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    add(member, cls=item.name)
    return operations


def build_inventory() -> list[dict]:
    result: list[dict] = []
    for engine in ENGINES:
        for source, path in (
            ("app", ROOT / "app" / "integrations" / f"{engine}.py"),
            ("lab", ROOT / "lab" / "bridges" / f"{engine}_bridge.py"),
        ):
            result.extend(_scan_module(path, project=engine, source=source, module="bridge"))
    for name in ORCHESTRATION:
        result.extend(_scan_module(ROOT / "app" / "orchestration" / f"{name}.py",
                                   project="orchestration", source="orchestration", module=name))
    result.sort(key=lambda x: (x["engine"], x["source"], x["module"], x["source_line"]))
    ids = [item["id"] for item in result]
    if len(set(ids)) != len(ids):
        raise RuntimeError("duplicate bridge operation id")
    return result


OPERATIONS = build_inventory()
OPERATION_MAP = {item["id"]: item for item in OPERATIONS}


def module_inventory() -> list[dict]:
    groups: dict[tuple[str, str, str], list[dict]] = {}
    for op in OPERATIONS:
        groups.setdefault((op["engine"], op["source"], op["module"]), []).append(op)
    return [
        {"engine": engine, "source": source, "module": module,
         "function_count": len(items),
         "functions": [{"id": op["id"], "name": op["id"].rsplit(".", 1)[-1],
                        "endpoint": op["endpoint"], "inputs": op["inputs"],
                        "output": op["output"], "guard": op["guard"],
                        "call_kind": op["call_kind"]} for op in items]}
        for (engine, source, module), items in sorted(groups.items())
    ]
