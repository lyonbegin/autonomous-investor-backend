"""Private JSON-line worker. Executes only the repository's bounded native demos."""
from __future__ import annotations

import json
import resource
import sys


PREFIX = "@investor-engine:"


def emit(value: dict) -> None:
    print(PREFIX + json.dumps(value, ensure_ascii=False, allow_nan=False), flush=True)


def main() -> None:
    resource.setrlimit(resource.RLIMIT_AS, (12 * 1024**3, 12 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (180, 185))
    from app.core.integrations import SPECS, probe

    key = sys.argv[1]
    spec = next(row for row in SPECS if row.key == key)
    result = probe(spec)
    result.pop("module_file", None)
    emit({"type": "ready", "probe": result})
    if not result["import_ok"]:
        return
    for line in sys.stdin:
        command = json.loads(line)
        if command.get("action") == "shutdown":
            return
        if command.get("action") != "demo":
            emit({"type": "result", "request_id": command.get("request_id"), "ok": False,
                  "error": {"type": "InvalidAction", "message": "only the existing bounded native demo is supported"}})
            continue
        try:
            from app.api.demo_routes import DEMOS
            output = DEMOS[key]()
            emit({"type": "result", "request_id": command["request_id"],
                  "ok": bool(output.get("ok")), "result": output})
        except Exception as exc:
            emit({"type": "result", "request_id": command["request_id"], "ok": False,
                  "error": {"type": type(exc).__name__, "message": str(exc)[:500]}})


if __name__ == "__main__":
    main()
