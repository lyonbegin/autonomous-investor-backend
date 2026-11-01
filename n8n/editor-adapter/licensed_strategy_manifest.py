"""Attribution-preserving N03 catalog from a third-party CC BY 4.0 manifest.

This is NOT a TradingView API call, not a live/latest-on-TradingView feed,
not a Pine-source download, and not an automatically verified publication list.
It is a real, public, fixed-revision research snapshot curated by PyneSys.
No TradingView terms circumvention, scraping, session automation, or fake items.
"""
import csv
import datetime as dt
import io
import re
import ssl
import urllib.parse
import urllib.request

MANIFEST_REVISION="c6ea4d54afed3d6f887414ea12b4193e5c18eb74"
MANIFEST_REPOSITORY="https://github.com/PyneSys/pyne-in-the-wild"
MANIFEST_LICENSE="CC BY 4.0 — PyneSys (metadata manifest only; Pine code excluded)"
MANIFEST_URL=("https://raw.githubusercontent.com/PyneSys/pyne-in-the-wild/"
             + MANIFEST_REVISION + "/corpus/manifest.csv")
MAX_MANIFEST_BYTES=750000
EXPECTED_COLS={"id","kind","name","pine_version","script_version","tv_url","fetched_at"}

def validate_url(url):
    p=urllib.parse.urlsplit(url)
    if p.scheme!="https" or p.hostname not in (
       "www.tradingview.com","kr.tradingview.com","tradingview.com"):
        raise ValueError("MANIFEST_ENTRY_NOT_TRADINGVIEW_URL")
    if not re.fullmatch(r"/script/[A-Za-z0-9]{6,14}/",p.path):
        raise ValueError("MANIFEST_ENTRY_INVALID_SCRIPT_PATH")
    return url

def fetch_manifest():
    request=urllib.request.Request(MANIFEST_URL,headers={
        "Accept":"text/csv","User-Agent":"autonomous-investor-licensed-metadata-reader/1"})
    try:
        with urllib.request.urlopen(request,timeout=18,context=ssl.create_default_context()) as response:
            if response.status!=200:
                raise ValueError("LICENSED_MANIFEST_HTTP_"+str(response.status))
            raw=response.read(MAX_MANIFEST_BYTES+1)
    except (OSError,TimeoutError) as exc:
        raise ValueError("LICENSED_MANIFEST_FETCH_FAILED:"+type(exc).__name__) from exc
    if len(raw)>MAX_MANIFEST_BYTES:
        raise ValueError("LICENSED_MANIFEST_TOO_LARGE")
    try:
        text=raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("LICENSED_MANIFEST_INVALID_ENCODING") from exc
    rows=list(csv.DictReader(io.StringIO(text)))
    if not rows or not EXPECTED_COLS.issubset(rows[0]):
        raise ValueError("LICENSED_MANIFEST_MISSING_COLUMNS")
    if len(rows)>5000:
        raise ValueError("LICENSED_MANIFEST_TOO_MANY_ENTRIES")
    return rows

def catalog_from_snapshot(*,kind,page,page_size,sort):
    if kind!="strategy":
        raise ValueError("LICENSED_MANIFEST_STRATEGIES_ONLY")
    if sort!="recent_extended":
        raise ValueError("LICENSED_MANIFEST_INVALID_SORT")
    if not (1<=page<=3 and 1<=page_size<=100):
        raise ValueError("LICENSED_MANIFEST_INVALID_PAGE")
    rows=fetch_manifest()
    selected=[];skipped=0
    for item in rows:
        if item.get("kind")!="strategy":
            continue
        try:
            source_id=item["id"]
            if not isinstance(source_id,str) or not source_id.startswith("PUB;") or len(source_id)>100:
                raise ValueError("MANIFEST_ENTRY_INVALID_ID")
            source_url=validate_url(item["tv_url"])
            recorded=item.get("fetched_at","")
            dt.date.fromisoformat(recorded)
        except (ValueError,TypeError,KeyError):
            skipped+=1
            continue
        selected.append({
            "kind":"strategy",
            "source_id":source_id,
            "source_url":source_url,
            "title":(item.get("name") or "").strip()[:300],
            "version_key":str(item.get("script_version") or "")[:150],
            "published_at":None, # NOT in manifest; do not invent a publication time.
            "updated_at":None,
            "access":"open_source_as_reported_by_corpus_not_reverified",
            "pine_version":item.get("pine_version"),
            "source_code_fetched":False,
            "catalog_observed_at":recorded,
            "metadata_origin":MANIFEST_REPOSITORY,
        })
    if not selected:
        raise ValueError("LICENSED_MANIFEST_NO_VALID_STRATEGIES")
    # Snapshot observed dates are NOT TradingView script publication dates.
    selected.sort(key=lambda r:(r["catalog_observed_at"],r["source_id"]),reverse=True)
    start=(page-1)*page_size
    items=selected[start:start+page_size]
    if not items:
        raise ValueError("LICENSED_MANIFEST_PAGE_EMPTY")
    return {"kind":"strategy","page":page,"items":items,
        "count":len(items),"total_count":len(selected),
        "has_more":start+len(items)<len(selected),
        "catalog_source":"PYNE_GITHUB_CC_BY_4_METADATA_SNAPSHOT",
        "catalog_is_live":False,
        "latest_tradingview_verified":False,
        "sort_basis":"manifest_observed_at_not_publication_date",
        "invalid_entries_skipped":skipped,
        "pine_source_acquired":False,
        "tradingview_requested":False,
        "real_tradingview_publication_links_reported":True,
        "no_pine_redistributed":True,
        "source_record_kind":"external_strategy_list"}
