"""Hash-verifiable open-source Pine from a pinned independent GitHub mirror.

Never scrape TradingView, execute supplied code or accept protected Pine.
A source path is allowed only when its TradingView ID is present in a
pinned, metadata-only list intersected with PyneSys's external corpus.
The actual file MUST match the corpus's SHA-256 after explicit and logged
newline-only canonicalization. Authors retain their own source licenses.
"""
import hashlib
import json
from pathlib import Path
import re
import ssl
import urllib.request
from urllib.parse import quote

SOURCE_ID="PUB;8188390243e646cf9466d3eb890232c9"
TRADINGVIEW_URL="https://www.tradingview.com/script/Hrc7Gfqe/"
EXPECTED_SHA256="9463e8e9a951580df1c49e69ba839e31573b0c231e132ef2590e7ea0b7bb5a6c"
ARCHIVE_REPO="venkatalokeshanne/trading_strategies_indicators"
ARCHIVE_REV="a9a6f4a9145de22bacacc24b827fb4095a3a425c"
ARCHIVE_PATH="TradingView/strategies/Hrc7Gfqe-McGinley-T3-Flow-Campaign-NICK789-v-1.pine"
ARCHIVE_URL="https://raw.githubusercontent.com/"+ARCHIVE_REPO+"/"+ARCHIVE_REV+"/"+ARCHIVE_PATH
INDEX_PATH=Path(__file__).with_name("verified_pine_archive_index.json")
MAX_PINE_BYTES=60000

def archive_path_for(candidate):
    if not isinstance(candidate,dict):return None
    url=candidate.get("source_url")
    if not isinstance(url,str):return None
    m=re.fullmatch(r"https://www\.tradingview\.com/script/([A-Za-z0-9]{8})/",url)
    if not m:return None
    try:
        index=json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except (ValueError,OSError) as exc:
        raise ValueError("N11_PINNED_ARCHIVE_INDEX_UNAVAILABLE") from exc
    if index.get("mirror_revision")!=ARCHIVE_REV or index.get("mirror_repo")!=ARCHIVE_REPO:
        raise ValueError("N11_ARCHIVE_INDEX_REVISION_MISMATCH")
    path=index.get("paths",{}).get(m.group(1))
    if not isinstance(path,str) or not re.fullmatch(
        r"TradingView/strategies/[A-Za-z0-9]{8}(?:-[A-Za-z0-9._-]+)?\.pine",path):
        return None
    if not path.split("/")[-1].startswith(m.group(1)):
        return None
    return path

def acquire_verified_pine(candidate):
    if not isinstance(candidate,dict) or not isinstance(candidate.get("source_id"),str):
        raise ValueError("N11_NOT_IN_VERIFIED_SOURCE_ARCHIVE")
    if not isinstance(candidate.get("source_url"),str):
        raise ValueError("N11_ARCHIVE_SCRIPT_URL_MISMATCH")
    path=archive_path_for(candidate)
    if path is None:
        raise ValueError("N11_NOT_IN_VERIFIED_SOURCE_ARCHIVE")
    version=str(candidate.get("pine_version"))
    if version not in ("5","6"):
        raise ValueError("N11_ARCHIVE_PINE_VERSION_MISMATCH")
    if str(candidate.get("source_license_reported","")).upper()!="MPL-2.0":
        raise ValueError("N11_ARCHIVE_LICENSE_NOT_MATCHING_CORPUS")
    expected=str(candidate.get("source_sha256_reported") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}",expected):
        raise ValueError("N11_ARCHIVE_EXPECTED_SHA_MISMATCH")
    archive_url=("https://raw.githubusercontent.com/"+ARCHIVE_REPO+"/"+ARCHIVE_REV
                 +"/"+quote(path,safe="/-._"))
    req=urllib.request.Request(archive_url,method="GET",headers={
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
    raw_sha=hashlib.sha256(raw).hexdigest()
    normalized=raw
    method="NONE"
    if raw_sha!=expected:
        newline_variants=[
            ("CRCRLF_TO_CRLF",raw.replace(b"\r\r\n",b"\r\n")),
            ("LF_TO_CRLF",raw.replace(b"\r\n",b"\n").replace(b"\n",b"\r\n")),
            ("CRLF_TO_LF",raw.replace(b"\r\n",b"\n"))
        ]
        for name,alternate in newline_variants:
            if alternate!=raw and hashlib.sha256(alternate).hexdigest()==expected:
                normalized=alternate;method=name;break
        else:
            raise ValueError("N11_ARCHIVE_BYTES_SHA256_MISMATCH:"+raw_sha[:16])
    try:
        text=normalized.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("N11_ARCHIVE_PINE_INVALID_UTF8") from exc
    if ("Mozilla Public License 2.0" not in text[:1200] or
        not re.search(r"(?m)^\s*//@version="+version+r"\s*$",text) or
        not re.search(r"(?m)^\s*strategy\s*\(",text)):
        raise ValueError("N11_ARCHIVE_LICENSE_VERSION_OR_STRATEGY_MISSING")
    author=str(candidate.get("author") or ("NICK789" if candidate["source_id"]==SOURCE_ID else ""))
    if not author:
        raise ValueError("N11_ARCHIVE_AUTHOR_METADATA_MISSING")
    author_notice_present=("© "+author).lower() in text[:1200].lower()
    return {"pine_code":text,
        "pine_source_sha256":hashlib.sha256(normalized).hexdigest(),
        "source_archive_url":archive_url,"source_archive_revision":ARCHIVE_REV,
        "source_archive_raw_sha256":raw_sha,
        "source_archive_newline_normalization":method,
        "pine_source_origin":"GITHUB_PINNED_OPEN_SOURCE_ARCHIVE",
        "source_author":author,
        "source_author_notice_present":author_notice_present,
        "source_author_notice_status":"MATCH" if author_notice_present else "NOT_PRESENT_REVIEW_REQUIRED",
        "rights_state":"MPL_2_0_REVIEW_REQUIRED",
        "tradingview_requested":False,"tradingview_chart_rendered":False}
