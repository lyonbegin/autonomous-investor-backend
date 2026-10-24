from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    ROOT / "core" / "tradingview.py",
    ROOT / "core" / "corporate_bonds.py",
    ROOT / "core" / "market_history.py",
    ROOT / "core" / "macro_data.py",
    ROOT / "core" / "toss_market.py",
]
FORBIDDEN = [
    re.compile(r"request\.urlopen\s*\("),
    re.compile(r"requests\.(?:get|post|put|patch|delete|request)\s*\("),
    re.compile(r"httpx\.(?:get|post|put|patch|delete|request)\s*\("),
]
ALLOWED_FILES = {"browser_http.py"}

violations: list[str] = []
checked: list[str] = []

for path in TARGETS:
    if not path.exists():
        continue
    checked.append(str(path.relative_to(ROOT.parent)))
    text = path.read_text(encoding="utf-8")
    for pattern in FORBIDDEN:
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            violations.append(f"{path.name}:{line}: {match.group(0).strip()}")

if violations:
    print("External data egress audit FAILED")
    for item in violations:
        print(" -", item)
    sys.exit(1)

print("External data egress audit OK")
for item in checked:
    print(" -", item)
print("All audited market/macro/source HTTP must flow through app.core.browser_http.")
