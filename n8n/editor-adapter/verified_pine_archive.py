"""Pinned, independently archived open-source Pine source for ONE verified ID.

This is not TradingView scraping, not a TradingView API, and not an attempt
to extract protected/invite-only code. Repository mirror is not the author;
SHA-256 from the independent 2026-10-31 corpus is required to match exactly.
Pine file belongs to the original author and retains its MPL-2.0 notice.
"""
import hashlib
import ssl
import urllib.request

SOURCE_ID="PUB;8188390243e646cf9466d3eb890232c9"
TRADINGVIEW_URL="https://www.tradingview.com/script/Hrc7Gfqe/"
EXPECTED_SHA256="9463e8e9a951580df1c49e69ba839e31573b0c231e132ef2590e7ea0b7bb5a6c"
ARCHIVE_REPO="venkatalokeshanne/trading_strategies_indicators"
ARCHIVE_REV="a9a6f4a9145de22bacacc24b827fb4095a3a425c"
ARCHIVE_PATH="TradingView/strategies/Hrc7Gfqe-McGinley-T3-Flow-Campaign-NICK789-v-1.pine"
ARCHIVE_URL=("https://raw.githubusercontent.com/"+ARCHIVE_REPO+"/"
             +ARCHIVE_REV+"/"+ARCHIVE_PATH)
MAX_PINE_BYTES=60000

def acquire_verified_pine(candidate):
    if not isinstance(candidate,dict) or candidate.get("source_id")!=SOURCE_ID:
        raise ValueError("N11_NOT_IN_VERIFIED_SOURCE_ARCHIVE")
    if candidate.get("source_url")!=TRADINGVIEW_URL:
        raise ValueError("N11_ARCHIVE_SCRIPT_URL_MISMATCH")
    if str(candidate.get("pine_version"))!="6":
        raise ValueError("N11_ARCHIVE_PINE_VERSION_MISMATCH")
    if str(candidate.get("source_license_reported","")).upper()!="MPL-2.0":
        raise ValueError("N11_ARCHIVE_LICENSE_NOT_MATCHING_CORPUS")
    if str(candidate.get("source_sha256_reported","")).lower()!=EXPECTED_SHA256:
        raise ValueError("N11_ARCHIVE_EXPECTED_SHA_MISMATCH")
    req=urllib.request.Request(ARCHIVE_URL,method="GET",headers={
        "Accept":"text/plain",
        "User-Agent":"autonomous-investor-original-source-verifier/1"})
    try:
        with urllib.request.urlopen(req,timeout=15,context=ssl.create_default_context()) as resp:
            if resp.status!=200:
                raise ValueError("N11_ARCHIVE_HTTP_"+str(resp.status))
            raw=resp.read(MAX_PINE_BYTES+1)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("N11_ARCHIVE_REQUEST_FAILED:"+type(exc).__name__) from exc
    if len(raw)>MAX_PINE_BYTES or len(raw)<100:
        raise ValueError("N11_ARCHIVE_FILE_SIZE_INVALID")
    # The mirror and research corpus can serialize the same Pine source
    # with different line ending encodings. Canonicalization is LIMITED to
    # newline bytes only; the final source MUST match independently pinned
    # SHA-256 exactly. Record BOTH raw digest and transformation.
    received_sha=hashlib.sha256(raw).hexdigest()
    normalized=raw
    normalization="NONE"
    if received_sha!=EXPECTED_SHA256:
        candidates=[
            ("CRCRLF_TO_CRLF",raw.replace(b"\r\r\n",b"\r\n")),
            ("LF_TO_CRLF",raw.replace(b"\r\n",b"\n").replace(b"\n",b"\r\n")),
            ("CRLF_TO_LF",raw.replace(b"\r\n",b"\n"))
        ]
        for method,alternate in candidates:
            if alternate!=raw and hashlib.sha256(alternate).hexdigest()==EXPECTED_SHA256:
                normalized=alternate
                normalization=method
                break
        else:
            raise ValueError("N11_ARCHIVE_BYTES_SHA256_MISMATCH:"+received_sha[:16])
    got=hashlib.sha256(normalized).hexdigest()
    try:
        text=normalized.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("N11_ARCHIVE_PINE_INVALID_UTF8") from exc
    if not text.lstrip().startswith("// This Pine Script") or (
       "Mozilla Public License 2.0" not in text[:300]) or (
       "© NICK789" not in text[:300]) or ("//@version=6" not in text[:800]):
        raise ValueError("N11_ARCHIVE_LICENSE_VERSION_OR_AUTHOR_MISSING")
    return {"pine_code":text,
        "pine_source_sha256":got,
        "source_archive_url":ARCHIVE_URL,
        "source_archive_revision":ARCHIVE_REV,
        "source_archive_raw_sha256":received_sha,
        "source_archive_newline_normalization":normalization,
        "pine_source_origin":"GITHUB_PINNED_OPEN_SOURCE_ARCHIVE",
        "source_author":"NICK789",
        "rights_state":"MPL_2_0_REVIEW_REQUIRED",
        "tradingview_requested":False,
        "tradingview_chart_rendered":False}
