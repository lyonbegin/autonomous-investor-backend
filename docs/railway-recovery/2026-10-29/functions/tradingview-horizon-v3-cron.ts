// Railway Function code archive (deployed), 2026-10-29.
// Service: tradingview-horizon-v3-cron
// Railway ID: 30242c82-5bb3-4a93-856d-f20203bb6b4a
// Runtime: bun 1.4.4
// Do NOT run automatically; inspect endpoints and permissions before restoration.

// Incremental Horizon collector: bounded work per cron invocation.
// The prior limit=500/max_markets=3 request regularly exceeded 280 seconds.
const base = "https://autonomous-investor-tradingview-production.up.railway.app";
const started = Date.now();
const headers = {"User-Agent": "AUTONOMOUS-INVESTOR-HorizonV3Cron/1.1"};
const report = (data) => console.log(JSON.stringify({job:"Horizon v3",at:new Date().toISOString(),elapsed_ms:Date.now()-started,...data}));
try {
  const before = await fetch(base+"/api/v1/horizon-discovery/queue-status",{
    headers,signal:AbortSignal.timeout(12000)
  });
  if(!before.ok) throw new Error("queue-status HTTP "+before.status);
  const queue = await before.json();
  if(Number(queue.remaining ?? 0)<=0) {
    report({ok:true,skipped:true,reason:"queue empty",queue});
  } else {
    // Cap a batch below the cron interval; backlog is picked up next run.
    const response = await fetch(base+"/api/v1/horizon-discovery/batch?limit=20&max_markets=1",{
      method:"POST",headers,signal:AbortSignal.timeout(100000)
    });
    const body = await response.text();
    report({ok:response.ok,status:response.status,remaining_before:queue.remaining,
      result:body.slice(0,4000)});
    if(!response.ok) process.exitCode=1;
  }
} catch(error) {
  report({ok:false,error:String(error)});
  process.exitCode=1;
}