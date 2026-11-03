"""Parse user-supplied TradingView script publication DOM into a typed WF02 reference.

This does NOT execute scraped HTML, assume the publication is a live strategy
runner, or mark any PyneCore/Pine compilation validated.
"""
from __future__ import annotations
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from bs4 import BeautifulSoup

MAX_HTML_BYTES = 280_000
MAX_SOURCE_BYTES = 120_000
_REFERENCE_DIR = Path("/data/tv_publication_references")

def _compact(text: str) -> str:
    return " ".join(text.split())

def parse_publication_html(html: str) -> dict:
    if not isinstance(html, str) or not 200 <= len(html.encode("utf-8")) <= MAX_HTML_BYTES:
        raise ValueError("PUBLICATION_HTML_SIZE_INVALID")
    soup = BeautifulSoup(html, "html.parser")
    # CSS class hashes are unstable: prefer semantic title, chart and report
    # selectors, and allow a known Monaco source view as fallback.
    published_chart = soup.select_one('[data-name="publication-view-chart-container"]')
    strategy_legend = (published_chart.select_one('[data-qa-id="legend-source-item"]')
                       if published_chart else None)
    report = soup.select_one('[data-qa-id="backtesting-static"]')
    source_container = (soup.select_one(".monaco-editor-tv-pine-light") or
                        soup.select_one(".pineViewer-riih8Fd5 .code-YN1MHq8F"))
    if not published_chart or not strategy_legend or not report or not source_container:
        raise ValueError("TRADINGVIEW_PUBLISHED_STRATEGY_CHART_REPORT_SOURCE_NOT_FOUND")

    for br in list(source_container.find_all("br")):
        br.replace_with("\n")
    pine = source_container.get_text("", strip=False).replace("\xa0", " ").replace("\u202f", " ")
    if (len(pine.encode("utf-8")) > MAX_SOURCE_BYTES or
        not re.search(r"(?m)^\s*//@version=[456]\b", pine) or
        not re.search(r'(?m)^\s*strategy\s*\(', pine) or
        not re.search(r"strategy\.(entry|order)\s*\(", pine)):
        raise ValueError("PUBLISHED_SOURCE_NOT_VALID_PINE_STRATEGY")
    declaration = re.search(r'(?m)^\s*strategy\s*\(\s*"([^"]{1,160})"', pine)
    if not declaration:
        raise ValueError("PUBLISHED_STRATEGY_TITLE_MISSING")
    title = declaration.group(1)
    source_link = soup.select_one('a[href^="/pine/"]')
    source_id = ""
    if source_link:
        match = re.search(r"PUB;([a-zA-Z0-9]{8,80})", source_link.get("href", ""))
        source_id = "PUB;" + match.group(1) if match else ""
    preview = soup.select_one('img[src*="s3.tradingview.com/"]')
    image = ""
    chart_id = ""
    if preview:
        candidate = preview.get("src", "")
        u = urlparse(candidate)
        if u.scheme == "https" and u.hostname == "s3.tradingview.com":
            image = candidate
            match = re.search(r"/([A-Za-z0-9]{8})_(?:mid|big|small)\.", u.path)
            chart_id = match.group(1) if match else ""
    if not image or not chart_id:
        raise ValueError("PUBLICATION_CHART_PREVIEW_MISSING")

    interval = published_chart.select_one('[data-qa-id*="legend-source-interval"]')
    symbol = published_chart.select_one('[data-qa-id*="legend-source-title"]')
    author_match = re.search(r"(?m)^\s*//\s*©\s*([^\n]+)", pine)
    rights_match = re.search(r"(Mozilla Public License 2\.0|MPL[- ]2\.0)", pine, re.I)
    facts = []
    for cell in report.select('[data-qa-id="strategy-key-facts"] .containerCell-dJrHEJrZ'):
        value = _compact(cell.get_text(" ", strip=True))
        if value:
            facts.append(value)
    tabs = [
        {"id": tab.get("id", ""), "title": _compact(tab.get_text(" ", strip=True)),
         "selected_in_snapshot": tab.get("aria-selected") == "true"}
        for tab in report.select('[role="tab"]')
        if tab.get("id") in {"Overview", "Performance", "Trades Analysis",
                             "Ratios", "List of Trades", "Properties"}
    ]
    evidence = {
        "status": "TRADINGVIEW_PUBLISHED_STRATEGY_REFERENCE_PARSED",
        "evidence_kind": "USER_SUPPLIED_TRADINGVIEW_PUBLICATION_DOM",
        "strategy_title": title,
        "source_id": source_id,
        "source_line_count": len(pine.splitlines()),
        "source_sha256": hashlib.sha256(pine.encode("utf-8")).hexdigest(),
        "source_rights": "MPL-2.0" if rights_match else "UNDETERMINED",
        "source_author": author_match.group(1).strip() if author_match else "",
        "chart_id": chart_id,
        "chart_preview_url": image,
        "chart_symbol_title": _compact(symbol.get_text(" ", strip=True)) if symbol else "",
        "chart_timeframe_display": _compact(interval.get_text(" ", strip=True)) if interval else "",
        "strategy_legend_present": True,
        "published_strategy_report_present": True,
        "report_title": (report.select_one("[data-strategy-title]").get("data-strategy-title", "")
                         if report.select_one("[data-strategy-title]") else ""),
        "report_key_facts": facts,
        "report_tabs": tabs,
        "report_trade_rows_extracted": False,
        "pine_source": pine,
        "pinecomp_compiled": False,
        "python_execution_complete": False,
        "tradingview_pynecore_strategy_parity_verified": False,
        "strategy_orders_extracted": False,
        "provenance_note": "Supplied HTML from TradingView publication, not a live Strategy Tester export",
        "imported_at": datetime.now(timezone.utc).isoformat(),
    }
    if not facts or not source_id or len(tabs) < 3:
        raise ValueError("PUBLISHED_STRATEGY_REFERENCE_INCOMPLETE")
    return evidence

def _path(root: Path, sid: str) -> Path:
    # SID comes from the existing studio session and is never a pathname.
    return root / (hashlib.sha256(sid.encode("utf-8")).hexdigest() + ".json")

def save_reference(sid: str, evidence: dict, root: Path = _REFERENCE_DIR) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    dest = _path(root, sid)
    import os
    import tempfile
    fd, tmp = tempfile.mkstemp(prefix=".tvref-", suffix=".tmp", dir=str(root))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(evidence, handle, ensure_ascii=False, allow_nan=False)
        os.replace(tmp, dest)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return {"status": evidence["status"], "source_sha256": evidence["source_sha256"]}

def latest_reference(sid: str, root: Path = _REFERENCE_DIR) -> dict:
    dest = _path(root, sid)
    if not dest.is_file():
        return {"status": "NO_PUBLISHED_STRATEGY_REFERENCE"}
    return json.loads(dest.read_text(encoding="utf-8"))
