"""Manually resumable source-linked hierarchy for *all* TradingView Markets pages.

No fixed number of categories, regions, countries or market sections:
- Begin from public Markets navigation and canonical asset-type roots.
- Record every discovered /markets/ link, source anchor text and parent.
- Traverse source-linked submenus over repeated EXPLICIT update clicks.
- Keep failed/blocked pages and frontier visible; no silent truncation.
- Do not call hidden endpoints, authenticate, modify the original site or
  schedule crawls. Data rights for OHLCV are a separate concern.

Even an empty frontier certifies only reachable public HTML links; it does
NOT certify complete instruments, exchange coverage or pixel UI fidelity.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit, unquote
import re
import sqlite3

from bs4 import BeautifulSoup
import httpx

BASE="https://kr.tradingview.com"
ROOT="/markets/"
from .market_taxonomy import PUBLIC_MARKET_TYPE_PATHS

# Existing source pages were inspected via actual public HTML and return 200.
# OPTIONS is preserved separately in Symbol Search/option chains, never added
# here as the nonexistent /markets/options/ page.
ROOTS=(ROOT,)+tuple(dict.fromkeys(
    path for paths in PUBLIC_MARKET_TYPE_PATHS.values() for path in paths
))
# Historical guessed paths are retained as evidence, not as active root links.
OBSOLETE_GUESSED_ROOTS=(
    "/markets/stocks/","/markets/funds/","/markets/forex/",
    "/markets/options/","/markets/economy/",
)

SCHEMA="""CREATE TABLE IF NOT EXISTS market_pages(
 path TEXT PRIMARY KEY, label TEXT NOT NULL, parent_path TEXT,
 status TEXT NOT NULL DEFAULT 'pending', source_status_code INTEGER,
 discovered_at TEXT NOT NULL, fetched_at TEXT, link_count INTEGER,
 error_code TEXT
);
CREATE TABLE IF NOT EXISTS market_page_links(
 from_path TEXT NOT NULL, to_path TEXT NOT NULL,
 source_label TEXT NOT NULL, PRIMARY KEY(from_path,to_path,source_label)
);
"""


def stamp():
    return datetime.now(timezone.utc).isoformat()


def safe_path(url:str,base:str=BASE+ROOT):
    resolved=urljoin(base,url)
    parsed=urlsplit(resolved)
    if parsed.scheme!="https" or parsed.hostname not in (
            "kr.tradingview.com","www.tradingview.com","tradingview.com"):
        return None
    # Paths only. Never incorporate query strings, username or fragments.
    path=re.sub(r"/+","/",unquote(parsed.path))
    if not (path==ROOT or path.startswith(ROOT)):
        return None
    if re.search(r"[<>\\\x00-\x1f]",path) or len(path)>300:
        return None
    if not path.endswith("/"):
        path+="/"
    return path


def discover(html:str,from_path:str):
    soup=BeautifulSoup(html,"html.parser")
    # Include accessible nested category links in header and main, but not
    # symbol deep-links, api hosts, social URLs, profile links or logout.
    result=[]
    seen=set()
    for element in soup.select("a[href]"):
        path=safe_path(str(element.get("href","")),BASE+from_path)
        if path is None or path==from_path:
            continue
        label=" ".join(element.stripped_strings).strip()
        if not label:
            label=element.get("aria-label") or element.get("title") or path
        label=re.sub(r"\s+"," ",str(label))[:280]
        identity=(path,label)
        if identity not in seen:
            result.append((path,label))
            seen.add(identity)
    return result


class WorldMarketPageGraph:
    def __init__(self,root:str|Path):
        self.root=Path(root)
        self.root.mkdir(parents=True,exist_ok=True)
        self.db=self.root/"market_pages.sqlite3"
        with self.connect() as con:
            con.executescript(SCHEMA)
            con.executemany(
                """INSERT OR IGNORE INTO market_pages
                (path,label,parent_path,status,discovered_at)
                VALUES(?,?,NULL,'pending',?)""",
                [(x,x.split("/")[-2] if x!=ROOT else "TradingView Markets",stamp())
                 for x in ROOTS])
            # Upgrade existing volume in place: old 404/301 entries came from
            # guessed slugs, not from original TradingView menu discovery.
            # Do NOT delete them, retry them forever or mark option products
            # unsupported just because /markets/options/ returns 404.
            con.executemany(
                """UPDATE market_pages SET status='noncanonical_seed',
                       error_code='INCORRECT_GUESSED_ROOT'
                   WHERE path=? AND parent_path IS NULL
                     AND status='failed'
                     AND source_status_code IN (301,404)""",
                [(path,) for path in OBSOLETE_GUESSED_ROOTS],
            )

    def connect(self):
        return sqlite3.connect(self.db,timeout=20)

    def status(self):
        with self.connect() as con:
            rows=con.execute(
                "SELECT status,COUNT(*) FROM market_pages GROUP BY status"
            ).fetchall()
            links=con.execute("SELECT COUNT(*) FROM market_page_links").fetchone()[0]
        counts=dict(rows)
        return {
            "discovered_pages":sum(counts.values()),
            "pending_pages":counts.get("pending",0),
            "fetched_pages":counts.get("fetched",0),
            "failed_pages":counts.get("failed",0),
            "noncanonical_historical_seeds":counts.get("noncanonical_seed",0),
            "market_navigation_seed_source":"observed_public_200_not_guessed_slug",
            "source_edges":links,
            "public_link_graph_exhausted":counts.get("pending",0)==0,
            "all_tradingview_asset_categories_complete":False,
            "all_instruments_collected":False,
            "all_venues_data_verified":False,
            "manual_click_only":True,
            "scheduled_cron":False,
        }

    def get(self,limit=500,offset=0,query=""):
        if not 1<=limit<=5000 or offset<0:
            raise ValueError("INVALID_MARKET_GRAPH_PAGINATION")
        with self.connect() as con:
            where="WHERE path LIKE ? OR label LIKE ?" if query else ""
            params=[f"%{query}%",f"%{query}%"] if query else []
            count=con.execute(
                f"SELECT COUNT(*) FROM market_pages {where}",params
            ).fetchone()[0]
            cursor=con.execute(
                f"""SELECT path,label,parent_path,status,source_status_code,
                   fetched_at,link_count,error_code FROM market_pages {where}
                   ORDER BY CASE WHEN path=? THEN 0 ELSE 1 END,path
                   LIMIT ? OFFSET ?""",params+[ROOT,limit,offset])
            columns=[d[0] for d in cursor.description]
            pages=[dict(zip(columns,r)) for r in cursor.fetchall()]
        return {"items":pages,"total_count":count,"limit":limit,"offset":offset,
                "has_more":offset+len(pages)<count,"summary":self.status(),
                "source_base":BASE,
                "scope":"public /markets/ links in available HTML only"}

    def reserve_one(self):
        with self.connect() as con:
            # Retry failed pages only if deliberately requeued by user.
            # Prioritize every canonical major asset root before secondary
            # news/ideas pagination. Never discard later pages: keep them in DB.
            priority_placeholders=",".join("?" for _ in ROOTS[1:])
            sql=f"""SELECT path FROM market_pages WHERE status='pending'
                ORDER BY CASE
                    WHEN path=? THEN 0
                    WHEN path IN ({priority_placeholders}) THEN 1
                    ELSE 2 END,
                (LENGTH(path)-LENGTH(REPLACE(path,'/',''))) ASC,
                CASE WHEN path LIKE '%/ideas/%' OR path LIKE '%/news/%'
                     THEN 1 ELSE 0 END ASC,
                path
                LIMIT 1"""
            row=con.execute(sql,[ROOT,*ROOTS[1:]]).fetchone()
            return row[0] if row else None

    def store_result(self,path,code:int,links:list[tuple[str,str]],error=None):
        with self.connect() as con:
            for dest,label in links:
                con.execute(
                    """INSERT OR IGNORE INTO market_pages
                    (path,label,parent_path,status,discovered_at)
                    VALUES(?,?,?,'pending',?)""",
                    (dest,label,path,stamp()))
                con.execute("""INSERT OR IGNORE INTO market_page_links
                    (from_path,to_path,source_label) VALUES(?,?,?)""",
                    (path,dest,label))
            con.execute("""UPDATE market_pages SET status=?,source_status_code=?,
                fetched_at=?,link_count=?,error_code=? WHERE path=?""",
                ("fetched" if 200<=code<300 else "failed",code,stamp(),
                 len(links),error,path))

    def requeue_failed(self):
        with self.connect() as con:
            cursor=con.execute("""UPDATE market_pages
                                  SET status='pending' WHERE status='failed'""")
            return cursor.rowcount

    async def manual_step(self,pages=10,pause_seconds=.45):
        if not 1<=pages<=50:
            raise ValueError("PAGES_PER_CLICK_MUST_BE_1_TO_50")
        results=[]
        async with httpx.AsyncClient(
            follow_redirects=False,timeout=20,
            headers={"User-Agent":"Mozilla/5.0 (compatible; personal market taxonomy research)"}
        ) as client:
            for i in range(pages):
                path=self.reserve_one()
                if path is None:break
                try:
                    response=await client.get(BASE+path)
                    status=response.status_code
                    if status==200 and "html" in response.headers.get("content-type","html"):
                        links=discover(response.text,path)
                        self.store_result(path,status,links)
                        results.append({"path":path,"code":status,"links":len(links)})
                    else:
                        self.store_result(path,status,[],error="NON_HTML_OR_HTTP_ERROR")
                        results.append({"path":path,"code":status,"links":0,
                                        "error":"NON_HTML_OR_HTTP_ERROR"})
                        if status in (401,403,429):
                            # Respect server access/rate limits; no evasions.
                            break
                except httpx.HTTPError as exc:
                    self.store_result(path,0,[],error=type(exc).__name__)
                    results.append({"path":path,"code":0,"links":0,
                                    "error":type(exc).__name__})
                    break
                if i+1<pages:
                    await asyncio.sleep(pause_seconds)
        return {"processed":results,"summary":self.status(),
                "full_content_completeness_verified":False}
