from __future__ import annotations

import importlib
import importlib.metadata
import json
import sys
from pathlib import Path

name = sys.argv[1]
module_name = sys.argv[2]
symbols = sys.argv[3:]

result = {
    "name": name,
    "module": module_name,
    "python": sys.version,
    "ok": False,
    "version": None,
    "module_file": None,
    "symbols": {},
}

try:
    module = importlib.import_module(module_name)
    result["ok"] = True
    result["module_file"] = str(Path(getattr(module, "__file__", "") or "").resolve())
    result["version"] = getattr(module, "__version__", None)
    for symbol in symbols:
        result["symbols"][symbol] = hasattr(module, symbol)
except Exception as exc:
    result["error"] = f"{type(exc).__name__}: {exc}"

print("PROBE_RESULT=" + json.dumps(result, ensure_ascii=False, sort_keys=True))
