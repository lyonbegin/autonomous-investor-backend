from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from typing import Any
from urllib import parse, request
from urllib.error import HTTPError
import xml.etree.ElementTree as ET

from app.core.browser_http import browser_json, browser_text

DB_PATH = os.getenv("QUANT_DB_PATH", "/tmp/quant_lab.sqlite3")
BLS_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
TREASURY_XML_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
)

BLS_SERIES = {
    "CUSR0000SA0": {
        "name": "미국 CPI-U 계절조정",
        "unit": "index",
        "frequency": "monthly",
    },
    "LNS14000000": {
        "name": "미국 실업률",
        "unit": "percent",
        "frequency": "monthly",
    },
    "CES0000000001": {
        "name": "미국 비농업고용",
        "unit": "thousand_persons",
        "frequency": "monthly",
    },
}

TREASURY_SERIES = {
    "BC_2YEAR": {"name": "미국 국채 2년", "unit": "percent", "frequency": "daily"},
    "BC_10YEAR": {"name": "미국 국채 10년", "unit": "percent", "frequency": "daily"},
    "BC_30YEAR": {"name": "미국 국채 30년", "unit": "percent", "frequency": "daily"},
}

ATOM_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata",
    "d": "http://schemas.microsoft.com/ado/2007/08/dataservices",
}


def utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_macro_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS macro_observations (
                source TEXT NOT NULL,
                series_id TEXT NOT NULL,
                series_name TEXT NOT NULL,
                observation_date TEXT NOT NULL,
                value REAL NOT NULL,
                unit TEXT NOT NULL,
                frequency TEXT NOT NULL,
                raw_json TEXT,
                collected_at TEXT NOT NULL,
                PRIMARY KEY (source, series_id, observation_date)
            );

            CREATE INDEX IF NOT EXISTS idx_macro_series_date
                ON macro_observations(series_id, observation_date DESC);

            CREATE TABLE IF NOT EXISTS macro_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                snapshot_date TEXT NOT NULL,
                data_json TEXT NOT NULL,
                source_dates_json TEXT NOT NULL,
                collected_at TEXT NOT NULL
            );
            """
        )


def _post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        raw = browser_json(
            url,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "AUTONOMOUS-INVESTOR-Macro/2.0",
            },
            payload=payload,
            timeout=40,
        )
        if not isinstance(raw, dict):
            raise RuntimeError(f"Macro JSON source returned {type(raw).__name__}")
        return raw
    except Exception as exc:
        raise RuntimeError(f"Macro JSON source failed via Chromium gateway: {type(exc).__name__}: {exc}") from exc


def _get_text(url: str, accept: str) -> str:
    try:
        return browser_text(
            url,
            method="GET",
            headers={
                "Accept": accept,
                "User-Agent": "Mozilla/5.0 AUTONOMOUS-INVESTOR-Macro/2.0",
            },
            timeout=40,
        )
    except Exception as exc:
        raise RuntimeError(f"Macro text source failed via Chromium gateway: {type(exc).__name__}: {exc}") from exc

def _bls_period_to_date(year: str, period: str) -> str | None:
    if not period.startswith("M"):
        return None
    try:
        month = int(period[1:])
        if not 1 <= month <= 12:
            return None
        return f"{int(year):04d}-{month:02d}-01"
    except (TypeError, ValueError):
        return None


def collect_bls(years_back: int = 2) -> dict[str, Any]:
    init_macro_db()
    now_year = datetime.now(UTC).year
    start_year = max(1900, now_year - max(1, years_back))
    raw = _post_json(
        BLS_URL,
        {
            "seriesid": list(BLS_SERIES.keys()),
            "startyear": str(start_year),
            "endyear": str(now_year),
        },
    )
    if raw.get("status") != "REQUEST_SUCCEEDED":
        raise RuntimeError(f"BLS request failed: {raw.get('message')}")

    collected_at = utcnow()
    stored = 0
    with _connect() as conn:
        for series in ((raw.get("Results") or {}).get("series") or []):
            series_id = str(series.get("seriesID") or "")
            meta = BLS_SERIES.get(series_id)
            if not meta:
                continue
            for item in series.get("data") or []:
                observation_date = _bls_period_to_date(
                    str(item.get("year") or ""),
                    str(item.get("period") or ""),
                )
                if not observation_date:
                    continue
                value_raw = str(item.get("value") or "").strip()
                try:
                    value = float(value_raw)
                except ValueError:
                    continue
                conn.execute(
                    """
                    INSERT INTO macro_observations (
                        source,series_id,series_name,observation_date,value,unit,frequency,raw_json,collected_at
                    ) VALUES (?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(source,series_id,observation_date) DO UPDATE SET
                        value=excluded.value,
                        raw_json=excluded.raw_json,
                        collected_at=excluded.collected_at
                    """,
                    (
                        "BLS",
                        series_id,
                        meta["name"],
                        observation_date,
                        value,
                        meta["unit"],
                        meta["frequency"],
                        json.dumps(item, ensure_ascii=False),
                        collected_at,
                    ),
                )
                stored += 1

    return {
        "source": "BLS Public Data API",
        "series": list(BLS_SERIES.keys()),
        "stored": stored,
        "collected_at": collected_at,
    }


def collect_treasury(year: int | None = None) -> dict[str, Any]:
    init_macro_db()
    target_year = year or datetime.now(UTC).year
    query = parse.urlencode(
        {
            "data": "daily_treasury_yield_curve",
            "field_tdr_date_value": str(target_year),
        }
    )
    xml_text = _get_text(f"{TREASURY_XML_URL}?{query}", "application/xml,text/xml,*/*")
    root = ET.fromstring(xml_text)
    collected_at = utcnow()
    stored = 0

    with _connect() as conn:
        for entry in root.findall("atom:entry", ATOM_NS):
            props = entry.find("atom:content/m:properties", ATOM_NS)
            if props is None:
                continue
            date_node = props.find("d:NEW_DATE", ATOM_NS)
            if date_node is None or not date_node.text:
                continue
            observation_date = date_node.text[:10]
            for series_id, meta in TREASURY_SERIES.items():
                node = props.find(f"d:{series_id}", ATOM_NS)
                if node is None or not node.text:
                    continue
                try:
                    value = float(node.text)
                except ValueError:
                    continue
                conn.execute(
                    """
                    INSERT INTO macro_observations (
                        source,series_id,series_name,observation_date,value,unit,frequency,raw_json,collected_at
                    ) VALUES (?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(source,series_id,observation_date) DO UPDATE SET
                        value=excluded.value,
                        collected_at=excluded.collected_at
                    """,
                    (
                        "US_TREASURY",
                        series_id,
                        meta["name"],
                        observation_date,
                        value,
                        meta["unit"],
                        meta["frequency"],
                        None,
                        collected_at,
                    ),
                )
                stored += 1

    return {
        "source": "U.S. Treasury Daily Treasury Par Yield Curve Rates",
        "year": target_year,
        "stored": stored,
        "collected_at": collected_at,
    }


def _series_rows(series_id: str, limit: int = 24) -> list[dict[str, Any]]:
    init_macro_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT source,series_id,series_name,observation_date,value,unit,frequency,collected_at
            FROM macro_observations
            WHERE series_id = ?
            ORDER BY observation_date DESC
            LIMIT ?
            """,
            (series_id, min(max(limit, 1), 5000)),
        ).fetchall()
    return [dict(row) for row in rows]


def macro_series(series_id: str, limit: int = 120) -> dict[str, Any]:
    rows = _series_rows(series_id, limit)
    return {"series_id": series_id, "count": len(rows), "items": rows}


def _latest(series_id: str) -> dict[str, Any] | None:
    rows = _series_rows(series_id, 1)
    return rows[0] if rows else None


def _latest_and_previous(series_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    rows = _series_rows(series_id, 2)
    return (rows[0] if rows else None, rows[1] if len(rows) > 1 else None)


def _cpi_yoy() -> dict[str, Any] | None:
    rows = _series_rows("CUSR0000SA0", 18)
    if len(rows) < 13:
        return None
    latest = rows[0]
    latest_date = latest["observation_date"]
    year = int(latest_date[:4]) - 1
    month = latest_date[5:7]
    target = f"{year:04d}-{month}-01"
    prior = next((x for x in rows if x["observation_date"] == target), None)
    if prior is None or not prior["value"]:
        return None
    yoy = (float(latest["value"]) / float(prior["value"]) - 1.0) * 100.0
    return {
        "value": round(yoy, 4),
        "unit": "percent",
        "latest_date": latest_date,
        "comparison_date": prior["observation_date"],
    }


def _make_snapshot_payload() -> tuple[dict[str, Any], dict[str, str]]:
    cpi = _latest("CUSR0000SA0")
    unemployment = _latest("LNS14000000")
    payroll, payroll_prev = _latest_and_previous("CES0000000001")
    y2 = _latest("BC_2YEAR")
    y10 = _latest("BC_10YEAR")
    y30 = _latest("BC_30YEAR")
    cpi_yoy = _cpi_yoy()

    payroll_change = None
    if payroll and payroll_prev:
        payroll_change = float(payroll["value"]) - float(payroll_prev["value"])

    curve_10y_2y = None
    if y2 and y10:
        curve_10y_2y = float(y10["value"]) - float(y2["value"])

    data = {
        "cpi_index": float(cpi["value"]) if cpi else None,
        "cpi_yoy": cpi_yoy["value"] if cpi_yoy else None,
        "unemployment_rate": float(unemployment["value"]) if unemployment else None,
        "nonfarm_payroll_thousands": float(payroll["value"]) if payroll else None,
        "nonfarm_payroll_mom_change_thousands": payroll_change,
        "treasury_2y": float(y2["value"]) if y2 else None,
        "treasury_10y": float(y10["value"]) if y10 else None,
        "treasury_30y": float(y30["value"]) if y30 else None,
        "yield_curve_10y_2y": round(curve_10y_2y, 4) if curve_10y_2y is not None else None,
    }
    source_dates = {
        "cpi": cpi["observation_date"] if cpi else "",
        "unemployment": unemployment["observation_date"] if unemployment else "",
        "payroll": payroll["observation_date"] if payroll else "",
        "treasury_2y": y2["observation_date"] if y2 else "",
        "treasury_10y": y10["observation_date"] if y10 else "",
        "treasury_30y": y30["observation_date"] if y30 else "",
    }
    return data, source_dates


def build_macro_snapshot() -> dict[str, Any]:
    init_macro_db()
    data, source_dates = _make_snapshot_payload()
    if not any(value is not None for value in data.values()):
        return {
            "ready": False,
            "reason": "No macro observations have been collected yet.",
            "data": data,
            "source_dates": source_dates,
        }

    collected_at = utcnow()
    snapshot_date = datetime.now(UTC).date().isoformat()
    snapshot_id = f"MACRO-{snapshot_date}"
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO macro_snapshots (
                snapshot_id,snapshot_date,data_json,source_dates_json,collected_at
            ) VALUES (?,?,?,?,?)
            ON CONFLICT(snapshot_id) DO UPDATE SET
                data_json=excluded.data_json,
                source_dates_json=excluded.source_dates_json,
                collected_at=excluded.collected_at
            """,
            (
                snapshot_id,
                snapshot_date,
                json.dumps(data, ensure_ascii=False),
                json.dumps(source_dates, ensure_ascii=False),
                collected_at,
            ),
        )
    return {
        "ready": True,
        "snapshot_id": snapshot_id,
        "snapshot_date": snapshot_date,
        "data": data,
        "source_dates": source_dates,
        "collected_at": collected_at,
        "sources": ["BLS", "U.S. Treasury"],
    }


def refresh_macro() -> dict[str, Any]:
    bls = collect_bls(years_back=2)
    treasury = collect_treasury()
    snapshot = build_macro_snapshot()
    return {
        "status": "ok",
        "bls": bls,
        "treasury": treasury,
        "snapshot": snapshot,
    }


def latest_macro_snapshot() -> dict[str, Any]:
    init_macro_db()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT snapshot_id,snapshot_date,data_json,source_dates_json,collected_at
            FROM macro_snapshots
            ORDER BY collected_at DESC
            LIMIT 1
            """
        ).fetchone()
    if row is None:
        return build_macro_snapshot()
    return {
        "ready": True,
        "snapshot_id": row["snapshot_id"],
        "snapshot_date": row["snapshot_date"],
        "data": json.loads(row["data_json"]),
        "source_dates": json.loads(row["source_dates_json"]),
        "collected_at": row["collected_at"],
        "sources": ["BLS", "U.S. Treasury"],
    }


def macro_ready() -> bool:
    snapshot = latest_macro_snapshot()
    data = snapshot.get("data") or {}
    required = (
        "cpi_yoy",
        "unemployment_rate",
        "treasury_2y",
        "treasury_10y",
        "yield_curve_10y_2y",
    )
    return bool(snapshot.get("ready") and all(data.get(key) is not None for key in required))
