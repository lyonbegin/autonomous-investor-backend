// Railway Function code archive (deployed), 2026-10-29.
// Service: tradingview-collector-cron
// Railway ID: b07ee32b-315e-4da4-a703-cfe5889930e6
// Runtime: bun 1.4.4
// Do NOT run automatically; inspect endpoints and permissions before restoration.

const base = "https://autonomous-investor-tradingview-production.up.railway.app";

const jobs = [
  { name: "ideas-recent", path: "/api/v1/tradingview/ideas/live?sort=recent&page=1&lang=ko", method: "GET", timeout: 30000 },
  { name: "scripts-recent", path: "/api/v1/tradingview/scripts/live?page=1&sort=recent_extended&editors_picks=false", method: "GET", timeout: 30000 },

  // Persistent cursors eventually traverse every available TradingView page.
  // Details save full text + all discovered images; scripts also save public Pine source.
  { name: "ideas-full-backfill", path: "/api/v1/tradingview/backfill/ideas?pages=5&fetch_details=true&fetch_pine=false", method: "POST", timeout: 90000 },
  { name: "ideas-complete-missing", path: "/api/v1/tradingview/ideas/complete-missing?limit=1000", method: "POST", timeout: 90000 },
  { name: "scripts-full-backfill", path: "/api/v1/tradingview/backfill/scripts?pages=5&fetch_details=true&fetch_pine=true", method: "POST", timeout: 90000 },
  { name: "scripts-complete-missing", path: "/api/v1/tradingview/scripts/complete-missing?limit=500", method: "POST", timeout: 90000 },

  { name: "market-korea", path: "/api/v1/tradingview/markets/korea?limit=50&offset=0&sort_by=volume&sort_order=desc", method: "GET", timeout: 30000 },
  { name: "market-global-stocks", path: "/api/v1/tradingview/markets/global-stocks?limit=50&offset=0&sort_by=volume&sort_order=desc", method: "GET", timeout: 30000 },
  { name: "market-crypto", path: "/api/v1/tradingview/markets/crypto?limit=50&offset=0&sort_by=volume&sort_order=desc", method: "GET", timeout: 30000 },
  { name: "market-futures", path: "/api/v1/tradingview/markets/futures?limit=50&offset=0&sort_by=volume&sort_order=desc", method: "GET", timeout: 30000 },
  { name: "market-forex", path: "/api/v1/tradingview/markets/forex?limit=50&offset=0&sort_by=change&sort_order=desc", method: "GET", timeout: 30000 },
  { name: "market-bonds", path: "/api/v1/tradingview/markets/bonds?limit=50&offset=0&sort_by=change&sort_order=desc", method: "GET", timeout: 30000 },
  { name: "market-etf", path: "/api/v1/tradingview/markets/etf?limit=50&offset=0&sort_by=volume&sort_order=desc", method: "GET", timeout: 30000 },
  { name: "market-indices", path: "/api/v1/tradingview/markets/indices?limit=50&offset=0&sort_by=change&sort_order=desc", method: "GET", timeout: 30000 },
  { name: "market-vietnam", path: "/api/v1/tradingview/markets/vietnam?limit=50&offset=0&sort_by=volume&sort_order=desc", method: "GET", timeout: 30000 },

  // Full market-universe cursors. Each run advances up to 25,000 exact source rows.
  { name: "market-full-korea", path: "/api/v1/tradingview/markets/korea/backfill?chunks=25&page_size=1000", method: "POST", timeout: 90000 },
  { name: "market-full-global-stocks", path: "/api/v1/tradingview/markets/global-stocks/backfill?chunks=25&page_size=1000", method: "POST", timeout: 90000 },
  { name: "market-full-crypto", path: "/api/v1/tradingview/markets/crypto/backfill?chunks=25&page_size=1000", method: "POST", timeout: 90000 },
  { name: "market-full-futures", path: "/api/v1/tradingview/markets/futures/backfill?chunks=25&page_size=1000", method: "POST", timeout: 90000 },
  { name: "market-full-forex", path: "/api/v1/tradingview/markets/forex/backfill?chunks=25&page_size=1000", method: "POST", timeout: 90000 },
  { name: "market-full-bonds", path: "/api/v1/tradingview/markets/bonds/backfill?chunks=25&page_size=1000", method: "POST", timeout: 90000 },
  { name: "market-full-etf", path: "/api/v1/tradingview/markets/etf/backfill?chunks=25&page_size=1000", method: "POST", timeout: 90000 },
  { name: "market-full-indices", path: "/api/v1/tradingview/markets/indices/backfill?chunks=25&page_size=1000", method: "POST", timeout: 90000 },
  { name: "market-full-america", path: "/api/v1/tradingview/markets/america/backfill?chunks=25&page_size=1000", method: "POST", timeout: 90000 },
  { name: "market-full-japan", path: "/api/v1/tradingview/markets/japan/backfill?chunks=25&page_size=1000", method: "POST", timeout: 90000 },
  { name: "market-full-india", path: "/api/v1/tradingview/markets/india/backfill?chunks=25&page_size=1000", method: "POST", timeout: 90000 },
  { name: "market-full-vietnam", path: "/api/v1/tradingview/markets/vietnam/backfill?chunks=25&page_size=1000", method: "POST", timeout: 90000 },

  { name: "candidates-build", path: "/api/v1/tradingview/candidates/build?limit=500", method: "POST", timeout: 90000 },
  { name: "source-registry-sync", path: "/api/v1/strategy-sources/sync?limit=10000", method: "POST", timeout: 90000 },
];

async function runJob(job) {
  let last = null;
  for (let attempt = 1; attempt <= 2; attempt++) {
    const started = Date.now();
    try {
      const response = await fetch(base + job.path, {
        method: job.method,
        headers: { "User-Agent": "AUTONOMOUS-INVESTOR-Collector/3.0" },
        signal: AbortSignal.timeout(job.timeout || 30000),
      });
      const body = await response.text();
      last = {
        name: job.name,
        method: job.method,
        ok: response.ok,
        status: response.status,
        attempt,
        ms: Date.now() - started,
        preview: body.slice(0, 320),
      };
      if (response.ok) return last;
    } catch (error) {
      last = {
        name: job.name,
        method: job.method,
        ok: false,
        status: 0,
        attempt,
        ms: Date.now() - started,
        error: String(error),
      };
    }
    await Bun.sleep(1200);
  }
  return last;
}

const results = [];
for (const job of jobs) {
  results.push(await runJob(job));
  await Bun.sleep(500);
}

const failed = results.filter(x => !x?.ok);
console.log(JSON.stringify({
  collector: "TradingView full-source exact-row collector v3",
  at: new Date().toISOString(),
  ok: failed.length === 0,
  failed: failed.map(x => x?.name),
  results
}, null, 2));

if (failed.length >= 3) process.exit(1);
