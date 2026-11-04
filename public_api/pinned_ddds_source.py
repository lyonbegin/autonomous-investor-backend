"""Immutable DDDS source already captured from the author's PUBLIC publication.

Used ONLY for the DDDS source ID when the catalog SQLite/TradingView collector
is unavailable. Never substitute for a different script, and never skip the
SHA-256 + 141-line check. Original licence: MPL-2.0, author: blitz_locked.
"""
from __future__ import annotations

import base64
import gzip
import hashlib
from functools import lru_cache
from pathlib import Path

DDDS_ID = "PUB;5442675d418140c58486eb4a7ae12768"
DDDS_SHA256 = "5a245e99447f13012dd026528235fc2c299cad5cb7b228653c684886dcba6507"
DDDS_PUBLICATION_URL = (
    "https://www.tradingview.com/script/"
    "LkgKT3TG-Displaced-Donchian-Decycler-Trend-Breakout-Strategy-with-MFI/"
)


@lru_cache(maxsize=1)
def verified_ddds_source() -> str:
    fixture = Path(__file__).resolve().parent / "fixtures" / "ddds_published_source.gz.b64"
    source = gzip.decompress(base64.b64decode(fixture.read_text(encoding="ascii").strip(), validate=True))
    decoded = source.decode("utf-8")
    if hashlib.sha256(source).hexdigest() != DDDS_SHA256 or len(decoded.splitlines()) != 141:
        raise ValueError("DDDS_IMMUTABLE_SOURCE_MISMATCH")
    return decoded


def pinned_ddds_source_response() -> dict:
    original = verified_ddds_source()
    return {
        "ok": True,
        "from_cache": True,
        "script_id_part": DDDS_ID,
        "version": "last",
        "script_name": "Displaced Donchian Decycler | Trend Breakout Strategy with MFI",
        "kind": "strategy",
        "pine_version": 6,
        "source_hash": DDDS_SHA256,
        "source": original,
        "source_chars": len(original),
        "source_line_count": 141,
        "license": "MPL-2.0",
        "author": "blitz_locked",
        "source_provenance": "PINNED_USER_SUPPLIED_PUBLICATION_DOM_SHA256_VERIFIED",
        "publication_url": DDDS_PUBLICATION_URL,
        "official_tradingview_chart_parity_verified": False,
    }


def pinned_ddds_meta_response() -> dict:
    # Metadata comes only from the already archived public author's DDDS
    # publication; it is NOT an independently live chart quote.
    verified_ddds_source()
    return {
        "script_id_part": DDDS_ID,
        "script_id": DDDS_ID,
        "name": "Displaced Donchian Decycler | Trend Breakout Strategy with MFI",
        "author": "blitz_locked",
        "script_type": "strategy",
        "script_access": "open",
        "version": "last",
        "symbol": "BATS:AMZN",
        "interval": "120",
        "chart_url": DDDS_PUBLICATION_URL,
        "source_hash": DDDS_SHA256,
        "source_provenance": "PINNED_USER_SUPPLIED_PUBLICATION_DOM_SHA256_VERIFIED",
        "chart_is_historical_publisher_snapshot": True,
    }
