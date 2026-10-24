from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"

ALLOWED = {
    "app/core/browser_http.py",   # the only external-data egress client
    "app/core/internal_http.py",  # Railway service-to-service client
}

PATTERNS = [
    re.compile(r"\brequest\.urlopen\s*\("),
    re.compile(r"\burllib\.request\.urlopen\s*\("),
    re.compile(r"\brequests\.(?:get|post|put|patch|delete|request)\s*\("),
    re.compile(r"\bhttpx\.(?:get|post|put|patch|delete|request)\s*\("),
    re.compile(r"\baiohttp\.ClientSession\s*\("),
]

violations: list[str] = []
if APP.exists():
    for file in sorted(APP.rglob("*.py")):
        rel = file.relative_to(ROOT).as_posix()
        if rel in ALLOWED:
            continue
        text = file.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for pattern in PATTERNS:
                if pattern.search(line):
                    violations.append(f"{rel}:{lineno}: {line.strip()}")
                    break

if violations:
    print("EXTERNAL_EGRESS_AUDIT_FAILED")
    print("\n".join(violations))
    print("External provider access must go through app/core/browser_http.py.")
    sys.exit(1)

print("EXTERNAL_EGRESS_AUDIT_OK")
