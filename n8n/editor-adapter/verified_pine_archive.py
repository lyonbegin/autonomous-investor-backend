"""Retrieve Pine text from known public script mirrors.

No author-name matching, hash/provenance ledger, or TradingView scraping.
A mirror URL is NOT proof of identity with the current TradingView version.
Rights remain pending; retrieval never grants reuse or trading approval.
"""
import json
from pathlib import Path
import re
import ssl
import urllib.request
from urllib.parse import quote

ARCHIVE_REPO="venkatalokeshanne/trading_strategies_indicators"
ARCHIVE_REV="a9a6f4a9145de22bacacc24b827fb4095a3a425c"
INDEX_PATH=Path(__file__).with_name("verified_pine_archive_index.json")
MAX_PINE_BYTES=512 * 1024

def archive_path_for(candidate):
    if not isinstance(candidate,dict):
        return None
    url=candidate.get("source_url")
    if not isinstance(url,str):
        return None
    match=re.fullmatch(r"https://www\.tradingview\.com/script/([A-Za-z0-9]{8})/",url)
    if not match:
        return None
    try:
        index=json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except (ValueError,OSError) as exc:
        raise ValueError("PINE_MIRROR_INDEX_UNAVAILABLE") from exc
    if index.get("mirror_revision")!=ARCHIVE_REV or index.get("mirror_repo")!=ARCHIVE_REPO:
        raise ValueError("PINE_MIRROR_INDEX_INVALID")
    path=index.get("paths",{}).get(match.group(1))
    if not isinstance(path,str) or not re.fullmatch(
        r"TradingView/strategies/[A-Za-z0-9]{8}(?:-[A-Za-z0-9._-]+)?\.pine",path):
        return None
    return path if path.split("/")[-1].startswith(match.group(1)) else None

def acquire_verified_pine(candidate):
    """Legacy function name retained for adapter import compatibility.

    Returns SOURCE_RETRIEVED, not hash/author-verified TradingView origin.
    """
    path=archive_path_for(candidate)
    if path is None:
        raise ValueError("PINE_SOURCE_NOT_AVAILABLE")
    url=("https://raw.githubusercontent.com/"+ARCHIVE_REPO+"/"+ARCHIVE_REV+
         "/"+quote(path,safe="/-._"))
    request=urllib.request.Request(url,method="GET",headers={
        "Accept":"text/plain","User-Agent":"autonomous-investor-pine-reader/1"})
    try:
        with urllib.request.urlopen(request,timeout=15,context=ssl.create_default_context()) as response:
            if response.status!=200:
                raise ValueError("PINE_SOURCE_HTTP_"+str(response.status))
            raw=response.read(MAX_PINE_BYTES+1)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("PINE_SOURCE_FETCH_FAILED:"+type(exc).__name__) from exc
    if not raw:
        raise ValueError("PINE_SOURCE_EMPTY")
    if len(raw)>MAX_PINE_BYTES:
        raise ValueError("PINE_SOURCE_TOO_LARGE")
    try:
        code=raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("PINE_SOURCE_NOT_UTF8") from exc
    if not re.search(r"(?m)^\s*//@version=[456]\s*$",code) or not re.search(
        r"(?m)^\s*(strategy|indicator|library)\s*\(",code):
        raise ValueError("PINE_SOURCE_NOT_PARSEABLE_HEADER")
    return {"pine_code":code,"pine_source_acquired":True,
        "rights_state":"PENDING_REVIEW","source_identity_verified":False}
