// Railway Function code archive (deployed), 2026-10-29.
// Service: tradingview-corporate-bond-cron
// Railway ID: 6f240b92-5fdf-4b1e-8288-12349d3fab39
// Runtime: bun 1.4.4
// Do NOT run automatically; inspect endpoints and permissions before restoration.

const base="https://autonomous-investor-tradingview-production.up.railway.app";
const started=Date.now();
try{
  const response=await fetch(base+"/api/v1/tradingview/markets/corporate-bonds/prefix-backfill?max_prefixes=100",{
    method:"POST",
    headers:{"User-Agent":"AUTONOMOUS-INVESTOR-CorporateBondPrefixCron/4.0"},
    signal:AbortSignal.timeout(85000)
  });
  const body=await response.text();
  let parsed=null; try{parsed=JSON.parse(body)}catch{}
  console.log(JSON.stringify({
    job:"TradingView corporate bond ISIN-prefix backfill",
    at:new Date().toISOString(),
    status:response.status,
    ok:response.ok,
    ms:Date.now()-started,
    processed:parsed?.processed_prefixes,
    stored:parsed?.stored_count,
    pending:parsed?.pending_prefixes,
    failed:parsed?.failed_prefixes,
    result:parsed||body.slice(0,12000)
  },null,2));
  if(!response.ok) process.exit(1);
}catch(error){
  console.log(JSON.stringify({
    job:"TradingView corporate bond ISIN-prefix backfill",
    ok:false,
    ms:Date.now()-started,
    error:String(error)
  },null,2));
  process.exit(1);
}